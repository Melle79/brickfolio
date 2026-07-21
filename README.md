# Finn's Brickfolio 🧱

*[🇬🇧 English](README.en.md) · 🇩🇪 Deutsch*

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/melle79)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Selbstgehostete PWA zum Scannen, Verwalten und Bewerten einer LEGO®-Sammlung –
gebaut für die ganze Familie auf einer gemeinsamen Datenbank, mit optionalem
**Sammlerprofi-Modus** für alle, die auf Flohmärkten kaufen und verkaufen.

**Foto → Erkennung → Sammlung.** Die Erkennung läuft über die kostenlose
[Brickognize-API](https://brickognize.com); Preise, Set-Inhalte und Metadaten
kommen von [BrickLink](https://www.bricklink.com) und
[Rebrickable](https://rebrickable.com) (eigene API-Keys nötig, siehe unten).

> 📖 Das ausführliche **Benutzerhandbuch** liegt unter
> [`docs/HANDBUCH.md`](docs/HANDBUCH.md).

## Funktionen

**Erfassen & Verwalten**
- 📷 Figuren und Sets direkt mit der Handykamera scannen (Kandidatenliste mit
  Trefferscore) oder per Name/Nummer suchen – reine Nummern werden automatisch
  als Set *und* Figur nachgeschlagen
- 📦 Mengen, Zustand (neu/gebraucht), Notizen, Bildergalerie, Volltextsuche,
  Sortierung und Typ-Filter
- 👥 **Figuren beim Set übernehmen**: Beim Hinzufügen eines Sets fragt die App,
  welche der enthaltenen Minifiguren dabei sind (alle, keine oder eine Auswahl,
  inklusive Zustand) – ohne den Gesamtwert doppelt zu zählen
- 👥 Set-Vernetzung: Sets kennen ihre Figuren („👥 3/4 ✔"-Vollständigkeit),
  Figuren zeigen, in welchen euren Sets sie stecken; fehlende Set-Figuren
  landen mit einem Tipp gesammelt auf der Wunschliste

**Preise & Wert**
- 💶 BrickLink-Ø-Preise (neu/gebraucht) automatisch im Hintergrund, mit
  eigener **Preisverlaufs-Aufzeichnung** und Chart pro Artikel
- 📊 **Statistik-Tab**: Kennzahlen, Wertentwicklung der Gesamtsammlung,
  Aufteilung nach Typ/Zustand, Wert nach Erscheinungsjahr, Top 10

**Wunschliste**
- ⭐ Merken aus jedem Scan/Suchergebnis, Ø-Preis-Widgets, „Gekauft"-Übernahme
  in die Sammlung inkl. Zustandswahl
- 🧩 Figuren, die zu einem eurer Sets gehören und noch fehlen, sind mit „fehlt
  zu eurem Set" gekennzeichnet – ein Tipp springt direkt zum Set

**Sammlerprofi-Modus** (Rolle, die der Admin pro Benutzer vergibt)
- 💰 Kaufpreis je Eintrag – automatisch mit dem BrickLink-Ø vom Erfassungstag
  vorbelegt (⚙️) oder manuell (✏️), mit Gewinn-/Verlust-Anzeige
- 🛒 **Einkaufslisten** für den Flohmarkt: befüllen per Scan, Marktwert live,
  Einkaufspreis je Artikel, **Gesamtangebot** mit anteiliger Verteilung nach
  Marktwert und 60-%-Preisvorschlag
- 📋 **Verkaufsliste**: alle Doppelten mit abgebbarer Menge und Verkaufswert –
  für eigene Sets gebrauchte Figuren bleiben reserviert, von allem anderen
  bleibt ein Behalte-Exemplar
- 🗒 Beim Verbuchen von einer Einkaufsliste landet der **Listenname in den
  Notizen** des Sammlungs-Eintrags (Herkunft bleibt nachvollziehbar)
- 📈 Zusätzliche Statistik: bezahlt gesamt, Gewinn, beste Wertsteigerungen

**Familie & Betrieb**
- 🔐 Mehrbenutzer mit Token-Login (PBKDF2-gehashte Passwörter), Admin- und
  Profi-Rollen, eigene Passwort-/Namensänderung
- 💾 Komplett-**Sicherung** als JSON (herunterladen & wieder einspielen),
  CSV-Export und druckfertige Listen
- 🏷 Konfigurierbarer **Anzeigename** in Logo und Titel (Standard „Finn");
  ideal, wenn mehrere Familienmitglieder je eine eigene Instanz betreiben
- 📲 Als PWA installierbar, Offline-Shell, keine Cloud – alles bleibt auf
  eurem Server

## Screenshots

| Scannen | Sammlung |
|:---:|:---:|
| <img src="docs/screenshots/scannen.png" width="260" alt="Scannen"> | <img src="docs/screenshots/sammlung.png" width="260" alt="Sammlung"> |
| **Statistik** | **Einkaufsliste (Flohmarkt-Modus)** |
| <img src="docs/screenshots/statistik.png" width="260" alt="Statistik"> | <img src="docs/screenshots/einkaufsliste.png" width="260" alt="Einkaufsliste"> |

*(Screenshots mit Demo-Daten)*

## Schnellstart (Docker)

```bash
git clone https://github.com/Melle79/brickfolio.git
cd brickfolio
cp docker-compose.example.yml docker-compose.yml
docker compose up -d --build
```

Aufrufen: `http://<server>:8300` – beim ersten Besuch führt die App durch
die **Ersteinrichtung** (Admin-Konto anlegen). Die Datenbank liegt
persistent unter `./data/brickfolio.db`.

**Ohne git** (z. B. auf Synology-NAS, wo git meist fehlt) – das neueste
Release als Archiv laden:

```bash
mkdir brickfolio && cd brickfolio
curl -sL https://github.com/Melle79/brickfolio/archive/refs/heads/main.tar.gz | tar xz --strip-components=1
cp docker-compose.example.yml docker-compose.yml
docker compose up -d --build
```

### Synology NAS

Ordner unter `/volume1/docker/brickfolio` anlegen und die Befehle per SSH
mit `sudo` ausführen (bei der curl-Variante: `sudo sh -c 'curl … | tar …'`,
damit die ganze Pipe mit Rechten läuft).

## Konfiguration

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `ADMIN_USER` / `ADMIN_PASSWORD` | nein | Optional: Admin automatisch anlegen (sonst Ersteinrichtung im Browser) |
| `DB_PATH` | nein | Pfad zur SQLite-Datei (Default im Container: `/data/brickfolio.db`) |
| `BL_CONSUMER_KEY` / `BL_CONSUMER_SECRET` / `BL_TOKEN` / `BL_TOKEN_SECRET` | nein | BrickLink-Store-API für Preise & Set-Inhalte ([Key beantragen](https://www.bricklink.com/v2/api/register_consumer.page)) |
| `BACKUP_KEEP` | nein | Automatische tägliche Sicherungen aufbewahren (Standard 14, 0 = aus) |
| `REBRICKABLE_KEY` | nein | Rebrickable-API für die Namenssuche ([Key erstellen](https://rebrickable.com/api/)) |

Alle API-Keys lassen sich alternativ **in der App** hinterlegen
(Mehr → API-Schlüssel, nur Admin) – ENV-Variablen dienen als Fallback.

## Rechte-Übersicht

| Aktion | Standard | Sammlerprofi | Admin |
|---|:-:|:-:|:-:|
| Scannen, Sammlung, Wünsche, Statistik | ✔ | ✔ | ✔ |
| Einkaufslisten sehen & Artikel „ist da" verbuchen | ✔¹ | ✔ | ✔¹ |
| Listen anlegen/befüllen/archivieren, Gesamtangebot, Verkaufsliste | – | ✔ | – |
| Kaufpreise & Gewinn sehen | – | ✔ | – |
| Benutzer, Rollen, API-Keys, Sicherung | – | – | ✔ |

¹ Tab erscheint nur, wenn mindestens eine aktive Liste existiert.
Rollen sind kombinierbar (der Admin kann sich selbst zum Profi machen).

## Updates & Backup

- Neue Version einspielen: Dateien ersetzen, dann
  `docker compose up -d --build` – Datenbank-Migrationen laufen automatisch.
- Sicherung: In-App unter Mehr → Sicherung (JSON mit allen Daten inkl.
  Benutzern und Preisverläufen) **oder** einfach `data/brickfolio.db` kopieren.

## Technik

FastAPI + SQLite (ohne ORM) · Vanilla JS PWA (kein Build-Schritt) ·
Docker-Deployment · APIs: Brickognize, BrickLink Store API (OAuth1),
Rebrickable.

## Rechtliches

LEGO® ist eine Marke der LEGO Gruppe, die dieses Projekt weder sponsert noch
autorisiert oder unterstützt. BrickLink und Rebrickable sind Marken ihrer
jeweiligen Inhaber; für deren APIs gelten die jeweiligen Nutzungsbedingungen.
Dieses Projekt ist ein privates Hobby-Projekt ohne kommerzielle Absicht.

## Unterstützen

Brickfolio ist ein privates Hobby-Projekt und kostenlos. Wenn es dir gefällt
und du die Entwicklung unterstützen magst, freue ich mich über einen Kaffee ☕

<a href="https://buymeacoffee.com/melle79"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-melle79-ffdd00?logo=buymeacoffee&logoColor=black" alt="Buy Me a Coffee"></a>

## Lizenz

[MIT](LICENSE)
