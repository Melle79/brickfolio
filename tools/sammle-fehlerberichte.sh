#!/bin/sh
# Holt Fehlerberichte vom Brickfolio-Hub ab und legt sie auf dem Mac mini ab.
#
# Der Hub ist ein **Postfach**, kein Archiv: Was hier ankommt, wird dort
# bestätigt und gelöscht. Sonst wächst die Hub-Datenbank still weiter, und
# die Frage „was liegt eigentlich alles beim Hub?" hätte irgendwann eine
# unangenehme Antwort.
#
# Bestätigt wird **erst nach** dem Schreiben auf die Platte. Andersherum wäre
# ein Bericht weg, sobald das Netz mitten in der Übertragung abreißt.
#
# Einrichtung (auf dem Mac mini):
#   mkdir -p ~/brickfolio-berichte
#   printf '%s' 'bfr_…' > ~/.brickfolio-collector-token && chmod 600 !$
#   Aufgabe alle 30 Minuten: sh ~/tools/sammle-fehlerberichte.sh
set -eu

HUB="${HUB_URL:-https://brickfolio-hub.bfhub.workers.dev}"
TOKEN_DATEI="${COLLECTOR_TOKEN_FILE:-$HOME/.brickfolio-collector-token}"
ABLAGE="${BERICHTE_DIR:-$HOME/brickfolio-berichte}"
NEU="$ABLAGE/neu"

[ -r "$TOKEN_DATEI" ] || { echo "Kein Sammel-Token in $TOKEN_DATEI" >&2; exit 1; }
TOKEN=$(cat "$TOKEN_DATEI")
mkdir -p "$NEU"

ROH=$(mktemp)
trap 'rm -f "$ROH"' EXIT
curl -sS -m 30 -H "Authorization: Bearer $TOKEN" "$HUB/v1/collect" > "$ROH"
grep -q '"reports"' "$ROH" || {
  echo "Unerwartete Antwort vom Hub: $(head -c 200 "$ROH")" >&2
  exit 1
}

# Auswerten, ablegen und die Kennungen der wirklich geschriebenen Berichte
# zurückgeben – nur die werden danach bestätigt.
#
# Die Antwort kommt über eine **Datei**, nicht über eine Pipe: Bei
# `python3 - <<'PY'` ist das Here-Dokument die Standardeingabe, eine
# vorgeschaltete Pipe käme dort nie an. Genau daran ist der erste Lauf
# gescheitert.
IDS=$(/usr/bin/python3 - "$NEU" "$ROH" <<'PY'
import json, os, sys, pathlib
ziel = pathlib.Path(sys.argv[1])
daten = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
fertig = []
for r in daten.get("reports", []):
    name = f"{r['created_at']}-{r['label']}-{r['id'][:8]}.txt"
    kopf = (f"Absender : {r['label']}\n"
            f"Version  : {r.get('app_version') or '?'}\n"
            f"Abstürze : {r.get('crashes', 0)}\n"
            f"Ansichten: {r.get('views') or '–'}\n"
            f"Empfangen: {r['created_at']}\n"
            + "-" * 60 + "\n")
    pfad = ziel / name
    pfad.write_text(kopf + (r.get("payload") or ""), encoding="utf-8")
    os.fsync(os.open(pfad, os.O_RDONLY))     # erst auf der Platte, dann melden
    fertig.append(r["id"])
print(" ".join(fertig))
PY
)

[ -n "$IDS" ] || { echo "Nichts Neues."; exit 0; }

# Erst jetzt bestätigen.
LISTE=$(printf '%s' "$IDS" | tr ' ' '\n' | sed 's/.*/"&"/' | paste -sd, -)
curl -sS -m 30 -X POST -H "Authorization: Bearer $TOKEN" \
     -H "content-type: application/json" \
     -d "{\"ids\":[$LISTE]}" "$HUB/v1/collect/ack" > /dev/null

ANZAHL=$(printf '%s' "$IDS" | wc -w | tr -d ' ')
echo "$ANZAHL Bericht(e) abgeholt und im Hub bestätigt."
