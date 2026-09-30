# Zugriff ohne Portfreigabe – Protokoll

Verbindliche Beschreibung für alle drei Seiten: Vermittler, Verbinder in der
Instanz (`backend/connect.py`) und externes Gerät. Wer hier etwas ändert,
ändert es überall – und die Kreuztests (`tests/test_connect.py`, Vektoren in
`tests/daten/`) müssen weiter grün sein.

Version: **v1** (Pfadpräfix `/v1/`, Kontext `nupplo-connect-v1`).

## 1. Instanz-ID und Nachweis

- Die Instanz hat einen **Ed25519-Schlüssel** (Datei im Datenordner, nur für
  sie lesbar). Ihre **ID** ist Base32 (RFC 4648, klein, ohne `=`) des SHA-256
  ihres öffentlichen Schlüssels (32 Byte roh), gekürzt auf **26 Zeichen**
  (130 Bit). Sie ist selbstbeglaubigend – vergeben wird nichts.
- Anmelden: WebSocket an

  ```
  wss://connect.nupplo.com/v1/instanz/<id>?pub=<P>&zeit=<T>&zufall=<Z>&sig=<S>
  ```

  | Feld | Inhalt |
  |---|---|
  | `pub` | öffentlicher Schlüssel, 32 Byte, base64url ohne `=` |
  | `zeit` | Unix-Zeit in Sekunden; höchstens **300 s** daneben |
  | `zufall` | 16 frische Zufallsbytes, base64url |
  | `sig` | Ed25519 über `nupplo-connect-v1\n<id>\n<zeit>\n<zufall>` (UTF-8), base64url |

- Der Vermittler prüft alles und nimmt **jede Unterschrift nur einmal**.
  Der Zufall ist Pflicht: Ed25519 unterschreibt gleichen Inhalt immer gleich,
  eine Anmeldung in derselben Sekunde galt sonst als Wiederholung.
- Abgewiesen wird mit HTTP 403 und dem Grund als Text: `nachweis-fehlt`,
  `nachweis-unlesbar`, `uhrzeit`, `falsche-id`, `unterschrift`,
  `nachweis-schon-benutzt`, `nicht-freigeschaltet`.
- Eine neue Anmeldung derselben Instanz löst die alte ab (Schließcode 4000);
  deren Geräte bekommen `FEHLER instanz-neu-verbunden`.

## 2. Rahmen (liest der Vermittler)

```
[1 Byte Art][4 Byte Kanal, Big Endian][Nutzlast]
```

| Art | Wert | Richtung | Nutzlast |
|---|---|---|---|
| OEFFNEN | 1 | Vermittler → Instanz | JSON `{"ip": "<IP des Geräts>"}` |
| DATEN | 2 | beide | unverändert durchgereicht |
| SCHLIESSEN | 3 | beide | leer |
| FEHLER | 4 | Vermittler → Gerät | Grund als Text, danach Schluss |

- Nur **Binärnachrichten**. Text `ping` beantwortet der Vermittler mit
  `pong`, ohne das Durable Object zu wecken (Lebenszeichen alle 30 s).
- Höchstens **1 MiB + 5 Byte** je Rahmen, sonst Schließcode 1009.
- Das Gerät schickt seine Rahmen mit Kanal 0; **den Kanal setzt der
  Vermittler** – ein Gerät kann nicht in fremde Kanäle schreiben.
- `FEHLER`-Gründe: `instanz-offline`, `instanz-getrennt`,
  `instanz-neu-verbunden`, `zu-viele-verbindungen` (mehr als 8 Geräte).
- HTTP 429 `zu-viele-versuche`: mehr als 30 Geräteverbindungen je Minute und IP.

## 3. Ströme (liest nur Instanz und Gerät)

In der Nutzlast von `DATEN` – ab Schritt 2 **verschlüsselt** (Noise IK):

```
[4 Byte Strom][1 Byte Typ][Inhalt]
```

| Typ | Wert | Inhalt |
|---|---|---|
| KOPF | 1 | JSON – Anfrage `{"m","w","k"}`, Antwort `{"s","k"}` |
| KOERPER | 2 | Stück des Körpers, höchstens 256 KiB |
| ENDE | 3 | leer |
| ABBRUCH | 4 | leer |

Eine HTTP-Anfrage ist ein Strom; die Antwort kommt auf demselben zurück.
Mehrere Ströme laufen gleichzeitig über einen Kanal.

- **Kopfzeilen gehen unverändert durch** – der Verbinder fügt nichts hinzu
  (Probelauf: `requests` hängte `Accept-Encoding: gzip` an, Fotos kamen
  gepackt an). Nur Verbindungskopfzeilen (`Host`, `Connection`,
  `Content-Length`, …) fallen weg.
- Die IP aus `OEFFNEN` gibt der Verbinder der Instanz als Absender mit –
  sonst bremst die Sperre gegen Passwortraten alle Geräte gemeinsam.

## 4. Verschlüsselung und Koppeln (Noise IK)

`Noise_IK_25519_ChaChaPoly_SHA256`, Prologue `nupplo-connect-v1`. Das Gerät ist
Initiator und kennt den statischen X25519-Schlüssel der Instanz aus dem
QR-Code; die Instanz lernt den Geräteschlüssel in der ersten
Nachricht. Umsetzung in der Instanz: `backend/connect_noise.py`, geprüft gegen
`tests/daten/noise_ik_cacophony.json` (offizielle Vektoren) und
`tests/daten/noise_ik_nupplo.json` (Mitschnitt, den die Gegenseite ebenso
nachspielt).

Je Kanal:

1. Gerät → Instanz, erstes `DATEN`: Noise-Nachricht 1. Nutzlast JSON:
   - `{}` – ein schon gekoppeltes Gerät, oder
   - `{"code": "<Einmalcode aus dem QR>", "name": "<Gerätename>"}` – Koppeln.
2. Instanz → Gerät, erstes `DATEN`: Noise-Nachricht 2. Nutzlast JSON:
   - `{"ok": true}` – danach Ströme, oder
   - `{"fehler": "nicht-gekoppelt" | "code-ungueltig" | "code-abgelaufen"}`,
     danach `SCHLIESSEN`. Das Gerät erfährt den Grund, ist aber sicher, dass
     er von der echten Instanz kommt (Nachricht 2 ist schon authentisch).
3. Jedes weitere `DATEN` ist **eine** Noise-Transportnachricht mit genau einem
   Strom-Rahmen (Abschnitt 3) darin. Höchstens 65 535 Byte je Nachricht
   (Spezifikation) – deshalb Körperstücke zu **60 KiB**.

**Nur gekoppelte Geräte kommen durch:** Kennt die Instanz den
Geräteschlüssel nicht und stimmt kein Code, gibt es keine Ströme – ein
Fremder erreicht nicht einmal die Anmeldeseite.

Der QR-Code:

```
nupplo-connect://v1?i=<Instanz-ID>&k=<X25519 der Instanz, base64url>
                   &c=<Einmalcode>&l=<Heimnetz-Adresse(n)>&r=<Vermittler>
```

## 5. Noch offen

- Schritt 5: Abo statt Freischaltliste.
