"""Was auf dem Bild zu sehen ist – Teil für Teil.

Unverändert übernommen aus der App (2.40.0), wo dieser Block über Tage
gereift ist. Was darin steckt, ist teuer bezahlt: die Längengrenzen im
Schema (das Modell verfiel bei `sw0326` in eine Endlosschleife **innerhalb
einer Zeichenkette** und schrieb 15.190 Token am Stück), die Trennung von
„Ausfall" und „unbrauchbare Antwort" (45 Figuren waren als angesehen
abgehakt, ohne je angesehen worden zu sein), und die Frage nach der Art
**zuerst und mit Beispielen** (hinten angehängt wurde sie prompt unbrauchbar).

Geändert ist nur die Anbindung: Die Adresse des Modells kommt aus der
Umgebung dieses Dienstes statt aus den Einstellungen einer Instanz.
"""
import base64
import json
import os
import re

import io

import requests
from PIL import Image, ImageOps

USER_AGENT = "Brickfolio-Katalogdienst"


def ollama_url():
    # Über `konfig`, damit die Konsole die Adresse ändern kann, ohne dass
    # jemand auf die NAS muss.
    from katalog import konfig
    return (konfig("OLLAMA_URL") or "").strip().rstrip("/")


def ollama_enabled():
    return bool(ollama_url())


def ollama_bild_modell():
    from katalog import konfig
    return konfig("OLLAMA_BILD_MODEL") or OLLAMA_BILD_STD


# **Das Schlusslicht der eigenen Messung stand hier als Vorgabe.**
#
# Bis 1.0.0 war das `minicpm-v:latest` – und zwar aus der Zeit, als es das
# einzige Sehmodell auf dem Mac mini war. Die Messungen danach haben es
# überholt, die Vorgabe blieb stehen:
#
#   21.08.2026, dieselben drei Figuren: `qwen3-vl` erkennt R-3PO als
#   Droiden, den AT-AT-Fahrer als Soldaten und Darth Vader **namentlich**,
#   bei richtigen Farben in allen drei Fällen. `gemma3:12b` liegt knapp
#   dahinter, `qwen2.5vl:7b` und `minicpm-v` deutlicher.
#
#   Bei der Art traf `minicpm-v` zwei von drei Proben nicht (Darth Vader →
#   „Droide", AT-AT-Fahrer → „Roboter"), `qwen3-vl` an zehn echten Figuren
#   zehnmal. Auf „das ist R-3PO" antwortete `minicpm-v` prompt „R2-D2".
#
# **Kein Argument ist die Entgleisungsfrage.** `sw0326` und `cty0131` sind
# nirgends einem Modell zugeordnet, und beide liegen nach dem 21.08. – also
# vermutlich bei `qwen3-vl` selbst. Die Längengrenzen im Schema schützen
# gegen das, was jedes Modell tun kann; sie sprechen für keines.
#
# Wer `OLLAMA_BILD_MODEL` gesetzt hat, merkt von dieser Zeile nichts – sie
# trifft die frische Aufsetzung, und die soll nicht mit dem schwächsten
# Modell anfangen, das je gemessen wurde.
OLLAMA_BILD_STD = "qwen3-vl:latest"
# Ein Bild dauert länger als eine Übersetzung, und das Modell muss oft erst
# geladen werden. 120 s sind großzügig – wer hier zu knapp misst, bekommt
# leere Ergebnisse und hält das Modell für unfähig.
OLLAMA_BILD_TIMEOUT = 120

# Wie viele Token die Antwort höchstens haben darf. Reine Notbremse, kein
# Sparziel: Sie muss über dem liegen, was das begrenzte Schema unten im
# schlimmsten Fall braucht (rund 1.500 Zeichen), sonst zerschneidet sie
# gültige Antworten – und eine zerschnittene zählt als Fehlschlag, die Figur
# bliebe liegen. Ein Test rechnet das gegen die Längen im Schema nach.
#
# Echte Antworten liegen bei etwa 160 Token. Eine Entgleisung kostet damit
# gut 20 s statt der vollen 120 s Zeitgrenze.
OLLAMA_BILD_MAX_TOKEN = 900

# Wiederholungsbremse. Ollama fährt ohne (`repeat_penalty` 1.0), und bei
# `temperature: 0` gibt es aus einer Schleife dann keinen Ausweg – das Modell
# verfiel bei `cty0131` mitten im Aufdruck in „TATATATATA…". 1.1 ist der
# übliche Wert und reicht: An sechs Vergleichsfiguren blieben Art und Farben
# gleich, die Laufzeit halbierte sich (8–9,7 s auf 2,4–4,3 s), weil das
# Modell nicht mehr auspolstert.
OLLAMA_BILD_WIEDERHOLUNG = 1.1

# **Die Längen sind kein Schönheitswunsch, sie sind die Abbruchbedingung.**
#
# Am 22.08.2026 blieb der Bilderlauf bei `sw0326` stehen – und zwar bei jedem
# Anlauf, immer nach exakt 120 s. Das Modell hatte weder Ladeprobleme noch zu
# wenig Speicher: Es lud in 3,8 s, verarbeitete das Bild in 2,8 s und schrieb
# dann 15.190 Token am Stück, 436 Sekunden lang. Der Inhalt war eine
# Endlosschleife **innerhalb einer einzigen Zeichenkette**:
#
#   "...and a dark blue stripe on the upper part of the legs, and a dark blue
#    stripe on the lower part of the legs, and a dark blue stripe on the ..."
#
# `maxItems` hielt die Teileliste sauber bei sechs – Arrays begrenzt das
# Schema also. Die Länge einer Zeichenkette begrenzte es nicht, und darin
# verhakte sich das Modell: `temperature: 0` heißt gierige Dekodierung, und
# `repeat_penalty` steht bei Ollama auf 1.0. Einmal in der Schleife, immer in
# der Schleife.
#
# Mit den Grenzen unten kann die Schleife nicht entstehen, weil die Grammatik
# die Zeichenkette schließen **muss**: dieselbe Figur, 4,1 s statt 436, und
# das Ergebnis ist brauchbar. Ein Ausreißer wird dabei mitten im Wort
# abgeschnitten – das ist gewollt. Ein angeschnittenes Merkmal ist Suchtext,
# eine hängende Anfrage kostet den ganzen Lauf.
_BILD_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "maxLength": 24},
        # **Acht, nicht sechs.** Kopf, Haar, Helm, Torso, Arme, Beine sind
        # bereits sechs – ein Umhang oder ein Rock verdrängte dann etwas.
        # Gemessen am 26.08.2026: 4.623 von 19.201 Figuren saßen genau auf
        # der Grenze, und die Verteilung endete dort hart. Das ist keine
        # natürliche Häufung, das ist eine Wand.
        "parts": {"type": "array", "maxItems": 8, "items": {
            "type": "object",
            "properties": {"part": {"type": "string", "maxLength": 40},
                           "color": {"type": "string", "maxLength": 40},
                           "print": {"type": "string", "maxLength": 100}},
            "required": ["part", "color", "print"]}},
        "accessories": {"type": "array", "maxItems": 3,
                        "items": {"type": "string", "maxLength": 40}}},
    "required": ["kind", "parts"]}
# **Teil für Teil, nicht nur „rot".**
#
# Vorher standen hier Art und bis zu drei Farben. Damit fand „roter Droide"
# zwar den roten Droiden – aber „roter Protokolldroide mit schwarzem
# Aufdruck" hatte nichts, woran es sich festhalten konnte: Der Aufdruck kam
# im Suchtext gar nicht vor.
#
# Gemessen am 21.08.2026 an sechs echten Figuren: Der Dragon Master
# (`cas001`) kam als „Umhang gelb, grüner Drache mit roten Flügeln, Torso
# rot, Helm schwarz mit gelben Hörnern" heraus – das deckt sich mit dem
# BrickLink-Namen bis ins Detail.
#
# „Nur auffällige Teile" steht aus einem gemessenen Grund in der Frage: Ohne
# das schrieb das Modell zu jedem Arm „no visible printing" und brauchte
# 9,3 s je Figur. Mit dem Zusatz sind es 5,4 s – so schnell wie das alte,
# dünne Schema, bei einem Vielfachen an Inhalt.
#
# Die Frage nach der **Art** steht bewusst zuerst und mit Beispielen. Im
# ersten Anlauf hing sie hinten dran und wurde prompt unbrauchbar
# („LEGO minifigure", „Ninjago"); davor traf sie zehn von zehn.
# Art **und** Farbe – aber das hing am Modell.
#
# Zunächst stand hier nur die Farbfrage, weil `minicpm-v` die Art in zwei
# von drei Proben verfehlte (Darth Vader → „Droide", AT-AT-Fahrer →
# „Roboter"). Mit `qwen3-vl` sieht es anders aus: an zehn echten Figuren
# aus dem Abzug **zehn Treffer** – Stormtrooper → Soldat, Wookiee → Alien,
# R2-D2 → Droide, Yoda → Alien, Leia → Mensch. Deshalb wieder beides.
#
# Wer ein schwächeres Modell einstellt, bekommt schwächere Antworten; die
# Art landet dann als Rauschen im Suchtext. Das ist der Preis der freien
# Wahl und steht so im Handbuch.
#
# Den **Namen** der Figur mitzugeben bringt nichts (gemessen: dreimal
# dieselben Farben) und schadet mit schwachen Modellen sogar – auf „das ist
# R-3PO" antwortete `minicpm-v` prompt „R2-D2".
#
# **Englisch, nicht deutsch.** Der erste Anlauf legte die Merkmale deutsch
# ab („rot", „droide") – und traf damit nie: Die Suchbegriffe kommen aus der
# Übersetzung und sind englisch, und selbst die rohe deutsche Frage
# scheiterte an der Beugung („roter" ist nicht „rot"). Mit englischen
# Merkmalen ist der Index einsprachig, und die Übersetzung greift wie
# überall sonst. Gemessen liefert `qwen3-vl` auf Englisch sogar bessere
# Antworten – beim Wookiee „Wookiee" statt nur „Alien".
_BILD_FRAGE = (
    "This LEGO minifigure. First: what kind of figure is it? Answer with one "
    "or two English words (e.g. Soldier, Droid, Robot, Animal, Knight, Pilot, "
    "Alien, Police, Wizard). "
    "Then describe it part by part for a catalogue search: head, hair, "
    "helmet or headgear, torso, arms, legs, cape. For each, give its main "
    "colour in plain English (red, dark blue, light gray, tan) and a short "
    "description of what is printed on it - pattern, markings, face, insignia, "
    "and the colours of that printing. "
    "Only list parts that stand out by colour or printing; skip plain parts "
    "and anything you cannot see. Finally list what the figure holds.")


def _ollama_inhalt(nachricht: dict) -> str:
    """Die Antwort – auch wenn das Modell sie ins Denken geschrieben hat.

    `qwen3-vl` ist ein Denkmodell und legt seine Antwort in `thinking` ab;
    `content` bleibt leer, und `think: false` ändert daran nichts (geprüft
    am 21.08.2026). Ohne diesen Griff sah ausgerechnet das neueste Modell
    aus, als könne es gar nichts – dabei stand die richtige Antwort da, nur
    im falschen Feld.
    """
    inhalt = (nachricht or {}).get("content") or ""
    if inhalt.strip():
        return inhalt
    return (nachricht or {}).get("thinking") or ""


GRUNDTEILE = ("head", "torso", "arms", "legs")

_ERGAENZ_SCHEMA = {
    "type": "object",
    "properties": {"parts": {"type": "array", "maxItems": 4, "items": {
        "type": "object",
        "properties": {"part": {"type": "string", "maxLength": 20},
                       "color": {"type": "string", "maxLength": 40},
                       "print": {"type": "string", "maxLength": 100}},
        "required": ["part", "color", "print"]}}},
    "required": ["parts"]}


def merkmale_ergaenzen(bild: bytes, vorhanden: str) -> str:
    """Fehlende Grundteile gezielt nachfragen – und **nur** die.

    Das Modell hört bei aufwendigen Figuren früh auf: Beim Triceratops-
    Kostüm (`col431`) beschrieb es den Kopf und war fertig, Torso, Arme und
    Beine fehlten. Bei 19.201 Figuren fehlten 3.183-mal die Arme, 173-mal
    die Beine, 49-mal der Torso (26.08.2026).

    **Nicht neu beschreiben lassen.** Ein voller zweiter Lauf ist gemessen
    schädlich: Er brachte 15 % mehr Teile und 25 % weniger. Eine Nachfrage
    nur nach dem Fehlenden kann dagegen nichts verlieren – sie fügt hinzu
    oder gibt nichts zurück.

    Gibt die Zeichenkette zurück, die anzuhängen ist; leer, wenn nichts
    fehlt oder nichts zu holen war.
    """
    if not bild or not ollama_enabled():
        return ""
    fehlend = [x for x in GRUNDTEILE
               if not re.search(r"(^|; )" + x + r" ", (vorhanden or "").lower())]
    if not fehlend:
        return ""
    frage = ("This is a LEGO minifigure. Describe ONLY these parts: "
             + ", ".join(fehlend) + ". For each give the part name, its "
             "color, and any printing. If a part is not visible, omit it. "
             "Do not describe anything else.")
    try:
        resp = requests.post(
            ollama_url() + "/api/chat",
            json={"model": ollama_bild_modell(), "stream": False,
                  "think": False, "format": _ERGAENZ_SCHEMA,
                  "options": {"temperature": 0, "num_predict": 300},
                  "keep_alive": "30m",
                  "messages": [{"role": "user", "content": frage,
                                "images": [base64.b64encode(bild).decode()]}]},
            timeout=OLLAMA_BILD_TIMEOUT,
            headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        d = json.loads(_ollama_inhalt(resp.json().get("message", {})))
    except Exception:
        # Eine misslungene Ergänzung ist kein Fehler: Was schon dasteht,
        # bleibt brauchbar.
        return ""
    stuecke, gesehen = [], set()
    for teil in d.get("parts") or []:
        if not isinstance(teil, dict):
            continue
        name = _bild_wort(teil.get("part"), 2)
        # **Jedes Teil nur einmal.** Das Modell nennt die Arme gern zweimal,
        # links und rechts – im Suchtext wäre das nur Wiederholung.
        if name not in fehlend or name in gesehen:
            continue
        farbe = _bild_wort(teil.get("color"), 3)
        druck = _bild_wort(teil.get("print"), 12)
        if farbe in ("none", ""):
            farbe = ""
        if druck in ("none", "plain", ""):
            druck = ""
        if not (farbe or druck):
            continue
        gesehen.add(name)
        stuecke.append(" ".join(x for x in (name, farbe, druck) if x))
    return "; ".join(stuecke)


def bild_merkmale(bild: bytes, modell: str = "") -> dict:
    """Art und Farben einer Figur aus ihrem Bild.

    Leere Werte heißen „nicht erkannt", und das ist kein Fehler: Der Abzug
    ist auch ohne brauchbar, der Name trägt die Hauptlast.

    `modell` übergeht die Einstellung – **nur** für den Modellvergleich
    (`tools/bildmodelle-vergleich.py`). Der Lauf selbst lässt es leer und
    nimmt, was eingestellt ist. Ohne diesen Parameter müsste der Vergleich
    `OLLAMA_BILD_MODEL` zwischen den Modellen umschreiben, also am
    laufenden Dienst drehen, um ihn zu vermessen.

    **`fehler` trennt zwei Dinge, die gleich aussehen.** „Angesehen und
    nichts erkannt" ist ein Ergebnis; „gar nicht erst gefragt bekommen"
    ist ein Ausfall. Bis 2.37.3 war beides dasselbe – als Ollama nicht mehr
    antwortete, hakte der Farbenlauf trotzdem eine Figur nach der anderen
    als erledigt ab. Die sieht sich nie wieder jemand an.
    """
    if not bild or not ollama_enabled():
        return {"art": "", "farben": [], "fehler": ""}
    basis = ollama_url()
    try:
        resp = requests.post(
            basis + "/api/chat",
            json={"model": modell or ollama_bild_modell(), "stream": False,
                  "think": False, "format": _BILD_SCHEMA,
                  "options": {"temperature": 0,
                              "num_predict": OLLAMA_BILD_MAX_TOKEN,
                              "repeat_penalty": OLLAMA_BILD_WIEDERHOLUNG},
                  "keep_alive": "30m",
                  "messages": [{"role": "user", "content": _BILD_FRAGE,
                                "images": [base64.b64encode(bild).decode()]}]},
            timeout=OLLAMA_BILD_TIMEOUT, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        roh = resp.json()
    except Exception as e:
        # Gar nicht erst gefragt bekommen – das ist ein Ausfall des Dienstes.
        return {"art": "", "farben": [], "merkmale": "",
                "fehler": "%s: %s" % (type(e).__name__, e)}
    try:
        d = json.loads(_ollama_inhalt(roh.get("message", {})))
        art = d.get("kind", "")
        teile = d.get("parts") or []
        halt = d.get("accessories") or []
    except Exception as e:
        # **Geantwortet, aber unbrauchbar.** Das ist etwas anderes als ein
        # Ausfall: Der Dienst läuft, diese eine Figur bringt ihn aus dem
        # Tritt. Am 24.08.2026 war das `cty0131` – das Modell verfiel im
        # Aufdruck-Feld in „TATATATATA…", die Längengrenze schnitt die
        # Zeichenkette ab, es begann im nächsten Feld von vorn, und
        # `num_predict` kappte schließlich mitten im JSON. Unlesbar, und
        # weil ein Fehlschlag nichts wegschreibt, kam dieselbe Figur endlos
        # wieder und beendete nach zwölf Anläufen den ganzen Lauf.
        #
        # Der Aufrufer muss das unterscheiden können: Bei einem Ausfall
        # darf er nichts abhaken, bei einer unbrauchbaren Antwort darf er
        # die Figur nach ein paar Versuchen ziehen lassen.
        return {"art": "", "farben": [], "merkmale": "", "unbrauchbar": True,
                "fehler": "%s: %s" % (type(e).__name__, e)}
    farben, stuecke = [], []
    for teil in teile if isinstance(teile, list) else []:
        if not isinstance(teil, dict):
            continue
        name = _bild_wort(teil.get("part"), 3)
        farbe = _bild_wort(teil.get("color"), 3)
        druck = _bild_wort(teil.get("print"), 12)
        # „none" ist die Art, wie das Modell „hat es nicht" sagt – als Wort
        # im Suchtext träfe es jede Suche nach Nichtvorhandenem.
        if farbe in ("none", "nonoe", ""):
            farbe = ""
        if druck in ("none", "plain", "n a", ""):
            druck = ""
        if not name or (not farbe and not druck):
            continue
        stuecke.append(" ".join(x for x in (name, farbe, druck) if x))
        for wort in farbe.split():
            if len(wort) >= 3 and wort not in farben:
                farben.append(wort)
    for ding in halt if isinstance(halt, list) else []:
        d2 = _bild_wort(ding, 4)
        if d2 and d2 != "none":
            stuecke.append("holding " + d2)
    # Die Art knapp halten: Ein ganzer Satz im Suchtext trifft irgendwann
    # alles. Zwei Wörter reichen für „Alien", „Clone Trooper", „Droide".
    art = " ".join(re.sub(r"[^a-z ]", " ", str(art).lower()).split()[:2])
    return {"art": art, "farben": farben[:5], "merkmale": "; ".join(stuecke),
            "fehler": ""}


# Wörter, die nicht am Ende stehen dürfen. Nach der Wortgrenze blieb sonst
# ein Bindewort in der Luft hängen: „holding orange tool pouch **with**"
# (genau 4 Wörter) oder „a small black dot on **the**" (genau 12). Gemessen
# am 26.08.2026 an 19.201 Figuren: 352 Beschreibungen endeten so.
#
# Die Grenze selbst ist richtig – ein ganzer Satz im Suchtext trifft
# irgendwann alles. Nur das Abschneiden war unhöflich.
_SCHWEBEND = frozenset("""
with and on the a an of in or to at for from by over under into onto
his her its their that which having between across along
""".split())


def _bild_wort(roh, hoechstens: int) -> str:
    """Ein Stück Modellantwort auf durchsuchbaren Text eintrocknen.

    Kleinschreibung und nur Buchstaben, damit `_passt` dieselbe Elle anlegt
    wie beim Namen. Die Wortgrenze hält die Beschreibung knapp: Ein ganzer
    Satz im Suchtext trifft irgendwann alles.

    Bindewörter am Ende fallen weg – sie tragen nichts zur Suche bei und
    lassen die Beschreibung aussehen, als wäre sie kaputt.
    """
    woerter = re.sub(r"[^a-z ]", " ", str(roh or "").lower()).split()[:hoechstens]
    while woerter and woerter[-1] in _SCHWEBEND:
        woerter.pop()
    return " ".join(woerter)




# --------------------------------------------------- Das Bild beschaffen

# Nur BrickLinks eigener Bildserver. Die Adresse kommt aus dem Abzug und
# folgt der Nummer, aber eine Weissliste kostet nichts und schliesst aus,
# dass ein manipulierter Eintrag den Dienst irgendwohin schicken kann.
BILD_HOSTS = {"img.bricklink.com"}


def bild_holen(url: str, hosts: set | None = None) -> bytes:
    """Katalogbild von erlaubten CDNs laden."""
    from urllib.parse import urlparse
    p = urlparse(url)
    erlaubt = BILD_HOSTS if hosts is None else hosts
    if p.scheme not in ("http", "https") or p.hostname not in erlaubt:
        raise ValueError("Bild-URL nicht erlaubt")
    resp = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    if len(resp.content) > 10 * 1024 * 1024:
        raise ValueError("Bild zu groß")
    return resp.content




def bild_vorbereiten(raw: bytes, max_side: int = 1200) -> bytes:
    """EXIF-Rotation anwenden, verkleinern, als JPEG komprimieren."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue()