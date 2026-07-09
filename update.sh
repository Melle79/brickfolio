#!/bin/sh
# Brickfolio über GitHub aktualisieren (ohne git, z. B. auf Synology).
# Aufruf im Projektordner:  sudo bash update.sh
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

echo "Hole aktuellen Stand von GitHub …"
curl -sL https://github.com/Melle79/brickfolio/archive/refs/heads/main.tar.gz | tar xz --strip-components=1

echo "Baue und starte den Container …"
docker compose up -d --build

echo "Fertig – Brickfolio ist auf dem neuesten Stand. 🧱"
