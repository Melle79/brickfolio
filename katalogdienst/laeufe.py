"""Die beiden Läufe: Namen abklappern, Bilder ansehen.

Unverändert übernommen aus der App (2.40.0). Was hier steht, ist über Tage
an echten Daten gereift – die Ziffernbreite je Thema, die 25 Lücken als
Ende, der Unterschied zwischen „Ausfall" und „unbrauchbare Antwort", die
Pause nach einem Fehlschlag. Geändert ist nur die Anbindung: eigene
Datenbank statt der einer Instanz, eigene BrickLink-Anbindung.

Getrennt gehalten sind die Läufe mit Absicht: Der eine holt Namen von
BrickLink und kostet fremdes Kontingent, der andere sieht Bilder an und
kostet Rechenzeit auf dem Mac mini, der nebenher die Heimautomatisierung
macht. Wer beides zusammenwirft, kann keines von beidem einzeln anhalten.
"""
import time

import requests

import bild as bildmodul
from katalog import (bricklink_item, db, einstellung, setze_einstellung,
                     wortanfaenge)


def scrub(text):
    """Zugangsdaten aus einer Fehlermeldung halten.

    Sie landet in der Konsole und im Protokoll; ein `requests`-Fehler kann
    die vollständige Adresse samt Signatur enthalten.
    """
    t = str(text)
    for n in ("BL_CONSUMER_KEY", "BL_CONSUMER_SECRET", "BL_TOKEN",
              "BL_TOKEN_SECRET"):
        import os
        v = os.environ.get(n)
        if v and v in t:
            t = t.replace(v, "…")
    return t[:400]


KATALOG_TAKT = 1.0            # Sekunden zwischen zwei Abrufen

# Buchstaben, mit denen BrickLink Varianten kennzeichnet. „Die erste
# Variante bekommt ueblicherweise `a`, die zweite `b`" -- laut offizieller
# Dokumentation. Abgebrochen wird beim ersten Fehlgriff: Wer kein `b` hat,
# hat auch kein `c`. Bis `f` reicht weit; mehr Varianten hat kaum eine
# Figur, und jeder weitere Buchstabe kostet nur dort etwas, wo es die
# vorherigen wirklich gibt.
VARIANTEN = ("a", "b", "c", "d", "e", "f")
# Lücken sind normal: BrickLink vergibt Nummern, die es später nicht mehr
# gibt. Beim ersten 404 abzubrechen hieße, mitten im Katalog stehen zu
# bleiben. 25 am Stück heißt dagegen zuverlässig: Hier ist das Ende.
KATALOG_LUECKE = 25
KATALOG_MAX = 4000            # Notbremse gegen eine endlose Schleife

# Die Themen, die BrickLink über das Nummernpräfix unterscheidet. Keine
# vollständige Liste – das sind die, die im Haushalt vorkommen. Weitere
# trägt man im Feld einfach dazu; der Lauf prüft selbst, ob es sie gibt.
# Gemessen am 21.08.2026 über die Bestandteile bekannter Sets – eine Liste
# der Präfixe gibt BrickLink nicht heraus. Die Ziffernbreite unterscheidet
# sich je Thema und wird zur Laufzeit ermittelt (siehe `_katalog_breite`).
KATALOG_THEMEN = ["sw", "cty", "njo", "sh", "frnd", "cas", "pi", "hp",
                  "jw", "sp", "ww", "lor", "iaj", "gen",
                  # Am 21.08.2026 mit dem Prüfknopf nachgemessen – alle drei
                  # dreistellig: col001 „Tribal Hunter", adv001 „Achu",
                  # trn001 (Bahnarbeiter). `trn` ist ein eigenes Präfix und
                  # nicht in `cty` enthalten.
                  "col", "adv", "trn"]

_katalog_lauf = {"aktiv": False, "praefix": "", "nummer": 0, "gefunden": 0,
                 "neu": 0, "stop": False, "fehler": "", "seit": 0,
                 "warteschlange": []}


def _katalog_eintragen(item_no: str, daten: dict) -> bool:
    """Eine Figur in den Index schreiben. Wahr, wenn sie neu war."""
    name = (daten.get("name") or "").strip()
    if not name:
        return False
    jetzt = int(time.time())
    with db() as conn:
        vorher = conn.execute(
            "SELECT name FROM katalog_index WHERE item_no = ? AND "
            "item_type = 'minifig'", (item_no,)).fetchone()
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such,"
            " img_url, category_id, jahr, updated_at) "
            "VALUES (?, 'minifig', ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(item_no, item_type) DO UPDATE SET "
            "name = excluded.name, such = excluded.such, "
            "img_url = excluded.img_url, "
            "category_id = excluded.category_id, "
            "jahr = excluded.jahr, updated_at = excluded.updated_at",
            (item_no, name, wortanfaenge(name)[0],
             # Fehlt sie in der Antwort, aus der Nummer bilden: Die
             # Adresse folgt ihr, und der Bildserver unterscheidet nicht
             # zwischen Groß- und Kleinschreibung. Ohne den Rückfall bekäme
             # so eine Figur nie ein Bild – und damit auch nie eine Farbe.
             ((daten.get("img_url") or "").strip()
              # Nicht `/ML/{nr}.jpg`: Das ältere Muster gibt es nicht zu
              # jeder Figur -- 102 von 19.201 gaben dort einen 404, und
              # der Bilderlauf legte sie als „nichts erkannt" ab, obwohl
              # das Bild unter `ItemImage` bereitlag (26.08.2026).
              or "https://img.bricklink.com/ItemImage/MN/0/%s.png" % item_no),
             str(daten.get("category_id") or ""),
             daten.get("year_released") or 0, jetzt))
    return vorher is None


def _katalog_breite(praefix: str) -> int:
    """Wie viele Ziffern hat die Nummer dieses Themas – drei oder vier?

    Das ist keine Kosmetik: `sw0002` gibt es, `sw002` nicht – und umgekehrt
    heißt die Burgfigur `cas001`, nicht `cas0001`. Fest verdrahtete vier
    Ziffern ließen `cas`, `pi`, `hp`, `jw`, `sp`, `ww`, `lor` und `iaj`
    **komplett leer** ausgehen; der Lauf meldete „fertig" nach fünfundzwanzig
    Fehlgriffen. Genau so ist es am 21.08.2026 passiert.

    Ein paar Abrufe zu Beginn klären das ein für alle Mal.
    """
    for breite in (4, 3):
        for n in (1, 2, 3, 5, 10):
            try:
                bricklink_item("minifig",
                                            "%s%0*d" % (praefix, breite, n))
                return breite
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code != 404:
                    # 429 heißt Kontingent erschöpft, 401 falscher Zugang.
                    # Beides als „gibt es nicht" zu lesen hieße, munter
                    # weiterzufragen – der Hauptlauf bricht gleich ohnehin ab.
                    return 4
            except Exception:
                return 4          # Zugang gestört – hier nicht entscheiden
            time.sleep(KATALOG_TAKT)
    return 4


def _katalog_anbau(praefix: str = "sw"):
    """Die Nummern eines Themas der Reihe nach abklappern.

    Setzt dort fort, wo der letzte Lauf aufgehört hat – ein Abbruch nach
    zwanzig Minuten soll nicht bedeuten, dass man wieder bei eins beginnt.
    """
    _katalog_lauf.update({"aktiv": True, "praefix": praefix, "neu": 0,
                          "stop": False, "fehler": "",
                          "seit": int(time.time())})
    try:
        with db() as conn:
            r = conn.execute("SELECT zuletzt FROM katalog_lauf WHERE "
                             "praefix = ?", (praefix,)).fetchone()
        nummer = (r["zuletzt"] if r else 0) + 1
        # Die einmal gemessene Breite steht in der Tabelle. Sie jedes Mal
        # neu zu ermitteln kostet bis zu zehn Abrufe je Thema – bei
        # achtzehn Themen 180 für eine Antwort, die sich nie ändert.
        with db() as conn:
            r = conn.execute("SELECT breite FROM katalog_lauf WHERE "
                             "praefix = ?", (praefix,)).fetchone()
        breite = (r["breite"] if r else 0) or 0
        if not breite:
            breite = _katalog_breite(praefix)
            with db() as conn:
                conn.execute("UPDATE katalog_lauf SET breite = ? WHERE "
                             "praefix = ?", (breite, praefix))
        luecke = 0
        while nummer <= KATALOG_MAX and luecke < KATALOG_LUECKE:
            if _katalog_lauf["stop"]:
                break
            item_no = "%s%0*d" % (praefix, breite, nummer)
            _katalog_lauf["nummer"] = nummer
            try:
                daten = bricklink_item("minifig", item_no)
                if _katalog_eintragen(item_no, daten):
                    _katalog_lauf["neu"] += 1
                _katalog_lauf["gefunden"] += 1
                luecke = 0
                # **Varianten sind eigene Eintraege.** Die offizielle
                # Dokumentation nennt das Format
                # `{Series}{Sequential}{Variant}` mit Beispiel `sw0073a` --
                # und `sw0073a` ist tatsaechlich eine andere Figur als
                # `sw0073` („Dark Bluish Gray Body" statt „Light and Dark
                # Gray"). Ohne diese Schleife fehlt uns jede davon.
                #
                # Kostet einen Abruf je vorhandener Figur: Bei den meisten
                # gibt es kein `a`, und dann ist nach einem Versuch Schluss.
                # Das ist der Preis fuer Vollstaendigkeit, und er faellt nur
                # dort an, wo wirklich eine Figur steht.
                for zusatz in VARIANTEN:
                    if _katalog_lauf["stop"]:
                        break
                    try:
                        d2 = bricklink_item("minifig", item_no + zusatz)
                    except Exception:
                        break            # keine weitere Variante
                    if _katalog_eintragen(item_no + zusatz, d2):
                        _katalog_lauf["neu"] += 1
                    _katalog_lauf["gefunden"] += 1
                    time.sleep(KATALOG_TAKT)
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code == 404:
                    luecke += 1
                else:
                    # Alles andere ist ein Grund aufzuhören: 401 heißt
                    # falscher Zugang, 429 heißt Kontingent erschöpft. Stur
                    # weiterzulaufen machte beides schlimmer.
                    _katalog_lauf["fehler"] = f"BrickLink antwortet mit {code}"
                    break
            except Exception as e:
                _katalog_lauf["fehler"] = scrub(str(e))
                break
            with db() as conn:
                conn.execute(
                    "INSERT INTO katalog_lauf (praefix, zuletzt, hoechste,"
                    " gefunden) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(praefix) DO UPDATE SET zuletzt = ?, "
                    "hoechste = MAX(hoechste, ?), gefunden = ?",
                    (praefix, nummer, nummer, _katalog_lauf["gefunden"],
                     nummer, nummer - luecke, _katalog_lauf["gefunden"]))
            nummer += 1
            time.sleep(KATALOG_TAKT)
        if luecke >= KATALOG_LUECKE:
            # Am Ende angekommen: Den Zeiger hinter die letzte gefundene
            # Nummer zurücksetzen, damit der nächste Lauf die Lücke erneut
            # abtastet – dort können neue Figuren erscheinen.
            with db() as conn:
                conn.execute("UPDATE katalog_lauf SET zuletzt = hoechste, "
                             "fertig_at = ? WHERE praefix = ?",
                             (int(time.time()), praefix))
            print(f"[katalogdienst] Katalog-Anbau {praefix}: fertig, "
                  f"{_katalog_lauf['gefunden']} Figuren "
                  f"({_katalog_lauf['neu']} neu)", flush=True)
    finally:
        _katalog_lauf["aktiv"] = False


# ------------------------------------------------- Farben aus den Bildern
#
# Zweiter Durchgang, getrennt vom Abzug: Der holt die Namen von BrickLink,
# dieser sieht sich die Bilder an. Getrennt, weil er ganz andere Kosten hat –
# kein fremdes Kontingent, dafür Rechenzeit auf dem Mac mini, und der macht
# nebenher die Heimautomatisierung.
#
# **Nur Farben.** Die Art der Figur steht im BrickLink-Namen; das Modell rät
# sie in zwei von drei Fällen falsch (gemessen 21.08.2026: Darth Vader →
# „Droide", AT-AT-Fahrer → „Roboter"). Was es kann, ist die Farbe – und
# genau die fehlt vielen Namen: „R-3PO Protocol Droid" sagt nirgends „rot".
KATALOG_FARB_TAKT = 0.3

# `offen` steht hier bewusst **nicht** mehr drin: Es beschreibt die Daten,
# nicht den Lauf, und wird im Status frisch gezählt. Als Feld im Laufzustand
# war es nach jedem Neustart des Containers 0 – die Oberfläche meldete dann
# „alle Bilder angesehen", während in Wahrheit 8.328 Figuren offen waren
# (gesehen am 22.08.2026 nach drei Ausrollvorgängen an einem Tag).
_farb_lauf = {"aktiv": False, "getan": 0, "gefunden": 0,
              "stop": False, "fehler": ""}


# Wie viele Ausfälle hintereinander, bevor der Lauf aufgibt. Weiterzulaufen
# wäre das Schlimmste: Der Lauf hakte dann eine Figur nach der anderen als
# „angesehen" ab, ohne je hingesehen zu haben, und keine davon käme je wieder
# an die Reihe.
#
# Von fünf auf zwölf heraufgesetzt, mit Pause dazwischen. Fünf passten zu
# einem Lauf über Minuten; der erste vollständige geht über **Stunden**
# (9.000 Figuren zu 4–9 s). Auf dieser Strecke reicht ein Moment, in dem
# Home Assistant das Textmodell in den Speicher zieht und das Bildmodell
# verdrängt wird – dann kippen ein paar Anfragen hintereinander, und der
# ganze Lauf stand still, obwohl nichts kaputt war.
#
# Die Pause ist der eigentliche Griff: Ohne sie prasseln die Versuche im
# Takt von 0,3 s auf ein Ollama ein, das gerade lädt, und brennen die
# Schwelle in anderthalb Sekunden durch. Mit ihr bekommt es Zeit,
# fertigzuladen. Ein echter Ausfall („KI ist weg") wird trotzdem erkannt –
# er dauert dann vier Minuten statt anderthalb Sekunden.
KATALOG_FARB_PATZER = 12
KATALOG_FARB_PAUSE = 20        # Sekunden nach einem Fehlschlag

# Wie oft eine einzelne Figur eine unlesbare Antwort liefern darf, bevor sie
# als angesehen abgehakt wird. Drei, weil die Entgleisung bei
# `temperature: 0` reproduzierbar ist – ein vierter Anlauf brächte dasselbe.
KATALOG_FARB_AUFGEBEN = 3


def _katalog_farben(grenze: int = 0):
    _farb_lauf.update({"aktiv": True, "getan": 0, "gefunden": 0,
                       "stop": False, "fehler": ""})
    patzer = 0
    zaeh: dict = {}          # Figuren, deren Antwort unbrauchbar war
    try:
        while not _farb_lauf["stop"]:
            with db() as conn:
                # `merkmale` ist die Warteschlange, nicht `farben`: Beim
                # Umstieg auf die Teilbeschreibung sollen auch die Figuren
                # noch einmal drankommen, die nach dem alten, dünnen Schema
                # schon eine Farbe bekommen haben.
                rows = conn.execute(
                    "SELECT item_no, img_url FROM katalog_index "
                    "WHERE merkmale = '' AND img_url != '' LIMIT 25").fetchall()
            if not rows:
                break
            for r in rows:
                if _farb_lauf["stop"]:
                    break
                try:
                    roh = bildmodul.bild_holen(r["img_url"])
                    bild = bildmodul.bild_vorbereiten(roh, 512)
                except Exception:
                    # Kein Bild vorhanden (BrickLink liefert für manche
                    # Figuren keins) oder unlesbar. Das ist ein Ergebnis,
                    # kein Ausfall – die Figur ist damit abgearbeitet.
                    m = {"art": "", "farben": [], "fehler": ""}
                else:
                    m = bildmodul.bild_merkmale(bild)

                if m.get("fehler") and m.get("unbrauchbar"):
                    # **Geantwortet, nur unlesbar.** Kein Ausfall des
                    # Dienstes, sondern eine Figur, die das Modell aus dem
                    # Tritt bringt – deshalb keine Pause und kein Zählen auf
                    # den Ausfall-Zähler.
                    #
                    # Nach ein paar Anläufen wird sie trotzdem abgehakt.
                    # Sonst blockiert eine einzige Figur den ganzen Lauf: Ein
                    # Fehlschlag schreibt nichts weg, also steht sie beim
                    # nächsten Griff wieder vorn. Am 24.08.2026 war `cty0131`
                    # die letzte offene von 9.741 – zwölf Anläufe an
                    # derselben Figur, dann war der Lauf beendet.
                    zaeh[r["item_no"]] = zaeh.get(r["item_no"], 0) + 1
                    if zaeh[r["item_no"]] < KATALOG_FARB_AUFGEBEN:
                        continue
                    print("[katalogdienst] %s nach %d unlesbaren Antworten "
                          "übersprungen: %s" % (r["item_no"],
                                                zaeh[r["item_no"]],
                                                m["fehler"][:120]), flush=True)
                    # Kein `continue`: Sie läuft in das Wegschreiben unten und
                    # gilt damit als angesehen, ohne Ergebnis.
                elif m.get("fehler"):
                    # Nichts schreiben: Die Figur wurde nie angesehen. Sie
                    # bleibt offen und kommt beim nächsten Lauf wieder dran.
                    patzer += 1
                    if patzer >= KATALOG_FARB_PATZER:
                        _farb_lauf["fehler"] = (
                            "Die lokale KI antwortet nicht (%d Versuche in "
                            "Folge): %s" % (patzer, m["fehler"]))
                        return
                    # Die Figur bleibt offen und kommt beim nächsten Griff in
                    # die Warteschlange von selbst wieder – ein eigener
                    # Wiederholungszweig wäre hier nur doppelt.
                    time.sleep(KATALOG_FARB_PAUSE)
                    continue
                else:
                    patzer = 0
                # Auch ein leeres Ergebnis festhalten – sonst versucht der
                # nächste Lauf dieselbe Figur wieder und käme nie ans Ende.
                with db() as conn:
                    # `updated_at` zieht mit: Die Zeile hat sich geändert,
                    # und der Schieber zum Hub erkennt Änderungen genau
                    # daran. Ohne das bliebe jede frisch analysierte Figur
                    # für ihn unsichtbar.
                    conn.execute("UPDATE katalog_index SET farben = ?, "
                                 "art = ?, merkmale = ?, updated_at = ? "
                                 "WHERE item_no = ?",
                                 (", ".join(m["farben"]) or "–", m["art"],
                                  m.get("merkmale") or "–", int(time.time()),
                                  r["item_no"]))
                _farb_lauf["getan"] += 1
                if m["farben"] or m["art"] or m.get("merkmale"):
                    _farb_lauf["gefunden"] += 1
                if grenze and _farb_lauf["getan"] >= grenze:
                    return
                time.sleep(KATALOG_FARB_TAKT)
    finally:
        _farb_lauf["aktiv"] = False




def _katalog_reihe(praefixe: list):
    """Ein Thema nach dem anderen – nicht nebeneinander.

    Parallel liefe schneller und wäre genau falsch: Alle Läufe teilen sich
    denselben BrickLink-Zugang. Zwei gleichzeitig hieße doppelter Takt,
    also die Drosselung ausgehebelt, für die es hier gute Gründe gibt.
    """
    # Die Warteschlange ist die Wahrheit, nicht `praefixe`: Wer während des
    # Laufs ein Thema nachreicht, hängt es hier an – bei einem Lauf über
    # Stunden ist „warte, bis er durch ist" keine zumutbare Antwort.
    _katalog_lauf["warteschlange"] = list(praefixe)
    while _katalog_lauf["warteschlange"]:
        if _katalog_lauf["stop"]:
            break
        p = _katalog_lauf["warteschlange"].pop(0)
        _katalog_anbau(p)
        # Ein Abbruch aus dem Lauf heraus (429, falscher Zugang) gilt für
        # alle folgenden Themen mit – der Zugang ist derselbe.
        if _katalog_lauf["fehler"]:
            break
    _katalog_lauf["warteschlange"] = []


