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

**Was hier hinausgeht und was nicht.** In 2.77.0 lag im Frontend eine
Zuordnung, deren Schlüssel ganze BrickLink-Katalognamen waren – samt
Beschreibung („Astromech Droid, R2-D2, Light Bluish Gray Head"). Das war
falsch und wurde entfernt.

Sven hat die Grenze am 05.09.2026 gezogen: **Die Namen selbst – „Bespin
Guard", „Clone Trooper" – sind Star-Wars-Begriffe und gehören nicht
BrickLink. Was BrickLink beisteuert, ist die Beschreibung im Titel**, und
genau die löst `begriff()` heraus, bevor irgendetwas in die Tabelle kommt.
Ein Test wacht darüber: Kein Schlüssel darf Komma, Klammer oder ein Wort
aus BrickLinks Beschreibungswortschatz enthalten.

**Sparsam.** Bis zu 50 Titel je Anfrage statt einer. Die 347 Begriffe aus
Svens Sammlung brauchen so keine 350 Abrufe, sondern gut ein Dutzend.

    python3 tools/jedipedia_titel.py --namen namen.txt
    python3 tools/jedipedia_titel.py --namen namen.txt --schreiben
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

# **Von Hand übersetzt, aber nicht von Hand geglaubt.** Für die englischen
# Gattungs- und Rollennamen findet keine Regel den Artikel: Das Wiki führt
# sie deutsch, und »Bespin Guard« heißt dort »Bespin-Sicherheitskräfte« –
# das lässt sich nicht ableiten, nur wissen. Also stehen die Übersetzungen
# hier und werden beim Lauf gegen die Schnittstelle geprüft: Was es dort
# nicht gibt oder was nur auf eine Begriffsklärung führt, fällt still weg.
#
# Aufgenommen wird nur, was **von der Figur handelt**. An den Kategorien
# nachgesehen und deshalb *nicht* aufgeführt: der AT-ST-Fahrer (der Artikel
# »Allterrain-Scouttransporter« steht unter »Bodenfahrzeuge« – das ist der
# Läufer, nicht sein Fahrer), der Wolkenwagen-Pilot und der
# Prätorianer-Trainingsdroide.
# Was hinter einem Komma eine **Einheit** ist und keine Beschreibung.
# Erlaubt statt verboten: Eine Verbotsliste („gray", „printed", „head" …)
# müsste jede Bemalung kennen, die BrickLink sich je ausdenkt. Eine Einheit
# dagegen sieht immer gleich aus - eine Ordnungszahl oder eines dieser
# Wörter.
EINHEIT = re.compile(
    r"(\b\d+(st|nd|rd|th)\b|\b(Legion|Battalion|Corps|Company|Squadron|"
    r"Squad|Guard|Force|Unit|Division|Regiment|Brigade)\b)", re.I)

# Die Einheiten, deutsch. Nachgeschlagen wie alles andere.
EINHEITEN = {
    "501st Legion": ["501. Legion"],
    "187th Legion": ["187. Legion"],
    "212th Attack Battalion": ["212. Angriffsbataillon"],
    "41st Elite Corps": ["41. Elitekorps"],
    "327th Star Corps": ["327. Sternenkorps"],
    "332nd Company": ["332. Kompanie"],
    "442nd Siege Battalion": ["442. Belagerungsbataillon"],
    "91st Mobile Reconnaissance Corps": ["91. Aufklärungskorps"],
    "91st Mobile Reconnaissance Corps Lightning Squadron":
        ["91. Aufklärungskorps"],
    "104th Battalion 'Wolfpack'": ["104. Bataillon"],
    "Rancor Battalion": ["Rancor-Bataillon"],
    "Coruscant Guard": ["Coruscant-Sicherheitskräfte"],
    "Experimental Unit Clone Force 99": ["Kloneinheit 99"],
}

# Wer davon eine **Person** ist und keine Rolle. Bei einer Person geht sie
# der Einheit vor: »Clone Trooper Commander Fox, Coruscant Guard« gehoert
# zu Fox, nicht zur Garde. Bei einer blossen Rolle ist es umgekehrt.
PERSONEN = frozenset("""
Clone Trooper Captain Rex|Clone Trooper Commander Cody|Clone Trooper Commander Fox|
Clone Trooper Commander Gree|Clone Trooper Commander Bly|
Clone Trooper Commander Wolffe|Commander Wolffe|Clone Commander Bacara|
Clone ARC Trooper Corporal Echo|Clone ARC Trooper Fives|Clone Captain Vaughn|
Clone Commando Commander Crosshair|Clone Commando Sergeant Hunter|
Clone Commando Wrecker|Clone Trooper Pilot Odd Ball|Grand Moff Wilhuff Tarkin|
General Maximillian Veers|Emperor Palpatine|Chancellor Palpatine|
The Grand Inquisitor|Vice Admiral Sloane|General Hux|Lieutenant Connix|
Supreme Leader Kylo Ren|The Armorer|Carasynthia 'Cara' Dune|Professor Huyang|
Dr. Cornelius Evazan|Pre-Mor Security Deputy Inspector Syril Karn
""".replace("\n", "").split("|")) - {""}

HANDGEPRUEFT = {
    # ── Klonkrieger ──────────────────────────────────────────────────
    "Clone Trooper": ["Klonkrieger"],
    "Clone Trooper Captain": ["Klonkrieger"],
    "Clone Trooper Sergeant": ["Klonkrieger"],
    "Clone Trooper Officer": ["Klonkrieger"],
    "Clone Trooper Specialist": ["Klonkrieger"],
    "Clone Trooper Lieutenant": ["Klonkrieger"],
    "Clone Trooper Gunner": ["Klonkrieger"],
    "Clone Heavy Trooper": ["Klonkrieger"],
    "Clone Bomb Squad Trooper": ["Klonkrieger"],
    "Clone Airborne Trooper": ["Klonkrieger"],
    "Clone Scout Trooper": ["Klonkrieger"],
    "Clone Scout Trooper Episode 3": ["Klonkrieger"],
    "Special Forces Clone Trooper": ["Klonkrieger"],
    "Clone Trooper Commander": ["Klonkommandant", "Klon-Kommandant"],
    "Special Forces Commander": ["Klonkommandant", "Klon-Kommandant"],
    "Clone Trooper Pilot": ["Klonpilot", "Klon-Pilot"],
    "Clone Trooper V-wing Pilot": ["Klonpilot", "Klon-Pilot"],
    "Clone Cadet": ["Klon-Kadett"],
    "Clone Jet Trooper": ["Jet-Trooper", "Klonkrieger"],
    "Clone ARF Trooper": ["Advanced Recon Force"],
    "Clone Shock Trooper": ["Coruscant-Sicherheitskräfte"],
    "Galactic Marine Clone Trooper": ["Galaktische Marineinfanterie"],
    # Benannte Klone: der lesbare Name vor der Kennzahl - »Commander Fox«
    # leitet auf »CC-1010«, und das ist derselbe Artikel.
    "Clone Trooper Captain Rex": ["CT-7567"],
    "Clone Trooper Commander Cody": ["Commander Cody"],
    "Clone Trooper Commander Fox": ["Commander Fox"],
    "Clone Trooper Commander Gree": ["Commander Gree"],
    "Clone Trooper Commander Bly": ["Commander Bly"],
    "Clone Trooper Commander Wolffe": ["CC-3636"],
    "Commander Wolffe": ["CC-3636"],
    "Clone Commander Bacara": ["Commander Bacara"],
    "Clone ARC Trooper Corporal Echo": ["CT-1409"],
    "Clone ARC Trooper Fives": ["CT-5555"],
    "Clone Captain Vaughn": ["CT-0292"],
    "Clone Commando Commander Crosshair": ["Crosshair"],
    "Clone Commando Sergeant Hunter": ["CT-9901"],
    "Clone Commando Wrecker": ["Wrecker"],
    "Clone Trooper Pilot Odd Ball": ["Odd Ball"],
    # ── Imperium ─────────────────────────────────────────────────────
    "Imperial Stormtrooper": ["Sturmtruppen"],
    "Imperial Stormtrooper Sergeant": ["Sturmtruppen"],
    "Imperial Artillery Stormtrooper": ["Sturmtruppen"],
    "Hot Tub Stormtrooper": ["Sturmtruppen"],
    "Imperial Trooper": ["Sturmtruppen"],
    "Imperial Hovertank Pilot": ["Sturmtruppen"],
    "Imperial Jet Pack Trooper": ["Sturmtruppen"],
    "Sandtrooper": ["Sandtruppen"],
    "Sandtrooper Squad Leader": ["Sandtruppen"],
    "Mimban Stormtrooper": ["Sumpftruppen", "Sturmtruppen"],
    "Scarif Stormtrooper": ["Küstenverteidigungstruppen", "Sturmtruppen"],
    "Imperial Shadow Trooper": ["Schattentruppen"],
    "Imperial Shadow Stormtrooper": ["Schattentruppen"],
    "Imperial Shock Trooper": ["Imperiale Stoßtruppen"],
    "Imperial Death Trooper": ["Todestruppen"],
    "Imperial Patrol Trooper": ["Patrouillentruppen"],
    "Imperial Scout Trooper": ["Scouttruppen", "Sturmtruppen"],
    "Imperial Royal Guard": ["Imperiale Garde", "Rote Garde"],
    "Imperial Praetorian Guard": ["Prätorianergarde"],
    "Shadow Guard": ["Schattenwache"],
    "Imperial Probe Droid": ["Sondendroide", "Aufklärungsdroide"],
    "DRK-1 Dark Eye Probe Droid": ["DRK-1-Sonde"],
    "Imperial TIE Fighter Pilot": ["TIE-Pilot"],
    "Imperial TIE Fighter / Interceptor Pilot": ["TIE-Pilot"],
    "Imperial TIE Fighter / Striker Pilot": ["TIE-Pilot"],
    "Imperial TIE Bomber Pilot": ["TIE-Pilot"],
    "AT-AT Driver": ["AT-AT-Pilot"],
    "Inferno Squad Agent": ["Inferno-Kommando", "Inferno-Trupp"],
    "Grand Moff Wilhuff Tarkin": ["Wilhuff Tarkin"],
    "General Maximillian Veers": ["Maximilian Veers"],
    "Emperor Palpatine": ["Sheev Palpatine"],
    "Chancellor Palpatine": ["Sheev Palpatine"],
    "The Grand Inquisitor": ["Großinquisitor"],
    "Imperial Inquisitor Fifth Brother": ["Fünfter Bruder"],
    "Vice Admiral Sloane": ["Rae Sloane"],
    # ── Separatisten und Droiden ─────────────────────────────────────
    "Battle Droid": ["B1-Kampfdroide"],
    "Battle Droid Pilot": ["B1-Kampfdroide"],
    "Security Battle Droid": ["B1-Kampfdroide"],
    "Rocket Battle Droid": ["B1-Kampfdroide"],
    "Rocket Battle Droid Commander": ["OOM-Kommandodroide"],
    "Battle Droid Commander": ["OOM-Kommandodroide"],
    "Super Battle Droid": ["B2-Superkampfdroide"],
    "Commando Droid": ["BX-Kommandodroide"],
    "Commando Droid Captain": ["BX-Kommandodroide"],
    "Assassin Droid": ["Attentäterdroide"],
    "Dwarf Spider Droid": ["Zwergspinnendroide"],
    "Mouse Droid": ["MSE-6-Mausdroide"],
    "Gonk Droid": ["Gonk-Droide"],
    "Reindeer Gonk Droid": ["Gonk-Droide"],
    "Protocol Droid": ["Protokolldroide"],
    "NI-L8 Protocol Droid": ["Protokolldroide"],
    "Buzz Droid": ["Pistoeka-Sabotagedroide"],
    "2-1B Medical Droid": ["2-1B"],
    "FA-4 Pilot Droid": ["FA-4"],
    "IG-100 MagnaGuard / Magna Droid": ["IG-100 MagnaWächter"],
    "K-2SO Droid": ["K-2SO"],
    "B2EMO Droid": ["B2EMO"],
    # ── Mandalorianer ────────────────────────────────────────────────
    "The Mandalorian / Din Djarin / 'Mando'": ["Din Djarin"],
    "Din Grogu / The Child / 'Baby Yoda'": ["Grogu"],
    "Mandalorian Warrior": ["Mandalorianer"],
    "Mandalorian Tribe Warrior": ["Mandalorianer"],
    "Mandalorian Loyalist": ["Mandalorianer"],
    "Mandalorian Fleet Commander": ["Mandalorianer"],
    "Mandalorian Super Commando": ["Supercommandos", "Mando Ori'ramikade"],
    "Mandalorian Death Watch Warrior": ["Todeswache"],
    "Mandalorian Nite Owl": ["Nite Owls", "Nachteulen"],
    "The Armorer": ["Waffenschmiedin"],
    # ── Rebellen, Widerstand, Erste Ordnung ──────────────────────────
    "Rebel Fleet Trooper": ["Flottensoldat", "Infanterie (Rebellen-Allianz)"],
    "Rebel Fleet Trooper / Rebel Scout Trooper":
        ["Flottensoldat", "Infanterie (Rebellen-Allianz)"],
    "Hoth Rebel Trooper": ["Infanterie (Rebellen-Allianz)"],
    "Endor Rebel Commando": ["Infanterie (Rebellen-Allianz)"],
    "Rebel Pilot": ["Rebellenpilot"],
    "Rebel Pilot A-wing": ["Rebellenpilot"],
    "Rebel Pilot B-wing": ["Rebellenpilot"],
    "Rebel Pilot U-wing": ["Rebellenpilot"],
    "Bespin Guard": ["Bespin-Sicherheitskräfte"],
    "Knight of Ren": ["Ritter von Ren"],
    "Supreme Leader Kylo Ren": ["Kylo Ren"],
    "General Hux": ["Armitage Hux"],
    "First Order Stormtrooper Officer": ["Sturmtruppen der Ersten Ordnung"],
    "First Order Heavy Assault Stormtrooper":
        ["Sturmtruppen der Ersten Ordnung"],
    "First Order Flametrooper": ["Flammentruppen der Ersten Ordnung",
                                 "Sturmtruppen der Ersten Ordnung"],
    "First Order Snowtrooper": ["Schneetruppen (Erste Ordnung)"],
    "First Order Officer": ["Erste Ordnung"],
    "First Order Crew Member": ["Erste Ordnung"],
    "First Order Walker Driver": ["Erste Ordnung"],
    "First Order TIE Fighter Pilot": ["TIE-Pilot"],
    "Resistance Trooper": ["Widerstand"],
    "Resistance Soldier": ["Widerstand"],
    "Resistance Officer": ["Widerstand"],
    "Resistance Pilot X-wing": ["Widerstand"],
    "Lieutenant Connix": ["Kaydel Ko Connix"],
    "DJ Code Breaker": ["DJ (Codeknacker)", "DJ"],
    # ── Republik, Sith, Spezies, Einzelne ────────────────────────────
    "Republic Trooper": ["Armee der Galaktischen Republik"],
    "Senate Commando": ["Senatswache"],
    "Senate Commando Captain": ["Senatswache"],
    "Gamorrean Guard": ["Gamorreaner"],
    "Geonosian": ["Geonosier"],
    "Geonosian Warrior": ["Geonosier"],
    "Geonosian Zombie": ["Geonosier"],
    "Gungan Soldier": ["Gungan"],
    "Klatooinian Raider": ["Klatooinianer"],
    "Bith Musician": ["Bith"],
    "Wooof": ["Klaatu"],
    "Dr. Cornelius Evazan": ["Cornelius Evazan"],
    "Carasynthia 'Cara' Dune": ["Cara Dune"],
    "Professor Huyang": ["Huyang"],
    "Pre-Mor Security Deputy Inspector Syril Karn": ["Syril Karn"],
    "Beach Luke": ["Luke Skywalker"],
    "Bounty Hunter C-3PO": ["C-3PO"],
    "Snowman BB-8": ["BB-8"],
}


def begriff(name: str) -> str:
    """Aus dem Katalognamen den Nachschlagebegriff machen.

    **Muss Zeichen fuer Zeichen dasselbe liefern wie `jedipediaBegriff` in
    `frontend/app.js`.** Sonst misst dieses Werkzeug etwas anderes, als die
    App spaeter tut. Ein Test vergleicht beide an echten Katalognamen.
    """
    # **Klammern zuerst weg, dann am Bindestrich trennen.** Andersherum
    # zerschneidet »AT-DP Pilot (Imperial Combat Driver - White Uniform)«
    # mitten in der Klammer, und uebrig bleibt »AT-DP Pilot (Imperial
    # Combat Driver« - eine offene Klammer als Suchbegriff.
    ganz = str(name or "")
    ohne = re.sub(r"\([^)]*\)", " ", ganz).split(" - ")[0]
    # Eine Kennung gewinnt, wo immer sie steht - in der Klammer wie hinter
    # einem Komma. Sie ist im Wiki **selbst** der Artikeltitel, damit
    # springt die Suche von allein hinein: »Assassin Droid (IG-88)« und
    # »Astromech Droid, C1-10P« landen so richtig, ohne jede Tabelle.
    for stueck in re.findall(r"\(([^)]*)\)", ganz) + ohne.split(","):
        if KENNZEICHEN.match(stueck.strip()):
            return stueck.strip()
    # Hinter dem Komma steht zweierlei: BrickLinks **Beschreibung** (Farbe,
    # Bedruckung, »Young«) - die fliegt raus - und die **Einheit**, die im
    # Wiki einen eigenen Artikel hat. Sven hat am 05.09.2026 darauf
    # hingewiesen: Bei »Clone Trooper Commander, 187th Legion« ist die
    # 187. Legion der interessantere Verweis, nicht der Klonkommandant.
    teile = [x.strip() for x in ohne.split(",")]
    behalten = [teile[0]] + [x for x in teile[1:] if EINHEIT.search(x)]
    return re.sub(r"\s+", " ", ", ".join(behalten)).strip(" ,;-")


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

    teile = [t.strip() for t in b.split(",")]
    # Die Einheit zuerst: Sie ist das Bestimmteste, was der Name hergibt.
    for t in teile[1:]:
        for uebersetzt in EINHEITEN.get(t, []):
            dazu(uebersetzt)
    # Kennung hinter dem letzten Komma: »Astromech Droid, R2-D2«.
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


def begriffsklaerungen(titel: list[str]) -> set:
    """Welche dieser Artikel nur eine Begriffsklaerung sind.

    **Ohne diese Pruefung greift die Kette daneben.** »Cody«, »Fox«,
    »Gree«, »Hammer«, »Hunter« - lauter Klonkrieger, und jeder dieser
    Titel ist im Wiki eine Begriffsklaerungsseite, keine Figur. Wer darauf
    klickt, steht vor einer Auswahlliste. Die Kennung (»CC-2224«) fuehrt
    dagegen direkt zur Figur, und die steht in der Kandidatenkette gleich
    dahinter - sie kam nur nie zum Zug, weil der kurze Name schon
    »existiert«.
    """
    aus = set()
    for i in range(0, len(titel), JE_ANFRAGE):
        haufen = titel[i:i + JE_ANFRAGE]
        daten = urllib.parse.urlencode({
            "action": "query", "titles": "|".join(haufen),
            "prop": "categories", "cllimit": "max",
            "format": "json", "formatversion": "1"})
        antrag = urllib.request.Request(API + "?" + daten,
                                        headers={"User-Agent": KENNUNG})
        try:
            with urllib.request.urlopen(antrag, timeout=45) as antwort:
                # formatversion 1: `pages` ist ein Woerterbuch nach
                # Seitennummer, keine Liste - `.values()` ist Pflicht.
                seiten = json.loads(
                    antwort.read())["query"]["pages"].values()
        except Exception:                                    # noqa: BLE001
            continue
        for s in seiten:
            for k in s.get("categories", []):
                if "Begriffsklärung" in k["title"]:
                    aus.add(s["title"])
        if i + JE_ANFRAGE < len(titel):
            time.sleep(PAUSE)
    return aus


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
    # Handgesetztes zuerst: Wo eine Übersetzung steht, ist sie besser als
    # alles, was die Kette findet - die fand für »Clone Trooper
    # Lieutenant« den allgemeinen Rang-Artikel statt der Figur.
    # **Person vor Einheit, sonst Einheit vor Rolle.** »Clone Trooper
    # Commander, 187th Legion« soll auf die 187. Legion zeigen - der
    # Klonkommandant allein waere nichtssagend. Steht dort aber ein Name,
    # gilt der: »Commander Fox, Coruscant Guard« gehoert zu Fox. Svens
    # beide Hinweise vom 05.09.2026, und sie widersprechen sich nicht.
    plan = {}
    for b in begriffe:
        kopf = b.split(",")[0].strip()
        vorn = HANDGEPRUEFT.get(b, [])
        if kopf in PERSONEN:
            vorn = vorn + HANDGEPRUEFT.get(kopf, [])
        plan[b] = vorn + kandidaten(b, gattungen)
    alle = sorted({k for ks in plan.values() for k in ks})
    if laut:
        print("%d Namen → %d Begriffe → %d verschiedene Kandidaten"
              % (len(namen), len(begriffe), len(alle)), file=sys.stderr)
    treffer = nachschlagen(alle, laut)

    # Begriffsklärungen sind keine Antwort - siehe `begriffsklaerungen`.
    unbrauchbar = begriffsklaerungen(sorted({z for z in treffer.values() if z}))

    tabelle, offen = {}, []
    for b, ks in plan.items():
        gewaehlt = ""
        for k in ks:
            ziel = treffer.get(k)
            if not ziel or ziel in unbrauchbar:
                continue
            # **Der lesbare Name vor der Kennzahl.** »Commander Fox« ist
            # eine Weiterleitung auf »CC-1010« - derselbe Artikel, aber die
            # Adresse sagt, wen man vor sich hat. Svens Wunsch vom
            # 05.09.2026, und er hat recht.
            gewaehlt = k if (KENNZEICHEN.match(ziel)
                             and not KENNZEICHEN.match(k)) else ziel
            break
        if not gewaehlt:
            offen.append(b)
        elif gewaehlt != b:
            # Was ohnehin schon passt, muss nicht in die Tabelle: Die Suche
            # springt bei einem Titeltreffer von selbst in den Artikel.
            tabelle[b] = gewaehlt
    return tabelle, offen


ZIEL = Path(__file__).resolve().parents[1] / "frontend" / "jedipedia-titel.js"


def schreiben(tabelle: dict[str, str]) -> None:
    """Die Zuordnung ins Frontend legen.

    Was hier hinausgeht, sind **Namen** – Star-Wars-Begriffe – und die
    zugehörigen Artikeltitel. BrickLinks Beschreibungen bleiben draußen;
    dafür sorgt `begriff()`, und ein Test wacht darüber.
    """
    zeilen = ",\n".join('  %s: %s' % (json.dumps(k, ensure_ascii=False),
                                      json.dumps(v, ensure_ascii=False))
                        for k, v in sorted(tabelle.items()))
    ZIEL.write_text(
        "/* Erzeugt von tools/jedipedia_titel.py – nicht von Hand ändern.\n"
        "\n"
        "   Der Katalog ist englisch, die Jedipedia deutsch: »Bespin Guard«\n"
        "   heißt dort »Bespin-Sicherheitskräfte«. Wo der Begriff nicht schon\n"
        "   selbst ein Artikeltitel ist, steht hier, wie der Artikel wirklich\n"
        "   heißt. Nachgeschlagen, nicht geraten: Jeder Eintrag kam aus der\n"
        "   MediaWiki-Schnittstelle des Wikis, und Begriffsklärungsseiten\n"
        "   sind aussortiert.\n"
        "\n"
        "   Schlüssel sind **Namen**, nie BrickLinks Beschreibungen – die\n"
        "   löst die Begriffsbildung vorher heraus.\n"
        "\n"
        "   %d Einträge. */\n"
        "const JEDIPEDIA_TITEL = {\n%s\n};\n" % (len(tabelle), zeilen),
        encoding="utf-8")
    print("geschrieben: %s (%d Einträge)" % (ZIEL, len(tabelle)))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--namen", required=True,
                   help="Datei mit einem Katalognamen je Zeile")
    p.add_argument("--offen", action="store_true",
                   help="die Begriffe ohne Artikel auflisten")
    p.add_argument("--schreiben", action="store_true",
                   help="Ergebnis nach frontend/jedipedia-titel.js schreiben")
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
    ueber_tabelle = [n for n in namen if begriff(n) in tabelle]
    print("\nFuer %d weitere Begriffe steht der Artikel unter einem anderen"
          " Namen - die kommen in die Tabelle." % len(tabelle))
    print("Das sind noch einmal %d Figuren." % len(ueber_tabelle))
    print("\nZusammen: %d der %d Figuren landen im Artikel."
          % (len(figuren) + len(ueber_tabelle), len(namen)))
    print("%d Begriffe finden im Wiki gar nichts - dort bleibt es bei der"
          " Suche." % len(offen))
    if a.schreiben:
        schreiben(tabelle)
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
