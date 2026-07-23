#!/bin/sh
# Brickfolio: Update ausführen, wenn die App eines angefordert hat.
#
# Die App schreibt dafür data/update-requested.json (Knopf unter
# Mehr → Version & Updates). Dieses Skript gehört auf den Server und wird
# regelmäßig aufgerufen – eine Minute Takt reicht völlig, das Update selbst
# dauert ohnehin ein bis drei Minuten.
#
# Synology (DSM): Systemsteuerung → Aufgabenplaner → Erstellen →
#   Geplante Aufgabe → Benutzerdefiniertes Skript
#   Benutzer: root · Zeitplan: täglich, jede 1 Minute wiederholen
#   Befehl:  sh /pfad/zu/brickfolio/update-watch.sh
#
# Linux mit cron:  * * * * * sh /pfad/zu/brickfolio/update-watch.sh
set -e
cd "$(dirname "$0")"

FLAG="data/update-requested.json"
LOG="data/update-watch.log"
ALIVE="data/update-watch-alive"

# Lebenszeichen bei JEDEM Lauf – daran erkennt die App, dass der Helfer
# eingerichtet ist, und bietet den Update-Knopf erst dann an.
mkdir -p data
: > "$ALIVE"

[ -f "$FLAG" ] || exit 0

# "execute_after" respektieren: vorher nichts tun (Karenzzeit läuft noch).
NOW=$(date +%s)
AFTER=$(sed -n 's/.*"execute_after"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' "$FLAG")
if [ -n "$AFTER" ] && [ "$NOW" -lt "$AFTER" ]; then
  exit 0
fi

# Markierung zuerst entfernen – sonst liefe das Update in einer Schleife,
# falls es unterwegs abbricht.
rm -f "$FLAG"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') Update angefordert, starte ==="
  sh ./update.sh
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') fertig ==="
} >> "$LOG" 2>&1
