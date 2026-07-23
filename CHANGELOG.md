# Changelog

## 1.9.4 – Juli 2026

### Behoben
- 🔑 Das Lebenszeichen des Update-Helfers wird jetzt ausdrücklich lesbar angelegt (`644`). Je nach Einstellung des Servers legte root es sonst als `600` an – dann hätte die App es nicht gelesen, sobald der Container einmal nicht als root läuft, und hätte fälschlich „Helfer nicht eingerichtet" gemeldet

## 1.9.3 – Juli 2026

### Behoben
- 🛠 Lief `update-watch.sh` ohne Root-Rechte, brach es mit einem nichtssagenden „Permission denied" ab. Jetzt erklärt es im Klartext, dass es als `root` laufen muss (von Hand mit `sudo`, im Aufgabenplaner unter „Allgemein"). Der `data`-Ordner gehört Docker und damit root – für `docker compose` braucht das Skript diese Rechte ohnehin

## 1.9.2 – Juli 2026

### Verbessert
- 🔎 Meldet sich der Update-Helfer nicht, sagt die App jetzt **woran es liegt**: entweder „hat sich noch **nie** gemeldet" (dann stimmt meist der Pfad im Skriptfeld nicht oder die Aufgabe läuft nicht als `root`) oder „lief zuletzt **vor X Stunden**" (dann ist sie eingerichtet, läuft aber nicht jede Minute – häufigster Grund: „Letzte Ausführungszeit" steht auf `00:59` statt `23:59`)

## 1.9.1 – Juli 2026

### Verbessert
- 🔒 **Schrift wird jetzt mitgeliefert** statt vom Google-CDN geladen. Damit werden beim Öffnen der App **keine Besucherdaten mehr an Dritte übertragen** – und die App funktioniert auch ohne Internet vollständig, denn bisher fehlte offline die Schrift (Nunito, SIL Open Font License 1.1)
- ℹ️ Neue Karte **Mehr → Quellen & Rechtliches**: woher Daten und Bilder stammen (Rebrickable, BrickLink, Brickognize), der Hinweis, dass beim Abfotografieren das Foto zur Erkennung übertragen wird, sowie Marken-, Schrift- und Lizenzangaben. Brickognize ist jetzt auch im README genannt

## 1.9.0 – Juli 2026

### Neu
- 🚀 **Update aus der App anstoßen** (Mehr → Version & Updates, nur Admin): sofort, in 1 oder in 5 Minuten. Alle angemeldeten Browser zeigen einen Countdown („bitte Eingaben abschließen"), danach einen Sperrbildschirm – und laden sich selbst neu, sobald der Server wieder da ist. Solange der Countdown läuft, lässt sich das Update abbrechen

  Die App führt das Update **nicht selbst** aus: Sie legt nur eine Markierung im Datenverzeichnis ab, die der neue Helfer `update-watch.sh` auf dem Server aufgreift. So braucht die App keinen Docker-Zugriff (das wäre faktisch Root auf dem Server)

  **Vollständig optional**: Ohne Einrichtung ändert sich nichts. Der Helfer hinterlässt bei jedem Lauf ein Lebenszeichen – nur wenn das frisch ist, bietet die App das Update überhaupt an. Sonst steht dort lediglich ein Hinweis, wie man es einrichten kann. Anleitung (auch für mehrere Instanzen) im README

## 1.8.4 – Juli 2026

### Verbessert
- ⚡ **Sammlung lädt deutlich schneller**: Ein fehlender Datenbank-Index sorgte dafür, dass die Zuordnung „steckt in diesen Sets" für jeden Eintrag die ganze Set-Tabelle durchsuchen musste. Gemessen bei 800 Figuren und 250 Sets: **49 ms → 3 ms**. Der Index wird beim nächsten Start automatisch angelegt

### Behoben
- 🔎 In den Suchergebnissen bekamen nur die **ersten 8 Treffer** ihre Kennzeichnung („✔ in Sammlung", „🧩 fehlt zu eurem Set"). Seit der Umstellung auf 10 Treffer pro Seite plus Nachladen fehlte sie damit ausgerechnet bei den späteren Treffern – jetzt werden alle angezeigten gekennzeichnet

### Sonstiges
- ✅ Testabdeckung von 28 auf **48 Fälle** erweitert: fehlende Set-Figuren, Katalogsuche mit Seiten, Kennzahl „Preisabruf älter als 7 Tage"

## 1.8.3 – Juli 2026

### Neu
- 🖼 **Bild nachladen** für Einträge in der Sammlung: Fehlt einem Eintrag das Bild (oder passt es nicht), holt ein Knopf im Detailbereich das aktuelle Katalogbild von BrickLink. Bisher ging das nur bei Einträgen ganz ohne BrickLink-Nummer

## 1.8.2 – Juli 2026

### Behoben
- 🖼 Der Knopf **„Namen & Bilder nachladen"** stand ganz am Ende der Liste und war bei vielen fehlenden Figuren praktisch unerreichbar – er steht jetzt **oben**, direkt unter der Überschrift
- 🔄 `app.js` wurde beim Ausliefern nie neu versioniert; Geräte konnten dadurch eine ältere Programmversion aus dem Zwischenspeicher behalten
- 🧱 Bilder, die sich nicht laden lassen, zeigen jetzt den Baustein-Platzhalter statt eines kaputten Symbols

## 1.8.1 – Juli 2026

### Behoben
- 🖼 In der Übersicht „Fehlende Set-Figuren" fehlten bei vielen Einträgen **Name und Bild** (nur die Nummer war zu sehen). Ursache: Diese Angaben kommen aus dem gespeicherten Set-Inhalt, der bei älteren Sammlungen noch ohne sie angelegt wurde. Statt sie still im Hintergrund und stark gedrosselt nachzuladen, zeigt die App jetzt offen an, bei wie vielen Sets Details fehlen – mit dem Knopf **„🔄 Namen & Bilder nachladen"**, der sie mit Fortschrittsanzeige holt

## 1.8.0 – Juli 2026

### Neu
- 🧩 **Übersicht „Fehlende Set-Figuren"** (Listen): zeigt über alle eigenen Sets hinweg, welche Minifiguren noch fehlen – mit Anzahl, zugehörigen Sets, geschätztem Nachkaufpreis und Aktionen (einzeln oder alle auf die Wunschliste, CSV, Drucken). Der Bedarf berücksichtigt, wie oft ihr ein Set besitzt
- 🔎 **Suchergebnisse markieren fehlende Set-Figuren**: Gehört eine gefundene Figur zu einem eurer Sets und fehlt dort noch, steht statt „in Sets" jetzt deutlich **„fehlt zu eurem Set"** – praktisch beim Stöbern auf dem Flohmarkt

### Sonstiges
- Set-Inhalte speichern jetzt auch Name und Bild der Figuren, damit die Übersicht ohne BrickLink-Abruf funktioniert (ältere Einträge werden im Hintergrund nachgezogen)

## 1.7.1 – Juli 2026

### Behoben
- 🖼 Im Design „Galaxie" wirkten die **Bildflächen unruhig**: Katalogfotos bringen meist einen weißen Hintergrund mit, der als heller Block auf der dunklen Kachel stand. Die Bildkachel ist dort jetzt weiß, sodass Foto und Fläche nahtlos verschmelzen

## 1.7.0 – Juli 2026

### Neu
- 🌌 **Zweites Design „Galaxie"**: ein dunkles, weltraum-inspiriertes Aussehen mit Sternenhimmel und leuchtenden Akzenten – umschaltbar unter **Mehr → Design**. „Klassisch" bleibt Standard, die Auswahl gilt pro Gerät und wird gemerkt

### Behoben
- 🖨 In den **Druckexporten** (Sammlung, Wunschliste, Verkaufsliste) stand in der Kopfzeile immer „Finn's Brickfolio" – jetzt erscheint dort der eingestellte Anzeigename

## 1.6.21 – Juli 2026

### Verbessert
- 🔍 Suchfelder mit **Lupen-Icon** statt „Suchen"-Text – der Platzhalter lautet jetzt kurz „Name oder Nummer" und wird nicht mehr abgeschnitten
- 🔍 Auch das Namensfeld beim **manuellen Erfassen** hat jetzt das Lupen-Icon
- ✕ **Löschen-Knopf** in beiden Suchfeldern: leert die Eingabe mit einem Tipp und stellt die vollständige Liste wieder her

## 1.6.20 – Juli 2026

### Verbessert
- 🔎 Katalogsuche: **10 Treffer pro Seite** (statt 20), „Weitere Ergebnisse laden" holt jeweils 10 nach
- 🏷 Beim manuellen Erfassen steht der **Typ (Minifigur/Teil/Set) jetzt direkt neben dem Namensfeld**

## 1.6.19 – Juli 2026

### Verbessert
- 🔎 Die **Katalogsuche** zeigt jetzt alle Treffer seitenweise: 20 pro Seite mit Anzeige „X von Y" und einem Knopf **„Weitere Ergebnisse laden"** (statt nur 8 fester Treffer)

## 1.6.18 – Juli 2026

### Verbessert
- 🔎 Die **Katalog-/Namenssuche** (neue Figuren/Sets) startet erst ab **3 Zeichen** – bei kürzerer Eingabe erscheint ein kurzer Hinweis. Das vermeidet unnötige Suchanfragen bei 1–2 Zeichen

## 1.6.17 – Juli 2026

### Verbessert
- 🕒 Das **Preis-Protokoll** (Mehr) zeigt jetzt an, bei wie vielen Artikeln in der Sammlung der Preisabruf älter als 7 Tage ist

## 1.6.16 – Juli 2026

### Neu
- 🧩 **Wunschliste zeigt fehlende Set-Figuren**: Steht eine Figur auf der Wunschliste, die zu einem Set in eurer Sammlung gehört und die ihr noch nicht habt, wird sie mit „fehlt zu eurem Set" gekennzeichnet – ein Tipp auf das Set springt direkt dorthin

## 1.6.15 – Juli 2026

### Behoben
- 📐 In der **Raster-Ansicht** sind zwei Karten einer Reihe jetzt immer gleich hoch (die kürzere dehnt sich auf die Höhe der höheren), statt unterschiedlich hoch zu stehen

## 1.6.14 – Juli 2026

### Verbessert
- 🧱 Die Lade-Anzeige der Sammlung zeigt jetzt einen **drehenden Klemmbaustein** statt eines Kreises

### Behoben
- 🎯 Die Lade-Anzeige ist in der **Raster-Ansicht** wieder mittig (war nach links versetzt)

## 1.6.13 – Juli 2026

### Verbessert
- ⚡ **Sammlung öffnet spürbar flüssiger**: Die Karten laden zunächst nur den Kopf; der Detailbereich einer Karte wird erst beim Aufklappen erzeugt. Dadurch entstehen bei großen Sammlungen rund **70 % weniger Seitenelemente**, und die Ansicht reagiert beim Öffnen (Antippen, Suchen) fast sofort statt erst nach ein paar Sekunden

## 1.6.12 – Juli 2026

### Verbessert
- ⏳ **Lade-Anzeige in der Sammlung**: Beim Öffnen des Sammlung-Tabs erscheint sofort ein Spinner „Sammlung wird geladen …", bis die Liste aufgebaut ist – kein irritierender Moment mehr, in dem die Ansicht wie eingefroren wirkt. Die Suchleiste ist dabei bereits nutzbar

## 1.6.11 – Juli 2026

### Behoben
- ✅ **Kein doppeltes Nachfragen des Zustands** beim Verbuchen aus einer Liste: „Da! Ab in die Sammlung" übernimmt jetzt direkt den bereits am Listeneintrag gewählten Zustand (neu/gebraucht). Sammlerprofis bestätigen nur noch den Einkaufspreis, alle anderen verbuchen mit einem Klick

## 1.6.10 – Juli 2026

### Sonstiges
- ✅ **Automatisierte Tests** für die fehleranfälligsten Bereiche (Ø-Preis-Fallback, Doppelzählung von Set-Figuren, anteilige Angebotsverteilung, Verbuchen/Rückgängig von Einkaufslisten) samt **CI**, die bei jedem Push und Pull Request läuft
- 🧹 Aufräumarbeiten im Backend (doppelte Setup-/Me-Routen entfernt, Rechenkern der Angebotsverteilung in eine testbare Funktion gelöst) – keine Änderung am Verhalten

## 1.6.9 – Juli 2026

### Neu
- 👥 **Figuren beim Set übernehmen**: Kommt ein Set in die Sammlung (Foto, Suche, Wunschliste, Einkaufsliste oder manuell), fragt die App, welche der enthaltenen Minifiguren dabei sind – alle, keine oder eine Auswahl, mit eigener Zustandswahl

### Geändert
- 💶 **Wertberechnung ohne Doppelzählung**: In eigenen Sets steckende Figuren sind im Set-Preis schon enthalten und zählen im Gesamtwert nicht mehr doppelt. Beim Filter „Figuren" (oder „Sets") erscheint weiterhin der volle Wert dieser Gruppe; Stückzahl, Top 10 und bezahlt/Gewinn bleiben unverändert
- ❓ Die Wertberechnung ist jetzt in der Hilfe und im Handbuch ausführlich erklärt; die Statistik weist den herausgerechneten Betrag offen aus

## 1.6.8 – Juli 2026

### Behoben
- 📊 Das Diagramm „Wert nach Erscheinungsjahr" reagiert jetzt auch auf **Antippen** (Touch): Jahr, Wert und Stückzahl erscheinen unter dem Diagramm, der gewählte Balken wird hervorgehoben

### Sonstiges
- 🇬🇧 Englisches README mit Sprach-Umschalter und aktualisierten Screenshots

## 1.6.7 – Juli 2026

### Neu
- 🗒 Beim Verbuchen von einer Liste wird der Listenname in die Notizen des Sammlungs-Eintrags übernommen (vorhandene Notiz bleibt erhalten)

### Behoben
- 📋 Verkaufsliste beschriftet zurückbehaltene Figuren jetzt korrekt: „für Sets reserviert" nur bei echtem Set-Bedarf, sonst „1 behalten"

## 1.6.6 – Juli 2026

### Neu
- 🏷 Konfigurierbarer Anzeigename in Logo und Fenstertitel (Mehr → Anzeigename, Admin); Standard bleibt „Finn"

## 1.6.5 – Juli 2026

### Neu
- 💶 Kaufpreis („Bezahlt") direkt beim Abfotografieren und manuellen Erfassen

## 1.6.4 – Juli 2026

### Neu
- 📇 Raster-Ansicht für die Sammlung (2 pro Reihe, Mengen-Badge, Auswahl wird gemerkt)
- 🔢 Im Raster steht beim Öffnen die Mengeneinstellung oben

## 1.6.3 – Juli 2026

### Neu
- 🖼 Scannen per Drag & Drop und Zwischenablage (Strg/Cmd+V)

### Verbessert
- 💶 Einkaufspreis direkt im 🛒-Dialog
- 📈 Manuelle Preisabrufe aktualisieren den jüngsten Verlaufspunkt

### Behoben
- Karten-Zahlen nach manuellem Preisabruf sofort aktuell (NaN-Fix)

## 1.6.2 – Juli 2026

### Verbessert
- 🕒 Uhrzeit an den automatischen Sicherungen in der Auswahlliste

## 1.6.1 – Juli 2026

### Verbessert
- 💶 Einkaufspreis direkt im 🛒-Dialog erfassbar
- 📈 Manuelle Preisabrufe aktualisieren den jüngsten Verlaufspunkt
- 🛡 Zustands-Migration gehärtet

### Behoben
- Karten-Zahlen nach manuellem Preisabruf sofort aktuell (NaN-Fix)

## 1.6.0 – Juli 2026

### Neu
- 🏷 Getrennte Sammlung-Einträge je Zustand (automatische Migration)
- ♻️ Zusammenführen beim Zustandswechsel auf einen vorhandenen Zustand
- 📦 Verkaufslisten-Reservierung je Figur über beide Zustände

## 1.5.1 – Juli 2026

### Verbessert
- 🛒 Einkaufslisten-Karten einklappbar (standardmäßig zu, Zustand wird gemerkt)

## 1.5.0 – Juli 2026

### Neu
- 💾 Automatische tägliche Sicherung nach data/backups/ (BACKUP_KEEP, Standard 14)
- ↩️ Tagesstände direkt in der App wiederherstellen (mit automatischer Sicherheitskopie)
- ⬇️ Tagesstände aus der App herunterladen

### Verbessert
- 🗂 Mehr-Tab-Karten aufklappbar (Zustand wird gemerkt)

## 1.4.6 – Juli 2026

### Verbessert
- 📸 README mit Screenshots
- 🔄 Update-Hinweis mit generischem Pfad

## 1.4.5 – Juli 2026

### Verbessert
- ✏️ Einkaufslisten umbenennen (Stift am Listennamen, Sammlerprofi)
- ✔ Verbuchen-Knopf heißt jetzt „Da! Ab in die Sammlung"

## 1.4.4 – Juli 2026

### Verbessert
- 🗂 Mehr-Tab aufgeräumt: klare Karten für Export, Sammlerprofi, API-Schlüssel, Benutzer, Sicherung und Version

## 1.4.2 – Juli 2026

### Verbessert
- 👤 **Profil als Popup**: Der Anmeldename oben rechts ist antippbar und öffnet Anzeigename ändern, Passwort ändern und Abmelden – der Mehr-Tab ist entsprechend aufgeräumt
- ❓ Hilfe-Knopf sitzt wieder rechts neben dem Namen

## 1.4.1 – Juli 2026

### Verbessert
- ❓ **Hilfe als Popup**: Über den ?-Knopf im Header von jedem Tab aus erreichbar – als Overlay mit allen Abschnitten; die bisherige Hilfe-Karte im Mehr-Tab entfällt

## 1.4.0 – Juli 2026

### Neu
- 🛒 **Listen-Hinweis beim Scannen**: Vorschläge zeigen ein Badge, wenn der Artikel bereits auf einer aktiven Einkaufsliste steht – Schutz vor Doppel-Einplanung am Stand
- 🏷 **Zustandswahl beim Drauflegen**: Im 🛒-Dialog lässt sich Gebraucht/Neu direkt wählen; gleiche Artikel in unterschiedlichem Zustand sind getrennte Listen-Zeilen mit korrekten Marktwerten

## 1.3.0 – Juli 2026

### Neu
- 🔄 **Update-Hinweis in der App**: „Version & Updates" im Mehr-Tab (Admin) prüft gegen GitHub-Releases und meldet neue Versionen – mit Release-Notes-Link und fertigem Update-Befehl
- 🛠 **update.sh**: Ein-Befehl-Update direkt von GitHub (ohne git), mit automatischem Datenbank-Schnappschuss
- ⚙️ **Angebots-Vorschlag einstellbar** (Mehr-Tab, Sammlerprofi): Prozentsatz vom Marktwert statt fester 60 %
- 🧱 Favicon ergänzt (kein 404 mehr in der Browser-Konsole)

## 1.2.1 – Juli 2026

### Behoben
- 🐳 `docker-compose.example.yml` war nach dem Auskommentieren der Admin-Variablen ungültig („environment must be a mapping")

## 1.2.0 – Juli 2026
## Neu
- 🚀 **Ersteinrichtung im Browser**: Beim allerersten Start (leere Datenbank) führt Brickfolio durch das Anlegen des Admin-Kontos – kein Default-Passwort, kein Editieren der docker-compose.yml mehr nötig. `ADMIN_USER`/`ADMIN_PASSWORD` bleiben als optionale Variablen für unbeaufsichtigte Setups erhalten.

## Verbessert
- 📖 README, Handbuch und docker-compose.example.yml an den neuen Erststart angepasst


## 1.1.0 – Juli 2026
## Neu
- 📥 **CSV-Import** für Sammlerprofis (Mehr → Export & Druck) – mit Beispiel-CSV, toleranter Spaltenerkennung und Fehlerbericht je Zeile; vorhandene Artikel werden zusammengeführt
- ❓ **In-App-Hilfe** im Mehr-Tab: Erste Schritte, Schritt-für-Schritt-Anleitung zum Beschaffen der BrickLink-/Rebrickable-API-Schlüssel (inkl. Shop-Pflicht und IP-Feldern), Rollen, Flohmarkt-Ablauf, Symbole
- 🛒 **Neue Einkaufsliste direkt aus dem Scan-Dialog** anlegen – mit vorausgefülltem Namen „Flohmarkt <Datum>"; die Listenauswahl erscheint jetzt immer, damit Funde nicht versehentlich auf der falschen Liste landen

## Verbessert
- 📊 Statistik auf Mobilgeräten: Kennzahlen-Chips brechen sauber um, Beträge skalieren, Chart-Beschriftungen mit weißem Halo

## Behoben
- Frontend-Crash durch fehlende Funktionen nach fehlerhaftem Update (betroffen war nur der Zwischenstand 81)


## 1.0.0 – Juli 2026

Erste veröffentlichte Version, entstanden aus 75 internen Updates.

- Scannen (Brickognize) & Suche (Rebrickable/BrickLink), Sets & Figuren
- Sammlung mit Mengen, Zustand, Notizen, Galerie, Preisverlauf pro Artikel
- Set-Vernetzung: Vollständigkeits-Anzeige, enthaltene Figuren,
  „fehlende auf die Wunschliste"
- Wunschliste mit Preis-Widgets und „Gekauft"-Übernahme
- Sammlerprofi-Modus: Kaufpreise (automatisch ⚙️ / manuell ✏️ mit Datum),
  Gewinn-Anzeige, Einkaufslisten mit Marktwert, Einzel-Einkaufspreisen,
  Gesamtangebot (anteilige Verteilung, 60-%-Vorschlag) und Auto-Archiv,
  Verkaufsliste (Doppelte) mit Set-Reservierung
- Statistik-Tab: Kennzahlen, Wertentwicklung, Aufteilung, Wert nach Jahr,
  Top 10, Profi-Wertsteigerungen
- Mehrbenutzer mit Rollen, JSON-Komplettsicherung, CSV-Export, Drucklisten,
  PWA mit sauberem Cache-Verhalten
