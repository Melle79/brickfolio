#!/usr/bin/env python3
"""Sehmodelle an denselben Figuren gegeneinander messen.

**Warum es das gibt.** Die Modellwahl für den Bilderlauf stand bisher auf
Stichproben von Hand: „in zwei von drei Proben richtig", „an zehn echten
Figuren zehn Treffer". Bei drei Proben ist der Abstand zwischen Platz eins
und zwei nicht vom Zufall zu trennen – `gemma3:12b` lag am 21.08.2026
„knapp dahinter", und knapp dahinter bei n=3 heißt: gar nichts. Trotzdem
hing an dieser Zahl, welches Modell 19.201 Figuren beschreibt.

**Was es misst und was nicht.** Zählbar sind Laufzeit, Ausfälle,
unbrauchbare Antworten und wie viele Teile ein Modell überhaupt findet.
Nicht zählbar ist, ob „dark bluish gray" besser trifft als „gray" – dafür
gibt es keine Wahrheit im Haus: Der vorhandene Katalogtext stammt selbst
von einem Modell und taugt nicht als Maßstab. Deshalb stellt das Werkzeug
die Antworten nebeneinander und überlässt das Urteil einem Menschen; es
rechnet nur das aus, was sich wirklich ausrechnen lässt.

Aufruf (auf dem Rechner, auf dem Ollama läuft):

    python3 tools/bildmodelle-vergleich.py \\
        --modelle qwen3-vl:latest,gemma3:12b,minicpm-v:latest --anzahl 30

    python3 tools/bildmodelle-vergleich.py \\
        --modelle qwen3-vl:latest,minicpm-v:latest \\
        --figuren cas001,sw0326,cty0131 --url http://127.0.0.1:11434
"""
import argparse
import json
import os
import random
import statistics
import sys
import time

_HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HIER), "katalogdienst"))

import bild as bildmodul          # noqa: E402

# Unter dieser Zahl lohnt die Auswertung nicht. Sie ist keine Rechnung,
# sondern die Lehre aus den bisherigen Vergleichen: Bei drei Figuren
# entscheidet eine einzige gut getroffene Kopfbedeckung das Rennen.
GENUG_FIGUREN = 20

# Dieselbe Kantenlänge wie im Farbenlauf (`_katalog_farben`). Ein Vergleich
# bei anderer Größe sagt nichts über den Lauf aus: Weniger Pixel heißt
# weniger Aufdruck, und gerade daran unterscheiden sich die Modelle.
KANTE = 512

# Nach so vielen Ausfällen **in Folge** gilt ein Modell als nicht befragbar
# und wird übersprungen. Der Fall ist nicht theoretisch: Ein Tippfehler im
# Modellnamen sieht aus wie ein kaputter Dienst – die Verbindung steht, nur
# das Modell gibt es nicht (`qwen2.5:14b` gegen `qwen2.5-14b`). Ohne diese
# Bremse liefe der Vergleich in 30 Zeitgrenzen zu je 120 s, also eine
# Stunde, und meldete am Ende eine leere Spalte.
AUFGEBEN_NACH = 3


def bildadresse(conn, item_no):
    """Bildadresse aus dem Abzug, sonst aus der Nummer gebildet.

    Derselbe Rückfall wie in `_katalog_eintragen` – und aus demselben
    Grund nicht `/ML/{nr}.jpg`: Das ältere Muster fehlt bei 102 von 19.201
    Figuren (26.08.2026).
    """
    if conn is not None:
        r = conn.execute("SELECT img_url FROM katalog_index WHERE item_no = ?",
                         (item_no,)).fetchone()
        if r and (r["img_url"] or "").strip():
            return r["img_url"].strip()
    return "https://img.bricklink.com/ItemImage/MN/0/%s.png" % item_no


def figuren_waehlen(conn, anzahl, saat):
    """Eine wiederholbare Stichprobe quer durch den Abzug.

    Nicht `ORDER BY item_no LIMIT n`: Das liefert 30-mal dasselbe Thema,
    und Themen unterscheiden sich stark – Duplo-Tiere sind eine andere
    Aufgabe als Star-Wars-Soldaten. Die Saat hält den Lauf trotzdem
    wiederholbar, sonst ließen sich zwei Messungen nicht vergleichen.

    Gewählt wird nur unter Figuren mit Bild **und** vorhandener
    Beschreibung: Letztere ist zwar kein Maßstab, aber sie zeigt beim
    Nachlesen, was der Abzug heute stehen hat.
    """
    rows = conn.execute(
        "SELECT item_no FROM katalog_index WHERE img_url != '' AND "
        "merkmale != '' AND merkmale != '–' ORDER BY item_no").fetchall()
    alle = [r["item_no"] for r in rows]
    if len(alle) <= anzahl:
        return alle
    return sorted(random.Random(saat).sample(alle, anzahl))


def messen(modelle, figuren, bilder):
    """Jedes Modell über alle Figuren – Modell außen, Figur innen.

    **Die Reihenfolge ist der Punkt.** Andersherum tauscht Ollama vor jeder
    Figur das Modell, und ein Ladevorgang kostet auf dem Mac mini mehr als
    die Analyse selbst (`minicpm-v` lud in 3,8 s, verarbeitete das Bild in
    2,8 s). Gemessen würde dann das Nachladen, nicht das Modell.

    Aus demselben Grund sind die Bilder vorher schon geholt: Sonst hinge in
    jeder Zeitmessung BrickLinks CDN mit drin.
    """
    ergebnis = {}
    for modell in modelle:
        print("\n[%s] %d Figuren …" % (modell, len(figuren)), flush=True)
        je_figur = {}
        patzer = 0
        for nr in figuren:
            bild = bilder.get(nr)
            if bild is None:
                continue
            t0 = time.monotonic()
            m = bildmodul.bild_merkmale(bild, modell=modell)
            m["sekunden"] = round(time.monotonic() - t0, 1)
            # Nur der Ausfall zählt, nicht die unbrauchbare Antwort: Ein
            # Modell, das antwortet und dabei entgleist, ist ein Ergebnis
            # des Vergleichs – gerade das will man ja sehen.
            patzer = patzer + 1 if (m.get("fehler")
                                    and not m.get("unbrauchbar")) else 0
            # Die erste Figur trägt die Ladezeit des Modells mit. Sie wird
            # nicht verworfen – sie fließt nur nicht in den Median ein, und
            # der Bericht weist sie eigens aus.
            #
            # Die erste **gemessene**, nicht die erste der Liste: Fehlt zur
            # ersten Figur das Bild, wird sie übersprungen, und die Ladezeit
            # steckte dann unmarkiert in der zweiten.
            m["erste"] = not je_figur
            je_figur[nr] = m
            print("  %-12s %5.1fs  %s" % (nr, m["sekunden"],
                                          m.get("art") or "–"), flush=True)
            if patzer >= AUFGEBEN_NACH:
                print("  → %d Ausfälle in Folge, Modell übersprungen: %s"
                      % (patzer, (m.get("fehler") or "")[:100]), flush=True)
                break
        ergebnis[modell] = je_figur
    return ergebnis


def _teilzahl(m):
    return len([t for t in (m.get("merkmale") or "").split(";") if t.strip()])


def bericht(modelle, figuren, messwerte, katalogtext):
    """Erst Figur für Figur nebeneinander, dann die Summe je Modell.

    Gemessen wird Modell außen, **berichtet** wird Figur außen: Beurteilen
    lässt sich eine Antwort nur neben der Antwort der anderen zur selben
    Figur.
    """
    print("\n" + "=" * 72)
    print("FIGUR FÜR FIGUR")
    print("=" * 72)
    for nr in figuren:
        if not any(nr in messwerte[m] for m in modelle):
            continue
        print("\n%s" % nr)
        if katalogtext.get(nr):
            print("  %-22s %s" % ("[Abzug heute]", katalogtext[nr][:160]))
        for modell in modelle:
            m = messwerte[modell].get(nr)
            if m is None:
                continue
            if m.get("fehler") and not m.get("unbrauchbar"):
                stand = "AUSFALL: " + m["fehler"][:110]
            elif m.get("unbrauchbar"):
                stand = "UNBRAUCHBAR: " + m["fehler"][:110]
            else:
                stand = "[%s] %s" % (m.get("art") or "–",
                                     (m.get("merkmale") or "–")[:150])
            print("  %-22s %s" % (modell[:22], stand))

    print("\n" + "=" * 72)
    print("SUMME JE MODELL")
    print("=" * 72)
    print("%-24s %6s %6s %7s %7s %8s %7s"
          % ("Modell", "Figs", "Art", "Teile", "Unbr.", "Ausfall", "Median"))
    for modell in modelle:
        werte = list(messwerte[modell].values())
        gut = [m for m in werte if not m.get("fehler")]
        unbr = [m for m in werte if m.get("unbrauchbar")]
        aus = [m for m in werte if m.get("fehler") and not m.get("unbrauchbar")]
        # Der Median statt des Mittelwerts: Eine einzelne Entgleisung läuft
        # in die Zeitgrenze (120 s) und zöge jeden Mittelwert mit sich.
        zeiten = [m["sekunden"] for m in werte if not m.get("erste")]
        print("%-24s %6d %6d %7.1f %7d %8d %7s"
              % (modell[:24], len(werte),
                 len([m for m in gut if m.get("art")]),
                 statistics.mean([_teilzahl(m) for m in gut]) if gut else 0,
                 len(unbr), len(aus),
                 "%.1fs" % statistics.median(zeiten) if zeiten else "–"))
        erste = [m for m in werte if m.get("erste")]
        if erste:
            print("%-24s   (erste Figur mit Ladezeit: %.1fs, nicht im Median)"
                  % ("", erste[0]["sekunden"]))

    # Einfache Anführungszeichen: Das deutsche „…" endet auf einem
    # ASCII-Zeichen und zerlegt eine "…"-Zeichenkette (siehe CLAUDE.md).
    print('\n„Art" ist die Zahl der Figuren, zu denen überhaupt eine Art '
          'kam –\nnicht, ob sie stimmt. Das steht oben zum Nachlesen.')
    if len(figuren) < GENUG_FIGUREN:
        print("\n*** %d Figuren sind zu wenig, um zwei nahe Modelle zu "
              "trennen. ***\n*** Für eine Entscheidung mindestens %d "
              "(--anzahl %d). ***" % (len(figuren), GENUG_FIGUREN,
                                      GENUG_FIGUREN))


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--modelle", required=True,
                   help="Ollama-Modelle, mit Komma getrennt")
    p.add_argument("--figuren", default="",
                   help="Figurennummern statt einer Stichprobe")
    p.add_argument("--anzahl", type=int, default=30,
                   help="Größe der Stichprobe aus dem Abzug (Vorgabe 30)")
    p.add_argument("--saat", type=int, default=1,
                   help="Saat der Stichprobe – gleiche Saat, gleiche Figuren")
    p.add_argument("--db", default=os.environ.get("DB_PATH",
                                                  "/data/katalog.db"))
    p.add_argument("--url", default="",
                   help="Ollama-Adresse; sonst die des Dienstes")
    p.add_argument("--json", default="",
                   help="Messwerte zusätzlich als JSON ablegen")
    a = p.parse_args()

    modelle = [m.strip() for m in a.modelle.split(",") if m.strip()]
    if a.url:
        # Der Vergleich läuft von Hand und oft gegen einen anderen Rechner
        # als der Dienst. Die Adresse hier zu überschreiben ist harmloser,
        # als sie in den Einstellungen des laufenden Dienstes zu ändern.
        bildmodul.ollama_url = lambda: a.url.strip().rstrip("/")
    if not bildmodul.ollama_enabled():
        sys.exit("Keine Ollama-Adresse. --url setzen oder DB_PATH auf den "
                 "Abzug zeigen lassen, in dem OLLAMA_URL steht.")

    conn = None
    if os.path.exists(a.db):
        import katalog
        katalog.DB_PATH = a.db
        conn = katalog.db()
    elif not a.figuren:
        sys.exit("Ohne Abzug (%s) braucht es --figuren." % a.db)

    if a.figuren:
        figuren = [f.strip() for f in a.figuren.split(",") if f.strip()]
    else:
        figuren = figuren_waehlen(conn, a.anzahl, a.saat)
    if not figuren:
        sys.exit("Keine Figuren gefunden.")

    # Bilder zuerst, alle: Ein Netzfehler soll auffallen, bevor eine Stunde
    # Messzeit investiert ist – und die Zeitmessung unten darf ihn nicht
    # mitzählen.
    print("Bilder holen (%d Figuren) …" % len(figuren), flush=True)
    bilder, katalogtext, fehlend = {}, {}, []
    for nr in figuren:
        try:
            roh = bildmodul.bild_holen(bildadresse(conn, nr))
            bilder[nr] = bildmodul.bild_vorbereiten(roh, KANTE)
        except Exception as e:
            fehlend.append("%s (%s)" % (nr, e))
        if conn is not None:
            r = conn.execute("SELECT merkmale FROM katalog_index WHERE "
                             "item_no = ?", (nr,)).fetchone()
            if r:
                katalogtext[nr] = r["merkmale"]
    if fehlend:
        print("Ohne Bild, übersprungen: %s" % ", ".join(fehlend))
    if not bilder:
        sys.exit("Kein einziges Bild geladen.")

    figuren = [f for f in figuren if f in bilder]
    messwerte = messen(modelle, figuren, bilder)
    bericht(modelle, figuren, messwerte, katalogtext)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"figuren": figuren, "modelle": modelle,
                       "messwerte": messwerte}, fh,
                      ensure_ascii=False, indent=1)
        print("\nMesswerte in %s" % a.json)


if __name__ == "__main__":
    main()
