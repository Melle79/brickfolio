# Finn's Brickfolio – Das Handbuch

*Version 1.9 · Juli 2026 · für Brickfolio ab Release v1.9.8*

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
12. [Die Preis-Automatik im Detail](#12-die-preis-automatik-im-detail)
13. [Fehlerbehebung](#13-fehlerbehebung)
14. [FAQ](#14-faq)
15. [Anhang](#15-anhang)

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
Docker-Container auf eurem eigenen Server (FastAPI + SQLite), ohne Cloud,
ohne Konto bei Dritten. Mehrere Familienmitglieder teilen sich eine
Datenbank, jeder mit eigenem Login.

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

```bash
git clone https://github.com/Melle79/brickfolio.git
cd brickfolio
cp docker-compose.example.yml docker-compose.yml
docker compose up -d --build
```

Danach ist die App unter `http://<server>:8300` erreichbar. Die Datenbank
liegt persistent unter `./data/brickfolio.db` – dieser Ordner überlebt
Updates und Container-Neubauten.

**Port ändern / mehrere Instanzen:** Der erreichbare Port ist die *erste*
Zahl im `ports`-Mapping der `docker-compose.yml` – `"8301:8300"` macht die
App unter Port 8301 erreichbar (die zweite Zahl bleibt immer 8300). So
lassen sich auch mehrere Brickfolio-Instanzen parallel betreiben, z. B.
für getrennte Sammlungen oder eine Testinstallation: eigener Ordner,
eigener `container_name`, eigener Port – jede Instanz hat ihren eigenen
`data/`-Ordner und damit ihre eigene Datenbank.

**Ohne git** (viele NAS-Systeme, etwa Synology, haben kein git an Bord)
lädt man den aktuellen Stand als Archiv:

```bash
mkdir brickfolio && cd brickfolio
curl -sL https://github.com/Melle79/brickfolio/archive/refs/heads/main.tar.gz | tar xz --strip-components=1
cp docker-compose.example.yml docker-compose.yml
docker compose up -d --build
```

**Synology-Hinweis:** Ordner unter `/volume1/docker/brickfolio` anlegen und
alle Befehle per SSH mit `sudo` ausführen – bei der curl-Variante als
`sudo sh -c 'curl … | tar …'`, damit die gesamte Pipe mit Rechten läuft.

### 2.3 Erster Start: die Ersteinrichtung

Beim ersten Aufruf im Browser begrüßt dich Brickfolio mit der
**Ersteinrichtung**: Benutzername und Passwort für das Admin-Konto wählen,
„Admin-Konto anlegen" – du bist direkt angemeldet. Der Bildschirm
erscheint nur, solange noch kein Benutzer existiert; danach kommt immer
der normale Login.

*Für unbeaufsichtigte Setups:* Sind die Umgebungsvariablen
`ADMIN_USER`/`ADMIN_PASSWORD` gesetzt, legt Brickfolio den Admin beim
allerersten Start automatisch an und überspringt die Ersteinrichtung.

Als Nächstes: die API-Schlüssel einrichten.

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

> **Handy oder Rechner?** Die Navigation liegt auf dem **Handy als Leiste
> unten**, auf **breiten Bildschirmen als Seitenleiste links**. Dort nutzt
> die App die Fläche: Kennzahlen nebeneinander und in der Sammlung vier bis
> fünf Karten pro Reihe im Raster. Es ist dieselbe App – sie ordnet sich nur
> je nach Bildschirmbreite anders an, ohne dass man etwas umstellen muss.

Der Tab **Mehr** ist nach Themen sortiert (Karten per Antippen der
Überschrift auf- und zuklappbar; die App merkt sich den Zustand) – je
nach Rolle sichtbar:

| Karte | sichtbar für |
|---|---|
| 🎨 Design | alle |
| 📤 Export & Druck | alle |
| 📈 Preis-Protokoll | Sammlerprofi |
| 💼 Sammlerprofi (Angebots-Vorschlag, CSV-Import) | Sammlerprofi |
| 🏷 Anzeigename | Admin |
| 🔑 API-Schlüssel | Admin |
| 👥 Benutzer verwalten | Admin |
| 💾 Sicherung | Admin |
| 🌍 Preisgebiet | Admin |
| 🔄 Version & Updates | Admin |
| ℹ️ Quellen & Rechtliches | alle |

**🎨 Design** bietet drei Aussehen: **Klassisch** (hell, LEGO-Farben),
**Galaxie** (dunkel, mit Sternenhimmel und leuchtenden Akzenten) und
**Nova** (modernes Glas-Design – tiefdunkler, blau schimmernder Hintergrund,
durchscheinende Flächen und blauer Akzent). Die Wahl gilt **pro Gerät** und
wird gemerkt – auf dem Handy also unabhängig vom Rechner.

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

---

## 3. Benutzer & Rollen

Brickfolio kennt drei Stufen, die sich kombinieren lassen:

| Aktion | Standard | Sammlerprofi 💼 | Admin 🔧 |
|---|:-:|:-:|:-:|
| Scannen, Sammlung, Wünsche, Statistik | ✔ | ✔ | ✔ |
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

### 4.2 Per Suche (Katalog)

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
**✏️ Manuell erfassen** mit freiem Namen, eigener Nummer (z. B.
`manuell-01`), Typ, Menge, Zustand, optionalem **„Bezahlt €"** (Kaufpreis)
und Notizen. Solche Einträge bekommen keine automatischen Marktpreise –
der eingetragene Kaufpreis und die Notizen funktionieren normal.

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
und stehen nach dem Schließen auch in der Liste. Im Popup zeigt sich:

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
- **Bild antippen** öffnet die Großansicht.
- **Löschen** über den **Papierkorb bei der Anzahl** (erscheint, sobald
  nur noch eines übrig ist) – mit Sicherheitsabfrage.

#### Bild fehlt oder passt nicht?

Unten rechts am Bild sitzt ein kleines **↻-Symbol**. Es holt das aktuelle
Katalogbild von BrickLink und speichert es dauerhaft – praktisch bei
Einträgen, die ohne Bild in die Sammlung gekommen sind (etwa über den
CSV-Import).

*(Voraussetzung: hinterlegter BrickLink-Schlüssel.)*

### 5.3 Sets und ihre Figuren

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

### 5.4 Kaufpreise & Gewinn *(Sammlerprofi)*

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

Darunter rechnet die **Gewinnzeile** live: *Bezahlt 12,50 € · Wert
47,60 € · **+35,10 €*** (grün = Gewinn, rot = Verlust; Wert = aktueller
Ø-Preis × Menge).

---

## 6. Die Wunschliste

Der Tab **Wünsche** sammelt alles Gemerkte – mit Bild, Ø-Preisen und
Widgets, die die geschätzten Anschaffungskosten (gebraucht/neu) summieren.

- **✔ Gekauft!** fragt den Zustand ab und verschiebt den Artikel in die
  Sammlung. *Profis* können dabei den echten Kaufpreis eintragen (leer =
  BrickLink-Ø, automatisch ⚙️).
- **Nummer korrigieren:** In den Details lässt sich eine falsche Nummer
  ersetzen („Setzen") oder automatisch suchen („🔍 Auto") – die Preise
  werden danach sofort neu geholt.
- Artikel, die ihr schon besitzt, tragen ein Besitz-Badge – praktisch
  gegen Doppelkäufe.
- Gehört eine gemerkte Figur zu einem **Set aus eurer Sammlung** und fehlt
  dort noch, steht auf der Karte **🧩 fehlt zu eurem Set: <Setname>**. Ein
  Tipp auf das Set springt direkt dorthin in die Sammlung.

---

## 7. Einkaufslisten – der Flohmarkt-Modus

Das Herzstück für Sammlerprofis: strukturiert einkaufen mit
Marktwert-Wissen. Standard-Benutzer sehen aktive Listen und dürfen
angekommene Artikel verbuchen; alles andere ist Profi-Sache.

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
**Archiv** 🎉. Nur Profis sehen es („📦 Archiv anzeigen"), können Listen
reaktivieren, von Hand archivieren oder löschen – und Verbuchungen
**rückgängig** machen (↩︎; der Sammlung-Eintrag bleibt dabei bewusst
bestehen und wird bei Bedarf manuell angepasst).

---

## 8. Die Verkaufsliste (Doppelte)

*(Nur Sammlerprofi – Knopf „📋 Verkaufsliste (Doppelte)" im Listen-Tab.)*

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
- **Top 10 nach Wert** mit Bildern – und für Profis die **besten
  Wertsteigerungen** (aktueller Wert minus Kaufpreis, Top 5).

---

## 10. CSV-Import, Export & Druck

*(Export & Druck unter Mehr → 📤 Export & Druck; der CSV-Import wohnt
in der Karte Mehr → 💼 Sammlerprofi.)*

### 10.1 Export & Druck (alle Benutzer)

Sammlung und Wunschliste als **CSV** (Semikolon-getrennt, deutsche
Zahlenformate, Excel-/Numbers-tauglich) oder als **Druckansicht** – eine
aufgeräumte Tabelle mit Seitenumbrüchen, ideal für Versicherung oder
Vitrine.

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
automatisch im Hintergrund nach (siehe Kapitel 12) – bei großen Importen
dauert das einige Zeit.

---

## 11. Sicherung, Wiederherstellung & Updates

### 11.1 Sicherung (Admin)

**Mehr → Sicherung → 💾 herunterladen** erzeugt eine JSON-Datei mit
*allem*: Benutzer (inkl. Passwort-Hashes), Sammlung, Wunschliste,
Einkaufslisten, Preisverläufe, Set-Zuordnungen und Einstellungen.
**📥 einspielen** stellt diesen Stand komplett wieder her – nach
Sicherheitsabfrage mit Datum; **alle aktuellen Daten werden ersetzt**.
Sicherungen ohne Admin-Benutzer werden abgelehnt (Aussperr-Schutz).

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

Eingespielt wird mit einem Befehl auf dem Server:

```bash
cd /pfad/zu/brickfolio
sudo bash update.sh
```

Das Skript legt zuerst einen **Datenbank-Schnappschuss** an (die letzten
drei bleiben erhalten), holt dann den aktuellen Stand von GitHub (ohne
git, per Tarball – eure `docker-compose.yml` und der `data/`-Ordner
bleiben unberührt) und baut den Container neu. Datenbank-Migrationen
laufen beim Start automatisch und sind idempotent – mehrfaches
Aktualisieren schadet nie.

#### Update direkt aus der App *(optional)*

Mit einem kleinen Helfer auf dem Server geht es auch ohne SSH: In der
Karte **Version & Updates** stehen dann die Knöpfe **Jetzt**, **In 1
Minute** und **In 5 Minuten**.

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

## 12. Die Preis-Automatik im Detail

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

### 12.1 Preisgebiet: weltweit oder deutschsprachiger Raum

BrickLink liefert standardmäßig den **weltweiten** Durchschnitt. Unter
**Mehr → 🌍 Preisgebiet** (Admin) lässt sich stattdessen ein Markt wählen:
**Deutschland**, **Österreich**, **Schweiz** oder **Europa**.

**Wichtig – der zweistufige Rückfall:** Gerade bei selteneren Figuren gibt
es in einem einzelnen Land oft **gar keine Verkäufe**. Findet BrickLink im
gewählten Gebiet nichts, weitet die App automatisch aus – **erst auf
Europa, dann auf weltweit**. Der erste Markt mit echten Verkäufen zählt.
So bleibt kein Artikel ohne Preis; die Bewertung ist dann eben gemischt.
(Ist Europa oder weltweit direkt eingestellt, entfällt die jeweils engere
Stufe.)

**Woran man einen ausgewichenen Preis erkennt:** Stammt ein Ø-Preis nicht
aus dem eingestellten Gebiet, steht eine kleine **Flagge** daneben – 🇪🇺 für
Europa, 🌍 für weltweit. In der Detail-Preiskarte erklärt ein Tooltip den
Grund. Preise aus dem eingestellten Gebiet bleiben ohne Flagge, sind also
auf einen Blick als „echt deutsch" (bzw. österreichisch/schweizerisch)
erkennbar.

**Bestehende Sammlung umstellen.** Nach dem Wechsel stammen alle
gespeicherten Preise noch aus dem alten Gebiet. Die Karte zeigt deshalb,
wie viele Artikel betroffen sind, und bietet **🔄 Preise jetzt umrechnen**.

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

### 12.2 Das Preis-Protokoll

**Mehr → 📈 Preis-Protokoll** *(Sammlerprofi)* listet die jüngsten
Aufzeichnungen mit Zeitpunkt, Artikel, Preisen und Quelle (`auto` oder
`manuell`). Darüber steht, **bei wie vielen Artikeln der Preisabruf älter
als sieben Tage ist** – so seht ihr auf einen Blick, wie aktuell die
Bewertung eurer Sammlung ist. Sind alle Preise frisch, steht dort
stattdessen eine Bestätigung.

---

## 13. Fehlerbehebung

### 13.1 Der Fehlerbericht (Admin)

Geht in der App etwas kaputt, muss niemand mehr aufschreiben, „was da
stand". Jeder Fehler im Browser wird automatisch im Hintergrund an den
eigenen Server gemeldet und sammelt sich unter **Mehr → 🐞 Fehlerbericht**
– auch die von den Geräten der Kinder. Pro Eintrag stehen dort Fehlertext,
Stelle im Code, wie oft er auftrat, wann zuletzt, welche App-Version und
welcher Browser; unter „Details" die vollständigen Angaben.

**Gleichartige Fehler werden zusammengefasst.** Ein Fehler, der bei jedem
Seitenaufruf auftritt, erzeugt keine hundert Einträge, sondern einen mit
Zähler. Die Liste hält die letzten 100 verschiedenen Fehler.

**Was nicht gemeldet wird:** API-Schlüssel und der GitHub-Token werden aus
jedem Text entfernt (`***`), bevor er gespeichert oder verschickt wird.
Die Meldung geht ausschließlich an euren eigenen Server – nach außen geht
nur, was ihr selbst per Issue verschickt.

**Issue auf Knopfdruck.** Ist ein GitHub-Token hinterlegt, legt „🐙 Issue
anlegen" aus einem Eintrag direkt ein Issue im Projekt an. Der Knopf wird
danach zu „Issue ansehen ↗"; ein zweiter Klick legt kein Duplikat an.
Ohne Token bleibt der Fehlerbericht trotzdem nutzbar – „📋 Bericht
kopieren" legt die ganze Liste als Text in die Zwischenablage, den man von
Hand irgendwo einfügen kann. „Liste leeren" räumt auf.

**Den Token anlegen** (einmalig, unter „GitHub-Token" in derselben Karte):
auf GitHub unter *Settings → Developer settings → Personal access tokens →
Fine-grained tokens* einen Token erzeugen, als **Repository access** nur
**dieses eine Repository** wählen und als einzige Berechtigung
**Issues: Read and write** setzen. Mehr braucht die App nicht – und mehr
sollte der Token auch nicht können. Er liegt danach in eurer Datenbank
und wird in der Oberfläche nie wieder angezeigt.

### 13.2 Wenn BrickLink eine Nummer ändert oder löscht

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

### 13.3 Typische Stolpersteine

**Ein Update greift nicht / alte Oberfläche.** `sudo bash update.sh`
komplett durchgelaufen? Im Build-Log darf `COPY frontend/` nicht „CACHED"
sein, wenn sich Frontend-Dateien geändert haben. Welche Version läuft,
zeigt Mehr → 🔄 Version & Updates; danach reicht normales Neuladen.

**Preise fehlen bei einzelnen Artikeln.** Manuelle Nummern haben keine
BrickLink-Entsprechung. Frisch importierte Artikel werden in 40er-Häppchen
versorgt – Geduld oder im Detail-Popup das **↻** am Preisblock „Marktpreise"
drücken. Grundsätzlich keine Preise? → Mehr → API-Schlüssel → „Verbindung testen".

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

## 14. FAQ

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

## 15. Anhang

### 15.1 Symbole auf einen Blick

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

### 15.2 Umgebungsvariablen

| Variable | Bedeutung |
|---|---|
| `ADMIN_USER` / `ADMIN_PASSWORD` | Optional: Admin automatisch anlegen (sonst Ersteinrichtung im Browser) |
| `BACKUP_KEEP` | Automatische tägliche Sicherungen aufbewahren (Standard 14, 0 = aus) |
| `DB_PATH` | Pfad zur SQLite-Datei (Default: `/data/brickfolio.db`) |
| `BL_CONSUMER_KEY` / `BL_CONSUMER_SECRET` / `BL_TOKEN` / `BL_TOKEN_SECRET` | BrickLink-Store-API (Fallback zu den App-Einstellungen) |
| `REBRICKABLE_KEY` | Rebrickable-API (Fallback zu den App-Einstellungen) |
| `GITHUB_REPO` | Ziel-Repository für Issues aus dem Fehlerbericht (Default: `Melle79/brickfolio`) |

### 15.3 CSV-Import: erkannte Spaltennamen

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
