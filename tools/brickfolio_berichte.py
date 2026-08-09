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
HUB = "https://brickfolio-hub.bfhub.workers.dev"
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
    ausdrücklich, nichts zu ändern, sondern einzuschätzen.

    Die Antwort hat ein festes Kopfformat, weil daraus die Meldung aufs Handy
    wird – und die muss **kurz** sein. Der erste Versuch schickte den ganzen
    Fließtext, und die Benachrichtigung brach mitten im Wort ab.
    """
    teile = ["Neue Brickfolio-Absturzberichte. Schau sie dir an.\n",
             "WICHTIG: Nur lesen und einschätzen. Nichts ändern, nichts "
             "ausrollen, keine Dateien anfassen.\n",
             "Antworte GENAU in diesem Format, die ersten beiden Zeilen "
             "ohne alles Weitere:\n"
             "PRIO: <1-5>\n"
             "KURZ: <ein Satz, höchstens 120 Zeichen>\n"
             "<danach die ausführliche Einschätzung, höchstens 10 Sätze>\n",
             "PRIO bedeutet: 1 = Datenverlust oder alle betroffen, sofort "
             "handeln. 2 = klares Muster, sollte diese Woche weg. "
             "3 = auffällig, weiter beobachten. 4 = einzelner Fall ohne "
             "Muster. 5 = unauffällig, nur zur Kenntnis.\n",
             "Wenn sich ein Muster zeigt (gleiche Ansicht, gleiche Version, "
             "gleiches Gerät), sag es deutlich. Wenn nicht, sag auch das – "
             "eine erfundene Erklärung ist schlimmer als keine, und bei "
             "einem einzelnen Bericht ist PRIO 4 oder 5 fast immer richtig.\n",
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


def zerlegen(antwort: str) -> tuple:
    """PRIO, KURZ und den Rest auseinandernehmen.

    Hält sich Claude nicht ans Format, ist das kein Grund zu schweigen:
    Dann gilt Priorität 5 und der erste Satz als Kurzfassung. Lieber eine
    unscharfe Meldung als gar keine.
    """
    prio, kurz, rest = 5, "", antwort.strip()
    zeilen = rest.splitlines()
    ohne = []
    for z in zeilen:
        s = z.strip()
        if s.upper().startswith("PRIO:") and prio == 5:
            try:
                p = int("".join(c for c in s[5:] if c.isdigit())[:1])
                if 1 <= p <= 5:
                    prio = p
                continue
            except ValueError:
                pass
        if s.upper().startswith("KURZ:") and not kurz:
            kurz = s[5:].strip()[:120]
            continue
        ohne.append(z)
    rest = "\n".join(ohne).strip()
    if not kurz:
        kurz = (rest.split(".")[0][:120] if rest else "")
    return prio, kurz, rest


def finding_hochladen(kopf: dict, prio: int, kurz: str, analyse: str) -> bool:
    """Die Einschätzung in den Hub legen – dort sieht Sven sie in der
    Konsole. Der Rohverlauf bleibt hier auf der Platte."""
    token_datei = pathlib.Path.home() / ".brickfolio-collector-token"
    try:
        token = token_datei.read_text().strip()
        req = urllib.request.Request(
            HUB + "/v1/collect/finding", method="POST",
            data=json.dumps({
                "label": kopf.get("Absender", "?"),
                "app_version": kopf.get("Version", ""),
                "crashes": int(kopf.get("Abstürze", "0") or 0),
                "views": kopf.get("Ansichten", ""),
                "prio": prio, "kurz": kurz, "analyse": analyse,
            }).encode(),
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/json",
                     # Ohne eigene Kennung antwortet Cloudflare mit 403:
                     # `Python-urllib/3.x` gilt dort als Bot. Der Hub selbst
                     # hatte die Anfrage nie gesehen.
                     "User-Agent": "Brickfolio-Sammler/1.0"})
        urllib.request.urlopen(req, timeout=30).read()
        return True
    except Exception as e:
        log("   Einschätzung nicht in den Hub bekommen: %s" % str(e)[:120])
        return False


def main():
    neue = abholen()
    if not neue:
        return                                   # bei Ruhe still bleiben

    log("%d neue(r) Bericht(e): %s" % (len(neue), ", ".join(p.name for p in neue)))
    alte = vorgeschichte()
    prio, kurz, analyse = zerlegen(claude_fragen(neue, alte))

    kopf = kopfdaten(neue[-1])
    im_hub = finding_hochladen(kopf, prio, kurz, analyse)

    # Aufs Handy kommt **nur** das Nötigste. Der erste Entwurf schickte die
    # ganze Einschätzung, und die Benachrichtigung brach mitten im Wort ab.
    wer = ", ".join(sorted({kopfdaten(p).get("Absender", "?") for p in neue}))
    kopfzeile = "🐞 Prio %d · %s" % (prio, wer)
    text = kurz or "%s Absturz/Abstürze auf %s (v%s)" % (
        kopf.get("Abstürze", "?"), kopf.get("Ansichten", "–"),
        kopf.get("Version", "?"))
    text += "\n\n" + ("Ausführlich in der Hub-Konsole."
                      if im_hub else "(Einschätzung liegt nur auf dem Mac mini.)")
    melde(kopfzeile, text)

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
