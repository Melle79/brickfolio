#!/bin/sh
# Brickfolio aktualisieren (ohne git, z. B. auf Synology).
# Aufruf im Projektordner:  sudo bash update.sh
#
# Zwei Betriebsarten, das Skript erkennt sie selbst:
#   image: …  -> fertiges Image nachziehen (schnell, kein Quellcode nötig)
#   build: .  -> Quellcode holen und selbst bauen (wie bisher)
set -e
cd "$(dirname "$0")"

if [ ! -f docker-compose.yml ]; then
  echo "Keine docker-compose.yml gefunden – bitte im Brickfolio-Ordner ausführen."
  exit 1
fi

# `sudo` bringt seinen eigenen, kurzen PATH mit (secure_path). Auf Synology
# liegt docker unter /usr/local/bin und fällt da heraus. Genau der in dieser
# Datei dokumentierte Weg – `sudo bash update.sh` – lief deshalb bis zum
# letzten Schritt durch, tauschte den Quellstand auf der Platte aus und
# scheiterte erst dann. Der alte Container lief weiter: Auf der Platte der
# neue Stand, im Betrieb der alte, und die Meldung dazu stand in Zeile 30
# einer sonst erfolgreich aussehenden Ausgabe.
for verzeichnis in /usr/local/bin /usr/bin /bin; do
  case ":$PATH:" in
    *":$verzeichnis:"*) ;;
    *) PATH="$PATH:$verzeichnis" ;;
  esac
done
export PATH

# Lieber hier abbrechen als nach dem Austausch des Quellstands: Ein Abbruch
# vor dem ersten Schreiben lässt die Instanz genau so zurück, wie sie war.
if ! command -v docker >/dev/null 2>&1; then
  echo "docker nicht gefunden (PATH: $PATH)."
  echo "Auf Synology liegt es unter /usr/local/bin – dort nachsehen und den"
  echo "Pfad ergänzen. Es wurde noch nichts verändert."
  exit 1
fi

if [ -f data/brickfolio.db ]; then
  cp data/brickfolio.db "data/pre-update-$(date +%Y%m%d-%H%M%S).db"
  ls -t data/pre-update-*.db 2>/dev/null | tail -n +4 | xargs -r rm --
  echo "Datenbank-Schnappschuss angelegt (die letzten 3 werden aufbewahrt)."
fi

if grep -qE '^[[:space:]]*image:[[:space:]]*ghcr\.io/' docker-compose.yml; then
  echo "Hole das aktuelle Image …"
  docker compose pull
  docker compose up -d
else
  echo "Hole aktuellen Stand von GitHub …"
  curl -sL https://github.com/Melle79/brickfolio/archive/refs/heads/main.tar.gz | tar xz --strip-components=1
  echo "Baue und starte den Container …"
  docker compose up -d --build
fi

echo "Fertig – Brickfolio ist auf dem neuesten Stand. 🧱"
