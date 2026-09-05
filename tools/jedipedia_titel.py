#!/usr/bin/env python3
"""Baut die Zuordnung »Katalogbegriff → Jedipedia-Artikel«.

**Warum es diese Datei gibt.** Der Verweis ins deutsche Star-Wars-Wiki hat
bis 1.7.x immer nur *gesucht*: `Spezial:Suche?search=Clone+Trooper`. Bei
Eigennamen ging das gut – bei allem Englischen landete man auf der
Trefferliste statt im Artikel. Nachgemessen an Svens 563 Figuren: »Darth
Vader« traf, »Clone Trooper«, »Battle Droid«, »Imperial Stormtrooper« und
»Emperor Palpatine« nicht.

Geraten wird hier nichts. Gefragt wird die MediaWiki-Schnittstelle unter
`/w/api.php`, und übernommen wird nur, was es dort **wirklich gibt**:
entweder als Artikel oder als Weiterleitung, die die Schnittstelle selbst
auflöst (»Princess Leia« → »Prinzessin Leia«).

**Einmalig, nicht im Betrieb.** Die App holt nichts von Jedipedia – sie
verlinkt nur. Dieses Werkzeug läuft von Hand.

**Es schreibt nichts ins Frontend, und das ist der Punkt.** In 2.77.0 lag
dort eine Zuordnung mit BrickLink-**Namen** als Schlüssel, in einem
öffentlichen Repo. Das war falsch: Namen sind BrickLinks Inhalt, und deren
Weitergabe an Dritte untersagen die Nutzungsbedingungen – derselbe Grund,
aus dem `katalogdienst/veroeffentlichen.py` nur Nummer und eigene
Bildbeschreibung hinausgibt. Eine ausgelieferte Zuordnung müsste an der
**Nummer** hängen. Bis es die gibt, dient dieses Werkzeug dem **Messen**:
Es sagt, wie viele Figuren die Begriffsbildung trifft und wo sie
danebenliegt.

**Sparsam.** Bis zu 50 Titel je Anfrage statt einer. Die 347 Begriffe aus
Svens Sammlung brauchen so keine 350 Abrufe, sondern gut ein Dutzend.

    python3 tools/jedipedia_titel.py --namen namen.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.jedipedia.net/w/api.php"
KENNUNG = "Brickfolio-Katalogabgleich/1.0 (privat, einmalig; kein Dauerbetrieb)"
JE_ANFRAGE = 50
PAUSE = 1.0

# Eine Kennung wie IG-88, R2-D2, C1-10P, U-3PO, SR-V0. Genau die steht bei
# BrickLink oft in Klammern hinter dem englischen Gattungsnamen - und genau
# die warf die alte Begriffsbildung weg: »Assassin Droid (IG-88)« wurde zu
# »Assassin Droid« (Trefferliste), wo »IG-88« der Artikel gewesen waere.
KENNZEICHEN = re.compile(r"^[A-Z0-9]{1,4}[-–][A-Z0-9]{1,5}$")

# Woerter, die immer Gattung sind, auch wenn sie im Bestand nur einmal
# vorkommen. »Clone Trooper Lieutenant« endete sonst beim allgemeinen
# Rang-Artikel »Leutnant« - nachgesehen: Kategorie »Militaerische Raenge«,
# also nichts ueber diese Figur.
IMMER_GATTUNG = frozenset("""
droid droids trooper troopers stormtrooper snowtrooper sandtrooper
pilot pilots guard guards commander captain lieutenant officer officers
soldier soldiers warrior warriors sergeant general admiral driver drivers
gunner engineer member crew commando commandos jedi sith knight master
""".split())

def begriff(name: str) -> str:
    """Aus dem Katalognamen den Nachschlagebegriff machen.

    **Muss Zeichen fuer Zeichen dasselbe liefern wie `jedipediaBegriff` in
    `frontend/app.js`.** Sonst misst dieses Werkzeug etwas anderes, als die
    App spaeter tut. Ein Test vergleicht beide an echten Katalognamen.
    """
    kopf = str(name or "").split(" - ")[0]
    ohne = re.sub(r"\([^)]*\)", " ", kopf)
    # Eine Kennung gewinnt, wo immer sie steht - in der Klammer wie hinter
    # einem Komma. Sie ist im Wiki **selbst** der Artikeltitel, damit
    # springt die Suche von allein hinein: »Assassin Droid (IG-88)« und
    # »Astromech Droid, C1-10P« landen so richtig, ohne jede Tabelle.
    for stueck in re.findall(r"\(([^)]*)\)", kopf) + ohne.split(","):
        if KENNZEICHEN.match(stueck.strip()):
            return stueck.strip()
    # Sonst der Teil vor dem ersten Komma: Dahinter steht BrickLinks
    # Beiwerk - Einheit (», 41st Elite Corps«), Farbe, Bedruckung. Das
    # findet im Wiki nichts, es verhindert nur den Treffer.
    return re.sub(r"\s+", " ", ohne.split(",")[0]).strip(" ,;-")


def kandidaten(b: str, gattungen: frozenset = frozenset()) -> list[str]:
    """Womit es der Reihe nach versucht wird - genauestes zuerst.

    Der Katalogname packt oft mehreres in eine Zeile: »Astromech Droid,
    R2-D2« nennt Gattung *und* Namen, »The Mandalorian / Din Djarin /
    'Mando'« gleich drei Namen, »Clone ARC Trooper Fives, 501st Legion«
    Rang, Figur und Einheit. Das Wiki fuehrt sie unter *einem* davon.
    """
    aus: list[str] = []

    def dazu(x: str) -> None:
        x = re.sub(r"\s+", " ", str(x or "")).strip().strip("'\"")
        if x and x not in aus:
            aus.append(x)

    # Kennung hinter dem letzten Komma: »Astromech Droid, R2-D2«.
    teile = [t.strip() for t in b.split(",")]
    for t in teile[1:]:
        if KENNZEICHEN.match(t):
            dazu(t)
    # Namen um den Schraegstrich, jeder fuer sich.
    for t in re.split(r"\s*/\s*", teile[0]):
        if t.strip() and t.strip() != teile[0].strip():
            dazu(t)
    dazu(b)
    dazu(teile[0])
    # Der letzte grossgeschriebene Brocken vor dem Komma - dort steht bei
    # den Klonen die Figur: »Clone Commando Wrecker« -> »Wrecker«.
    #
    # **Aber nur, wenn das Wort keine Gattung ist.** Ohne diese Bedingung
    # war dieser Kandidat der schaedlichste von allen: »Battle Droid«,
    # »Assassin Droid«, »Gonk Droid« endeten alle bei »Droid«, das Wiki
    # leitet das auf den Sammelartikel »Droide« um - und damit zeigten
    # dreissig verschiedene Figuren auf denselben allgemeinen Artikel. Ein
    # falscher Artikel ist schlechter als eine Trefferliste.
    #
    # Was Gattung ist, wird nicht geraten, sondern **gezaehlt**: Ein Wort,
    # das viele verschiedene Figuren beendet, ist eine Kategorie und kein
    # Name. `gattungen` kommt aus dem ganzen Namensbestand.
    woerter = teile[0].split()
    if (len(woerter) > 1 and re.match(r"^[A-Z][a-z]+$", woerter[-1])
            and woerter[-1].lower() not in gattungen):
        dazu(woerter[-1])
    return aus


def gattungswoerter(begriffe, ab: int = 2) -> frozenset:
    """Welche Schlusswoerter mehrere Figuren teilen - das sind Kategorien."""
    zaehler: dict = {}
    for b in begriffe:
        woerter = b.split(",")[0].split()
        if len(woerter) > 1:
            zaehler[woerter[-1].lower()] = zaehler.get(
                woerter[-1].lower(), 0) + 1
    return frozenset(w for w, n in zaehler.items() if n > ab) | IMMER_GATTUNG


def _api(titel: list[str]) -> dict:
    """Eine Anfrage, bis zu 50 Titel. Gibt {angefragt: Artikel oder ""}."""
    daten = urllib.parse.urlencode({
        "action": "query", "titles": "|".join(titel),
        "redirects": "1", "format": "json", "formatversion": "1"})
    antrag = urllib.request.Request(API + "?" + daten,
                                    headers={"User-Agent": KENNUNG})
    with urllib.request.urlopen(antrag, timeout=45) as antwort:
        d = json.loads(antwort.read()).get("query", {})
    # `normalized` und `redirects` sagen, wie aus dem Angefragten das wurde,
    # was unter `pages` steht. Ohne diese Ketten liesse sich das Ergebnis
    # nicht mehr dem zuordnen, wonach gefragt wurde.
    kette = {}
    for art in ("normalized", "redirects"):
        for r in d.get(art, []):
            kette[r["from"]] = r["to"]

    def ziel(x: str) -> str:
        gesehen = set()
        while x in kette and x not in gesehen:
            gesehen.add(x)
            x = kette[x]
        return x

    da = {p["title"] for p in d.get("pages", {}).values() if "missing" not in p}
    return {t: (ziel(t) if ziel(t) in da else "") for t in titel}


def nachschlagen(alle: list[str], laut=True) -> dict[str, str]:
    ergebnis: dict[str, str] = {}
    offen = [t for t in alle if t]
    for i in range(0, len(offen), JE_ANFRAGE):
        haufen = offen[i:i + JE_ANFRAGE]
        try:
            ergebnis.update(_api(haufen))
        except Exception as e:                       # noqa: BLE001
            print("  Anfrage misslungen (%s) - der Haufen bleibt offen" % e,
                  file=sys.stderr)
            ergebnis.update({t: "" for t in haufen})
        if laut:
            print("  %d/%d nachgeschlagen" % (min(i + JE_ANFRAGE, len(offen)),
                                              len(offen)), file=sys.stderr)
        if i + JE_ANFRAGE < len(offen):
            time.sleep(PAUSE)
    return ergebnis


def aufloesen(namen: list[str], laut=True) -> tuple[dict, list]:
    """Begriff → Artikel. Zurueck kommt auch, was offen blieb."""
    begriffe = sorted({begriff(n) for n in namen if begriff(n)})
    gattungen = gattungswoerter(begriffe)
    plan = {b: kandidaten(b, gattungen) for b in begriffe}
    alle = sorted({k for ks in plan.values() for k in ks})
    if laut:
        print("%d Namen → %d Begriffe → %d verschiedene Kandidaten"
              % (len(namen), len(begriffe), len(alle)), file=sys.stderr)
    treffer = nachschlagen(alle, laut)

    tabelle, offen = {}, []
    for b, ks in plan.items():
        gefunden = next((treffer.get(k) for k in ks if treffer.get(k)), "")
        if gefunden:
            # Was ohnehin schon passt, muss nicht in die Tabelle: Die Suche
            # springt bei einem Titeltreffer von selbst in den Artikel.
            if gefunden != b:
                tabelle[b] = gefunden
        else:
            offen.append(b)
    return tabelle, offen


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--namen", required=True,
                   help="Datei mit einem Katalognamen je Zeile")
    p.add_argument("--offen", action="store_true",
                   help="die Begriffe ohne Artikel auflisten")
    a = p.parse_args()

    namen = [z.strip() for z in Path(a.namen).read_text(
        encoding="utf-8").splitlines() if z.strip()]
    # **Direkt gemessen, nicht abgeleitet.** Was die App tut, ist genau
    # eines: den Begriff bilden und danach suchen. Also wird gefragt, ob
    # dieser Begriff selbst ein Artikeltitel ist - die Kandidatenkette
    # weiter unten sagt etwas anderes und faelschte die Zahl schon einmal
    # nach oben (218 statt 170).
    begriffe = sorted({begriff(n) for n in namen if begriff(n)})
    print("\nWas die App selbst trifft:", file=sys.stderr)
    direkt = nachschlagen(begriffe, laut=False)
    selbst = {b for b in begriffe if direkt.get(b)}
    figuren = [n for n in namen if begriff(n) in selbst]
    print("\n%d von %d Begriffen sind selbst ein Artikeltitel - die Suche"
          " springt dort von allein hinein." % (len(selbst), len(begriffe)))
    print("Das sind %d der %d Figuren." % (len(figuren), len(namen)))

    tabelle, offen = aufloesen(namen)
    dazu = {b: z for b, z in tabelle.items() if b not in selbst}
    print("\nFuer %d weitere Begriffe gibt es im Wiki einen Artikel unter"
          " einem anderen Namen." % len(dazu))
    print("   Ausliefern liesse sich das nur an der **Nummer** - Namen sind"
          " BrickLinks Inhalt und duerfen nicht an Dritte.")
    print("%d Begriffe finden dort gar nichts." % len(offen))
    if a.offen:
        # Auf die Ausgabe, nicht in eine Datei: Was hier steht, sind
        # BrickLink-Namen. Sie duerfen auf den Bildschirm und in die
        # eigene Ueberlegung, aber nicht versehentlich in ein Repo.
        print("\noffen geblieben:")
        for b in offen:
            print("  " + b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
