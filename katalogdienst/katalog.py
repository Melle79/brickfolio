"""Den Katalogabzug erzeugen – auf der NAS, neben der Hub-Konsole.

Warum überhaupt ein eigener Abzug: Der rote Protokolldroide heißt bei
Rebrickable schlicht `R-3PO` – kein „rot", kein „Protokolldroide", nichts zum
Suchen. BrickLink nennt dieselbe Figur „R-3PO Protocol Droid", und das Bild
zeigt einen schwarzen Aufdruck auf rotem Torso. Wer eine Figur beschreibt
statt sie zu benennen, findet sie nur über einen eigenen Abzug.

Warum hier und nicht in jeder Instanz: Der Abzug beschreibt BrickLinks Fotos,
nicht die Sammlung von irgendwem – er ist für alle identisch. Ihn viermal zu
bauen wäre viermal dieselbe Arbeit: Tage an Abrufen und rund ein Tag
Grafikeinheit, je Instanz. Und jede bräuchte eigene BrickLink-Zugangsdaten
und ein Sehmodell; drei von vier haben beides nicht.

Warum hier und nicht bei Cloudflare: Dort war es am 24.08.2026 zweimal
gemessen unbrauchbar – der Cron löste über eine halbe Stunde und mehrere
Termine kein einziges Mal aus, und Workers AI beantwortete die Sichtprobe
mit einem Fehler. Das lokale `qwen3-vl` auf dem Mac mini trifft dagegen
nachweislich: Beim Dragon Master kam „Umhang gelb, grüner Drache mit roten
Flügeln" heraus, deckungsgleich mit dem BrickLink-Namen.

Die Zugangsdaten bleiben damit zu Hause, und geplante Arbeit läuft auf einem
Rechner, der sie nachweislich ausführt.
"""
import io
import json
import os
import re
import sqlite3
import threading
import time

import requests
from PIL import Image, ImageOps

DB_PATH = os.environ.get("DB_PATH", "/data/katalog.db")
USER_AGENT = "Brickfolio-Katalogdienst"

# --------------------------------------------------------------- Datenbank


def db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS katalog_index (
    item_no TEXT NOT NULL,
    item_type TEXT NOT NULL DEFAULT 'minifig',
    name TEXT NOT NULL,
    -- Derselbe Name ohne Satzzeichen, zusammengezogen. Der Vorfilter in SQL
    -- muss dieselbe Elle benutzen wie der Vergleich in der Instanz: „c3 po"
    -- soll `C-3PO` finden, und `LIKE '%c3%'` auf dem rohen Namen scheitert
    -- am Bindestrich.
    such TEXT NOT NULL DEFAULT '',
    img_url TEXT NOT NULL DEFAULT '',
    farben TEXT NOT NULL DEFAULT '',
    art TEXT NOT NULL DEFAULT '',
    -- Die Figur Teil für Teil: „torso red black and yellow dragon design;
    -- cape yellow green dragon with red wings". Farbe allein reichte nicht:
    -- „roter Droide" fand etwas, „roter Droide mit schwarzem Aufdruck" nicht.
    -- Leer heißt „noch nicht angesehen" – die Spalte ist zugleich die
    -- Warteschlange des Bilderlaufs.
    merkmale TEXT NOT NULL DEFAULT '',
    modell TEXT NOT NULL DEFAULT '',
    -- Wie oft eine Figur eine unbrauchbare Antwort geliefert hat. Am
    -- 24.08.2026 blieb der Lauf bei 9.740 von 9.741 stehen: `cty0131`
    -- brachte das Modell aus dem Tritt, ein Fehlschlag schreibt nichts weg,
    -- also stand sie beim nächsten Griff wieder vorn – zwölf Anläufe an
    -- derselben Figur.
    versuche INTEGER NOT NULL DEFAULT 0,
    category_id TEXT,
    jahr INTEGER,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (item_no, item_type)
);
CREATE INDEX IF NOT EXISTS idx_katalog_such ON katalog_index(such);
CREATE INDEX IF NOT EXISTS idx_katalog_stand ON katalog_index(updated_at);

CREATE TABLE IF NOT EXISTS katalog_lauf (
    praefix TEXT PRIMARY KEY,
    -- 0 heißt „noch nicht ermittelt"; der Lauf misst es dann selbst nach.
    -- Fest verdrahtete vier Ziffern ließen am 21.08.2026 acht Themen
    -- komplett leer ausgehen – und meldeten trotzdem „fertig".
    breite INTEGER NOT NULL DEFAULT 0,
    zuletzt INTEGER NOT NULL DEFAULT 0,
    -- Die hoechste je gefundene Nummer. Am Ende eines Themas wird `zuletzt`
    -- hierauf zurueckgesetzt, damit der naechste Lauf die Luecke dahinter
    -- erneut abtastet -- dort erscheinen neue Figuren.
    hoechste INTEGER NOT NULL DEFAULT 0,
    luecke INTEGER NOT NULL DEFAULT 0,
    gefunden INTEGER NOT NULL DEFAULT 0,
    fertig_at INTEGER,
    aktiv INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS einstellungen (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Die am 21./24.08.2026 gemessenen Themen. Keine vollständige Liste – die
# gibt BrickLink nicht heraus –, aber alle, die der Abzug bisher gefunden
# hat. Weitere trägt man in der Konsole dazu; die Breite misst der Lauf.
STANDARD_THEMEN = ["sw", "cty", "njo", "sh", "frnd", "cas", "pi", "hp",
                   "jw", "sp", "ww", "lor", "iaj", "gen", "col", "adv",
                   "trn", "idea"]


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with db() as conn:
        conn.executescript(SCHEMA)
        for p in STANDARD_THEMEN:
            conn.execute("INSERT OR IGNORE INTO katalog_lauf (praefix) "
                         "VALUES (?)", (p,))


def einstellung(name, standard=""):
    with db() as conn:
        r = conn.execute("SELECT value FROM einstellungen WHERE name = ?",
                         (name,)).fetchone()
    return r["value"] if r else standard


def konfig(name, standard=""):
    """Ein Wert – aus der Datenbank, sonst aus der Umgebung.

    Die Datenbank hat Vorrang: Was in der Konsole eingetragen wurde, gilt.
    Die Umgebung bleibt als Weg für alles, was beim Einrichten schon
    feststeht – so läuft der Dienst auch ohne einen einzigen Klick.

    Ändert sich ein Wert, muss `konfig_vergessen()` gerufen werden; sonst
    arbeitet der laufende Prozess mit dem alten weiter, und man sucht den
    Fehler an der falschen Stelle.
    """
    if _konfig_cache is None:
        _konfig_laden()
    if name in _konfig_cache and _konfig_cache[name]:
        return _konfig_cache[name]
    return os.environ.get(name) or standard


_konfig_cache = None


def _konfig_laden():
    global _konfig_cache
    with db() as conn:
        _konfig_cache = {r["name"]: r["value"] for r in
                         conn.execute("SELECT name, value FROM einstellungen")}


def konfig_vergessen():
    global _konfig_cache
    _konfig_cache = None


def setze_einstellung(name, wert):
    with db() as conn:
        conn.execute("INSERT INTO einstellungen (name, value) VALUES (?, ?) "
                     "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
                     (name, str(wert)))
    konfig_vergessen()


# -------------------------------------------------------------- BrickLink


def bl_auth():
    """Die vier Werte aus der Umgebung – sie bleiben auf der NAS."""
    from requests_oauthlib import OAuth1
    fehlt = [n for n in BL_FELDER if not konfig(n)]
    if fehlt:
        raise RuntimeError("BrickLink ist nicht eingerichtet: "
                           + ", ".join(fehlt))
    return OAuth1(konfig("BL_CONSUMER_KEY"), konfig("BL_CONSUMER_SECRET"),
                  konfig("BL_TOKEN"), konfig("BL_TOKEN_SECRET"))


BL_FELDER = ("BL_CONSUMER_KEY", "BL_CONSUMER_SECRET", "BL_TOKEN",
             "BL_TOKEN_SECRET")


def bl_enabled():
    return all(konfig(n) for n in BL_FELDER)


def bricklink_item(item_type, item_no):
    """Eine Figur bei BrickLink nachschlagen.

    **Wirft bei „gibt es nicht" eine `HTTPError` mit 404**, statt `None`
    zurückzugeben. Das ist kein Schönheitsfehler, sondern der Vertrag, auf
    dem der Lückenzähler steht: `_katalog_anbau` unterscheidet am Statuscode
    zwischen „Nummer existiert nicht" (weiterzählen) und „401/429"
    (aufhören). Gäbe es hier `None`, liefe der Lauf bei erschöpftem
    Kontingent munter weiter und hielte 4.000 Fehlgriffe für Lücken.
    """
    r = requests.get(
        "https://api.bricklink.com/api/store/v1/items/%s/%s"
        % (item_type, item_no),
        auth=bl_auth(), timeout=20, headers={"User-Agent": USER_AGENT})
    # BrickLink verpackt alles in `meta` + `data`; ein 200 mit meta.code 404
    # kommt vor und heißt dasselbe wie ein echter 404.
    if r.status_code == 200:
        d = r.json()
        meta = d.get("meta") or {}
        code = meta.get("code", 200)
        if code < 400:
            return d.get("data")
        r.status_code = code
    r.raise_for_status()
    raise requests.HTTPError("BrickLink %s" % r.status_code, response=r)


# ------------------------------------------------------------ Suchtext


def wortanfaenge(name):
    """Der Name ohne Satzzeichen, zusammengezogen.

    Die Satzzeichen müssen weg, damit „c3 po" den Artikel „C-3PO" findet –
    und zusammengezogen, weil die Instanz mit `such LIKE '%c3%'` vorfiltert.
    Mit Leerzeichen („c 3po") fände dieser Vorfilter nichts, und die Suche,
    für die der ganze Abzug da ist, liefe ins Leere.
    """
    return "".join(w for w in re.split(r"[^a-z0-9]+", str(name).lower()) if w)
