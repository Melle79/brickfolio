# Changelog

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
