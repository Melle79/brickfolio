#!/bin/sh
# Gedächtnis vom MacBook auf den Mac mini schieben.
#
# Warum von hier und nicht dort: Auf dem MacBook ist die Anmeldung über SSH
# abgeschaltet (`Connection refused`), der Mac mini kann sich die Notizen also
# nicht holen. Geschoben wird deshalb, wann immer dieser Rechner läuft.
#
# Warum überhaupt: Sitzungen werden **nicht** abgeglichen. Wer im Urlaub vom
# Handy eine Sitzung auf dem Mac mini öffnet, weiß nichts von dem, was hier
# besprochen wurde – aber er kann wissen, wie das Heimnetz aussieht, wo die
# Instanzen liegen und wie die Absturzberichte laufen. Genau dafür sind die
# Notizen da.
#
# Einweg, ohne `--delete`: Was auf dem Mac mini entsteht, soll nicht von hier
# aus verschwinden. Doppelte räumt man von Hand auf, verlorene Notizen nicht.
set -eu

QUELLE="$HOME/.claude/projects/-Users-sven-Downloads/memory"
ZIEL="macmini:.claude/projects/-Users-sven-Downloads/memory"

[ -d "$QUELLE" ] || { echo "Kein Gedächtnis unter $QUELLE" >&2; exit 1; }

ssh -o BatchMode=yes -o ConnectTimeout=10 macmini \
    'mkdir -p ~/.claude/projects/-Users-sven-Downloads/memory' || {
  echo "Mac mini nicht erreichbar – nächster Lauf versucht es erneut." >&2
  exit 0                     # kein Fehler: der Rechner darf mal aus sein
}

/usr/bin/rsync -a --itemize-changes -e 'ssh -o BatchMode=yes' \
    "$QUELLE/" "$ZIEL/" | sed 's/^/  /'

echo "Gedächtnis abgeglichen ($(ls -1 "$QUELLE" | wc -l | tr -d ' ') Notizen)."
