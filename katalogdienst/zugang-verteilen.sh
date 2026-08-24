#!/bin/sh
# Die BrickLink-Zugangsdaten aus dem Katalogdienst in alle .env-Dateien
# uebernehmen -- und die betroffenen Container neu starten.
#
# Reihenfolge: Sven erzeugt neue Werte bei BrickLink und traegt sie **in der
# Konsole** ein. Von dort holt dieses Skript sie und verteilt sie. Es laeuft
# auf der NAS; die Werte gehen durch keinen fremden Kanal und werden nirgends
# ausgegeben -- auf dem Bildschirm landet nur, wie lang sie sind.
#
# Ohne Argument nur anzeigen, was passieren wuerde ("Probelauf").
set -e
ECHT="$1"
DIENST=/volume1/docker/brickfolio-katalog
ZIELE="/volume1/docker/brickfolio /volume1/docker/brickfolio-nerdfan /volume1/docker/brickfolio-paul /volume1/docker/brickfolio-kello"
FELDER="BL_CONSUMER_KEY BL_CONSUMER_SECRET BL_TOKEN BL_TOKEN_SECRET"

# Aus der Datenbank des Dienstes -- das ist, was in der Konsole eingetragen
# wurde. Steht dort nichts, gilt weiter die Umgebung, und dann gibt es auch
# nichts zu verteilen.
WERTE=$(sudo -n /usr/local/bin/docker exec brickfolio-katalog python3 -c "
import sqlite3
c = sqlite3.connect('/data/katalog.db')
for n in '$FELDER'.split():
    r = c.execute('SELECT value FROM einstellungen WHERE name = ?', (n,)).fetchone()
    if r and r[0]:
        print(n + '=' + r[0])
")

anzahl=$(printf '%s\n' "$WERTE" | grep -c '^BL_' || true)
if [ "$anzahl" -lt 4 ]; then
  echo "In der Konsole stehen erst $anzahl von 4 Werten."
  echo "Erst dort eintragen (Katalog -> Einstellungen), dann dieses Skript."
  exit 1
fi

printf '%s\n' "$WERTE" | awk -F= '{printf "  %s = %d Zeichen\n", $1, length($2)}'

for ordner in $ZIELE; do
  datei="$ordner/.env"
  [ -f "$datei" ] || { echo "  uebersprungen (keine .env): $ordner"; continue; }
  if [ "$ECHT" != "--echt" ]; then
    echo "  wuerde ersetzen in: $datei"
    continue
  fi
  # Sicherungskopie, bevor irgendetwas angefasst wird. Eine .env mit
  # halb ersetzten Werten waere schlimmer als eine mit alten.
  cp "$datei" "$datei.vor-$(date +%Y%m%d-%H%M%S)"
  tmp="$datei.neu"
  grep -v '^BL_CONSUMER_KEY=\|^BL_CONSUMER_SECRET=\|^BL_TOKEN=\|^BL_TOKEN_SECRET=' \
    "$datei" > "$tmp"
  printf '%s\n' "$WERTE" >> "$tmp"
  mv "$tmp" "$datei"
  chmod 600 "$datei"
  echo "  ersetzt: $datei"
done

if [ "$ECHT" != "--echt" ]; then
  echo
  echo "Probelauf. Zum wirklichen Ersetzen: sh $0 --echt"
  exit 0
fi

echo "Container neu starten:"
for ordner in $ZIELE; do
  [ -f "$ordner/docker-compose.yml" ] || continue
  (cd "$ordner" && sudo -n /usr/local/bin/docker compose up -d >/dev/null 2>&1) \
    && echo "  neu gestartet: $(basename "$ordner")"
done
