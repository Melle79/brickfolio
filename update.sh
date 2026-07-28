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
