#!/bin/sh
# Läuft auf dem **Mac mini** und holt Gedächtnis und Gesprächsverläufe vom
# MacBook.
#
# Das Gegenstück zu `gedaechtnis-abgleich.sh`, das vom MacBook aus schiebt.
# Beide zusammen decken die zwei Fälle ab:
#
#   MacBook läuft, Mini aus   -> das Schieben greift beim nächsten Lauf
#   Mini läuft, MacBook kurz an -> das Holen greift, sobald es erreichbar ist
#
# Der zweite Fall ist der wichtige: Wenn Sven im Urlaub ist und das MacBook
# zu Hause nur gelegentlich angeht, friert der Stand sonst beim Zuklappen ein.
#
# Ohne `--delete`: Was auf dem Mini entsteht, soll nicht vom MacBook aus
# verschwinden. Ist das MacBook aus, ist das kein Fehler – es ist ein Laptop.
set -eu

QUELLE_HOST="macbook"
BASIS=".claude/projects/-Users-sven-Downloads"
ZIEL="$HOME/$BASIS"

ssh -o BatchMode=yes -o ConnectTimeout=8 "$QUELLE_HOST" true 2>/dev/null || {
  exit 0                       # MacBook aus oder unterwegs: still bleiben
}

mkdir -p "$ZIEL/memory"

/usr/bin/rsync -a -e 'ssh -o BatchMode=yes' \
    "$QUELLE_HOST:$BASIS/memory/" "$ZIEL/memory/"

/usr/bin/rsync -a --include='*.jsonl' --exclude='*/' --exclude='*' \
    -e 'ssh -o BatchMode=yes' "$QUELLE_HOST:$BASIS/" "$ZIEL/"

echo "$(date '+%Y-%m-%d %H:%M:%S') geholt: $(ls -1 "$ZIEL/memory" | wc -l | tr -d ' ') Notizen," \
     "$(ls -1 "$ZIEL"/*.jsonl 2>/dev/null | wc -l | tr -d ' ') Verläufe"
