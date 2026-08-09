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

/usr/bin/rsync -a -e 'ssh -o BatchMode=yes' "$QUELLE/" "$ZIEL/"
echo "Gedächtnis: $(ls -1 "$QUELLE" | wc -l | tr -d ' ') Notizen."

# Die Gesprächsverläufe dazu. Sie sind **kein** fortsetzbarer Verlauf – eine
# Sitzung auf dem Mac mini kann sie nicht als eigene Vorgeschichte laden.
# Was sie sind: ein durchsuchbares Archiv. „Was haben wir am 9.8. zum Hub
# besprochen?" lässt sich damit beantworten, und genau das fehlte bisher.
#
# rsync überträgt nur die Zuwächse; die Dateien wachsen, sie werden nicht
# umgeschrieben. Der erste Lauf ist der teure.
VERLAEUFE="$HOME/.claude/projects/-Users-sven-Downloads"
ZIEL_V="macmini:.claude/projects/-Users-sven-Downloads"
if [ -d "$VERLAEUFE" ]; then
    /usr/bin/rsync -a --include='*.jsonl' --exclude='*/' --exclude='*' \
        -e 'ssh -o BatchMode=yes' "$VERLAEUFE/" "$ZIEL_V/"
    echo "Verläufe:  $(ls -1 "$VERLAEUFE"/*.jsonl 2>/dev/null | wc -l | tr -d ' ')" \
         "Dateien, $(du -sh "$VERLAEUFE" 2>/dev/null | cut -f1)."
fi
