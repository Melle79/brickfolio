# Finn's Brickfolio – Das Handbuch

*Juli 2026 · [🇬🇧 English version](MANUAL.md)*

Brickfolio ist eine selbstgehostete Progressive Web App (PWA) zum Scannen,
Verwalten und Bewerten einer LEGO®-Sammlung. Dieses Handbuch erklärt jede
Funktion – vom ersten Start bis zum Flohmarkt-Einsatz.

## Inhalt

1. [Über Brickfolio](#1-über-brickfolio)
2. [Installation & erste Einrichtung](#2-installation--erste-einrichtung)
3. [Benutzer & Rollen](#3-benutzer--rollen)
4. [Scannen & Erfassen](#4-scannen--erfassen)
5. [Die Sammlung](#5-die-sammlung)
6. [Die Wunschliste](#6-die-wunschliste)
7. [Einkaufslisten – der Flohmarkt-Modus](#7-einkaufslisten--der-flohmarkt-modus)
8. [Die Verkaufsliste (Doppelte)](#8-die-verkaufsliste-doppelte)
9. [Der Statistik-Tab](#9-der-statistik-tab)
10. [CSV-Import, Export & Druck](#10-csv-import-export--druck)
11. [Sicherung, Wiederherstellung & Updates](#11-sicherung-wiederherstellung--updates)
12. [Das Tausch-Netzwerk](#12-das-tausch-netzwerk)
13. [Die Preis-Automatik im Detail](#13-die-preis-automatik-im-detail)
14. [Fehlerbehebung](#14-fehlerbehebung)
15. [FAQ](#15-faq)
16. [Anhang](#16-anhang)

---

## 1. Über Brickfolio

Brickfolio verfolgt drei Grundideen:

**Erfassen soll Sekunden dauern.** Figur oder Set mit der Handykamera
fotografieren, Treffer antippen, Zustand wählen – fertig. Die Erkennung
übernimmt die freie [Brickognize-API](https://brickognize.com), Namen und
Metadaten kommen von Rebrickable und BrickLink.

**Die Sammlung soll ihren Wert kennen.** BrickLink-Durchschnittspreise
werden automatisch geholt und fortlaufend aufgezeichnet – daraus entstehen
Preisverläufe pro Artikel und die Wertentwicklung der Gesamtsammlung.

**Eure Daten bleiben bei euch.** Alles läuft in einem einzigen
Docker-Container auf eurem eigenen Server (FastAPI + SQLite). Es gibt keinen
Brickfolio-Dienst dazwischen, bei dem ihr euch anmelden müsstet, und eure
Sammlung liegt nirgendwo sonst. Mehrere Familienmitglieder teilen sich eine
Datenbank, jeder mit eigenem Login.

Nach außen fragt die App nur dort, wo sie muss: beim Scannen (Brickognize),
bei der Namenssuche (Rebrickable) und für Preise und Set-Inhalte
(BrickLink). Für die beiden letzten braucht ihr eigene kostenlose Zugänge –
siehe 2.4. Ohne sie läuft alles andere weiter.

**Ein Punkt, der leicht übersehen wird: die Bilder.** In der Datenbank steht
zu jedem Artikel nur die *Adresse* seines Katalogbildes. Geholt wurde es
früher von **eurem Browser** direkt bei `img.bricklink.com`,
`cdn.rebrickable.com` oder – für alles Gescannte – bei
`storage.googleapis.com`, wo Brickognize seine Vorschaubilder ablegt. Aus der
Sammlung ging dabei nichts nach außen, aber die Bildadresse nennt die
Teilenummer, und bei jedem Blättern lief so ein Abruf.

**Seit 1.61.0 liegen die Bilder auf der Instanz.** Beim Erfassen holt der
Server das Bild einmal, verkleinert es auf 400 Pixel Kantenlänge und legt es
neben der Datenbank ab (`data/catalog/`). Danach fragt der Browser **nur noch
die eigene Instanz** – nach außen geht gar nichts mehr. Den Bestand aus der
Zeit davor holt **Mehr → 🖼 Bilder auf der Instanz** nach; die Karte sagt, wie
viele noch fehlen, und arbeitet sie in Häppchen ab.

Der Abruf kann ausschließlich zu den vier Katalog-Hosts gehen – als Weg nach
außen taugt er nicht, das prüfen eigene Tests. Der Dateiname wird aus der
Bildadresse **und dem Schlüssel eurer Instanz** gebildet; ohne den lässt sich
aus einer Teilenummer nicht ausrechnen, ob dieses Bild hier liegt.

Grob 10–25 KB je Artikel: 1000 Artikel sind also rund 15–25 MB auf der
Platte. In der JSON-Sicherung stecken sie **nicht** – die bleibt klein, und
verlorene Bilder holt der Knopf jederzeit neu.

Wer mag, verbindet seine Instanz zusätzlich mit dem **Tausch-Netzwerk**
(Kapitel 12) – dann sind auch mehrere Haushalte untereinander erreichbar.
Auch dabei bleibt die Sammlung zu Hause: Nach außen geht nur, was jemand
ausdrücklich zum Tausch anbietet, und Nachrichten sind Ende-zu-Ende
verschlüsselt.

**Technik in einem Satz:** Python-Backend (FastAPI) mit SQLite-Datenbank,
Vanilla-JS-Frontend ohne Build-Schritt, installierbar als PWA auf dem
Homescreen.

---

## 2. Installation & erste Einrichtung

### 2.1 Voraussetzungen

- Ein Server mit Docker und Docker Compose (getestet u. a. auf Synology
  DSM); 512 MB RAM genügen.
- Für Preise & Co.: kostenlose API-Zugänge bei BrickLink und Rebrickable
  (siehe 2.4 – die App funktioniert auch ohne, dann ohne Preise und
  Namenssuche).

### 2.2 Installation

Es gibt ein fertiges Image – nichts zu bauen, kein Quellcode nötig:

```bash
mkdir brickfolio && cd brickfolio
curl -sLo docker-compose.yml https://raw.githubusercontent.com/Melle79/brickfolio/main/docker-compose.example.yml
docker compose up -d
```

Danach ist die App unter `http://<server>:8300` erreichbar. Die Datenbank
liegt persistent unter `./data/brickfolio.db` – dieser Ordner überlebt
Updates und Container-Neubauten.

Das Image gibt es auf zwei Registries (inhaltlich gleich, nimm eine):
`ghcr.io/melle79/brickfolio:latest` und `melle79/brickfolio:latest`. Gebaut
wird für **amd64** (Intel/AMD, die meisten NAS) und **arm64** (Raspberry Pi,
ARM-NAS, Apple Silicon). Sehr alte 32-Bit-ARM-Geräte werden nicht
unterstützt.

**Ohne Konsole**, z. B. auf einer Synology: Die Oberfläche des Container
Managers nimmt dasselbe YAML entgegen. Schritt für Schritt steht das in
[`SYNOLOGY.md`](SYNOLOGY.md); für andere Hersteller listet das README, wo
die jeweilige Maske sitzt.

**Selbst bauen** (nur nötig für eigene Änderungen): Quellcode holen und in
der `docker-compose.yml` die Zeile `image: …` durch `build: .` ersetzen,
dann `docker compose up -d --build`.

**Port ändern / mehrere Instanzen:** Der erreichbare Port ist die *erste*
Zahl im `ports`-Mapping der `docker-compose.yml` – `"8301:8300"` macht die
App unter Port 8301 erreichbar (die zweite Zahl bleibt immer 8300). So
lassen sich auch mehrere Brickfolio-Instanzen parallel betreiben, z. B.
für getrennte Sammlungen oder eine Testinstallation: eigener Ordner,
eigener `container_name`, eigener Port – jede Instanz hat ihren eigenen
`data/`-Ordner und damit ihre eigene Datenbank.

**Synology-Hinweis:** Ordner unter `/volume1/docker/brickfolio` anlegen und
alle Befehle per SSH mit `sudo` ausführen.

### 2.3 Erster Start: der Einrichtungsassistent

Beim ersten Aufruf im Browser wählst du Benutzername und Passwort für das
**Admin-Konto**. Dieses erste Konto ist zugleich **Sammlerprofi** 💼 – wer
die Instanz einrichtet, ist ihr Eigner und soll Kaufpreise, Einkaufslisten
und Verkaufsliste von Anfang an sehen. Alle weiteren Benutzer starten als
Standard-Konto; die Profi-Rolle vergibt der Admin in der Benutzerverwaltung.

Danach bist du angemeldet, und ein Assistent führt in sieben Schritten durch
den Rest:

1. **Anzeigename** – der Name in Logo, Fenstertitel, **App-Symbol** und im
   Namen auf dem Startbildschirm des Handys („Svens Brickfolio")
2. **Preisgebiet und Währung** – aus welchem Markt die Ø-Preise kommen und
   in welcher Währung; vorausgewählt ist, was zu den Spracheinstellungen des
   Browsers passt (siehe Kapitel 13.1)
3. **Rebrickable-Schlüssel** – für die Suche nach Namen, mit Direktlink
4. **BrickLink-Zugang** – die vier Werte für Preise und Set-Inhalte
5. **Verbindung prüfen** – ein echter Testabruf bei beiden Diensten; so
   fällt ein verdrehter Schlüssel sofort auf und nicht erst beim ersten Scan
6. **Tausch-Netzwerk** – falls dich jemand eingeladen hat (siehe Kapitel 12)
7. **Fertig**

**Jeder Schritt ist überspringbar**, und unten steht „Assistent beenden und
direkt loslegen". Ohne Schlüssel funktioniert alles außer Preisen,
Set-Inhalten und der Namenssuche – das **Scannen braucht keinen einzigen
Schlüssel**. Nachtragen lässt sich alles unter *Mehr → API-Schlüssel*.

Der Assistent läuft genau einmal, direkt nach dem Anlegen des Admin-Kontos.

**Umzug von einer anderen Instanz?** Dann lege hier gar nichts an: Unter dem
Knopf zum Anlegen steht **„📥 Sicherung einspielen"**. Damit kommt der ganze
alte Stand herüber – Sammlung, Listen, Kaufbuch **und die Konten**. Danach
meldest du dich mit deinen **bisherigen Zugangsdaten** an – Name und Passwort
wie vorher.

> Namen nennt der Anmeldebogen dabei bewusst keine: Er ist eine Seite, an der
> noch niemand angemeldet ist, und wer die Sicherung eingespielt hat, kennt
> seine Zugangsdaten ohnehin.

> Genau umgekehrt wäre es umständlich: Ein hier frisch angelegtes Admin-Konto
> würde vom Einspielen sofort wieder überschrieben, denn die Sicherung bringt
> ihre eigenen Benutzer mit. Deshalb der eigene Weg vor der Anmeldung.
>
> **Wieso geht das ohne Anmeldung?** Weil es nur geht, solange die Instanz
> **leer** ist. Wer sie in diesem Zustand erreicht, könnte ohnehin einfach
> das erste Admin-Konto anlegen und wäre damit Herr über alles. Sobald ein
> Benutzer existiert, ist der Weg zu – ab dann führt er nur noch über
> *Mehr → Sicherung* und einen angemeldeten Admin.

*Für unbeaufsichtigte Setups:* Sind die Umgebungsvariablen
`ADMIN_USER`/`ADMIN_PASSWORD` gesetzt, legt Brickfolio den Admin beim
allerersten Start automatisch an; dann entfällt der Assistent und die
Schlüssel kommen entweder aus Umgebungsvariablen oder aus *Mehr →
API-Schlüssel*.

### 2.4 API-Schlüssel einrichten (Admin)

Unter **Mehr → API-Schlüssel** (nur für Admins sichtbar):

**BrickLink** – liefert Ø-Preise, Erscheinungsjahre und Set-Inhalte:

1. Du brauchst ein BrickLink-Konto **mit eröffnetem Shop** – die Store-API
   steht nur Verkäufern offen. Der Shop muss nichts anbieten, er muss nur
   eingerichtet sein (BrickLink: *My Store*).
2. Auf [API → Register Consumer](https://www.bricklink.com/v2/api/register_consumer.page)
   die Nutzungsbedingungen akzeptieren und einen **Access Token** erzeugen.
   Dabei **beide IP-Felder** (IP-Adresse *und* Maske) mit `0.0.0.0`
   ausfüllen – das erlaubt Zugriff von beliebiger Adresse.
3. Die vier Werte – *Consumer Key*, *Consumer Secret*, *Token*,
   *Token Secret* – in die vier Felder der App kopieren und speichern.

**Rebrickable** – liefert die Suche nach Namen:

1. Kostenloses Konto auf rebrickable.com anlegen.
2. Unter [Account → API](https://rebrickable.com/api/) einen Key erzeugen
   und ins Feld *Rebrickable Key* eintragen.

Zum Abschluss **„Verbindung testen"** drücken – die App prüft beide
Zugänge und meldet das Ergebnis. Dieselbe Anleitung steckt übrigens auch
in der App: ❓-Knopf oben rechts → „API-Schlüssel besorgen". Gespeicherte Schlüssel werden maskiert
angezeigt; ein leeres Feld beim Speichern lässt den vorhandenen Wert
unverändert. Alternativ können alle Schlüssel als Umgebungsvariablen
gesetzt werden (siehe README), die App-Einstellungen haben Vorrang.

### 2.5 Als App aufs Handy (PWA)

Läuft Brickfolio auf einem Handy noch im Browser, steht auf der Scan-Seite
oben die Karte **„📲 Auf den Startbildschirm"**. Was sie anbietet, hängt vom
Gerät ab:

- **Android und andere Chromium-Browser**: „Jetzt hinzufügen" löst die
  Installation direkt aus.
- **iPhone und iPad**: Safari kennt keinen Knopf dafür – die Karte erklärt
  den Weg über *Teilen → „Zum Home-Bildschirm"*.
- **Über eine reine `http`-Adresse im Heimnetz** erlaubt kein Browser das
  Hinzufügen. Dann sagt die Karte genau das und verweist auf *Mehr →
  Externer Zugriff* (2.7), womit sich ein verschlüsselter Zugang einrichten
  lässt.

**Nach unten ziehen lädt neu.** Vom Startbildschirm gestartet fehlt die
Adressleiste und damit der Knopf zum Neuladen; auf iOS gibt es dort auch
keine Geste dafür. Deshalb bringt Brickfolio eine eigene mit: oben in der
Liste nach unten ziehen, bis der Stein grün wird, loslassen. Im Browser
bleibt sie aus – da kann die Adressleiste das schon.

Sobald die App vom Startbildschirm läuft, verschwindet die Karte von selbst –
sie erkennt den Anzeigemodus. „Nicht mehr anzeigen" blendet sie dauerhaft
aus, pro Gerät.

Brickfolio im Handy-Browser öffnen → Teilen-Menü → **„Zum Home-Bildschirm"**
(iOS/Safari) bzw. **„App installieren"** (Android/Chrome). Danach startet
Brickfolio wie eine native App im Vollbild – inklusive Kamerazugriff fürs
Scannen.

### 2.6 Orientierung: Kopfzeile und Mehr-Tab

In der Kopfzeile sitzen zwei ständige Begleiter: der **❓-Knopf** (oben
rechts) öffnet die Hilfe als Popup – von jedem Tab aus, mit Anleitungen zu
allen Funktionen. Und der **eigene Name** daneben ist antippbar: Dahinter
liegt das **Profil-Popup** mit Anzeigename ändern, Passwort ändern und
Abmelden.

**💬 Ungelesene Nachrichten.** Wartet im Tausch-Netzwerk etwas, erscheint
links daneben ein Zeichen mit der Zahl der ungelesenen Nachrichten – von
jedem Tab aus zu sehen. Ein Tipp darauf führt direkt zu *Tausch → Meine
Vorgänge*. Ist nichts offen, ist auch kein Zeichen da. Beim Öffnen der App
fragt Brickfolio einmal beim Hub nach, damit die Zahl gleich stimmt und
nicht erst nach dem nächsten Takt.

> **Handy oder Rechner?** Die Navigation liegt auf dem **Handy als Leiste
> unten**, auf **breiten Bildschirmen als Seitenleiste links**. Dort nutzt
> die App die Fläche: Kennzahlen nebeneinander und in der Sammlung vier bis
> fünf Karten pro Reihe im Raster. Es ist dieselbe App – sie ordnet sich nur
> je nach Bildschirmbreite anders an, ohne dass man etwas umstellen muss.

Der Tab **Mehr** steht in vier Gruppen, sortiert danach, **wen es
angeht**. Die Karten klappen per Antippen der Überschrift auf und zu; die
App merkt sich den Zustand. Ist eine ganze Gruppe für die eigene Rolle
leer, verschwindet auch ihre Überschrift – ein normaler Benutzer sieht
also nur die erste Gruppe und ganz unten die Quellen.

| Gruppe | Karte | sichtbar für |
|---|---|---|
| 🙋 **Für dich** | 🌐 Sprache | alle |
| | 🎨 Design | alle |
| | ↕️ Sortierung der Sammlung | alle |
| | 📤 Export & Druck | alle |
| | 💼 Sammlerprofi (Angebots-Vorschlag, CSV-Import) | Sammlerprofi |
| | 📈 Preis-Protokoll | Sammlerprofi |
| 🏠 **Diese Instanz** | 🏷 Anzeigename | Admin |
| | 👥 Benutzer verwalten | Admin |
| | 🔑 API-Schlüssel | Admin |
| | 🌍 Preisgebiet & Währung | Admin |
| | 🖼 Bilder auf der Instanz | Admin |
| 🌐 **Nach außen** | 🌐 Externer Zugriff | Admin |
| | 🤝 Tausch-Netzwerk (verbinden/trennen) | Admin |
| 🛠 **Wartung** | 💾 Sicherung | Admin |
| | 🔄 Version & Updates | Admin |
| | 🐞 Fehlerbericht | Admin |
| *(ohne Gruppe)* | ℹ️ Quellen & Rechtliches | alle |

**🎨 Design** bietet drei Aussehen: **Klassisch** (hell, LEGO-Farben),
**Galaxie** (dunkel, mit Sternenhimmel und leuchtenden Akzenten) und
**Nova** (modernes Glas-Design – tiefdunkler, blau schimmernder Hintergrund,
durchscheinende Flächen und blauer Akzent). Die Wahl wird **im Profil
gespeichert** und gilt damit **auf allen Geräten**, sobald man angemeldet
ist. Der Admin sieht zusätzlich an jedem Design einen **Stern**: ⭐ markiert
das **Standard-Design der Instanz**; ein Tipp auf den Stern eines anderen
Designs macht dieses zum Standard. Er gilt für den Login-Bildschirm und für
Benutzer, die noch keine eigene Wahl getroffen haben (die eigene Auswahl
ändert der Stern nicht).

**ℹ️ Quellen & Rechtliches** nennt, woher Daten und Bilder stammen
(Rebrickable, BrickLink, Brickognize), weist darauf hin, dass beim
Abfotografieren das Foto zur Erkennung übertragen wird, und führt Marken-,
Schrift- und Programmlizenz auf.

### 2.7 Von unterwegs erreichbar machen (Cloudflare Tunnel)

Standardmäßig läuft Brickfolio nur im **Heimnetz**. Wer auch von unterwegs
(Handy im Mobilfunknetz, anderer Ort) zugreifen möchte, sollte **keine
Ports am Router freigeben** – das öffnet den Server dem ganzen Internet.
Empfohlen ist stattdessen ein **Cloudflare Tunnel**: sicherer, einfacher
und kostenlos.

**Warum Cloudflare Tunnel**

- **Kein offener Port.** Der Tunnel baut eine *ausgehende* Verbindung zu
  Cloudflare auf – am Router und NAS muss nichts nach innen freigegeben
  werden. Das verkleinert die Angriffsfläche enorm.
- **HTTPS inklusive.** Die App ist über eine eigene (Sub-)Domain
  verschlüsselt erreichbar, ohne selbst Zertifikate zu pflegen.
- **Funktioniert hinter CGNAT** und ohne feste öffentliche IP – gerade bei
  vielen Kabel-/Mobilfunk-Anschlüssen wichtig.

**Voraussetzung:** ein kostenloses Cloudflare-Konto und eine Domain, die
bei Cloudflare verwaltet wird (eine günstige Domain registrieren oder eine
vorhandene umziehen).

**Empfohlene Installation** – `cloudflared` als zweiter Container direkt
neben Brickfolio, gesteuert per Tunnel-Token:

1. Im **Cloudflare Zero Trust**-Dashboard unter *Networks → Tunnels* einen
   Tunnel anlegen und den angezeigten **Token** kopieren.
2. Beim Tunnel einen *Public Hostname* eintragen, z. B.
   `brickfolio.deine-domain.de`, mit Service
   **`http://brickfolio:8300`** (der Container-Name und Port von oben).
3. In der `docker-compose.yml` neben dem `brickfolio`-Dienst ergänzen:

   ```yaml
     cloudflared:
       image: cloudflare/cloudflared:latest
       container_name: brickfolio-tunnel
       restart: unless-stopped
       command: tunnel run
       environment:
         TUNNEL_TOKEN: "hier-den-token-einsetzen"
   ```

   Beide Container liegen im selben Compose-Netz, daher erreicht
   `cloudflared` die App unter `http://brickfolio:8300`. Dann
   `docker compose up -d`.

Danach ist Brickfolio unter `https://brickfolio.deine-domain.de` von
überall verschlüsselt erreichbar – ganz ohne Portfreigabe. Als PWA lässt
es sich über diese Adresse auch aufs Handy legen (siehe 2.5).

> **Extra-Schloss (empfohlen):** Im Zero-Trust-Dashboard lässt sich vor die
> App eine **Access-Policy** setzen – etwa Anmeldung per E-Mail-Einmalcode
> oder Beschränkung auf bestimmte Adressen. Dann kommt nur an die
> Login-Seite, wer vorher von Cloudflare bestätigt wurde. Für die eigene
> Familie genügt oft auch der normale Brickfolio-Login; die Access-Policy
> ist die zweite Tür für alle, die ganz sichergehen wollen.

**Mehrere Instanzen** (z. B. eine je Familienmitglied): einfach mehrere
*Public Hostnames* anlegen, die auf die jeweiligen Container-Ports zeigen –
ein einziger `cloudflared`-Container reicht dafür aus.

### 2.8 Wie die App abgesichert ist – und wofür sie nicht gebaut ist

Brickfolio ist für das **Heimnetz** gebaut. Wer den Port am Router
freigibt, sollte wissen, was dann greift und was nicht.

**Was da ist:**

- **Jeder Datenzugriff verlangt eine Anmeldung.** Offen sind nur die
  Startseite, das Anmelden, die Ersteinrichtung und die Bilddateien selbst
  (deren Namen zufällig und nicht erratbar sind).
- **Passwörter** liegen als PBKDF2-SHA256 mit 200.000 Runden und eigenem
  Salz je Benutzer – nicht im Klartext, nicht als einfacher Hash.
- **Passwortraten wird gebremst**: zehn Fehlversuche je Konto und je
  Herkunft, danach 15 Minuten Pause. Auch das richtige Passwort zählt in
  dieser Zeit nicht – sonst käme jemand durch, der es gerade erraten hat.
  Eine geglückte Anmeldung setzt die Zähler zurück.
- **Schutz-Header**: Die Seite lässt sich nicht in einen fremden Rahmen
  stecken, der Browser darf Dateitypen nicht raten, und eine
  Inhaltsrichtlinie erlaubt Skripte nur aus der App selbst.
- **Hochgeladene Bilder** werden neu kodiert – das entfernt EXIF-Daten
  (etwa GPS aus Handyfotos) und verhindert, dass etwas anderes als ein Bild
  gespeichert wird.
- **Rollen**: Kaufpreise, Listenverwaltung, Benutzer, Schlüssel und
  Sicherung hängen an Profi- bzw. Admin-Rechten. **Rechte kommen bei jeder
  Anfrage frisch aus der Datenbank**, nicht aus dem Sitzungs-Token: Entzieht
  ein Admin jemandem die Rechte oder löscht das Konto, wirkt das sofort und
  nicht erst mit Ablauf der Sitzung.
- **Ein Passwortwechsel beendet alle bisherigen Sitzungen** (seit v1.67.0) –
  auf allen Geräten. Wer sein Passwort ändert, weil ein Gerät abhandengekommen
  ist, sperrt es damit wirklich aus; das eigene Gerät bekommt eine frische
  Sitzung und bleibt angemeldet. Dasselbe gilt, wenn ein Admin ein Passwort
  zurücksetzt oder einen zweiten Faktor abnimmt.
- **Geheimnisse werden aus jeder Fehlermeldung entfernt**, bevor sie
  gespeichert oder als GitHub-Issue verschickt wird – API-Schlüssel,
  GitHub-Token, Hub-Zugang, der private Hub-Schlüssel und der
  Push-Schlüssel. Ein Test schlägt an, sobald eine neue Einstellung
  dazukommt, die niemand als geheim oder offen eingeordnet hat.

**Was fehlt – und warum eine Portfreigabe trotzdem keine gute Idee ist:**

- **Keine Verschlüsselung.** Die App spricht `http`. Über eine Portfreigabe
  gingen Passwort und Sitzungs-Token **im Klartext** durchs Internet. Das
  ist der schwerwiegendste Punkt.
- **Passwörter dürfen kurz sein** (mindestens acht Zeichen seit v1.57.0,
  vorher vier). Für zu Hause in Ordnung, für das offene Internet dünn.
- **Sitzungen gelten 90 Tage** und liegen im Browser-Speicher. Anpassbar
  über `TOKEN_DAYS` in `docker-compose.yml`.
- **Kein Schutz gegen jemanden, der schon im Heimnetz ist.** Die Bilddateien
  und die Katalogbilder sind ohne Anmeldung abrufbar – ihre Namen sind
  allerdings ohne den Schlüssel der Instanz nicht auszurechnen.
- **`latest` heißt Vertrauen in die Registry.** Wer das Image mit dem Zusatz
  `:latest` einträgt, bekommt bei jedem Update den neuesten Stand von dort –
  auch dann, wenn dieses Konto einmal in falsche Hände geriete. Wer das nicht
  möchte, trägt eine **feste Version** ein
  (`image: ghcr.io/melle79/brickfolio:1.67.0`). Dann läuft nur, was ihr selbst
  ausgewählt habt.
  > **Aber:** Eine feste Versionsnummer legt nur den *Namen* fest. Wer die
  > Registry kontrolliert, könnte unter `1.67.0` genauso etwas anderes
  > ausliefern wie unter `latest`. Wirklich schützt nur ein **Digest**
  > (`image: ghcr.io/melle79/brickfolio@sha256:…`) – der beschreibt den Inhalt
  > selbst und lässt sich nicht umhängen. Den Digest zeigt die
  > Release-Seite bzw. `docker image inspect`.
  >
  > **Der Preis in beiden Fällen:** Der Update-Knopf in der App bewirkt nichts mehr.
  > `docker compose pull` holt bei einer festen Version denselben Stand, der
  > Container startet neu und zeigt dieselbe Version. Aktualisieren heißt dann:
  > Zeile in der `docker-compose.yml` ändern und `docker compose up -d`. Die
  > App meldet weiterhin, dass eine neue Version bereitsteht – das ist dann
  > ein Hinweis, keine Aufforderung an den Knopf.

**Die Empfehlung** ist deshalb unverändert der **Cloudflare Tunnel** (2.7):
Er bringt Verschlüsselung mit, öffnet keinen Port, und mit einer
Access-Policy steht sogar eine zweite Tür davor. Wer trotzdem eine
Portfreigabe machen will, sollte mindestens ein langes, einmaliges Passwort
vergeben und den Zugang auf bekannte Adressen einschränken.

---

### 2.9 Lokale KI für die Suche (Admin, optional)

Ganz freiwillig – ohne diesen Abschnitt funktioniert Brickfolio vollständig.

**Wozu.** Die Oberfläche ist deutsch, die Artikelnamen kommen von BrickLink
und sind englisch. „Ritter" fand deshalb nichts, obwohl die Figur als
„Castle Knight" in der Sammlung liegt. Ist hier eine lokale KI hinterlegt,
übersetzt die App erfolglose Suchbegriffe ins Englische und sucht erneut –
sowohl in der eigenen Sammlung (siehe 5.1) als auch im Katalog beim manuellen
Erfassen (siehe 4.2 und 4.4).

**Einrichten.** Unter **Mehr → 🤖 Lokale KI für die Suche**:

**📚 Der Katalog-Abzug.** Ein Abzug des BrickLink-Katalogs, der die Suche
nach dem **Aussehen** möglich macht: „roter Protokolldroide mit schwarzem
Aufdruck" findet `R-3PO Protocol Droid`. Über den gewöhnlichen Katalog geht
das nicht – Rebrickable nennt dieselbe Figur nur `R-3PO`, ohne ein einziges
Wort zum Suchen. Zu jeder Figur steht darin, was auf dem Bild zu sehen ist,
Teil für Teil: „torso red black chest panel; cape yellow green dragon with
red wings".

**Erzeugt wird er nicht hier.** Auf Svens NAS läuft ein Dienst, der
BrickLink abklappert und ein lokales Sehmodell die Katalogfotos beschreiben
lässt. Das Ergebnis veröffentlicht er als Datei:

```
https://raw.githubusercontent.com/Melle79/brickfolio/main/katalog/index.ndjson
```

Jede Installation zieht sie sich alle zwölf Stunden – **ohne Zugang zu
irgendwem und ohne dass irgendwo etwas laufen muss**.

> **Darin steht nur, was uns gehört:** die BrickLink-Nummer als Kennung und
> der Text, den das Sehmodell über das Foto geschrieben hat. Name, Jahr,
> Kategorie und Bildadresse stehen **nicht** darin – das ist BrickLinks
> Inhalt, und dessen Weitergabe an Dritte untersagen deren
> Nutzungsbedingungen.
>
**Die Themen** sind Nummernvorsilben, keine Kategorien – und die Zuordnung
gibt BrickLink nicht heraus.

| Präfix | Thema | | Präfix | Thema | | Präfix | Thema |
|---|---|---|---|---|---|---|---|
| `sw` | Star Wars | | `adv` | Adventurers | | `hs` | Hidden Side |
| `cty` | City | | `trn` | Eisenbahn | | `dim` | Dimensions |
| `njo` | Ninjago | | `twn` | Town (älter) | | `vid` | Vidiyo |
| `sh` | Super Heroes | | `idea` | LEGO Ideas | | `sim` | Simpsons |
| `frnd` | Friends | | `cre` | Creator | | `tnt` | Turtles |
| `cas` | Burg | | `js` | Jack Stone | | `min` | Minecraft |
| `pi` | Piraten | | `4j` | 4 Juniors | | `dis` | Disney |
| `hp` | Harry Potter | | `poc` | Fluch der Karibik | | `tlm` | The LEGO Movie |
| `jw` | Jurassic World | | `atl` | Atlantis | | `hol` | Feiertage |
| `sp` | Weltraum | | `mof` | Monster Fighters | | `edu` | Lernen & Dacta |
| `ww` | Western | | `exf` | Exo-Force | | `stu` | Studios |
| `lor` | Herr der Ringe | | `arc` | Arktis | | `soc` | Fußball |
| `iaj` | Indiana Jones | | `aqu` | Aquazone | | `nba` | Basketball |
| `gen` | Allgemein | | `uagt` | Agents | | `hky` | Eishockey |
| `col` | Sammelfiguren | | | | | | |

Vier Ziffern haben `sw`, `cty`, `njo`, `sh` und `frnd`; alle übrigen drei.

> **Wie diese Liste entstanden ist** – der Weg ist wichtiger als die Liste,
> denn sie ist bis heute nicht vollständig.
>
> BrickLink zeigt einen Katalogbaum auf der Webseite, aber deren
> Nutzungsbedingungen untersagen automatische Abrufe („any robot, spider,
> other automatic device"). Der Umweg geht über die **offizielle API**:
> `/categories` liefert in *einem* Aufruf alle Kategorien, und jede
> abgeklapperte Figur bringt ihre `category_id` mit. Damit sieht man, welche
> Kategorien nur über den Sammeltopf `gen` abgedeckt sind – und genau die
> haben fast immer ein eigenes Präfix. Raten, über die API nachprüfen,
> fertig: Am 24.08.2026 saßen so 22 von 31 Versuchen.

Drei Fallen stecken darin:

- **Präfix ≠ Kategorie.** `cty` deckt „Town" *und* „Train" ab – und trotzdem
  gibt es beide daneben eigenständig als `twn` und `trn`. Umgekehrt teilen
  sich `js`, `4j` und `cre` die Kategorie „4 Juniors".
- **Die Ziffernbreite unterscheidet sich.** `sw0002` hat vier, `cas001` nur
  drei. Fest verdrahtete vier ließen am 21.08.2026 acht Themen **komplett
  leer** ausgehen – und der Lauf meldete trotzdem „fertig".
- **Ein Präfix kann mit einer Ziffer beginnen.** `4j` ist „4 Juniors". Eine
  Prüfung auf „nur Buchstaben" wies das Thema am 24.08.2026 ab, obwohl es
  die Figuren gibt.

Weitere trägt man in der Hub-Konsole einfach dazu; der Prüfknopf sagt
vorher, ob es sie gibt und mit wie vielen Ziffern.

**Er ist optional.** 3,3 MB alle zwölf Stunden, und beim ersten Mal rund
9.700 BrickLink-Abrufe für die Namen. Wer die Suche nach dem Aussehen nicht
braucht, schaltet ihn in den Einstellungen ab; der bereits geholte Bestand
bleibt dabei liegen und wäre sonst beim Wiedereinschalten noch einmal zu
holen.

> **Der schnelle Weg zu den Namen:** BrickLink bietet seinen Katalog jedem
> Mitglied zum Herunterladen an – *My Account → Downloads → Catalog Items*,
> Item Type *Minifigures*, Format XML. Diese Datei lässt sich in den
> Einstellungen einlesen, und alle 19.158 Namen stehen **sofort** da statt
> über drei Tage einzeln abgerufen zu werden. Es kostet kein Kontingent,
> die Beschreibungen bleiben erhalten, und es ist unbedenklich: Jeder lädt
> seine eigene Datei, weitergegeben wird nichts.
>
> Den **Namen** schlägt sonst jede Installation über ihren eigenen
> BrickLink-Zugang nach, gedrosselt im Hintergrund. Beim ersten Mal sind das
> rund 9.700 Abrufe über ein paar Tage – dasselbe Kontingent trägt die
> Preise, und die braucht man täglich. Bis ein Name da ist, steht in der
> Suche die Nummer; **gefunden** wird die Figur trotzdem, denn dafür sorgt
> die Beschreibung, und die ist sofort da. Bis 2.40.0 tat das jede Instanz selbst, und das war dreifach
verkehrt:

- **Viermal dieselbe Arbeit für dasselbe Ergebnis.** Der Abzug beschreibt
  BrickLinks Fotos, nicht die Sammlung von irgendwem – er ist für alle
  identisch. Tage an Abrufen und rund ein Tag Grafikeinheit, je Instanz.
- **Jede brauchte ein Sehmodell.** Seit dem 23.08.2026 hatten drei von vier
  keines mehr.

Der BrickLink-Zugang bleibt gebraucht – aber nur noch für die Namen und die
Preise, nicht mehr für den Abzug selbst.

In den Einstellungen steht deshalb nur noch eine Zeile: wie viele Figuren
angekommen sind, wie viele davon beschrieben, und wann zuletzt geholt wurde.
Gesteuert wird nichts mehr – Themen, Prüfknopf, Abzug starten, Bilderlauf,
das Modell fürs Bilderansehen: alles im Hub.

> **Was die App trotzdem noch braucht.** Der Abzug liegt lokal in
> `katalog_index`, nicht nur im Hub: Gesucht wird darin ohne Netz und ohne
> Wartezeit. Der Hub ist die Quelle, nicht die Suchmaschine.

Die lokale KI übersetzt weiterhin **Suchbegriffe** – „Ritter" zu „Knight".
Das ist eine ganz andere Aufgabe als Bilder ansehen und bleibt deshalb hier.

**📖 Gelernte Begriffe.** Unter der KI-Karte steht die Bilanz („1.243
Begriffe gelernt, davon 12 eigene"); **Ansehen und pflegen** öffnet die Liste
in einem eigenen Fenster, mit Suchfeld und seitenweise. Sie wächst mit jedem
Suchlauf und hätte die Einstellungen sonst zugeschüttet. Gesucht wird in
beiden Richtungen: „ritter" über den deutschen Begriff, „Knight" über das,
was dabei herauskommt. Hinein wandert, **was wirklich etwas gefunden hat** –
„ritter → Knight", nicht die ganze Modellantwort; eigene Zeilen trägst du
selbst ein und sie haben **Vorrang**:

| Gesucht wird nach | Finden soll er |
|---|---|
| `roter c3po` | `R-3PO` |

Das ist nützlich, wo ihr etwas anders nennt als der Katalog. Der rote
Protokolldroide heißt bei BrickLink „R-3PO Protocol Droid" – wer ihn „roter
C-3PO" nennt, fand ihn vorher nie, weil das Modell am Eigennamen C-3PO
festhält.

Drei Dinge sind dabei absichtlich so:

- **Eigene Zeilen gelten auch ohne KI.** Das Gelernte hängt an der App, nicht
  am Modell. Ein Wechsel des Modells oder des Rechners nimmt es mit.
- **Die KI überschreibt deine Zeilen nicht.** Sonst wäre das Beigebrachte beim
  nächsten Suchlauf wieder weg.
- **Gemerkt wird nur, was getroffen hat.** Nicht jede Suche. Bis 2.37.5
  landete jede Modellantwort dauerhaft in der Liste, auch wenn kein einziger
  Treffer dabei herauskam – und die Liste wird **vor** dem Modell befragt.
  Eine erfundene Übersetzung war damit für immer festgeschrieben, und die
  Liste füllte sich mit Anfragen, die nie wiederkehren. Von den vier
  Begriffen, die das Modell zu „Ritter" nennt, bleibt jetzt der stehen, der
  in der Sammlung wirklich etwas gefunden hat.
- **Tippzwischenstände räumen sich selbst weg.** Ab dem dritten Zeichen löst
  jeder Tastendruck eine Suche aus, und jede merkte sich ihren Begriff: In der
  Liste standen „rit", „ritt", „ritte" neben „ritter". Ein kürzerer Begriff,
  der ein Anfang des neuen ist und in den letzten zwei Minuten entstand,
  fliegt jetzt wieder raus. Von Hand Eingetragenes und ältere Suchen bleiben
  unberührt.

  Es ging dabei nicht nur um Krempel: Aus einem abgeschnittenen Wort reimt
  sich das Modell etwas zusammen, das es nicht gibt. Aus `at st captain
  phasm` wurde am 21.08.2026 ein „Phantom Captain" – sechs Sekunden bevor
  `at st captain phasma` die richtige Antwort brachte. Beides stand danach
  nebeneinander in der Liste, und beides galt gleich viel.
- **Fehlschläge werden nicht gelernt.** Ein leeres Ergebnis ist kein Wissen –
  dauerhaft gespeichert stellte es den Begriff für immer tot.

Nebenbei wird die Suche schneller: Ein bekannter Begriff kostet Millisekunden
statt eineinhalb Sekunden, weil das Modell gar nicht erst gefragt wird.

> **Das Modell aussuchen statt abtippen.** Steht die Adresse, holt die App
> die Liste der dort installierten Modelle und stellt sie zur Wahl. Das ist
> mehr als Bequemlichkeit: Der Name muss exakt stimmen, und auf einem Server
> liegen leicht `qwen2.5:14b` **und** `qwen2.5:14b-instruct` nebeneinander –
> ein Vertipper sah bisher aus wie ein kaputter Dienst. Antwortet der Server
> nicht, bleibt das Textfeld; wer den Namen kennt, trägt ihn weiter von Hand
> ein. Über **Modelle laden** lässt sich die Liste erneut holen, etwa nach
> einem `ollama pull`.

1. Auf einem Rechner im Heimnetz [Ollama](https://ollama.com) installieren
   und ein Modell laden, z. B. `ollama pull qwen2.5:14b`.
2. Damit Brickfolio es erreicht, muss Ollama im Netz lauschen, nicht nur
   lokal – bei der Ollama-App über deren Einstellungen, sonst über
   `OLLAMA_HOST=0.0.0.0:11434`.
3. In der App die **Adresse** eintragen, etwa
   `http://192.168.0.10:11434`, dazu den **Modellnamen**. Bleibt das
   Modellfeld leer, nimmt die App `qwen2.5:14b`.
4. **„Verbindung testen"** drücken: Die App fragt das Modell nach „Ritter"
   und zeigt, was zurückkommt. Steht dort `Knight`, passt alles.

Alternativ über die Umgebungsvariablen `OLLAMA_URL` und `OLLAMA_MODEL`
(siehe `docker-compose.example.yml`); die Einstellung in der App hat
Vorrang.

**Was die KI darf – und was nicht.** Sie bekommt ausschließlich den
Suchbegriff zu sehen, nie die Sammlung. Sie liefert **Suchbegriffe, niemals
Ergebnisse**: Gesucht wird weiterhin nur in der eigenen Datenbank, ein
unpassender Begriff findet einfach nichts. Deshalb reicht hier ein kleines
Modell, und deshalb kann nichts erscheinen, was es nicht gibt.

**Wenn der Dienst schweigt.** Antwortet er nicht innerhalb von acht
Sekunden, bleibt es beim gewohnten Hinweis „Nichts gefunden" – die Suche
wartet nicht und meldet keinen Fehler. Ein leeres Adressfeld schaltet die
Funktion wieder ab.

> **Die Adresse gilt als Geheimnis.** Sie verrät den Aufbau des Heimnetzes
> und kann Zugangsdaten enthalten. Brickfolio entfernt sie deshalb wie einen
> API-Schlüssel aus Fehlerberichten – die können als öffentliches Issue enden.

## 3. Benutzer & Rollen

Brickfolio kennt drei Stufen, die sich kombinieren lassen:

| Aktion | Standard | Sammlerprofi 💼 | Admin 🔧 |
|---|:-:|:-:|:-:|
| Scannen, Sammlung, Listen (Wünsche), Statistik | ✔ | ✔ | ✔ |
| Einkaufslisten sehen, Artikel „ist da" verbuchen | ✔¹ | ✔ | ✔¹ |
| Listen anlegen/befüllen/archivieren, Gesamtangebot | – | ✔ | – |
| Kaufpreise & Gewinn sehen, Verkaufsliste, CSV-Import | – | ✔ | – |
| Benutzer, Rollen, API-Schlüssel, Sicherung | – | – | ✔ |

¹ Der Listen-Tab erscheint für Standard-Benutzer nur, wenn mindestens eine
aktive Liste existiert.

**Benutzer anlegen (Admin):** Mehr → 👥 Benutzer verwalten → Name +
Passwort → „Benutzer anlegen". Jeder Benutzer ändert sein Passwort und
seinen Anzeigenamen selbst, indem er **oben rechts auf seinen Namen
tippt** (Profil-Popup); der Admin kann Passwörter zurücksetzen und
Benutzer entfernen.

> **Was beim Entfernen mit seinen Sachen passiert:** Sammlung, Wünsche,
> Listen und abgehakte Listeneinträge **bleiben** – sie gehören der
> Instanz, nicht der Person; nur der Name dahinter verschwindet. Mit
> gelöscht wird allein seine Push-Anmeldung, damit sein Gerät keine
> Meldungen dieser Instanz mehr bekommt.

**Rollen vergeben:** In der Benutzerliste macht der **Admin**-Knopf einen
Benutzer zum weiteren Admin (👑) oder nimmt die Rechte wieder – der
**letzte** Admin bleibt aber immer Admin, damit sich niemand aussperrt.
Der **Profi**-Knopf schaltet den Sammlerprofi-Modus.

**Sammlerprofi-Rolle vergeben (Admin):** In der Benutzerliste den
**„Profi"**-Knopf antippen – er wird grün („Profi ✔"). Die Rolle wirkt
sofort, ohne Neuanmeldung; nochmaliges Antippen entzieht sie wieder.
Typisches Familien-Setup: Ein Elternteil ist Admin + Profi, das Kind
verwaltet mit dem Standard-Konto einfach seine Sammlung.

**Gut zu wissen:** Kaufpreise werden für *alle* Einträge im Hintergrund
mitgeführt – wer die Profi-Rolle später bekommt, sieht rückwirkend
vollständige Daten.

### 3.1 Zwei-Faktor-Anmeldung (freiwillig, je Benutzer)

Wer mag, sichert sein Konto zusätzlich mit einem **Einmalcode aus einer
Authenticator-App** (Aegis, 1Password, Google Authenticator …). Das ist die
sinnvollste Ergänzung, sobald die App von außen erreichbar ist.

**Einschalten** unter *Profil* (Name oben rechts antippen) → **🔐
Zwei-Faktor-Anmeldung**:

1. Passwort eingeben, „Einrichten" – es erscheint ein **QR-Code**; wer nicht
   scannen kann, tippt den darunter stehenden Schlüssel ab.
2. Den sechsstelligen Code aus der App eintragen und „Einschalten". Erst
   dieser Schritt aktiviert die Sicherung – so kann sich niemand mit einem
   falsch übertragenen Schlüssel aussperren.
3. Es erscheinen **acht Rettungscodes**. Sie werden **nur dieses eine Mal**
   angezeigt: Danach liegen in der Datenbank nur noch ihre Prüfsummen.
   Ausdrucken oder in den Passwortspeicher legen.

**Anmelden** läuft danach in zwei Schritten: erst Passwort, dann Code. Wer
das Telefon nicht zur Hand hat, gibt statt des Codes einen **Rettungscode**
ein – jeder gilt genau einmal, die App sagt danach, wie viele übrig sind.

**Ausschalten** verlangt Passwort *und* einen gültigen Code.

> **Telefon verloren und keine Rettungscodes mehr?** Dann nimmt ein **Admin**
> den zweiten Faktor in der Benutzerverwaltung ab. Ohne diesen Ausweg wäre
> ein verlorenes Gerät ein verlorenes Konto. Der letzte Admin sollte seine
> Rettungscodes deshalb besonders sorgfältig aufbewahren.

**Gut zu wissen:**

- Ein Code gilt **nur einmal**. Wer ihn über die Schulter abliest, kann ihn
  nicht innerhalb derselben halben Minute wiederverwenden.
- Eine Uhr-Abweichung von einer halben Minute ist eingeplant. Meldet die App
  hartnäckig „Code stimmt nicht", stimmt meist die **Uhrzeit des Telefons**
  nicht.
- Auch der zweite Schritt ist gegen Raten gebremst (siehe 2.8).
- Die Codes rechnet die App nach RFC 6238 – demselben Verfahren wie alle
  gängigen Authenticator-Apps.

---

## 4. Scannen & Erfassen

### 4.1 Per Kamera

Im Tab **Scannen** auf **„Figur oder Set fotografieren"** tippen, die
Figur oder das Set möglichst formatfüllend und bei gutem Licht
fotografieren. Am Rechner kann man ein Bild auch **per Drag & Drop** auf
die Scan-Fläche ziehen oder einen **Screenshot mit Strg/Cmd+V** einfügen.
Die App zeigt eine Kandidatenliste mit Trefferwahrscheinlichkeit, Bild,
Nummer und – je nach Datenlage – Jahr, Ø-Preisen und Besitz-Hinweisen.

**Tipps für gute Trefferquoten:** Einfarbiger Hintergrund, Figur von vorn,
keine spiegelnden Verpackungen. Bei Sets funktioniert das Boxbild oder das
aufgebaute Modell.

> **Was mit dem Foto passiert.** Es wird **im Browser** auf 1200 Pixel
> verkleinert, bevor irgendetwas damit geschieht – und zwar schon beim
> Entpacken. Ein 12-Megapixel-Foto belegt vollständig entpackt 46 MB, so
> aber nur 4. Zum Server gehen danach rund 90 KB statt mehrerer Megabyte.

**Mehrere Figuren auf einem Bild.** Die Erkennung sucht **ein** Objekt je
Anfrage – so ist der Dienst gebaut. Liegen mehrere Figuren auf dem Foto,
sucht sie sich eine aus. Damit man sieht, welche, umrahmt die Vorschau die
erkannte Figur **grün**.

Damit trotzdem alle auf einmal gehen, gibt es **🔎 Alle Figuren erkennen** –
und der Weg dorthin ist seit Version 1.97.0 ein anderer: Die App sucht die
Figuren **nicht mehr selbst**, sondern lässt den Erkennungsdienst suchen.

**Wie das geht.** Jede Antwort des Dienstes bringt einen Rahmen mit – er sagt
also immer mit, *wo* er hingeschaut hat. Die App nutzt das reihum: erkennen,
den gefundenen Bereich in Hintergrundfarbe ausblenden, erneut fragen. Was
übrig bleibt, wird beim nächsten Mal zum auffälligsten Objekt. Sobald nichts
mehr kommt, ist Schluss – die Zahl der Figuren muss also niemand vorgeben.

Jede Runde liefert **Fundort und Bestimmung in einer Antwort**. Der Weg kostet
damit nicht mehr Anfragen als früher, kommt aber mit Anordnungen zurecht, an
denen das alte Verfahren scheiterte: mit Figuren, die sich **berühren**, mit
**mehreren Reihen**, mit kreuz und quer Liegendem. Gemessen an vier
Klonkriegern dicht nebeneinander: **4 von 4 Figuren, 72 bis 91 % sicher, in
1,2 Sekunden** – das alte Verfahren fand an derselben Aufnahme **gar nichts**.

> **Was vorher hier stand.** Bis 1.96.0 maß die App, wie viel Struktur in
> jeder Bildspalte steckt, und schnitt in den Lücken. Das funktionierte bei
> Figuren mit Abstand und versagte, sobald sie sich berührten – es gibt dann
> keine Lücke. Darunter stand ein Regler für die Zahl der Streifen; auch der
> ist weg, weil es nichts mehr einzustellen gibt.

**Wo auch das an seine Grenze kommt.** Der Dienst findet immer das
auffälligste verbliebene Objekt. Sehr kleine oder halb verdeckte Figuren
fallen durch.

**Nach 10 Figuren fragt die App zurück.** Das ist keine technische Grenze,
sondern Rücksicht: Jede Runde ist eine Anfrage an einen **kostenlos**
bereitgestellten Dienst. Sind nach zehn Funden noch Figuren da, erscheint
deshalb **🔎 Weitersuchen** – die App macht dort weiter, wo sie aufgehört hat,
und die neuen Funde kommen zu den bisherigen dazu. Wer nicht weitersucht, hat
nichts verloren; wer will, entscheidet das selbst. Kommt nichts mehr,
verschwindet der Knopf von allein.

Für alles, was übrig bleibt, gibt es den Weg von Hand:

Für diese Fälle gibt es den **verlässlichen Weg**, und der ist schnell:

1. Rahmen um eine Figur ziehen
2. **➕ Rahmen merken**
3. Für jede weitere Figur wiederholen – die gemerkten bleiben nummeriert
   stehen
4. **🔎 Alle erkennen**

Das funktioniert bei jeder Anordnung, weil ihr die Grenzen setzt und nicht
die App sie raten muss. **Verwerfen** räumt die gemerkten Rahmen wieder weg.

Der einzelne grüne Rahmen mit der Beschriftung **„hier geschaut"** ist etwas
anderes: Er kommt vom Erkennungsdienst und zeigt, worüber er beim ersten
Scan geraten hat. Sobald nummerierte Rahmen da sind, verschwindet er.

### 5.6 Das eigene Foto zusätzlich am Artikel

Über den Treffern steht ein Kästchen: **📷 Mein Foto zusätzlich am
Artikel.** Ist es angehakt, hängt alles, was ihr aus diesem Scan anlegt –
Sammlung, Wunschliste **und** Einkaufsliste –, euer eigenes Foto an den
Artikel. Gedacht ist es wie die Bilder, die Käufer bei BrickLink
beisteuern: Das **Katalogbild bleibt**, wo es ist, euer Foto kommt daneben.

Zu sehen sind sie in der **Galerie**: Tippt auf das Bild eines Artikels, und
blättert. Das Katalogbild ist das erste – es zeigt die Figur sauber
freigestellt –, eure Fotos folgen. Bei einem eigenen steht oben **„mein
Foto"**, und unten erscheint **🗑 Mein Foto entfernen**.

Bei mehreren Figuren auf einem Foto bekommt **jede ihren eigenen
Ausschnitt**: genau den Rahmen, in dem sie gefunden wurde. Ob der aus der
Reihum-Suche stammt, von einem gemerkten Rahmen oder von einem, den ihr
selbst gezogen habt, spielt keine Rolle. Nur wenn es gar keinen Rahmen gibt,
wird das ganze Foto genommen.

**Standardmäßig ist es aus.** Die Entscheidung merkt sich die App auf diesem
Gerät, ihr müsst sie also nicht bei jedem Scan neu treffen.

**Nur das Foto, sonst nichts.** Steht die Figur längst in der Sammlung und
ihr wollt bloß ein Bild davon hinterlegen, nehmt den Knopf **📷 Nur Foto
dazu** auf der Trefferkarte. Er hängt das Foto an den Artikel und rührt
sonst nichts an – keine zweite Zeile, keine erhöhte Menge, kein Eintrag auf
einer Liste. Der Knopf wirkt **unabhängig vom Kästchen** oben: Das gilt
fürs Anlegen, hier ist das Foto ja der ganze Zweck. Danach heißt er
„📷 Foto dabei ✔".

Er erscheint **nur, wenn es den Artikel schon gibt** – in eurer Sammlung
oder auf einer Einkaufsliste. Sonst gäbe es ja nichts, woran das Foto hängen
könnte. Die **Wunschliste zählt hier nicht**: Was ihr euch wünscht, habt ihr
gerade nicht.

> Praktisch, wenn man die Sammlung nach und nach bebildern will: Figur vor
> die Kamera, scannen, ein Tipp – fertig. Das grüne Schild **„✔ 1× in eurer
> Sammlung"** auf der Karte zeigt dabei gleich, dass ihr sie schon habt.

> **Die Fotos hängen am Artikel, nicht an der Zeile.** Wer dieselbe Figur
> zweimal besitzt – einmal neu, einmal gebraucht –, sieht bei beiden
> dieselben Fotos. Das ist Absicht: Es ist ja dieselbe Figur.
>
> Daraus folgt auch, wann sie **verschwinden**: Löscht ihr eine Zeile, bleiben
> die Fotos, solange den Artikel noch irgendetwas führt – die zweite Zeile,
> die Wunschliste, eine Einkaufsliste. Erst wenn er nirgends mehr auftaucht,
> werden Fotos und Dateien mit entfernt. Sie wären danach ohnehin durch
> nichts mehr erreichbar. Eine Aufnahme, die an mehreren Artikeln hängt,
> bleibt liegen, solange einer davon sie noch braucht.

> **Hochgeladen wird erst beim Anlegen.** Wer nur schaut, wer den Zustand
> wieder abbricht oder die Listenauswahl schließt, lädt nichts hoch – sonst
> lägen nach jedem Herumprobieren Bilder herum, die zu nichts gehören.
>
> Das Bild wird beim Empfang auf 800 px verkleinert und als JPEG abgelegt;
> das begrenzt den Platzbedarf und entfernt nebenbei die EXIF-Daten des
> Fotos, also auch den GPS-Ort.
>
> **Entfernen löst nur die Verbindung.** Die Datei bleibt liegen – sie kann
> an einem anderen Artikel hängen, und ein verwaistes Bild schadet weniger
> als ein verschwundenes.

Der geht immer: mit dem Finger (oder der Maus) einen **Rahmen um eine Figur
ziehen** und **🔍 Diesen Ausschnitt erkennen** antippen. Zugeschnitten wird
im Browser, zum Server geht nur der Ausschnitt.

> **Wie viele Figuren aufs Bild dürfen.** Je kleiner eine Figur im Foto ist,
> desto weniger bleibt von ihr übrig, wenn man sie herausschneidet – und
> genau dieser Ausschnitt geht zur Erkennung. Ein Regalfoto mit vierzig
> Figuren gibt jeder davon rund ein Fünfzigstel der Bildfläche; da kommt
> selten mehr als ein Rateergebnis heraus, und die Karte sagt das dann auch
> („nur mäßig sicher"). **Fünf bis zehn Figuren aus der Nähe** bringen
> deutlich mehr als vierzig aus zwei Metern. Ab Version 1.91.0 wird
> zugeschnitten aus einer Arbeitskopie mit 2400 Pixeln statt aus der
> Vorschau mit 1200 – jeder Ausschnitt hat damit die **vierfache Fläche**,
> gemessen an einem 12-Megapixel-Foto: 238×334 statt 120×168 Pixel. Das
> ersetzt die Nähe nicht, holt aber heraus, was im Foto steckt.

### 4.2 Per Suche (Katalog)

> **Deutsch eingetippt?** Findet der Katalog nichts und ist eine lokale
> KI eingerichtet (siehe 2.9), übersetzt die App den Begriff und fragt
> noch einmal nach. „Roter c3po" findet so den `C-3PO - Dark Red Arm`.
> Über den Treffern steht, wonach zusätzlich gesucht wurde.

Unter dem Kamerabereich liegt die Textsuche. Sie versteht:

- **Namen** („Shoretrooper", „TIE Striker") – via Rebrickable
- **Figurennummern** (`sw0815`, `col424`)
- **Setnummern** (`75154` oder `75154-1`)
- **Reine Zahlen** werden automatisch mehrgleisig nachgeschlagen – als Set
  *und* als Figur; die App zeigt, was sie findet.

Die Suche startet **ab drei Zeichen** – bei kürzerer Eingabe erscheint
ein kurzer Hinweis statt einer Anfrage. Der **Typ** (Minifigur/Teil/Set)
steht direkt neben dem Namensfeld, damit gezielt gesucht werden kann.

Gefunden werden **10 Treffer pro Seite**; darunter steht „X von Y
angezeigt" und ein Knopf **Weitere Ergebnisse laden**, der jeweils zehn
weitere anhängt – so lassen sich alle Treffer durchblättern.

**Detailansicht.** Ein Tipp auf einen Treffer – aus der Suche **wie aus dem
Scan** – öffnet ein Popup mit allem, was bekannt ist: Bild in groß, Jahr,
Thema, Ø-Preise neu/gebraucht, BrickLink-Link. Bei **Minifiguren** lässt
sich dort „Enthaltene Teile" aufklappen: jedes Teil mit Nummer, Anzahl und
**Farbnamen** – praktisch, um am Stand eine unvollständige Figur zu
beurteilen. Die Knöpfe zum Übernehmen sind dieselben wie auf der Karte.

### 4.3 Aktionen auf jeder Treffer-Karte

- **＋ Zur Sammlung** – fragt den **Zustand** (Gebraucht/Neu) ab und
  bietet ein optionales **„Bezahlt €"**-Feld: Wer den Kaufpreis schon
  kennt, trägt ihn gleich mit ein (er landet als Kaufpreis in der
  Sammlung). Ist der Artikel schon vorhanden, erhöht sich die Menge.
- **☆ Merken** – setzt ihn auf die Wunschliste (⭐-Badge erscheint).
- **🛒 Liste** *(nur Profi)* – legt ihn auf eine Einkaufsliste (siehe
  Kapitel 7): Im Dialog zuerst optional den **Zustand** wählen
  (Gebraucht/Neu, Gebraucht ist vorausgewählt), dann die Liste antippen –
  oder mit **„＋ Neue Liste"** direkt am Stand eine anlegen (Name
  „Flohmarkt <Datum>" ist vorbefüllt).

Die Treffer-Karten tragen außerdem Hinweis-Badges: **✔ n× in eurer
Sammlung**, **⭐ auf eurer Wunschliste** und **🛒 auf »Listenname«**, wenn
der Artikel bereits auf einer aktiven Einkaufsliste eingeplant ist – der
eingebaute Schutz vor Doppelkäufen und Doppel-Einplanung.

Gehört eine gefundene Figur zu einem **Set aus eurer Sammlung** und fehlt
dort noch, steht statt „📦 in Sets" deutlich in Rot: **🧩 fehlt zu eurem
Set: <Setname>**. Auf dem Flohmarkt seht ihr damit sofort, ob ein Fund
eine Lücke schließt. Besitzt ihr die Figur bereits, bleibt es beim
normalen Hinweis „in Sets".

### 4.4 Manuell erfassen

Für alles, was keine BrickLink-Nummer hat (Eigenbauten, Konvolute):
**✏️ Manuell erfassen** mit freiem Namen, eigener Nummer, Typ, Menge,
Zustand, optionalem **„Bezahlt €"** (Kaufpreis) und Notizen. Solche
Einträge bekommen keine automatischen Marktpreise – der eingetragene
Kaufpreis und die Notizen funktionieren normal.

Beim Tippen des Namens schlägt die App parallel Katalogtreffer vor; passt
einer, übernimmt ein Tipp Nummer und Bild.

*(Profi)* **„🛒 Auf eine Liste"** legt den Eintrag direkt auf eine
Einkaufsliste – auch für Eigenbauten, die in keinem Katalog stehen.

### 4.5 Eigene Figuren (Custom)

Der Schalter **„🎨 Eigene Figur (Custom)"** im manuellen Formular ist für
Eigenbauten gedacht:

- Die **Nummer vergibt die App fortlaufend** (`custom-001`, `-002`, …),
  überschreibbar, wenn ihr ein eigenes Schema führt.
- **Eigenes Bild**: hochladen – oder, wenn beim Scannen nichts erkannt
  wurde, mit **„📷 Foto vom Scan verwenden"** direkt das eben gemachte
  Foto nehmen. Auf der Scan-Seite gibt es dafür auch den Knopf
  **„🎨 Eigene Figur mit diesem Foto"**.
- Custom-Figuren werden **nicht** bei BrickLink gesucht; Preise und
  Katalogbilder gibt es dafür nicht.
- In der Sammlung stehen sie unter dem Thema **„Custom"**.
- Im Tausch-Netzwerk reist ihr Bild verkleinert mit (siehe Kapitel 12).

---

## 5. Die Sammlung

### 5.1 Überblick & Filter

Der Tab **Sammlung** zeigt alle Artikel als Karten. Oben: Volltextsuche
(mit 🔍-Symbol im Feld und **✕ zum Leeren**), Sortierung (Neueste, Name,
Wert …) und der Typ-Filter (Alle / Figuren / Sets). Die Kennzahlen-Widgets
(Stückzahl, Gesamtwert) beziehen sich immer auf den aktuellen Filter.

Während die Sammlung lädt, dreht sich ein **Klemmbaustein** mit dem
Hinweis „Sammlung wird geladen …" – die Suchleiste ist dabei schon
benutzbar. Damit große Sammlungen zügig öffnen, bauen die Karten zunächst
nur ihren Kopf auf; der Detailbereich entsteht erst beim Aufklappen.

**Die Liste kommt blockweise.** Beim Öffnen stehen die ersten 60 Karten da,
der Rest kommt beim Scrollen nach – man merkt es nicht, es sei denn, man
springt mit der Bildlaufleiste ans Ende. Bei 815 Einträgen sind das beim
Öffnen rund 2.000 Elemente statt 14.700. Verlässt man den Tab, gibt die
Sammlung ihren Platz wieder frei und baut sich beim Zurückkommen neu auf;
die Daten bleiben so lange im Speicher. Findet die Suche nichts, steht das
auch da – samt Knopf, der die Filter räumt.

**Deutsch suchen, englisch finden.** Die Namen in der Sammlung kommen von
BrickLink und sind englisch. Wer „Ritter" eintippte, bekam deshalb eine leere
Liste, obwohl die Figur als „Castle Knight" in der Datenbank steht – dasselbe
galt für „Kopf" (Head), „Schwert" (Sword) oder „Piraten" (Pirate). Ist eine
**lokale KI eingerichtet** (siehe 2.9), übersetzt die App in genau diesem Fall
den Suchbegriff und sucht erneut. Über den Treffern steht dann, wonach
zusätzlich gesucht wurde.

Auch Schreibweisen sind egal: BrickLink führt `C-3PO` und `R2-D2` mit
Bindestrich, „c3 po" oder „r2d2" finden sie trotzdem. Nennt man eine
Eigenschaft – „roter c3 po" –, steht der passende zuerst und die übrigen
C-3POs darunter.

**Auch beim Erfassen.** Dasselbe gilt im Feld **Name** unter „✏️ Manuell
erfassen", das im Katalog sucht. Dort hilft es sogar mehr: In der eigenen
Sammlung kann man notfalls blättern, im Katalog sucht man etwas Unbekanntes –
ohne Treffer hat man gar nichts. Findet der Katalog nichts, übersetzt die App
und fragt mit den zwei genauesten Begriffen noch einmal nach; darüber steht
dann, wonach gesucht wurde. Mehr als zwei sind es bewusst nicht: Jeder Versuch
ist eine eigene Anfrage an Rebrickable.

Wichtig zu wissen: **Die KI liefert nur Suchbegriffe, niemals Ergebnisse.**
Jede angezeigte Karte kommt weiter aus der eigenen Datenbank – die Funktion
kann keine Figur anzeigen, die es in der Sammlung nicht gibt. Ohne
eingerichtete KI bleibt es beim gewohnten Hinweis „Nichts gefunden".

**Sortierung nach Thema.** Wählt man bei der Sortierung „Thema", zeigt die
Sammlung **aufklappbare Themenkarten** – Star Wars, City, Harry Potter,
Custom, „Ohne Thema" – jeweils mit Anzahl und Wert. Das Thema leitet die
App bei Minifiguren aus dem Nummernpräfix ab (`sw…` → Star Wars) und holt
es bei Sets von BrickLink; unter *Mehr* lässt es sich für Bestandsdaten
nachziehen.

> **Wenn BrickLink schweigt:** Die Kategorie-ID eines Sets taucht nicht
> immer in BrickLinks Kategorieliste auf – dann bleibt die Kette gleich am
> ersten Glied stehen, und das Set landet unter „Ohne Thema", obwohl es
> dort eindeutig gelistet ist. In diesem Fall fragt die App die **Figuren
> im Set**: Stecken dort `sw…`-Nummern, ist es Star Wars. Es zählt, was am
> häufigsten vorkommt. Voraussetzung ist, dass die Set-Inhalte schon
> geladen wurden – das passiert beim Erfassen von selbst.

**Teile und ihr Thema.** Bei Teilen fragt „🔄 Themen nachladen" den Katalog
in zwei Stufen ab:

1. **Zweitnummer.** Bedruckte Teile tragen bei BrickLink oft die Nummer der
   Figur, zu der sie gehören. Beim Karbonitblock mit Han Solo steht `sw0978`
   daneben – und `sw…` heißt Star Wars. Das ist ein **echtes Thema** und hat
   deshalb Vorrang.
2. **Katalogpfad.** Hat ein Teil keine Zweitnummer – der Gungan-Schild
   `2586ps1` etwa steht dort ohne –, zählt die Kategorie: aus
   *Catalog: Parts: Minifigure, Shield* wird das Thema **„Minifigure,
   Shield"**. Das ist eine Form und kein Thema im engeren Sinn, sortiert den
   Eintrag aber sinnvoll ein statt ihn unter „Ohne Thema" liegen zu lassen.
   Wem das nicht passt, setzt auf der Karte von Hand „Star Wars" – von Hand
   Gesetztes bleibt stehen.

> **Zwei Kataloge, zwei Nummern.** Rebrickable nennt dieselben Teile
> `87561pr0001` und `2586pr0028`, BrickLink `87561pb01` und `2586ps1`. Wer mit
> der einen Nummer beim anderen anfragt, bekommt **gar nichts** – weder
> Zweitnummer noch Kategorie. Die App klärt die Nummer deshalb **einmal** über
> Rebrickable und verwendet sie danach für beide Wege. Dafür braucht es beide
> Schlüssel.

Bleibt danach etwas übrig – ein schlichter Stein etwa hat keine
Figurennummer –, steht in den Karten-Details ein Feld **Thema**: eintippen
(die Vorschlagsliste kennt alle Themen, die du schon hast), **Setzen** –
fertig. Leeren stellt „Ohne Thema" wieder her.

**Hat die Automatik eins gefunden, steht seit 2.14.0 nur das Thema da** –
Feld und Knopf für etwas, das längst richtig ausgefüllt ist, wären zwei
Zeilen zu viel. Der **✏️** daneben holt sie zurück, wenn doch etwas falsch
einsortiert ist. Ein von Hand gesetztes Thema bleibt stehen; die Automatik
überschreibt nie eins, das schon da ist.

> Der Wert einer Themenkarte rechnet Figuren, die in euren eigenen Sets
> stecken, nur anteilig mit – genau wie die Gesamtsumme oben. Sonst läge
> die Summe der Karten über dem Gesamtwert.

**Die zuletzt gewählte Sortierung merkt sich das Profil** – sie gilt beim
nächsten Öffnen wieder, auch auf einem anderen Gerät. Der Standard lässt
sich unter *Mehr → Sortierung der Sammlung* festlegen.

Über den **Ansichts-Umschalter** rechts neben den Filtern (Symbol plus
Beschriftung auf breiten Schirmen) wechselt man zwischen **Listenansicht**
und **Raster** (mehrere Figuren pro Reihe, kompakt, mit Mengen-Badge in der
Ecke); der Knopf zeigt, in welche Ansicht man wechselt, und die Wahl wird
pro Gerät gemerkt. In der Liste schimmert das **Produktbild** zudem als
dezenter Hintergrund in die Karte. Zwei Karten einer Reihe sind immer
**gleich hoch**, auch wenn ein Name umbricht.

### 5.2 Die Karten-Details

Ein Tipp auf eine Karte öffnet die Details als **Popup** – ein mittiges
Fenster über der Liste, auf dem Handy fast bildschirmfüllend. Schließen
per **✕**, Klick daneben oder **Esc**; Änderungen sind sofort gespeichert
und stehen nach dem Schließen auch in der Liste.

**Der Steckbrief ist in vier Abschnitte geteilt** (ab 2.69.0), weil er über
die Zeit auf zehn Blöcke angewachsen war:

| Abschnitt | Inhalt |
|---|---|
| **Mein Exemplar** | Anzahl, Zustand, Kaufpreis, Tauschbörse |
| **Einordnung** | Notizen (und das Themenfeld, falls nötig) |
| **Nachschlagen** | Preisverlauf, BrickLink, enthaltene Teile/Figuren |
| **Marktpreise** | die Ø-Preise samt ↻ |

Beschriftung steht links, Inhalt rechts – nur die Notizen bekommen die
volle Breite. Ein Abschnitt ohne Inhalt wird gar nicht gezeichnet: Ohne
BrickLink-Zugang steht keine Überschrift „Marktpreise" über einer leeren
Fläche.

**Das Thema steht oben im Kopf**, gleich unter Nummer und Zustand – es
gehört zur Figur, nicht zu dem, was ihr mit ihr macht. Einen **✏️** gibt es
dort nur, wo die App das Thema nicht aus der Nummer ableiten kann: bei
eigenen Figuren, Teilen und unbekannten Kürzeln. `sw1213` ist Star Wars, da
gibt es nichts zu entscheiden.

Im Popup zeigt sich:

- **Menge** (± Stepper) und **Zustand** (Gebraucht/Neu) – Änderungen
  greifen sofort, ohne die Karte zu schließen. **Neu und Gebraucht sind
  getrennte Einträge**: Dieselbe Figur kann einmal neu und einmal
  gebraucht in der Sammlung stehen, jeweils mit eigener Menge, eigenem
  Kaufpreis und zustandsgerechtem Wert. Wechselt man den Zustand eines
  Eintrags auf einen bereits vorhandenen, führt die App beide zusammen
  (Mengen und Kaufpreise werden addiert).
- **Kaufpreis** *(Sammlerprofi)* – einfach eintippen; er speichert sich
  beim Verlassen des Feldes (oder mit Enter) von selbst.
- **Notizen** – Freitext, z. B. Herkunft oder Besonderheiten; speichern
  sich automatisch kurz nach dem Tippen (ein „✓ gespeichert" bestätigt).
- **Preise**: aktuelle Ø-Werte (neu/gebraucht); das **↻** am Preisblock
  „Marktpreise" holt sie sofort neu, der **Preisverlauf** zeigt sie als
  Chart (blau = neu, grün = gebraucht) mit Link zur BrickLink-Preisseite.
- **Bild antippen** öffnet die Großansicht. Der Hinweis „Wischen zum
  Blättern" erscheint nur, wenn es wirklich mehr als ein Bild gibt – in
  aller Regel also erst, wenn ihr ein eigenes Foto dazugehängt habt.
- **ⓘ neben dem Namen** (nur Star Wars, und nur wenn eingeschaltet unter
  *Mehr → 📖 Jedipedia-Verweis*) schlägt die Figur im deutschen
  Star-Wars-Wiki nach. Gesucht wird, nicht direkt verlinkt: Der Katalog ist
  englisch, das Wiki deutsch – „Battle Droid" heißt dort „Kampfdroide".
- **Löschen** über den **Papierkorb bei der Anzahl** (erscheint, sobald
  nur noch eines übrig ist) – mit Sicherheitsabfrage.

#### Bild fehlt oder passt nicht?

Unten rechts am Bild sitzt ein kleines **↻-Symbol**. Es holt das aktuelle
Katalogbild von BrickLink und speichert es dauerhaft – praktisch bei
Einträgen, die ohne Bild in die Sammlung gekommen sind (etwa über den
CSV-Import).

*(Voraussetzung: hinterlegter BrickLink-Schlüssel.)*

### 5.3 Dieselbe Nummer, zweimal erfasst

Auf der Packung steht **21306**, BrickLink führt dasselbe Set als
**21306-1**. Wer eines von Hand einträgt und das andere scannt, hat zwei
Zeilen für ein Set – und die Sammlung zählt es doppelt.

Die App merkt das und legt einen Hinweis auf die **Scan-Seite**:

> 🔔 **Dasselbe Set zweimal erfasst?**
> „The Beatles Yellow Submarine" ist als 21306 und als 21306-1 in der
> Sammlung – bei BrickLink ist das dieselbe Nummer, die Endung gehört dort
> dazu. **Zusammenführen?** [ Ein Exemplar ] [ Zwei Exemplare ]

- **Ein Exemplar** – derselbe Kasten, zweimal erfasst. Es bleibt eine Zeile
  mit der Stückzahl der BrickLink-Nummer; das Kaufbuch der aufgegebenen
  Zeile fällt weg, sonst stünde der Betrag doppelt drin.
- **Zwei Exemplare** – ihr besitzt wirklich zwei. Die Stückzahlen werden
  addiert und beide Käufe stehen danach im Kaufbuch.

Bleiben darf die Zeile mit der **BrickLink-Nummer**: Sie hat Preise,
Set-Inhalte und passt zum Katalog – **samt ihres Namens**. Der aus dem
Katalog gilt, nicht der selbst getippte.

**Vorbeugen statt aufräumen.** Beim **manuellen Erfassen** eines Sets ergänzt
die App die Endung gleich selbst: Wer `21306` eintippt, bekommt `21306-1` –
und landet damit sofort in derselben Zeile wie ein gescanntes Exemplar. Sind
die BrickLink-Schlüssel hinterlegt, wird zusätzlich der **Katalogname**
übernommen; ohne Schlüssel bleibt der eingetippte stehen. Das gilt auch für
die Wunschliste und den CSV-Import.

> Angefasst wird nur, was eindeutig ist: eine reine Zahl bei einem **Set**.
> Figurennummern (`sw0312`), Teilenummern, eigene Nummern (`manuell-…`) und
> alles, was schon eine Endung hat, bleibt unverändert.

> **Wo sich die App heraushält:** Bei zwei echten Varianten – etwa `21306-1`
> und `21306-2` – kommt kein Hinweis. Dort sind es zwei verschiedene
> Ausgaben, und welche gemeint ist, weiß nur ihr.

### 5.4 Sets und ihre Figuren

Brickfolio kennt die Figuren-Inventare eurer Sets (via BrickLink,
automatisch geladen):

- Die Set-Karte zeigt in der Infozeile dezent **„👥 3/4"** – drei der vier
  enthaltenen Figuren sind in der Sammlung, bei Vollständigkeit steht
  „👥 4/4 ✔".
- In den Set-Details listet **„👥 Enthaltene Figuren"** alle Figuren mit
  Besitz-Badges; fehlende lassen sich mit einem Knopf **gesammelt auf die
  Wunschliste** setzen.
- Umgekehrt zeigen Figuren-Karten **„📦 aus euren Sets"** mit Sprung zur
  jeweiligen Set-Karte.
- In den Figuren-Details (Suche wie Sammlung) sind Sets aus **eurer
  Sammlung** als **gelbe Chips mit ✔** gekennzeichnet und springen zur
  Set-Karte; Sets, die ihr nicht besitzt, erscheinen als blaue
  BrickLink-Links.

### 5.5 Kaufpreise & Gewinn *(Sammlerprofi)*

Jeder Eintrag führt einen **Kaufpreis** (Gesamtbetrag der Position):

- **⚙️ automatisch**: Ohne manuelle Eingabe setzt die App den
  BrickLink-Ø-Preis vom Erfassungstag ein (passend zum Zustand). Der
  Tooltip nennt das Datum.
- **✏️ manuell**: Über das kompakte Feld „Bezahlt [Betrag] €" jederzeit
  überschreibbar (Komma-Eingabe wie „12,50"). Manuelle Werte werden von
  keiner Automatik mehr angetastet.
- Kommen weitere Exemplare hinzu (Scan-Merge, „Gekauft" von der
  Wunschliste), erhöht sich der Kaufpreis um den jeweiligen Tages- bzw.
  angegebenen Wert.

**Mehrere Käufe zum selben Artikel.** Dasselbe Set einmal bei LEGO für
39,99 € und einmal im Markt für 34,99 €: In der Sammlung ist das **eine**
Zeile mit Stückzahl 2 – Nummer, Typ und Zustand sind eindeutig. Die Summe
stimmte immer, aber welcher Kauf welcher war, ließ sich nicht mehr sagen.

Deshalb steht unter der Gewinnzeile ein **Kaufbuch**:

| | | |
| --- | --- | --- |
| 1× | 39,99 € | LEGO Store · 14.6.2026 |
| 1× | 34,99 € | MediaMarkt · 2.7.2026 |

Das **＋** am Ende der Bezahlt-Zeile öffnet ein kleines Fenster: Gesamtpreis
dieses Kaufs, Stückzahl und wahlweise die Quelle – alles auf einmal. Die
Stückzahl des Eintrags wächst mit. Das **✕** nimmt einen Kauf zurück, ebenfalls samt Stückzahl. Die
Aufstellung erscheint erst ab dem zweiten Posten – bei einem einzigen sagt
sie nichts, was nicht schon oben steht. Für Figuren gilt dasselbe wie für
Sets.

> Oben im Feld „Bezahlt" steht weiterhin die **Summe**, und mit ihr rechnen
> Statistik, Gewinn und die Einkaufslisten. Wer dort von Hand einen Betrag
> einträgt, meint den ganzen Posten – das Kaufbuch wird dann auf diesen
> einen Eintrag zurückgesetzt, damit Summe und Aufstellung nicht
> auseinanderlaufen.

Darunter rechnet die **Gewinnzeile** live: *Wert 47,60 € · **+35,10 €***
(grün = Gewinn, rot = Verlust; Wert = aktueller Ø-Preis × Menge). Den
bezahlten Betrag wiederholt sie nicht – der steht eine Zeile darüber im
Feld. Ohne Marktpreis bleibt die Zeile weg.

---

## 6. Die Wunschliste

**Wo sie liegt:** Wünsche, Einkaufslisten und Archiv teilen sich seit 1.62.0
den Tab **Listen** – drei Reiter über der Ansicht:

| Reiter | Inhalt | Sichtbar |
|---|---|---|
| ⭐ **Wünsche** | alles Gemerkte | immer |
| 🛒 **Einkaufen** | aktive Einkaufslisten, Verkaufsliste, fehlende Set-Figuren | wenn es Listen gibt oder ihr Profi seid |
| 📦 **Archiv** | abgearbeitete Listen | ebenso |
| 📚 **Katalog** | alle Figuren eines Themas zum Durchblättern | immer |

Vorher waren das zwei Einträge in der Leiste für dieselbe Frage – *was will
ich noch, was nehme ich mit?* –, und das Archiv war ein Knopf, der dieselben
Karten mit einem anderen Symbol zeigte. Jetzt ist es ein eigener Bereich, und
archivierte Listen sind auch gedämpft dargestellt.

Der Reiter **⭐ Wünsche** sammelt alles Gemerkte – mit Bild, Ø-Preisen und
Widgets, die die geschätzten Anschaffungskosten (gebraucht/neu) summieren.

- **✔ Gekauft!** fragt den Zustand ab und verschiebt den Artikel in die
  Sammlung. *Profis* können dabei den echten Kaufpreis eintragen (leer =
  BrickLink-Ø, automatisch ⚙️).
- **Nummer korrigieren:** In den Details lässt sich eine falsche Nummer
  ersetzen („Setzen") oder automatisch suchen („🔍 Auto") – die Preise
  werden danach sofort neu geholt.
- Artikel, die ihr schon besitzt, tragen ein Besitz-Badge – praktisch
  gegen Doppelkäufe.
- Ein Tipp auf **Name oder Nummer** öffnet den **Steckbrief** (siehe unten).
- Steht ein Wunsch schon auf einer **offenen Einkaufsliste**, trägt die
  Karte den blauen Vermerk **🛒 auf Einkaufsliste: <Listenname>** – dann
  ist er unterwegs und niemand muss ihn ein zweites Mal besorgen. Mehrere
  Listen werden alle genannt, mit zusammengezählter Stückzahl. Abgehakte
  Posten und archivierte Listen zählen nicht mehr mit.
- Gehört eine gemerkte Figur zu einem **Set aus eurer Sammlung** und fehlt
  dort noch, steht auf der Karte **🧩 fehlt zu eurem Set: <Setname>**. Ein
  Tipp auf das Set springt direkt dorthin in die Sammlung.

### 6.1 Der Steckbrief

Überall, wo eine Figur oder ein Teil nur als **Zeile** auftaucht, führt ein
Tipp auf Name oder Nummer zum **Steckbrief**. Das gilt

- unter einem Set in eurer Sammlung („👥 Enthaltene Figuren anzeigen"),
- in der Teileliste einer Figur („🧩 Enthaltene Teile anzeigen"),
- bei den **fehlenden Set-Figuren**,
- auf der **Wunschliste** und den **Einkaufslisten**,
- in der Statistik (Spitzenreiter) und bei den **Doppelten**.

Er beantwortet die Frage, die man an dieser Stelle hat:

| Zeile | Was sie sagt |
|---|---|
| Bild und Nummer | welche Variante genau, mit Erscheinungsjahr |
| 🟢 ✔ *n*× in eurer Sammlung | habt ihr |
| 🔵 🛒 <Listenname> | liegt schon im Einkaufskorb |
| 🟡 ⭐ auf eurer Wunschliste | wollt ihr |
| „noch nirgends erfasst" | kennt die App noch gar nicht |
| 💶 Marktpreis | Ø neu und Ø gebraucht |
| 📦 Steckt in diesen Sets | eure Sets zuerst und anklickbar, danach die übrigen bei BrickLink |

Unten stehen **＋ Sammlung**, **☆ Merken** (fällt weg, wenn die Figur schon
auf der Wunschliste liegt) und **BrickLink ↗**.

Ein Tipp **neben** den Steckbrief schließt ihn wieder, ebenso ✕ und die
Escape-Taste. Das Bild darin öffnet weiterhin die **Galerie** – Escape
schließt dann erst das Bild und beim zweiten Druck den Steckbrief.

> **Knöpfe bleiben Knöpfe.** In den Zeilen mit ＋ Sammlung und ☆ Merken
> lösen diese weiterhin ihre eigene Aufgabe aus, nicht den Steckbrief.

---

### 6.2 📚 Katalog durchblättern (ab 2.59.0)

Die Suche beantwortet *„wo ist X?"*. Dieser Reiter beantwortet die andere
Frage: **„was gibt es überhaupt, und was davon fehlt mir?"**

Oben wählt ihr ein **Thema** – Star Wars, City, Ninjago … – und ob ihr
Figuren oder Sets sehen wollt. Daneben steht, wie viele davon ihr schon
habt: *Star Wars · 225/1663*. Darunter läuft die vollständige Liste des
Themas in **Nummernfolge**, nicht alphabetisch. Das ist Absicht: So stehen
Varianten beieinander (sw0001a bis sw0001d), und das Jahr wächst von oben
nach unten.

**Rechts am Rand liegt ein Sprungbalken.** Oben steht das Kürzel des
Themas, darunter die Hunderterblöcke: **SW** über **12** heißt `sw12xx`. Ein
Tipp darauf springt dorthin – bei 1.663 Star-Wars-Figuren ist das der
Unterschied zwischen Suchen und Finden. Der gerade sichtbare Block ist rot
markiert und zieht beim Scrollen mit.

Ein paar Themen laufen bei BrickLink unter **mehreren Kürzeln** – Belville
etwa unter vier (`belvbaby`, `belvfairy`, `belvfemale`, `belvmale`). Sie
stehen trotzdem als *ein* Thema in der Auswahl; der Sprungbalken zeigt dann
die Kürzel statt der Ziffern: BABY, FAIRY, FEMALE, MALE.

Und einmal ist es umgekehrt: **`cc` trägt zwei Themen.** `cc4058` ff. sind
Studios-Figuren, `cc4443` ff. die Coca-Cola-Fußballer der WM 2002. Die
beiden stehen getrennt in der Auswahl.

**Der runde Pfeil unten rechts** bringt euch in einem Schritt zurück an den
Anfang. Er erscheint, sobald ihr zwei Bildschirmhöhen weit unten seid – und
zwar in *jeder* langen Liste, nicht nur hier.

**Antippen:**

| Ihr tippt auf … | … dann passiert |
|---|---|
| **✔** | die Figur wandert in eure Sammlung (Stück 1, gebraucht) |
| **♥** | die Figur kommt auf die Wunschliste |
| **den Namen** | ein Steckbrief mit großem Bild und denselben zwei Knöpfen |

Der Haken lässt sich auch wieder ausschalten – aber **nur, wenn nichts
daran hängt.** Habt ihr die Figur mehrfach, oder steht eine Notiz oder ein
Kaufpreis daran, sagt die App das und rührt den Eintrag nicht an: Ein
Fehltipper auf einem daumengroßen Knopf darf keine Daten wegräumen. Löschen
geht dann in der Sammlung selbst.

**Die Themenauswahl aufräumen:** Bei 199 Themen ist die Liste lang, und
die meisten braucht ihr nie. Unter **Mehr → 📚 Katalog-Themen** bekommt
jedes Thema zwei Schalter:

| | |
|---|---|
| **★** | Favorit – steht in der Auswahl ganz oben, egal wie klein |
| **☑ / ☐** | ob es überhaupt in der Auswahl erscheint |

Der bequemste Weg: ein paar Sterne setzen, dann **★ Nur Favoriten** – das
blendet alles andere aus. **Alle einblenden** holt sie zurück. Beides gilt
nur für euch; Paul kann eine ganz andere Auswahl haben als Sven.

Der Stern überlebt das Ausblenden: Wer ein Thema wieder einschaltet, findet
seine Markierung, wo er sie gelassen hat.

**Die vier Filter** darüber grenzen ein: *Alle*, *Fehlt mir* (was noch
aussteht), *Hab ich*, *Gemerkt*. „Fehlt mir" ist die Einkaufsliste für ein
ganzes Thema.

**Auch Sets** stehen im Katalog, sobald jemand BrickLinks `Sets.xml`
eingelesen hat (*Mehr → Katalog → Katalogdatei einlesen*). Dafür braucht es
einen zweiten Schritt: **Kategorien holen** auf derselben Seite.

Der Grund: Figuren tragen ihr Thema in der Nummer – `sw1213` ist Star Wars.
Sets nicht: `75192-1` sagt nichts. Deren Thema steht allein in der
BrickLink-Kategorie, und die kommt als **Nummer**. Ein einziger Abruf holt
den Kategoriebaum; danach stehen Sets unter „Star Wars" statt unter einer
Ziffer. Ohne ihn bleibt das Thema leer – lieber gar keines als ein
geratenes.

**Wenn statt des Namens die Nummer steht** („sw0023a · Name folgt"), ist die
Figur im Katalog, ihr Name aber noch nicht nachgeschlagen. Der veröffentlichte
Abzug enthält **keine Namen** – die sind BrickLinks Katalogtext, und den
verteilen wir nicht weiter. Jede Instanz schlägt sie über ihren eigenen
BrickLink-Zugang nach. Das Bild und die Bildbeschreibung sind trotzdem da,
gefunden wird die Figur also auch ohne Namen.

**Zur Technik, für die Neugierigen:** In der Liste stehen alle Zeilen eines
Themas, aber **geladen sind nur die Bilder in Sichtweite** – bei 1.663
Zeilen sind das rund 26. Entpackte Bilder liegen außerhalb des
JavaScript-Speichers, und zu viele davon haben in der Sammlung wiederholt den
Browser-Tab umgebracht. Hier lädt ein Beobachter das Bild erst, wenn die
Zeile in die Nähe kommt.


## 7. Einkaufslisten – der Flohmarkt-Modus

Das Herzstück für Sammlerprofis: strukturiert einkaufen mit
Marktwert-Wissen. Standard-Benutzer sehen aktive Listen und dürfen
angekommene Artikel verbuchen; alles andere ist Profi-Sache.

> **Die Ansicht hält sich von selbst aktuell.** Alle fünf Sekunden fragt
> Brickfolio nach, ob sich an den Daten etwas geändert hat – und lädt die
> offene Ansicht **nur dann** neu. Legt also ein Familienmitglied am Handy
> etwas auf eine Liste, oder ein Werkzeug an der Schnittstelle, steht es
> Sekunden später da. Ohne Neuladen, ohne Fensterwechsel, und ohne dass die
> Liste dabei zuklappt.
>
> Abgefragt wird dabei kein Datenbestand, sondern ein **Fingerabdruck**: eine
> Handvoll Zahlen. Erst wenn der sich ändert, wird wirklich geladen.
>
> Der **Scannen-Tab bleibt ausgenommen** – dort steht womöglich ein Foto samt
> Treffern, und das darf nichts wegräumen. Ein Tab im Hintergrund fragt gar
> nicht erst. Und zusätzlich frischt die App auf, wenn ihr nach ein paar
> Sekunden aus einem anderen Fenster zurückkommt.

### 7.1 Der typische Ablauf am Stand

**1. Liste anlegen.** Entweder im Tab **Listen** („Neue Einkaufsliste …")
– oder direkt beim Scannen: Der **🛒 Liste**-Knopf bietet immer auch
**„＋ Neue Liste"** an, mit vorausgefülltem Namen wie „Flohmarkt 09.07.".
Zwei Tipps, und die Liste existiert samt erstem Artikel.

**2. Kiste durchscannen.** Jeden interessanten Fund per 🛒 auf die Liste
legen – den **Zustand** wählt ihr direkt im Dialog (Gebraucht ist
vorausgewählt), und wer den Preis schon kennt (Preisschild am Stand),
trägt ihn optional gleich im Feld **„Einkauf €"** mit ein – er landet als
Einkaufspreis am Listen-Artikel. Nachträglich geht beides am
Listen-Artikel selbst (gelber Umschalter bzw. Einkauf-Feld). Gleicher Artikel im gleichen Zustand nochmal = Menge
erhöht sich; **unterschiedliche Zustände sind getrennte Zeilen** mit
eigenen Marktwerten. Alles rechnet zustandsgerecht.

**3. Marktwert ablesen.** Die Listen-Kopfzeile zeigt laufend:
*„7 Artikel · 7 offen · Marktwert ca. 86,40 € (je Zustand)"* – deine
Verhandlungsbasis, ohne dass der Verkäufer etwas davon mitbekommt.

**4. Angebot machen: 💰 Gesamtangebot.** Der Dialog zeigt den
Ø-Marktwert aller offenen Artikel und einen **roten Preisvorschlag**
(standardmäßig 60 % des Marktwerts – antippen übernimmt ihn ins Feld;
der Prozentsatz ist unter Mehr → 💼 Sammlerprofi einstellbar). Nach der
Einigung den Endpreis eintragen und **„Verteilen"** drücken:

> **Die Verteilungs-Mathematik:** Der Gesamtpreis wird anteilig nach
> Marktwert auf die offenen Artikel umgelegt. Beispiel: Kiste für 40 €,
> enthalten sind Figuren im Wert von 60 / 30 / 10 € → Anteile 24 / 12 /
> 4 €. Artikel **ohne** BrickLink-Preis erhalten den Durchschnittsanteil
> der übrigen; Rundungsreste gleicht der letzte Artikel aus, sodass die
> Summe exakt stimmt. Das Angebot lässt sich beliebig oft neu verteilen,
> einzelne Preise bleiben von Hand korrigierbar („Einkauf … € ✓").

**5. Zu Hause verbuchen.** Wenn die Funde ankommen bzw. sortiert werden,
tippt **irgendjemand** (auch ohne Profi-Rolle) auf **„✔ Da! Ab in die
Sammlung"**. Zustand bestätigen (der gespeicherte ist mit ✓ markiert),
Profis können den Preis nochmal anpassen – vorausgefüllt ist der
Listen-Einkaufspreis. Verbuchte Artikel werden **ausgegraut** mit Vermerk
*„✔ in Sammlung von Finn am 09.07.2026"*. In die **Notizen** des
Sammlungs-Eintrags schreibt die App automatisch, von welcher Liste der
Artikel stammt (z. B. *„Von Liste »Flohmarkt Riem« (09.07.2026)"*) –
eine vorhandene Notiz bleibt erhalten, der Hinweis wird angehängt.

### 7.2 Wenn der Artikel schon in der Sammlung ist

Beim Verbuchen eines bereits vorhandenen Artikels fragt die App:

- **＋ Zusätzlich** – Menge erhöht sich; als Kaufpreis wird der
  **Durchschnitt** aus bisherigem und neuem Preis eingetragen.
- **Überschreiben** – der Sammlung-Eintrag wird komplett ersetzt
  (Anzahl, Zustand, Name, Kaufpreis des Listen-Artikels).

### 7.3 Kaufpreis-Prioritäten beim Verbuchen

1. Im Verbuchen-Dialog eingetragener Preis *(Profi)* → ✏️ manuell
2. Am Listen-Artikel hinterlegter Einkaufspreis → ✏️ manuell
3. BrickLink-Ø des gewählten Zustands → ⚙️ automatisch

### 7.4 Archiv

Ist der **letzte** Artikel verbucht, wandert die Liste automatisch ins
**Archiv** 🎉 – den dritten Reiter im Listen-Tab. Nur Profis können Listen
reaktivieren, von Hand archivieren oder löschen – und Verbuchungen
**rückgängig** machen (↩︎; der Sammlung-Eintrag bleibt dabei bewusst
bestehen und wird bei Bedarf manuell angepasst).

---

## 8. Die Verkaufsliste (Doppelte)

*(Nur Sammlerprofi – Knopf „📋 Verkaufsliste (Doppelte)" unter
**Listen → 🛒 Einkaufen**.)*

Auf Knopfdruck erzeugt Brickfolio die Liste aller mehrfach vorhandenen
Artikel – live berechnet, keine Pflege nötig. Die Grundregel:

> **„So viele Figuren bleiben, wie eure Sets brauchen – mindestens
> aber eine."**

Gibt es eine Figur in beiden Zuständen, wird der Behalten-Anteil
bevorzugt auf die **neuen** Exemplare angerechnet – abgebbar sind zuerst
die gebrauchten.

In der Zeile steht, **warum** etwas zurückbleibt: Wird die Figur für
eigene Sets gebraucht, erscheint „*N× für Sets reserviert*". Steckt sie
in keinem eurer Sets, bleibt nur das eine Behalte-Exemplar – dann steht
schlicht „*1 behalten*".

Konkret: Für jede Figur wird der **Set-Bedarf** ermittelt (Inventar-Menge
× Anzahl des Sets in eurer Sammlung). Abgebbar ist nur, was über
`max(Set-Bedarf, 1)` hinausgeht. Beispiele:

| vorhanden | in Sets benötigt | bleibt | abgebbar |
|:-:|:-:|:-:|:-:|
| 3× | 2× | 2 | **1×** |
| 2× | 0× | 1 | **1×** |
| 2× | 2× | 2 | *erscheint nicht* |
| 5× | 3× | 3 | **2×** |

Jede Zeile zeigt Zustand, „n× vorhanden (m× für Sets reserviert) → x×
abgebbar", den zustandsgerechten Ø-Stückpreis und den Verkaufswert; oben
stehen die Summen. **„Als CSV"** exportiert für die eigene Kalkulation,
**„Drucken"** erzeugt eine aufgeräumte Preisliste für den Stand. Doppelte
**Sets** selbst sind normal abgebbar – die Reservierung schützt die
Figuren *für* die Sets, nicht die Sets.

### 8.1 Fehlende Set-Figuren

Das Gegenstück zur Verkaufsliste sitzt daneben: **🧩 Fehlende
Set-Figuren** zeigt über **alle eigenen Sets hinweg**, welche Minifiguren
noch fehlen.

Oben steht die Zusammenfassung („6 Figuren fehlen in 2 von 5 Sets ·
Nachkauf ca. 14,24 €"), darunter je Figur:

- Bild, Name und Nummer
- **„3× fehlt (1 von 4 da)"** – der Bedarf berücksichtigt, **wie oft ihr
  ein Set besitzt**: Zwei TIE Fighter mit je zwei Piloten ergeben Bedarf 4
- **📦 für:** die Sets, die sie brauchen – antippbar, springt zum Set
- Ø-Preis, sofern bekannt (aus der Wunschliste oder dem Preisverlauf)
- **☆ Merken** bzw. der Hinweis „⭐ auf der Wunschliste"

Unten: **☆ Alle auf die Wunschliste**, **Als CSV** und **Drucken** – die
fertige Einkaufsliste zum Vervollständigen.

> **Namen und Bilder fehlen?** Diese Angaben stammen aus dem gespeicherten
> Set-Inhalt, der in älteren Versionen noch ohne sie angelegt wurde. Steht
> oben ein Hinweis mit dem Knopf **🔄 Namen & Bilder nachladen**, holt er
> sie von BrickLink (mit Fortschrittsanzeige). Bei vielen Sets ruhig
> zweimal drücken.

---

## 9. Der Statistik-Tab

Für alle sichtbar (📊 in der Tab-Leiste), lädt beim Öffnen automatisch:

- **Kennzahlen**: Stück, verschiedene Artikel, Ø-Wert je Stück,
  Gesamtwert – *Profis* sehen zusätzlich „bezahlt gesamt" und
  „Gewinn" (grün/rot; gerechnet nur über Einträge mit Kaufpreis, damit
  nichts verfälscht).
- **Wertentwicklung**: die Gesamtsammlung als Kurve, gespeist aus der
  eigenen Preisaufzeichnung. Gerechnet wird mit den *heutigen*
  Stückzahlen – die Kurve beantwortet „was wäre unsere Sammlung an Tag X
  wert gewesen". Sie wird mit jeder Woche aussagekräftiger.
- **Aufteilung**: Balken nach Typ (Figuren/Sets/Teile) und Zustand
  (Neu/Gebraucht), jeweils mit Stückzahl, Wert und Prozentanteil.
- **Wert nach Erscheinungsjahr**: Balkendiagramm über alle Jahrgänge;
  das Spitzenjahr ist beschriftet, Antippen zeigt Details.
- **Top 10 nach Wert** mit Bildern.
- Für Profis zwei Gegenstücke, jeweils die ersten fünf: **📈 Beste
  Wertsteigerungen** und **📉 Größte Wertverluste** – beide aus
  „aktueller Wert minus Kaufpreis", also nur für Artikel mit eingetragenem
  Kaufpreis. Ein Tipp auf eine Zeile öffnet den Steckbrief.

  > Die Verluste stehen bewusst getrennt. Vorher gab es nur die
  > Steigerungen, und ein Verlust rutschte dort nur hinein, wenn es weniger
  > als fünf Gewinner gab – ausgerechnet in einer gewachsenen Sammlung sah
  > man sie also nie. Und solange ihr die Stücke behaltet, ist der Verlust
  > ohnehin nur auf dem Papier.
- **Einkauf auf Listen** *(Profi)*: die Summe aller eingetragenen
  Einkaufspreise. Auf der Übersicht zählen bewusst nur **offene** Listen –
  das ist das Geld, das gerade „unterwegs" ist. Ein Tipp öffnet ein Popup
  mit **allen** Listen, auch den archivierten, einzeln aufgeschlüsselt.
  Dort lässt sich je Liste **„inventarisiert"** ankreuzen: Was verbucht und
  in die Sammlung übernommen wurde, fällt aus der Rechnung heraus, ohne
  dass die Liste gelöscht werden muss.

---

## 10. CSV-Import, Export & Druck

*(Export & Druck unter Mehr → 📤 Export & Druck; der CSV-Import wohnt
in der Karte Mehr → 💼 Sammlerprofi.)*

### 10.1 Export & Druck (alle Benutzer)

Sammlung und Wunschliste als **CSV** (Semikolon-getrennt,
Excel-/Numbers-tauglich) oder als **Druckansicht** – eine aufgeräumte
Tabelle mit Seitenumbrüchen, ideal für Versicherung oder Vitrine.

Überschriften, Dateinamen und Zahlenformat folgen der **eingestellten
Sprache**, die Geldspalten der **eingestellten Währung** – auf Englisch
heißt die Datei `brickfolio-collection.csv` und die Spalte
`avg used (GBP)`.

### 10.2 CSV-Import *(Sammlerprofi)*

Ganze Bestände in einem Rutsch einlesen – etwa eine Excel-Erfassung oder
eine BrickLink-Inventarliste. **„Beispiel-CSV laden"** liefert eine
korrekte Vorlage. Das Format:

```csv
Nummer;Typ;Name;Anzahl;Zustand;Bezahlt;Jahr;Notizen
sw0815;Figur;Shoretrooper;2;Gebraucht;24,50;2016;Flohmarkt Ottobrunn
75154;Set;TIE Striker;1;Neu;89,99;2016;
col424;Figur;;1;Gebraucht;;;leerer Name: Nummer wird als Name verwendet
```

Die Regeln – bewusst gutmütig:

- **Nur „Nummer" ist Pflicht**; Spaltenreihenfolge egal, Erkennung am
  Spaltennamen (auch englisch: `qty`, `condition`, `paid` …).
- Trennzeichen Semikolon **oder** Komma (automatisch erkannt).
- Defaults: Typ Figur, Anzahl 1, Zustand Gebraucht, leerer Name → Nummer.
- „Bezahlt" versteht deutsche Beträge („24,50", auch mit €) und wird als
  ✏️-manueller Kaufpreis übernommen.
- **Vorhandene Artikel** werden zusammengeführt (Menge addiert, Kaufpreis
  aufsummiert).
- Fehlerhafte Zeilen brechen nichts ab – sie werden übersprungen und mit
  Zeilennummer gemeldet („3 neu, 1 zusammengeführt, 2 Fehler").

Namen, Bilder, Preise, Jahre und Set-Inhalte holt die App nach dem Import
automatisch im Hintergrund nach (siehe Kapitel 13) – bei großen Importen
dauert das einige Zeit. Wer nicht warten will, stößt es unter **Mehr →
Wartung** von Hand an: **🖼 Bilder jetzt holen** trägt seit 2.18.0 auch
fehlende Bildadressen nach, **🔄 Preislose erneut abrufen** auch die noch
nie versuchten Artikel.

> **Die Spalte „Typ" nicht vergessen.** Fehlt sie, gilt jede Zeile als
> *Figur* – ein Set landet dann als Minifigur, und Preise, Themen und
> Filter stimmen danach nicht mehr. Erkannt werden `Typ`, `type`,
> `item_type` und `Art`.

---

## 11. Sicherung, Wiederherstellung & Updates

### 11.1 Sicherung (Admin)

**Mehr → Sicherung → 💾 herunterladen** erzeugt eine JSON-Datei mit
*allem*: Benutzer (inkl. Passwort-Hashes), Sammlung, Wunschliste,
Einkaufslisten, Preisverläufe, Set-Zuordnungen und Einstellungen.
**📥 einspielen** stellt diesen Stand komplett wieder her – nach
Sicherheitsabfrage mit Datum; **alle aktuellen Daten werden ersetzt**.
Sicherungen ohne Admin-Benutzer werden abgelehnt (Aussperr-Schutz).

**🖼 Eigene Bilder mitsichern.** Fotos an Artikeln (Kapitel 5.6) und die
Bilder eigener Figuren sind **Dateien**, keine Datenbankzeilen – ohne sie
trüge die Sicherung nur den Verweis, und nach einem Umzug zeigten die
Artikel ins Leere. Deshalb steht in der Karte ein Kästchen, sobald es
welche gibt; es nennt Anzahl und Größe und ist von Haus aus angehakt. Die
Bilder wandern dann als Teil derselben JSON-Datei mit, und beim Einspielen
legt Brickfolio sie unter ihren alten Namen wieder an – die Verweise passen
also weiter. Das gilt auch für die Sicherung, die man beim **allerersten
Start** einspielt (Kapitel 2.3).

> **Wenn es zu viel wird:** Ab etwa 150 MB Bildern wird eine einzelne
> JSON-Datei unhandlich. Dann verweigert die App das Mitsichern und sagt es
> auch – nehmt in dem Fall den Ordner `data/uploads/` (oder gleich das ganze
> `data/`) über euer normales Backup mit.

**Automatisch passiert es außerdem von selbst:** Brickfolio legt täglich
eine konsistente Sicherung der Datenbank unter `data/backups/` ab und
behält die letzten 14 Tagesstände (einstellbar über die Umgebungsvariable
`BACKUP_KEEP`, 0 schaltet ab). Die Sicherung-Karte zeigt Datum der
letzten automatischen Sicherung. Die Tagesstände lassen sich in
der Sicherung-Karte auswählen, **⬇ herunterladen** (z. B. für die eigene
externe Ablage) und **↩︎ direkt wiederherstellen** – der aktuelle Stand
wird dabei automatisch als zusätzliche Sicherung weggeschrieben, die
Aktion ist also umkehrbar.

Empfehlung trotzdem: vor größeren Aktionen zusätzlich eine JSON-Sicherung
ziehen – und wer ein NAS-Backup (z. B. Hyper Backup) betreibt, nimmt den
Ordner `data/` mit auf, damit auch ein Hardware-Ausfall abgedeckt ist.

### 11.2 Updates einspielen

Brickfolio sagt selbst Bescheid: Die Karte **Mehr → 🔄 Version & Updates**
(Admin) vergleicht die installierte Version mit dem neuesten
GitHub-Release – automatisch beim App-Start und beim Öffnen des Mehr-Tabs
(serverseitig für 6 Stunden zwischengespeichert), sofort per „Nach
Updates suchen". Wartet ein Update, erscheinen ein Hinweis-Toast und ein
gelber Banner mit Link zu den Release-Notes.

> **Ohne Anmeldung nachsehen:** Die laufende Version steht klein unter der
> Anmeldekarte („Brickfolio 2.4.1"). Praktisch, wenn mehrere Instanzen
> laufen und man wissen will, welche man gerade vor sich hat – oder wenn
> jemand einen Fehler meldet und die Version dazu braucht.

Wie eingespielt wird, hängt davon ab, wie ihr installiert habt.

**Mit fertigem Image** (der übliche Weg, siehe 2.2):

```bash
cd /pfad/zu/brickfolio
docker compose pull && docker compose up -d
```

Auf einer Synology geht dasselbe **ohne Konsole**: *Container Manager →
Projekt → brickfolio → Aktion → Erstellen neu starten*.

> **Ohne Projekt geht das nicht.** Wer den Container von Hand über
> *Registrierung → Container erstellen* angelegt hat, findet diesen Knopf
> nicht – und das ist kein Versäumnis von DSM: Ein Container kann sein Image
> nicht wechseln, ein neues Image heißt immer auch ein neuer Container. Beim
> Projekt erledigt das der Assistent, weil dort alle Einstellungen in der
> YAML stehen. Von Hand geklickt heißt es: sichern, Image neu laden,
> Container löschen, neu anlegen. Schritt für Schritt in
> [`SYNOLOGY.md`](SYNOLOGY.md).
>
> Besonders aufpassen, wenn **kein Ordner auf `/data`** liegt: Dann steckt
> die Datenbank in einem anonymen Volume, und der neue Container bekommt ein
> leeres. Vorher unbedingt *Mehr → Sicherung* herunterladen.

> **`update.sh` liegt hier nicht.** Das Skript gehört zum Quellcode und
> steckt weder im Image noch im Ordner, wenn ihr nur die
> `docker-compose.yml` geholt habt. Die beiden Befehle oben tun dasselbe –
> nur den **Schnappschuss** müsst ihr selbst machen: in der App unter
> *Mehr → Sicherung*. Wer die Bequemlichkeit möchte, lädt das Skript einmal
> dazu:
>
> ```bash
> curl -sLO https://raw.githubusercontent.com/Melle79/brickfolio/main/update.sh
> ```

**Aus dem Quellcode gebaut:**

```bash
cd /pfad/zu/brickfolio
sudo bash update.sh
```

Das Skript legt zuerst einen **Datenbank-Schnappschuss** an (die letzten
drei bleiben erhalten) und erkennt dann an eurer `docker-compose.yml`, wie
die Installation läuft:

- steht dort `image: ghcr.io/…`, zieht es das neue Image (Sekunden)
- steht dort `build: .`, holt es den Quellcode von GitHub und baut neu

**In beiden Fällen gilt:** Eure `docker-compose.yml` und der `data/`-Ordner
bleiben unberührt – dort liegen Datenbank, Sicherungen und eure hochgeladenen
Bilder. Datenbank-Migrationen laufen beim Start automatisch und sind
idempotent; mehrfaches Aktualisieren schadet nie. Ein Rückschritt auf eine
ältere Version ist dagegen **nicht** vorgesehen: Migrationen erweitern nur.
Wollt ihr das trotzdem, spielt vorher die Sicherung zurück.

#### Update direkt aus der App *(optional)*

Mit einem kleinen Helfer auf dem Server geht es auch ohne SSH: In der
Karte **Version & Updates** stehen dann die Knöpfe **Jetzt**, **In 1
Minute** und **In 5 Minuten**.

> Dafür braucht ihr **beide** Skripte auf dem Server – auch bei einer
> Installation über das fertige Image, wo sie nicht mitkommen:
>
> ```bash
> cd /pfad/zu/brickfolio
> curl -sLO https://raw.githubusercontent.com/Melle79/brickfolio/main/update.sh
> curl -sLO https://raw.githubusercontent.com/Melle79/brickfolio/main/update-watch.sh
> ```
>
> Ohne sie erscheinen die Knöpfe **gar nicht erst** – die App zeigt statt
> dessen einen Hinweis. Es entsteht also kein toter Knopf, der ins Leere
> führt.

So läuft es ab:

1. Alle angemeldeten Browser zeigen oben einen Countdown
   („Update in 1:00 Minuten – bitte Eingaben abschließen"). Solange er
   läuft, kann der Admin **abbrechen**.
2. Danach erscheint überall ein **Sperrbildschirm** „Update wird
   installiert".
3. Sobald der Server wieder da ist, **laden sich die Browser selbst neu** –
   auch dann, wenn der Tab währenddessen im Hintergrund lag.

**Warum ein Helfer?** Die App läuft im Container und kann sich nicht selbst
neu bauen. Sie legt deshalb nur die Markierung `data/update-requested.json`
ab; das Skript `update-watch.sh` auf dem Server greift sie auf und startet
`update.sh`. So braucht die App **keinen Docker-Zugriff** – den ins
Container zu reichen käme faktisch Root auf dem Server gleich.

**Einrichtung** – `update-watch.sh` jede Minute aufrufen lassen (das Update
selbst dauert ohnehin ein bis drei Minuten). Auf einer Synology:
Systemsteuerung → Aufgabenplaner → Erstellen → Geplante Aufgabe →
Benutzerdefiniertes Skript.

| Reiter | Einstellung |
|---|---|
| Allgemein | Benutzer: **`root`** (sonst kein `docker compose`) |
| Zeitplan | Täglich · Start `00:00` · „Weiterhin innerhalb desselben Tages ausführen" ✔ · jede Minute · Letzte Ausführungszeit: **`23:59`** |
| Aufgabeneinstellungen | `sh /pfad/zu/brickfolio/update-watch.sh` |

> ⚠️ „Letzte Ausführungszeit" steht anfangs auf `00:59` – dann liefe die
> Aufgabe nur in der ersten Stunde des Tages. Unbedingt auf `23:59` stellen.

Unter Linux mit cron: `* * * * * sh /pfad/zu/brickfolio/update-watch.sh`

**Mehrere Instanzen:** am besten **je Instanz eine eigene Aufgabe** – so
seht ihr pro Instanz, ob sie durchgelaufen ist. Wer alles in eine Aufgabe
schreibt, hängt an jede Zeile `|| true`, sonst bricht ein Fehler in der
ersten Zeile die zweite mit ab.

**Läuft der Helfer?** Die Karte sagt es: „✅ Update-Helfer läuft" – oder sie
nennt den Grund, wenn nicht („hat sich noch nie gemeldet" → Pfad oder
Benutzer prüfen; „lief zuletzt vor X Stunden" → Zeitplan prüfen). Ohne
Helfer erscheinen die Knöpfe gar nicht erst, damit die App nicht auf ein
Update wartet, das nie kommt. Protokoll jedes Laufs: `data/update-watch.log`.

---

## 12. Das Tausch-Netzwerk

Mehrere Brickfolio-Instanzen – etwa in einer Familie oder einem
Freundeskreis – können sich verbinden: Jeder veröffentlicht die Artikel,
die er abgeben möchte, sieht die Angebote der anderen und schreibt
Nachrichten dazu. Alles freiwillig; ohne Verbindung fehlt der Tab schlicht.

### 12.1 Was wo liegt

Vermittelt wird über einen kleinen **Hub**. Wichtig für das Verständnis:

- Im Hub liegen **nur die veröffentlichten Angebote** und die
  Vorgangsdaten. Eure Sammlung, Preise, Notizen und Einkaufslisten
  verlassen die eigene Instanz **nicht**.
- **Nachrichten sind Ende-zu-Ende verschlüsselt.** Der Hub kann sie nicht
  lesen; er bewahrt sie nur auf, bis die Gegenseite sie abholt, und löscht
  sie dann. Der lesbare Verlauf lebt auf den beteiligten Instanzen weiter –
  auch dann, wenn der Hub die Umschläge längst gelöscht hat.

> **Eine Einschränkung, die man kennen sollte.** Verschlüsselt wird mit dem
> öffentlichen Schlüssel des Gegenübers – und **verteilt werden diese
> Schlüssel vom Hub**. Wer den Hub kontrolliert, könnte statt des echten
> einen eigenen ausliefern und damit mitlesen, ohne dass es auffällt. Das
> ist keine Hintertür im Programm, aber es ist die Stelle, an der man dem
> Hub vertrauen muss.
>
> Seit v1.68.0 gibt es dagegen zwei Dinge:
>
> 1. **Die Instanz merkt sich den Schlüssel beim ersten Mal.** Taucht später
>    ein anderer auf, wird **nichts verschickt**, sondern abgebrochen – mit
>    einer Meldung. Ein Wechsel kann harmlos sein (Gegenüber neu aufgesetzt);
>    unterscheiden lässt es sich nur durch Nachfragen. Ist es geklärt,
>    bestätigt ein Admin den neuen Schlüssel.
> 2. **Eine Sicherheitsnummer zum Vergleichen.** Im Gespräch klappt
>    „🔐 Sicherheitsnummer vergleichen" zwei kurze Zahlenreihen auf: die
>    eigene und die des Gegenübers. Einmal am Telefon vorlesen – stimmen sie
>    auf beiden Seiten überein, ist niemand dazwischen. Sie ändert sich nur,
>    wenn sich der Schlüssel wirklich ändert.

### 12.2 Beitreten

Zum Mitmachen braucht es einen **Einladungscode** von jemandem, der schon
dabei ist. Eintragen unter **Mehr → Tausch-Netzwerk**: Code und den
gewünschten Anzeigenamen im Netzwerk eingeben, „Beitreten". Der Assistent
beim allerersten Start (2.3) fragt dasselbe ab.

Der Anzeigename ist netzwerkweit eindeutig und mindestens vier Zeichen
lang. Ändern lässt er sich nur über den Hub-Admin.

**Selbst einladen** darf jedes verbundene Mitglied: im Tausch-Tab
„✉️ Freund einladen". Jeder hat ein Kontingent von **drei** Einladungen und
kann beim Hub-Admin mehr anfragen. Der Code gilt einmal.

### 12.3 Was ich anbiete

Der Tab **Tausch** hat drei Bereiche. Unter **📤 Meine Auswahl** steht, was
ins Netzwerk geht:

- Einzelne Artikel wählst du in der **Sammlung** aus: Karte öffnen →
  „🤝 In der Tauschbörse anbieten".
- „➕ Abgebbare übernehmen" holt in einem Rutsch alles aus der
  Verkaufsliste (Doppelte, siehe Kapitel 8).
- Bei mehrfach vorhandenen Figuren wählst du die **Menge**, die angeboten
  wird – von drei Yodas also auch nur einen.
- An jedem Artikel steht, ob er **schon veröffentlicht** ist oder noch
  wartet. Was im Hub steht, hier aber nicht mehr ausgewählt ist, wird oben
  gemeldet – es verschwindet beim nächsten Veröffentlichen.

Sichtbar wird die Auswahl erst durch **„📤 Auswahl veröffentlichen"**
(Admin). Bis dahin ändert sich im Netzwerk nichts. Custom-Figuren reisen
mit einem verkleinerten Vorschaubild mit, damit beim Gegenüber kein
Platzhalter steht.

### 12.4 Angebote und Gespräche

Unter **🔎 Angebote** stehen die Artikel der anderen, mit Suchfeld über
Name und Nummer. Ein Tipp auf eine Karte öffnet das Anfrage-Fenster mit
einer vorgeschlagenen Nachricht, die du überschreiben kannst. Läuft zu dem
Angebot schon ein Gespräch, geht stattdessen direkt der Chat auf – an der
Karte steht das auch dran („angefragt · offen").

Unter **💬 Meine Vorgänge** liegen alle Gespräche. Im offenen Chat kommen
neue Nachrichten **von selbst** an, ohne „Abrufen". An eigenen Nachrichten
steht „unterwegs …" bzw. „zugestellt ✓".

Im Gespräch gibt es außerdem:

- **✔ Annehmen** / **✖ Ablehnen** – Ablehnen schließt das Fenster
- **🗑 Löschen** – entfernt die Unterhaltung hier und im Hub, samt der
  Umschläge beim Gegenüber
- **⚑ Melden** – siehe unten

Nimmt das Gegenüber einen Artikel aus dem Netzwerk, steht am Vorgang und
über dem Verlauf **„nicht mehr angeboten"**.

### 12.5 Angenommen – und dann?

„Annehmen" ist zunächst nur die Zusage im Gespräch. Damit sich auch in deinen
Beständen etwas tut, steht im Gespräch direkt unter dem Verlauf ein Knopf –
welcher, hängt von der Richtung ab:

| Richtung | Knopf |
|---|---|
| Der Artikel kommt **zu dir** (deine Anfrage) | **📥 In die Sammlung übernehmen** |
| Der Artikel geht **weg** (Anfrage an dich) | **📤 Aus der Sammlung austragen** (rot) |

Gleich nach dem Annehmen geht das passende Fenster von selbst auf.

#### Was reinkommt: übernehmen

Dort stellst du ein:

| Feld | Bedeutung |
|---|---|
| **Wohin?** | *Sammlung* – oder eine deiner Einkaufslisten *(Sammlerprofi)* |
| **Anzahl** | Standard 1 |
| **Zustand** | Neu / Gebraucht – vorbelegt mit dem Zustand aus dem Angebot |
| **Bezahlt** | freiwillig; landet im Kaufbuch der Karte (Kapitel 5.5) |

Der Eintrag entsteht wie ein normaler: Ist die Nummer schon vorhanden, wird
die Anzahl erhöht statt eine zweite Zeile anzulegen. In den Notizen steht
„Tausch mit …", damit später nachvollziehbar bleibt, woher das Stück kam.
Bild, Nummer und Art kommen aus dem Angebot; bei Vorgängen von vor Version
1.85.0 wird die Art aus der Nummer geraten (reine Ziffern = Set) und lässt
sich auf der Karte ändern.

**Erst zusagen, später buchen.** Gebucht wird nur auf Knopfdruck – zwischen
Zusage und Karton in der Hand liegen beim Tauschen gern ein paar Tage, und
oft steht der Preis erst dann fest. Solange nichts gebucht ist, trägt der
Vorgang in der Liste das Kennzeichen **„noch nicht verbucht"**. Danach steht
auf dem Knopf, wann gebucht wurde; ein weiterer Klick erhöht die Anzahl.

#### Was weggeht: austragen

Bei **eingehenden** Anfragen geht ein Stück weg. Das Fenster nennt Artikel,
Gegenüber und wie viele du davon hast, und fragt nach der **Anzahl**. Steht
die Nummer **neu und gebraucht** in der Sammlung, kommt außerdem die Frage
**„Welches Stück?"** dazu – geraten wird hier nichts, das wäre schnell das
falsche Exemplar. Ist danach nichts mehr übrig, verschwindet die Zeile ganz,
samt Kaufbuch – genau wie beim Austragen über die Karte.

Von allein passiert das nie: Ohne Klick auf **Austragen** im App-Fenster
bleibt die Sammlung, wie sie ist. In der Vorgangsliste steht so lange
**„noch nicht ausgetragen"**.

### 12.6 Melden

Läuft etwas schief, geht über „⚑ Melden" eine Meldung an den Hub-Admin.
Der Haken **„Nachrichtenverlauf mitschicken"** ist dabei die einzige
Möglichkeit, wie ein Verlauf jemals lesbar wird: Deine Instanz entschlüsselt
ihn und legt ihn freiwillig offen. Ohne Haken sieht der Admin nur deine
Begründung. Eine Hintertür im Hub gibt es nicht.

### 12.7 Wenn der Zugang gesperrt wurde

Ein Hub-Admin kann Zugänge sperren. Dann steht im Tausch-Tab ein deutlicher
Hinweis. Was das bedeutet:

- Angebote und neue Nachrichten sind nicht mehr möglich, und die eigenen
  Angebote verschwinden für alle anderen.
- **Bisherige Unterhaltungen bleiben lesbar** – sie liegen ja lokal.
- Es geht **nichts verloren**. Nach einer Freischaltung läuft alles weiter,
  ohne neu zu verbinden; in der Sperrzeit eingegangene Nachrichten werden
  nachgeliefert.

Deshalb der Rat auf dem Hinweis: **nicht die Verbindung trennen.** Trennen
löst das Konto, und der Weg zurück wird umständlicher.

### 12.8 Verwaltung

Mitglieder verwalten, Einladungsanfragen entscheiden, Meldungen ansehen,
Angebote aufräumen – das läuft **nicht** in der App, sondern in einer
separaten Admin-Konsole. Das hält Verwaltungsrechte aus der Familien-App
heraus.

---

## 13. Die Preis-Automatik im Detail

Damit klar ist, was wann von allein passiert:

**Preisabruf.** BrickLink-Ø-Preise (neu & gebraucht) werden geholt:
(1) sofort beim Erfassen eines Artikels, (2) manuell über „Preise
aktualisieren" in den Details, (3) automatisch vom **Hintergrundjob**:
Er läuft alle **12 Stunden**, nimmt sich Artikel vor, deren Preise älter
als **7 Tage** sind – maximal **40 je Durchlauf** und Tabelle, mit 2 s
Pause pro Anfrage, um BrickLink nicht zu belasten. Ergebnis: Jeder
Artikel ist automatisch nie älter als gut eine Woche.

**Preisverlauf.** Bei jedem Abruf entsteht ein Verlaufs-Punkt – höchstens
**einer pro 20 Stunden** je Artikel. Die Wertentwicklungs-Kurve im
Statistik-Tab entsteht aus genau diesen Punkten. Ein manueller Abruf
innerhalb dieser 20 Stunden aktualisiert den jüngsten Punkt, statt einen
neuen anzulegen (das Chart bleibt sauber).

**Preis-Protokoll.** Unter **Mehr → 📈 Preis-Protokoll** *(Sammlerprofi)*
listet die App die jüngsten Preis-Aktualisierungen quer über alle Artikel
– mit Datum, Artikel, gefundenen Preisen und einem Badge, ob der Punkt
**automatisch** (Hintergrundjob) oder **manuell** (↻-Knopf) entstand.
So ist jederzeit nachvollziehbar, wann welche Preise aufgezeichnet wurden.

**Kaufpreis-Automatik.** Einträge ohne manuellen Kaufpreis erhalten beim
ersten Preisabruf den Tages-Ø als ⚙️-Wert (siehe 5.4). Manuell gesetzte
Preise bleiben immer unangetastet.

**Figuren beim Set übernehmen.** Wandert ein **Set** in die Sammlung – per
Foto, Suche, Wunschliste, Einkaufsliste oder manuell –, fragt die App
anschließend, welche der enthaltenen Minifiguren dabei sind. Alle sind
vorausgewählt, einzelne lassen sich abwählen, „Keine übernehmen" überspringt
die Frage. Der Zustand ist mit dem des Sets vorbelegt und umstellbar; Figuren,
die mehrfach im Set stecken, werden auch mehrfach erfasst. Ohne
BrickLink-Schlüssel oder bei Sets ohne Minifiguren erscheint die Frage nicht.

**Papierkorb statt Minus.** Ist von einem Artikel nur noch **ein** Exemplar
vorhanden, zeigt der Mengenknopf ein 🗑 statt des −. Ein Tipp darauf löscht
den Eintrag – mit derselben Sicherheitsabfrage wie der Löschen-Knopf und,
bei Sets, samt Figuren-Frage.

**Beim Löschen genauso.** Wird ein Set aus der Sammlung entfernt, fragt die
App, ob die dazugehörigen Figuren mitgehen sollen. Vorgeschlagen wird genau
die Menge, die rechnerisch zu diesem Set gehört: Besitzt ihr eine Figur
dreimal und steckten zwei im Set, wird auf **eine** reduziert statt alles zu
löschen. „Figuren behalten" entfernt nur das Set.

**So entsteht der Gesamtwert – und warum Set-Figuren nur einmal zählen.**
Der Wert eines Eintrags ist *Ø-Preis × Menge*, passend zum eingetragenen
Zustand. Ein **Set-Preis** gilt bei BrickLink allerdings für das *komplette*
Set – die Minifiguren sind darin bereits enthalten. Wer Sets **und** deren
Figuren getrennt erfasst (was für die Übersicht sinnvoll ist), hätte sie
sonst zweimal in der Summe.

Deshalb rechnet die App so: **Sets zählen voll**, und von jeder Figur zählen
nur die Exemplare, die **nicht** in einem eigenen Set stecken. Gebunden sind
*Anzahl der besessenen Sets × Stückzahl der Figur im Set*, höchstens so
viele, wie tatsächlich vorhanden sind. Enthält ein Set zwei Sturmtruppler,
besitzt ihr das Set einmal und habt die Figur 3× erfasst, dann stecken zwei
im Set und **eines zählt** als echtes Extra. Bei gemischten Zuständen werden
zuerst zustandsgleiche Exemplare zugeordnet. Wie viel herausgerechnet wurde,
zeigt die Statistik offen unter den Kacheln.

Bereinigt wird nur dort, wo Sets und Figuren in **einer** Zahl zusammenkommen:
Gesamtwert, Wert-Widget der Sammlung bei Filter *Alle*, Aufteilung nach
Typ/Zustand, Wert nach Erscheinungsjahr und Wertentwicklungs-Kurve. Filtert
ihr auf **Figuren** oder **Sets**, erscheint der **volle** Wert dieser Gruppe;
einzelne Karten und die **Top 10** zeigen immer den vollen Einzelwert. Die
**Stückzahl** bleibt unverändert – die Figuren gehören euch ja physisch –,
und **bezahlt/Gewinn** rechnet weiter mit dem vollen Einzelwert.

**Weitere Hintergrund-Arbeiten:** fehlende Erscheinungsjahre werden
nachgetragen, Set-Inhalte (Figuren-Inventare) für neue Sets geladen.
CSV-Importe und manuelle Nummern (`manuell-…`, `fig-…`) ohne
BrickLink-Entsprechung bleiben preislos – alles andere versorgt sich
selbst.

---

### 13.1 Preisgebiet und Währung

BrickLink liefert standardmäßig den **weltweiten** Durchschnitt in Euro.
Unter **Mehr → 🌍 Preisgebiet** (Admin) lassen sich beide Seiten einstellen:

**Gebiet** – 21 Länder (Deutschland, Österreich, Schweiz, Großbritannien,
Irland, USA, Kanada, Australien, Neuseeland, Niederlande, Belgien,
Frankreich, Italien, Spanien, Portugal, Polen, Tschechien, Schweden,
Dänemark, Norwegen, Finnland), sieben Regionen (Europa, Nordamerika,
Südamerika, Asien, Ozeanien, Afrika, Naher Osten) oder weltweit.

**Währung** – Euro, Britisches Pfund, US-Dollar, Schweizer Franken,
Kanadischer und Australischer Dollar, Neuseeland-Dollar, Schwedische,
Dänische und Norwegische Krone, Złoty, Tschechische Krone. Umgerechnet
wird bei **BrickLink**: Die App schickt den Währungscode mit und speichert,
was zurückkommt. Sie führt keine eigenen Kurse – es gibt also nichts, was
veralten könnte.

Beides ist **unabhängig** voneinander: Wer in Deutschland wohnt, aber am
britischen Markt kauft, stellt Gebiet auf Großbritannien und die Währung
auf Euro – oder umgekehrt.

**Beim ersten Start** fragt der Einrichtungsassistent (Schritt 2) beides
ab und schlägt vor, was zu den Spracheinstellungen des Browsers passt:
`en-GB` führt zu Großbritannien und Pfund, `en-US` zu den USA und Dollar,
`de-DE` zu Deutschland und Euro. Wer das Land umstellt, bekommt die
passende Währung mitgezogen – eine danach von Hand gewählte Währung bleibt
stehen.

**Wichtig – der zweistufige Rückfall:** Gerade bei selteneren Figuren gibt
es in einem einzelnen Land oft **gar keine Verkäufe**. Findet BrickLink im
gewählten Gebiet nichts, weitet die App automatisch aus – **erst auf die
zugehörige Region, dann auf weltweit**. Die zweite Stufe richtet sich nach
dem Land: für die USA also Nordamerika, für Australien Ozeanien, für
Europa Europa. Der erste Markt mit echten Verkäufen zählt. So bleibt kein
Artikel ohne Preis; die Bewertung ist dann eben gemischt. (Ist eine Region
oder weltweit direkt eingestellt, entfällt die jeweils engere Stufe.)

**Woran man einen ausgewichenen Preis erkennt:** Stammt ein Ø-Preis nicht
aus dem eingestellten Gebiet, steht eine kleine **Flagge** daneben – 🇪🇺 für
Europa, 🌍 für weltweit. In der Detail-Preiskarte erklärt ein Tooltip den
Grund. Preise aus dem eingestellten Gebiet bleiben ohne Flagge, sind also
auf einen Blick als „echt deutsch" (bzw. österreichisch/schweizerisch)
erkennbar.

**Bestehende Sammlung umstellen.** Nach dem Wechsel stammen alle
gespeicherten Preise noch aus dem alten Gebiet – **oder aus der alten
Währung**. Beides zählt gleich: Die Karte zeigt, wie viele Artikel
betroffen sind, und bietet **🔄 Preise jetzt umrechnen**. Bis dahin stünden
sonst alte Beträge unter neuem Zeichen, und das wäre schlicht falsch.

> Jeder Artikel kostet **zwei BrickLink-Abrufe** (neu und gebraucht), und
> BrickLink hat ein Tageskontingent. Die App arbeitet deshalb in Häppchen
> und zeigt den Fortschritt („120 umgerechnet, 340 offen …"). Bei großen
> Sammlungen ruhig über mehrere Tage laufen lassen – der Stand bleibt
> erhalten, es wird immer dort weitergemacht, wo aufgehört wurde.

Artikel, die BrickLink nicht kennt, werden übersprungen und abgehakt,
damit der Lauf nicht an einer Nummer hängen bleibt.

**Artikel ohne Preis nachholen.** Zeigt die Karte „*X* Artikel haben noch
keinen Preis", waren das im gewählten Gebiet meist Nummern ohne Verkäufe.
**🔄 Preislose erneut abrufen** holt für genau diese die Bewertung neu –
mit dem zweistufigen Rückfall Europa → weltweit. Auch das läuft in
Häppchen. Was danach immer noch keinen Preis hat, wurde wirklich nirgends
verkauft; solche Artikel bleiben ehrlich als „ohne Preis" stehen, statt
den Lauf endlos zu wiederholen. (Der frühere Fehler, dass BrickLinks
„0.0000" bei fehlenden Verkäufen für einen echten Preis gehalten wurde und
Artikel dadurch grundlos ohne Preis oder mit 0,00 € dastanden, ist seit
Version 1.13.0 behoben.)

### 13.2 Das Preis-Protokoll

**Mehr → 📈 Preis-Protokoll** *(Sammlerprofi)* listet die jüngsten
Aufzeichnungen mit Zeitpunkt, Artikel, Preisen und Quelle (`auto` oder
`manuell`). Darüber steht, **bei wie vielen Artikeln der Preisabruf älter
als sieben Tage ist** – so seht ihr auf einen Blick, wie aktuell die
Bewertung eurer Sammlung ist. Sind alle Preise frisch, steht dort
stattdessen eine Bestätigung.

---

## 14. Fehlerbehebung

### 14.1 Der Fehlerbericht (Admin)

Geht in der App etwas kaputt, muss niemand mehr aufschreiben, „was da
stand". Jeder Fehler im Browser wird automatisch im Hintergrund an den
eigenen Server gemeldet und sammelt sich unter **Mehr → 🐞 Fehlerbericht**
– auch die von den Geräten der Kinder. Pro Eintrag stehen dort Fehlertext,
Stelle im Code, wie oft er auftrat, wann zuletzt, welche App-Version und
welcher Browser; unter „Details" die vollständigen Angaben.

**Gleichartige Fehler werden zusammengefasst.** Ein Fehler, der bei jedem
Seitenaufruf auftritt, erzeugt keine hundert Einträge, sondern einen mit
Zähler. Die Liste hält die letzten 100 verschiedenen Fehler.

**Fehlschläge vom Server stehen seit 2.13.0 mit drin.** Vorher wurde nur
aufgezeichnet, was niemand auffing – fast jeder Knopf fängt seinen Fehler
aber ab und schreibt ihn in eine Kurzmeldung. Auf dem Bildschirm stand also
„Fehler 502", und der Bericht meldete „keine Fehler". Jetzt landet jede
Antwort ab Status 500 im Protokoll, mit dem Weg (`GET /api/lookup/…`) und
dem **Anfang der Antwort**. Genau daran hängt die entscheidende Frage:

- Steht dort `{"detail": …}`, kommt der Fehler **aus der App** – der Text
  daneben sagt, was schiefging.
- Steht dort eine **HTML-Seite** (`<html>…502 Bad Gateway…`), kommt er von
  etwas **davor**: Zwischenserver, Cloudflare-Tunnel, Zugangsschutz. Dann
  ist nicht die App das Problem, sondern der Weg dorthin – typischerweise,
  weil die Antwort dem Tunnel zu lange gedauert hat.

Ein 404 („kennt BrickLink nicht") und ein 400 („Eingabe nicht gültig")
bleiben draußen: gewöhnlicher Betrieb, der die Liste nur zumüllt.

**„Script error." – der einzige Eintrag, der keiner ist.** Steht dort eine
Meldung ohne Datei und Zeile, ist die App nicht schuld. Der Browser kürzt
Fehler aus **fremden Skripten** aus Sicherheitsgründen auf genau diesen Satz
zusammen und verschweigt alles Nähere. Die Seite lädt nur zwei eigene Dateien
und bindet keine Rahmen ein – es kann also keins von uns sein. In Frage kommen
Browser-Erweiterungen, Inhaltsblocker und was der Browser selbst einspritzt
(Passwort-Ausfüllhilfe etwa); auf dem iPhone ist das der häufigste Fall.
Solche Einträge sind seit 2.4.3 als **🧩 Kein Fehler der App** beschriftet und
tragen unter *Details* wenigstens die letzten Schritte vor dem Fehler.

**Seit 2.19.0 steht dort auch, wer es war** – soweit es sich sehen lässt:
eingehängte Skripte und Stilblätter mit einer Erweiterungs-Adresse
(`chrome-extension://…`) und Elemente, die jemand nachträglich an die Seite
gehängt hat. Dasselbe steht in jeder Startzeile des Speicher-Verlaufs unter
**FREMD:** – denn bei einem Absturz gibt es oft gar keinen Fehlereintrag,
nur ein fehlendes Lebenszeichen.

> Das ist wichtiger, als es klingt: Fremder Code läuft im **selben
> Prozess** wie die App. Stürzt er ab, nimmt er den Tab mit – ganz gleich,
> wie sparsam die Seite gerade ist. Die App entfernt trotzdem nichts; es ist
> euer Browser.

> Ärgert es dich, teste einmal im **privaten Fenster** oder mit
> abgeschalteten Erweiterungen. Bleibt es dort aus, war es genau das.

**Was nicht gemeldet wird:** API-Schlüssel und der GitHub-Token werden aus
jedem Text entfernt (`***`), bevor er gespeichert oder verschickt wird.
Die Meldung geht ausschließlich an euren eigenen Server – nach außen geht
nur, was ihr selbst per Issue verschickt.

**Mitbekommen, dass etwas war.** Ein *neuer* Fehler legt einen Zettel auf
der Startseite ab – mit der Meldung und einem Knopf, der direkt zur Karte
springt. Nur Admins sehen ihn; der Fehlerbericht liegt in einer Admin-Karte,
für alle anderen wäre der Zettel eine Sackgasse. Es liegt immer **höchstens
einer** offen: Ein Problem löst oft mehrere verschiedene Fehler aus. Ist er
weggeklickt, meldet sich der nächste **neue** Fehler wieder – derselbe zum
zweiten Mal nicht.

**🔔 Benachrichtigung aufs Gerät.** Wer auch dann Bescheid wissen will, wenn
Brickfolio gerade zu ist, schaltet in derselben Karte Web-Push ein – **je
Gerät einzeln**, mit einer Berechtigungsabfrage des Browsers. Danach kommt
bei einem neuen Fehler eine Meldung aufs Handy oder an den Desktop.

> **Was dabei wohin geht.** Die Schlüssel entstehen beim ersten Einschalten
> auf eurem Server und bleiben dort – der private Teil verlässt ihn nie.
> Zustellen muss der Push-Dienst des jeweiligen Browser-Herstellers (Apple,
> Google, Mozilla); anders funktioniert Web-Push nicht. Deshalb steht in der
> Meldung nur „Ein Fehler wurde aufgezeichnet" – kein Fehlertext, keine
> Nummer, nichts aus der Sammlung. Der Inhalt ist auf dem Weg dorthin
> ohnehin verschlüsselt, aber was gar nicht drinsteht, kann auch nicht
> auffallen. **Der Tausch-Hub ist daran nicht beteiligt.**

Voraussetzungen: **https** (also der Cloudflare-Tunnel oder ein eigenes
Zertifikat – im reinen Heimnetz über `http` erlauben Browser keine
Benachrichtigungen) und auf dem iPhone die **auf dem Startbildschirm
installierte** App. Ein Knopf **Probemeldung senden** prüft die Zustellung,
damit sich das nicht erst beim echten Fehler zeigt. Wird die App neu
installiert, zeigt die alte Adresse ins Leere – solche Einträge räumt der
Server beim nächsten Versand selbst weg.

**🩺 Speicher-Verlauf.** Bricht der Browser die Seite ab („Auf dieser Seite
gibt es ein Problem"), hinterlässt das normalerweise nichts – keine
Konsole, kein Protokoll, nichts. Deshalb misst die App alle 30 Sekunden
JS-Speicher, Zahl der Elemente und Zahl der Bilder und legt das **im
Browser** ab, wo es einen Abbruch übersteht. Nach dem nächsten Start steht
in derselben Karte, was in den zwei Stunden davor passiert ist, samt Kurve.

Senkrechte Linien markieren den Beginn einer Sitzung. Ob dahinter ein
Absturz steckt, entscheidet der **Abschiedszettel**: Beim gewollten Ende –
neu laden, weiterklicken, schließen – hinterlässt die Seite eine Notiz, beim
Abwürgen durch den Browser nicht. Die Zusammenfassung unterscheidet deshalb
vier Fälle:

| Zeile | Bedeutung |
| --- | --- |
| „ohne sich zu verabschieden" | echter Absturz |
| „weiterer Tab" | ihr habt Brickfolio ein zweites Mal geöffnet |
| „von Hand neu geladen" | jemand hat neu geladen oder nach unten gezogen |
| „hat die App selbst neu geladen" | z. B. nach einem Server-Neustart |
| „vom Browser weggeräumt" | der Browser hat den Tab bei Speichermangel entsorgt |

Dazu steht in jedem Messwert die **Startzeit des Servers**; springt sie, ist
der Container neu gestartet. Ebenso die gerade **geöffnete Ansicht**
(`▸ scan`). Kommt es zu Abstürzen, nennt die Zusammenfassung, wo die App
dabei zuletzt stand – häufen sie sich auf einer Ansicht, steht das dort
schwarz auf weiß.

> **Mehrere Tabs teilen sich einen Verlauf.** Der Zettel liegt beim Browser,
> nicht beim einzelnen Tab – zwei offene Fenster schreiben also abwechselnd
> in dieselbe Liste. Steht in einer Zeile **„2 Tabs offen"**, gehören
> Speicher und Elemente der Zeilen darum herum nicht alle zur selben
> Sitzung. Das erklärt Sprünge, die sonst nach einem Leck aussehen.

> Bis Version 2.21.3 zählte ein zweiter Tab als **Absturz** – er findet den
> gemeinsamen Abschiedszettel nicht frisch vor, während der erste Tab noch
> läuft. Ältere Verläufe mit Abstürzen sind deshalb mit Vorsicht zu lesen.

**Wenn der Tab trotzdem abbricht, kostet es nichts mehr.** Seit Version 2.0.0
merkt sich die App zwei Dinge im Browser: **welche Ansicht offen war** und
**was im Formular „Manuell erfassen" stand**. Startet die App danach, ohne dass
sich die vorige Sitzung ordentlich verabschiedet hat, landet man wieder dort,
wo man war, und die angefangene Eingabe steht wieder im Formular. Bei einem
normalen Start passiert das **nicht** – dann öffnet die App wie immer den
Scan-Tab, denn niemand will nach dem Öffnen in den Einstellungen landen, nur
weil er dort zuletzt etwas nachgesehen hat.

> Gerettet wird nur Text. Ein ausgewähltes Foto lässt sich nicht
> wiederherstellen – aber ein halb ausgefülltes Formular ist ohnehin das, was
> wehtut.

> **Wenn die Kurve flach bleibt und der Tab trotzdem stirbt.** Dann liegt es
> nicht an der App, und der einzige Ort mit dem echten Grund ist die
> Absturzliste des Browsers: `edge://crashes` bzw. `chrome://crashes`. Jeder
> Eintrag hat eine **Bucket-ID** – sie fasst Abstürze mit derselben Ursache
> zusammen. Tragen alle Einträge dieselbe ID, ist es **immer derselbe Fehler**,
> und zwar einer des Browsers.
>
> So war es hier: 17 Abstürze über vier Tage, alle unter der Bucket-ID
> `8e89b35907…`, alle mit `P6 = renderer` (der Tab selbst), `P3 =
> Microsoft_Edge_Framework` (Edges eigener Code), `P7 = 0x6` (auf macOS
> SIGABRT – der Prozess bricht sich selbst ab) und immer an derselben Stelle
> im Programm. Drei davon fielen genau auf die Zeitpunkte, an denen auch der
> Speicher-Verlauf „OHNE ABSCHIED" verzeichnete – die übrigen vierzehn hat die
> App nie gesehen.
>
> **Und wie es weiterging – das gehört zur Wahrheit dazu.** Nach dem Update
> auf die nächste Edge-Fassung war jene Bucket-ID verschwunden. Es tauchte
> aber sofort eine **neue** auf: andere ID, andere Stelle im Programm,
> ansonsten dasselbe Bild – `renderer`, `Microsoft_Edge_Framework`, `0x6`.
> Ein Browser-Update kann so einen Fehler also beheben, muss aber nicht: Es
> tauscht ihn womöglich gegen den nächsten.
>
> **Was zu tun bleibt**, der Reihe nach:
> 1. **Hardwarebeschleunigung abschalten** (`edge://settings/system`) und
>    eine Weile so arbeiten. Renderer-Abbrüche kommen oft aus dem Grafikpfad
> 2. **Schonender Bildmodus** (unten) – falls es beim Scannen passiert
> 3. **Anderen Browser** nehmen und die App eine Stunde offen liegen lassen.
>    Bleibt es dort ruhig, ist der Fall klar
> 4. Einen Eintrag über **„Feedback senden"** melden. Berichte mit einer
>    **Cab-ID** tragen einen echten Speicherabzug – die sind die nützlichsten

**🔬 Bausteine einzeln abschalten** (ab 2.73.0). Vier Kästchen in derselben
Karte, alle standardmäßig an:

| Baustein | was aus ist | was ihr merkt |
|---|---|---|
| Sichtbarkeitsoptimierung | `content-visibility` auf den Sammlungskarten | große Sammlungen öffnen etwas langsamer |
| Klebende Leisten | `position: sticky` | Kopfleiste und Blocküberschriften scrollen mit |
| Milchglas | `backdrop-filter` (nur „Nova") | Flächen werden schlicht deckend |
| Offline-Helfer | der Service Worker | die App braucht beim Start eine Verbindung |

**Wozu.** Wenn alle Absturz-Dumps ausschließlich diese Seite betreffen,
steckt der Abbruch zwar im Browser – aber irgendetwas hier löst ihn aus.
Welches Stück, sagt niemand: Der Aufrufstapel im Speicherabzug trägt keine
Namen. Raten hilft dann nicht, halbieren schon.

Der Weg: **eines** abschalten, ein paar Stunden normal arbeiten. Was
abgeschaltet war, steht in jedem Fehlerbericht mit (`OHNE: cv,blur`) – erst
dadurch lässt sich hinterher zuordnen, welche Sitzung womit lief. Bleibt es
ruhig, habt ihr den Auslöser. Stürzt es weiter ab, das nächste Kästchen.

Nichts davon rührt eure Daten an, und die Wahl übersteht einen Absturz
samt Neuladen.

**🐢 Schonender Bildmodus.** Ein Kästchen in derselben Karte, standardmäßig
aus. „Aber andere Seiten stürzen doch nicht ab" – stimmt, und der Grund
dafür ist wahrscheinlich: Kaum eine andere Seite gibt dem Browser diese
Arbeit. Brickfolio entpackt Fotos, malt sie auf Zeichenflächen, liest
Bildpunkte aus und kodiert wieder als JPEG – bei der Reihum-Suche ein
Dutzend Mal hintereinander. Der Browser schiebt so etwas gern auf die
**Grafikeinheit**, und genau dort brechen Renderer ab.

Der schonende Modus geht denselben Weg zu Fuß: Entpacken über ein
gewöhnliches Bildelement, alle Zeichenflächen im Hauptspeicher. Etwas
langsamer, sonst gleich – dieselben Ergebnisse, dieselben Ausschnitte.

> **So grenzt ihr ein:** Modus einschalten, eine Weile wie gewohnt
> arbeiten. Bleibt es ruhig, lag es an diesem Weg. Stürzt es weiter ab –
> besonders **ohne dass ihr gescannt habt** –, liegt es nicht daran, und der
> Weg führt über den Browser: andere Anwendung testen,
> Hardwarebeschleunigung abschalten, melden.

> **Deshalb steht die Zahl der Bilder dabei.** Sie ist oft die eigentliche
> Last: Ein Bild von 400 px belegt entpackt 0,6 MB, und zwar **außerhalb**
> des JS-Speichers. Eine Ansicht mit 800 Bildern trug so über 500 MB, die in
> keiner Kurve auftauchten. Seit 2.11.0 holen die Karten deshalb eine
> Daumennagel-Fassung mit 160 px – dieselbe Ansicht kommt damit auf 85 MB.
> Steigt die Bilderzahl bei euch in die Hunderte und der Tab bricht ab, ist
> das der erste Ort zum Nachsehen.

> **Was die Zahl aussagt – und was nicht.** Gemessen wird der
> **JavaScript-Speicher**. Entpackte Bilder und der Aufbau der Seite selbst
> stecken da **nicht** drin. Wächst die Kurve, liegt es an der App. Bleibt
> sie flach, während der Tab trotzdem stirbt, liegt es sehr wahrscheinlich
> woanders – dann lohnt der Blick in `edge://crashes` und in den
> Task-Manager des Browsers (Umschalt+Esc), welcher Tab wirklich wächst.
> Auch das ist ein Ergebnis.

Am Beginn jeder Sitzung steht außerdem das **Gerät**: System, Browser, ob die
App installiert ist oder im Browser läuft, Arbeitsspeicher und
Bildschirmgröße. Bricht eine Sitzung ab, rechnet die Zusammenfassung ihre
**Laufzeit** aus – zweimal dieselbe Dauer wäre ein Muster.

**Zuletzt passiert.** Unter der Kurve steht die **Spur**: Zwischen zwei
Messwerten liegen 30 Sekunden, ein Absturz wartet darauf nicht. Deshalb wird
sofort festgehalten, was gerade lief – Foto aufgenommen (mit Megapixeln und
Dateigröße), verkleinert, Erkennung läuft und fertig, Ansicht gewechselt und
vor allem: **in den Hintergrund / wieder da**. Dazu der Update-Vorgang (nach
Update gesucht, Update angefordert, Sperre sichtbar, Server nicht erreichbar,
Server wieder da) und die Reihum-Suche mit jeder gefundenen Figur einzeln. Steht als letzte Zeile vor
einem Absturz „in den Hintergrund", war die Seite gar nicht im Vordergrund –
dann hat das Betriebssystem den Tab weggeräumt (typisch, während die
Kamera-App läuft), und nicht die App sich verschluckt.

Der Verlauf bleibt auf dem Gerät. „📋 Verlauf kopieren" legt ihn samt Spur als
Text in die Zwischenablage, um ihn woanders einzufügen.

**Issue auf Knopfdruck.** Ist ein GitHub-Token hinterlegt, legt „🐙 Issue
anlegen" aus einem Eintrag direkt ein Issue im Projekt an. Der Knopf wird
danach zu „Issue ansehen ↗"; ein zweiter Klick legt kein Duplikat an.
Ohne Token bleibt der Fehlerbericht trotzdem nutzbar – „📋 Bericht
kopieren" legt die ganze Liste als Text in die Zwischenablage, den man von
Hand irgendwo einfügen kann. „Liste leeren" räumt auf.

> **Wenn Kopieren nicht klappt.** Die Zwischenablage geben Browser nur
> ungern heraus: die moderne Schnittstelle nur an *sichere Kontexte*
> (`https://` oder `localhost`), den alten Weg nur unmittelbar nach einem
> Klick. Die App versucht deshalb **erst den alten, dann den modernen** –
> anders herum wäre der Rückfallweg wertlos, weil das Warten auf die moderne
> Schnittstelle den Klick „verbraucht".
>
> Klappt trotzdem keiner von beiden, ist der Text nicht verloren: Die App
> legt ihn in einem Fenster **fertig markiert** hin, Strg/Cmd+C genügt. Und
> die Meldung nennt den Grund in Klammern – der steht auch im Verlauf unter
> *Speicher-Verlauf*, falls es später jemand nachsehen will.

**Den Token anlegen** (einmalig, unter „GitHub-Token" in derselben Karte):
auf GitHub unter *Settings → Developer settings → Personal access tokens →
Fine-grained tokens* einen Token erzeugen, als **Repository access** nur
**dieses eine Repository** wählen und als einzige Berechtigung
**Issues: Read and write** setzen. Mehr braucht die App nicht – und mehr
sollte der Token auch nicht können. Er liegt danach in eurer Datenbank
und wird in der Oberfläche nie wieder angezeigt.

### 14.2 Wenn BrickLink eine Nummer ändert oder löscht

Der BrickLink-Katalog ist nicht in Stein gemeißelt: Nummern werden
umbenannt, doppelte Einträge zusammengelegt, selten auch gelöscht. Trifft
das einen Artikel aus eurer Sammlung, würde sein Preis stillschweigend auf
dem alten Stand einfrieren. Damit das nicht passiert, meldet sich die App.

**Wie sie es merkt.** Für jeden Artikel holt die App ohnehin alle sieben
Tage die Preise. Antwortet BrickLink für eine Nummer, die früher
funktioniert hat, plötzlich mit „unbekannt", ist etwas passiert. Eine von
Hand falsch eingetippte Nummer löst dagegen keinen Hinweis aus – die hat
nie funktioniert.

**Der Hinweis** erscheint oben im **Scannen**-Tab, also auf dem
Startbildschirm, und **bleibt dort stehen, bis ihn jemand über das ✕
wegklickt**. Er verschwindet nicht von selbst und taucht nach dem
Wegklicken auch nicht wieder auf – wer die Sache gesehen und entschieden
hat, soll nicht bei jedem Preislauf erneut gefragt werden.

**Die neue Nummer.** Nur wenn wirklich etwas fehlt, schaut die App in den
öffentlichen [BrickLink Catalog Change
Log](https://www.bricklink.com/catalogLogs.asp) und sucht dort ab dem
letzten erfolgreichen Preisabruf nach dem Nummernwechsel oder der
Zusammenlegung. Im Normalbetrieb wird diese Seite also gar nicht
angefasst. Wird sie fündig, nennt der Hinweis die neue Nummer und
**„Nummer übernehmen"** trägt sie überall ein: Sammlung, Wunschliste,
Einkaufslisten, die Set-Figuren-Verknüpfungen und den Preisverlauf.
Danach holt die App die Preise unter der neuen Nummer frisch.

**Findet der Log nichts** – etwa weil der Eintrag wirklich gelöscht wurde
–, bleibt der Hinweis trotzdem stehen, nur eben ohne neue Nummer. Nichts
geht verloren: Der Artikel bleibt mit seinem letzten bekannten Preis in
der Sammlung. Ihr könnt die Nummer dann von Hand über „BrickLink-Nr.
setzen" in den Karten-Details korrigieren.

### 14.3 Typische Stolpersteine

**Ein Update greift nicht / alte Oberfläche.** `sudo bash update.sh`
komplett durchgelaufen? Im Build-Log darf `COPY frontend/` nicht „CACHED"
sein, wenn sich Frontend-Dateien geändert haben. Welche Version läuft,
zeigt Mehr → 🔄 Version & Updates; danach reicht normales Neuladen.

**Preise fehlen bei einzelnen Artikeln.** Manuelle Nummern haben keine
BrickLink-Entsprechung. Frisch importierte Artikel werden in 40er-Häppchen
versorgt – Geduld oder im Detail-Popup das **↻** am Preisblock „Marktpreise"
drücken. Grundsätzlich keine Preise? → Mehr → API-Schlüssel → „Verbindung testen".

**Bedruckte Teile.** Die beiden Kataloge zählen Bedruckungen
unterschiedlich: Der Gungan-Schild heißt bei Rebrickable `2586pr0028` und
bei BrickLink `2586ps1`, der Karbonitblock `87561pr0001` bzw. `87561pb01`.
Die App schlägt die BrickLink-Nummer selbst nach, sobald die eigene nichts
ergibt, und merkt sie sich. Stammt der Preis von dieser Zweitnummer, steht
sie unter den Marktpreisen – sonst sucht man den Preis auf BrickLink unter
der eigenen Nummer vergebens. Dafür braucht es den
Rebrickable-Schlüssel; ohne ihn bleiben solche Teile ohne Preis.

**„Nur für Sammlerprofis" (403).** Die Funktion braucht die Profi-Rolle –
der Admin vergibt sie unter Mehr → Benutzer verwalten.

**Der Listen-Tab fehlt.** Bei Standard-Benutzern erscheint er nur, wenn
eine aktive Liste existiert; nach dem Archivieren der letzten Liste
verschwindet er wieder. Profis sehen ihn immer.

**Login klappt nicht mehr / Benutzer vergessen.** Das eigene Passwort
ändert man über das Profil-Popup (Name oben rechts antippen); vergessene
Passwörter setzt der Admin in der Benutzerverwaltung zurück. Ist der Admin selbst
ausgesperrt: letzte Sicherung einspielen oder `data/brickfolio.db` aus
einem Backup zurückkopieren.

**Kamera öffnet nicht.** PWA einmal schließen und neu öffnen;
Kamera-Berechtigung des Browsers prüfen. Auf iOS funktioniert der
Kamerazugriff nur über Safari bzw. die vom Home-Bildschirm installierte
App.

**Erkennung liefert Unsinn.** Besseres Licht, neutraler Hintergrund,
näher ran – oder einfach die Textsuche mit der Nummer vom Beinaufdruck /
der Bauanleitung nutzen.

---

## 15. FAQ

**Braucht Brickfolio Internet?** Für Scannen, Preise und Suche: ja (die
APIs liegen im Netz). Die eigenen Daten bleiben trotzdem komplett auf
eurem Server.

**Kostet BrickLink/Rebrickable etwas?** Nein, beide API-Zugänge sind
kostenlos – BrickLink verlangt nur ein Verkäuferkonto mit Shop.

**Kann mein Kind etwas kaputt machen?** Ohne Profi-/Admin-Rolle sieht es
weder Kaufpreise noch Listen-Verwaltung, Archiv oder Import – es kann
sammeln, wünschen und angekommene Artikel verbuchen. Und es gibt die
Sicherung. 🙂

**Woher kommen die Preise – und wie genau sind sie?** Es sind
BrickLink-Durchschnittspreise der letzten Verkäufe (neu/gebraucht
getrennt). Sie sind eine gute Orientierung, kein Gutachten – seltene
Zustände, Vollständigkeit und Region können real abweichen.

**Warum startet die Wertkurve so niedrig?** Die Aufzeichnung beginnt mit
der Einrichtung; anfangs sind erst wenige Artikel „bepreist". Sobald alle
Preise haben, zeigt die Kurve echte Marktbewegung.

**Mehrere Sammlungen/Familien?** Eine Brickfolio-Instanz = eine gemeinsame
Sammlung. Für getrennte Sammlungen einfach einen zweiten Container mit
eigenem `data/`-Ordner und Port starten.

**Ist das legal mit dem LEGO-Namen?** Brickfolio ist ein privates
Hobby-Projekt. LEGO® ist eine Marke der LEGO Gruppe, die dieses Projekt
weder sponsert noch autorisiert oder unterstützt; BrickLink und
Rebrickable sind Marken ihrer jeweiligen Inhaber, für deren APIs gelten
die jeweiligen Nutzungsbedingungen.

---

## 16. Anhang

### 16.1 Symbole auf einen Blick

| Symbol | Bedeutung |
|---|---|
| ⚙️ | Kaufpreis automatisch (BrickLink-Ø; Datum im Tooltip) |
| ✏️ | Kaufpreis manuell eingetragen |
| 👥 3/4 (✔) | 3 von 4 Set-Figuren vorhanden (✔ = komplett) |
| 📦 | „steckt in euren Sets" bzw. Archiv |
| ⭐ / ☆ | steht auf der Wunschliste / merken |
| 🛒 auf »…« | Artikel ist auf einer aktiven Einkaufsliste eingeplant |
| gelber Set-Link mit ✔ | dieses Set ist in eurer Sammlung |
| ✔ (ausgegraut) | Listen-Artikel wurde in die Sammlung verbucht |
| 🛒 | auf eine Einkaufsliste legen |
| 🐞 | Fehlerbericht (nur Admin, unter „Mehr") |

### 16.2 Umgebungsvariablen

| Variable | Bedeutung |
|---|---|
| `ADMIN_USER` / `ADMIN_PASSWORD` | Optional: Admin automatisch anlegen (sonst Ersteinrichtung im Browser) |
| `BACKUP_KEEP` | Automatische tägliche Sicherungen aufbewahren (Standard 14, 0 = aus) |
| `DB_PATH` | Pfad zur SQLite-Datei (Default: `/data/brickfolio.db`) |
| `BL_CONSUMER_KEY` / `BL_CONSUMER_SECRET` / `BL_TOKEN` / `BL_TOKEN_SECRET` | BrickLink-Store-API (Fallback zu den App-Einstellungen) |
| `REBRICKABLE_KEY` | Rebrickable-API (Fallback zu den App-Einstellungen) |
| `GITHUB_REPO` | Ziel-Repository für Issues aus dem Fehlerbericht (Default: `Melle79/brickfolio`) |

### 16.3 CSV-Import: erkannte Spaltennamen

| Feld | erkannte Namen |
|---|---|
| Nummer *(Pflicht)* | Nummer, item_id, no, number |
| Typ | Typ, type (Werte: Figur/minifig/fig, Set, Teil/part) |
| Name | Name |
| Anzahl | Anzahl, Menge, qty, quantity |
| Zustand | Zustand, condition (Neu/new, Gebraucht/used) |
| Bezahlt | Bezahlt, Kaufpreis, Einkauf, paid |
| Jahr | Jahr, year |
| Notizen | Notizen, notes, Bemerkung |

---

*Viel Spaß beim Sammeln! Fragen, Fehler oder Ideen gern als Issue auf
[github.com/Melle79/brickfolio](https://github.com/Melle79/brickfolio).* 🧱
