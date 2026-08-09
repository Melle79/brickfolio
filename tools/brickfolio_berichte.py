#!/usr/bin/env python3
"""Wächter für Brickfolio-Absturzberichte – läuft alle 30 Minuten auf dem
Mac mini.

Holt ab, was im Hub-Postfach liegt, lässt Claude einen Blick darauf werfen
und meldet sich auf Svens iPhone, wenn etwas dabei ist. Bei Ruhe bleibt er
still – ein Wächter, der jede halbe Stunde „nichts Neues" meldet, wird
weggewischt und dann auch dann, wenn es zählt.

Bewusst **nur lesen und melden**: Der Wächter ändert nichts an der App, an
den Instanzen oder am Hub. Was zu tun ist, entscheidet Sven, nachdem er den
Vorschlag gelesen hat.
"""
import datetime
import json
import pathlib
import subprocess
import sys
import urllib.request

HA = "http://192.168.0.222:8123"
TOKEN = (pathlib.Path.home() / ".ha_token").read_text().strip()
SAMMLER = str(pathlib.Path.home() / "tools/sammle-fehlerberichte.sh")
ABLAGE = pathlib.Path.home() / "brickfolio-berichte"
NEU = ABLAGE / "neu"
ARCHIV = ABLAGE / "gesehen"
LOG = pathlib.Path.home() / ".brickfolio-berichte.log"
CLAUDE = "/opt/homebrew/bin/claude"
PROJEKT = str(pathlib.Path.home() / "brickfolio")     # nur falls vorhanden


def log(text):
    zeile = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S ") + text
    with open(LOG, "a") as f:
        f.write(zeile + "\n")
    print(zeile, flush=True)


def melde(titel, text):
    """Einmal aufs iPhone, einmal als Benachrichtigung in HA."""
    for dienst, daten in (
        ("notify/mobile_app_svens_iphone", {"title": titel, "message": text}),
        ("notify/persistent_notification",
         {"title": titel, "message": text,
          "data": {"notification_id": "brickfolio_berichte"}}),
    ):
        try:
            req = urllib.request.Request(
                HA + "/api/services/" + dienst, method="POST",
                data=json.dumps(daten).encode(),
                headers={"Authorization": "Bearer " + TOKEN,
                         "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:
            log("   Meldung über %s fehlgeschlagen: %s" % (dienst, str(e)[:80]))


def abholen() -> list:
    """Sammler laufen lassen und die neu eingetroffenen Dateien zurückgeben."""
    NEU.mkdir(parents=True, exist_ok=True)
    vorher = {p.name for p in NEU.glob("*.txt")}
    r = subprocess.run(["sh", SAMMLER], capture_output=True, text=True,
                       timeout=180)
    if r.returncode != 0:
        log("Sammler scheiterte: %s" % (r.stderr or r.stdout)[:200])
        return []
    return sorted(p for p in NEU.glob("*.txt") if p.name not in vorher)


def kopfdaten(pfad: pathlib.Path) -> dict:
    """Die ersten Zeilen eines Berichts – Absender, Version, Abstürze,
    Ansichten. Der Sammler schreibt sie als Kopf über den Verlauf."""
    d = {}
    for zeile in pfad.read_text(encoding="utf-8").splitlines()[:6]:
        if ":" in zeile:
            k, _, v = zeile.partition(":")
            d[k.strip()] = v.strip()
    return d


def vorgeschichte() -> list:
    """Was lag schon da? Ein einzelner Absturz sagt wenig – die Frage ist
    immer, ob er sich zu den bisherigen fügt."""
    return sorted(ARCHIV.glob("*.txt"))[-20:]


def claude_fragen(neue: list, alte: list) -> str:
    """Claude auf die Berichte schauen lassen. Rein lesend: Der Auftrag ist
    ausdrücklich, nichts zu ändern, sondern einzuschätzen."""
    teile = ["Neue Brickfolio-Absturzberichte. Schau sie dir an und sag mir "
             "in höchstens 5 Sätzen, was auffällt.\n",
             "WICHTIG: Nur lesen und einschätzen. Nichts ändern, nichts "
             "ausrollen, keine Dateien anfassen.\n",
             "Wenn sich ein Muster zeigt (gleiche Ansicht, gleiche Version, "
             "gleiches Gerät), sag es deutlich. Wenn nicht, sag auch das – "
             "eine erfundene Erklärung ist schlimmer als keine.\n",
             "Schließe mit einer Zeile 'VORSCHLAG: …' – was Sven tun "
             "sollte, oder 'VORSCHLAG: nichts, weiter beobachten'.\n"]
    for p in neue:
        teile.append("\n=== NEU: %s ===\n%s" % (p.name, p.read_text(
            encoding="utf-8")[:12000]))
    if alte:
        teile.append("\n\n=== Bisher gesehen (nur Kopfzeilen) ===")
        for p in alte:
            k = kopfdaten(p)
            teile.append("%s | %s | Abstürze %s | Ansichten %s" % (
                p.name, k.get("Absender", "?"), k.get("Abstürze", "?"),
                k.get("Ansichten", "?")))
    try:
        r = subprocess.run([CLAUDE, "-p", "\n".join(teile)],
                           capture_output=True, text=True, timeout=600,
                           cwd=PROJEKT if pathlib.Path(PROJEKT).is_dir() else None)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        log("Claude antwortete nicht brauchbar: %s" % (r.stderr or "")[:200])
    except Exception as e:
        log("Claude-Aufruf fehlgeschlagen: %s" % str(e)[:200])
    return ""


def main():
    neue = abholen()
    if not neue:
        return                                   # bei Ruhe still bleiben

    log("%d neue(r) Bericht(e): %s" % (len(neue), ", ".join(p.name for p in neue)))
    alte = vorgeschichte()
    einschaetzung = claude_fragen(neue, alte)

    # Die Kurzfassung fürs Handy kommt aus den Kopfdaten – die steht auch
    # dann, wenn Claude gerade nicht antwortet.
    zeilen = []
    for p in neue:
        k = kopfdaten(p)
        zeilen.append("%s: %s Absturz/Abstürze auf %s (v%s)" % (
            k.get("Absender", "?"), k.get("Abstürze", "?"),
            k.get("Ansichten", "–"), k.get("Version", "?")))
    text = "\n".join(zeilen)
    if einschaetzung:
        text += "\n\n" + einschaetzung[:900]
    else:
        text += "\n\n(Keine Einschätzung – Claude war nicht erreichbar.)"
    melde("🐞 Brickfolio: neuer Absturzbericht", text)

    # Weggelegt, damit der nächste Lauf sie als Vorgeschichte hat und nicht
    # noch einmal meldet.
    ARCHIV.mkdir(parents=True, exist_ok=True)
    for p in neue:
        p.rename(ARCHIV / p.name)
    log("gemeldet und ins Archiv gelegt")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("Wächter abgebrochen: %s" % str(e)[:300])
        sys.exit(1)
