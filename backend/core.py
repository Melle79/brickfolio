"""Brickfolio – Datenbank & Authentifizierung."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager

import jwt

DB_PATH = os.environ.get("DB_PATH", "/data/brickfolio.db")
SECRET_KEY_FILE = os.environ.get("SECRET_KEY_FILE", "/data/secret.key")
TOKEN_DAYS = int(os.environ.get("TOKEN_DAYS", "90"))

PBKDF2_ITERATIONS = 200_000


def _load_secret() -> str:
    """Secret aus ENV, sonst persistent aus Datei (wird beim ersten Start erzeugt)."""
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    try:
        with open(SECRET_KEY_FILE, "r") as f:
            key = f.read().strip()
            if key:
                return key
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    os.makedirs(os.path.dirname(SECRET_KEY_FILE), exist_ok=True)
    with open(SECRET_KEY_FILE, "w") as f:
        f.write(key)
    os.chmod(SECRET_KEY_FILE, 0o600)
    return key


SECRET_KEY = _load_secret()


# ---------------------------------------------------------------- Passwörter

APP_VERSION = "2.64.0"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return hmac.compare_digest(check, digest)
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------- Tokens

def sitzungs_zaehler(user_id: int) -> int:
    """Aktueller Stand des Kontos. Steht er nicht im Token, ist es 0."""
    with db() as conn:
        row = conn.execute("SELECT token_epoch FROM users WHERE id = ?",
                           (user_id,)).fetchone()
    return int(row["token_epoch"]) if row and row["token_epoch"] else 0


def sitzungen_beenden(user_id: int) -> None:
    """Alle bestehenden Sitzungen dieses Kontos ungültig machen."""
    with db() as conn:
        conn.execute("UPDATE users SET token_epoch = COALESCE(token_epoch, 0)"
                     " + 1 WHERE id = ?", (user_id,))


def create_token(user_id: int, username: str, is_admin: bool,
                 minutes: int | None = None, zweck: str | None = None) -> str:
    """Sitzungs-Token – oder mit `zweck` eine kurzlebige Zwischenmarke.

    Die Marke für den zweiten Anmeldeschritt trägt `zweck="2fa"` und wird
    deshalb von `current_user` **nicht** als Sitzung akzeptiert: Sonst käme
    man mit dem halben Anmeldevorgang schon an alle Daten.
    """
    payload = {
        "sub": str(user_id),
        "name": username,
        "adm": bool(is_admin),
        "exp": int(time.time()) + (minutes * 60 if minutes
                                   else TOKEN_DAYS * 86400),
    }
    if zweck:
        payload["zweck"] = zweck
    else:
        # Nur echte Sitzungen tragen den Zählerstand – die Zwischenmarke des
        # zweiten Anmeldeschritts lebt ohnehin nur Minuten.
        payload["tv"] = sitzungs_zaehler(user_id)
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------- Datenbank

@contextmanager
def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def wortanfaenge(name: str) -> tuple:
    """Der Name ohne Satzzeichen – und die Stellen, an denen ein Wort beginnt.

    Die Satzzeichen müssen weg, damit „c3 po" den Artikel „C-3PO" findet.
    Ohne die Wortanfänge wäre der Vergleich aber zu großzügig: „Mage" steckt
    in „Damaged", und „Zauberer" lieferte damit einen kampfbeschädigten
    Anakin Skywalker aus einer echten Sammlung.
    """
    ganz, anfaenge = "", []
    for wort in re.split(r"[^a-z0-9]+", name.lower()):
        if not wort:
            continue
        anfaenge.append(len(ganz))
        ganz += wort
    return ganz, tuple(anfaenge)


def get_user_setting(user_id: int, schluessel: str, standard=None):
    """Eine Einstellung dieses Benutzers – oder `standard`, wenn keine da ist."""
    with db() as conn:
        r = conn.execute(
            "SELECT wert FROM benutzer_einstellungen"
            " WHERE user_id = ? AND schluessel = ?",
            (user_id, schluessel)).fetchone()
    return r["wert"] if r else standard


def set_user_setting(user_id: int, schluessel: str, wert: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO benutzer_einstellungen (user_id, schluessel, wert)"
            " VALUES (?, ?, ?) ON CONFLICT(user_id, schluessel)"
            " DO UPDATE SET wert = excluded.wert",
            (user_id, schluessel, wert))


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            );
            -- Einstellungen, die zum **Benutzer** gehören, nicht zur
            -- Instanz. Bis 2.47.1 lag der schonende Bildmodus allein im
            -- `localStorage` – und der gehört zur Adresse, nicht zum
            -- Gerät. Wer dieselbe App im Heimnetz über `http://…:8300`
            -- und von außen über HTTPS benutzt, hat zwei getrennte
            -- Speicher: Der Schalter war gesetzt und wirkte trotzdem
            -- nicht, weil er auf der anderen Adresse nie gesetzt worden
            -- war. Bei einer Einstellung, die Abstürze verhindern soll,
            -- ist das der schlechteste denkbare Ort (25.08.2026).
            CREATE TABLE IF NOT EXISTS benutzer_einstellungen (
                user_id INTEGER NOT NULL,
                schluessel TEXT NOT NULL,
                wert TEXT NOT NULL,
                PRIMARY KEY (user_id, schluessel)
            );
            CREATE TABLE IF NOT EXISTS collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT NOT NULL,           -- BrickLink-Nr., z.B. sw0001a
                item_type TEXT NOT NULL,         -- minifig / part / set
                name TEXT NOT NULL,
                img_url TEXT,
                bricklink_url TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                condition TEXT NOT NULL DEFAULT 'used',
                notes TEXT NOT NULL DEFAULT '',
                added_by INTEGER REFERENCES users(id),
                added_at INTEGER NOT NULL,
                UNIQUE (item_id, item_type, condition)
            );
            CREATE INDEX IF NOT EXISTS idx_collection_name ON collection(name);
            CREATE TABLE IF NOT EXISTS settings (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS wanted (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                name TEXT NOT NULL,
                img_url TEXT,
                bricklink_url TEXT,
                year INTEGER,
                notes TEXT NOT NULL DEFAULT '',
                price_new REAL,
                price_used REAL,
                price_updated_at INTEGER,
                price_data TEXT,
                added_by INTEGER REFERENCES users(id),
                added_at INTEGER NOT NULL,
                UNIQUE (item_id, item_type)
            );
            CREATE TABLE IF NOT EXISTS set_contents (
                set_no TEXT NOT NULL,
                fig_no TEXT NOT NULL,
                qty INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (set_no, fig_no)
            );
            CREATE TABLE IF NOT EXISTS set_meta (
                set_no TEXT PRIMARY KEY,
                figs_fetched_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS shopping_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0,
                archived_at INTEGER,
                inventoried INTEGER NOT NULL DEFAULT 0,
                created_by INTEGER REFERENCES users(id),
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS shopping_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL REFERENCES shopping_lists(id),
                item_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                name TEXT NOT NULL,
                img_url TEXT,
                bricklink_url TEXT,
                year INTEGER,
                qty INTEGER NOT NULL DEFAULT 1,
                condition TEXT NOT NULL DEFAULT 'used',
                price_new REAL,
                price_used REAL,
                price_updated_at INTEGER,
                price_data TEXT,
                paid_price REAL,
                done INTEGER NOT NULL DEFAULT 0,
                done_at INTEGER,
                done_by INTEGER REFERENCES users(id),
                added_at INTEGER NOT NULL
            );
            -- Tausch-Vorgänge und Nachrichten. Der Hub löscht Umschläge nach
            -- der Zustellung; der lesbare Verlauf lebt hier weiter.
            CREATE TABLE IF NOT EXISTS trades (
                id          TEXT PRIMARY KEY,      -- trd_… vom Hub
                direction   TEXT NOT NULL,         -- out (ich frage) | in
                other_id    TEXT NOT NULL,         -- Member-ID des Gegenübers
                other_name  TEXT NOT NULL,
                item_id     TEXT NOT NULL,
                item_name   TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'open',
                created_at  INTEGER NOT NULL,
                updated_at  INTEGER NOT NULL,
                read_at     INTEGER
            );
            CREATE TABLE IF NOT EXISTS trade_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id   TEXT NOT NULL,
                hub_id     INTEGER,               -- ID im Hub (für Dubletten)
                mine       INTEGER NOT NULL,      -- 1 = von mir
                body       TEXT NOT NULL,         -- entschlüsselter Text
                created_at INTEGER NOT NULL,
                delivered  INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_tmsg
                ON trade_messages(trade_id, created_at);
            CREATE TABLE IF NOT EXISTS fig_sets (
                fig_no TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                fetched_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fig_parts (
                fig_no TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                fetched_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                ts INTEGER NOT NULL,
                price_new REAL,
                price_used REAL
            );
            CREATE INDEX IF NOT EXISTS idx_history_item
                ON price_history(item_id, item_type, ts);
            -- Was die Suche gelernt hat: deutscher Begriff -> englische
            -- Katalogbegriffe.
            --
            -- Bis 2.31.0 stand das nur im Arbeitsspeicher. Damit war es nach
            -- jedem Neustart weg, und **nur das Modell** schrieb hinein –
            -- ansehen oder korrigieren ließ sich nichts. Wer „roter c3po"
            -- tippte, bekam für immer C-3PO-Varianten, obwohl die Figur
            -- R-3PO heißt.
            --
            -- `quelle` entscheidet den Vorrang: 'hand' schlägt 'ki'. Eine von
            -- Hand eingetragene Zeile darf das Modell nicht überschreiben,
            -- sonst wäre das Gelernte beim nächsten Suchlauf wieder weg.
            --
            -- Die Liste hängt bewusst an der App, nicht am Modell: Ein
            -- Wechsel des Modells oder des Rechners nimmt den Wissensstand
            -- mit, ein nachtrainiertes Modell täte das nicht.
            CREATE TABLE IF NOT EXISTS suchbegriffe (
                begriff TEXT PRIMARY KEY,
                begriffe TEXT NOT NULL,
                quelle TEXT NOT NULL DEFAULT 'ki',
                created_at INTEGER NOT NULL,
                used_at INTEGER
            );
            -- Ein lokaler Abzug des BrickLink-Katalogs, Thema für Thema.
            --
            -- Wozu: Rebrickable nennt die Figur schlicht `R-3PO`, BrickLink
            -- „R-3PO Protocol Droid". Wer den roten Protokolldroiden sucht,
            -- ohne seinen Namen zu kennen, findet ihn nur über die
            -- beschreibenden Wörter – und die gibt es nur hier. Kein Modell
            -- muss dafür etwas wissen; gesucht wird in eigenem Text.
            --
            -- Gefüllt wird über die Nummern: `sw0001`, `sw0002`, … Das
            -- Präfix kodiert das Thema, eine Auflistung bietet BrickLink
            -- nicht an (`items/MINIFIG?category_id=…` ist dort kein
            -- gültiger Weg, geprüft am 21.08.2026).
            CREATE TABLE IF NOT EXISTS katalog_index (
                item_no TEXT NOT NULL,
                item_type TEXT NOT NULL DEFAULT 'minifig',
                name TEXT NOT NULL,
                -- Derselbe Name ohne Satzzeichen, kleingeschrieben. Der
                -- Vorfilter in SQL muss dieselbe Elle benutzen wie der
                -- Vergleich in Python: „c3 po" soll `C-3PO` finden, und
                -- `LIKE '%c3%'` auf dem rohen Namen scheitert am
                -- Bindestrich. Ohne diese Spalte müsste der ganze Index
                -- durch Python – bei einem Thema egal, bei allen nicht.
                such TEXT NOT NULL DEFAULT '',
                img_url TEXT NOT NULL DEFAULT '',
                -- Was auf dem Bild zu sehen ist – **nur Farben**.
                --
                -- Gemessen am 21.08.2026 auf dem Mac mini: `minicpm-v`
                -- nennt die richtige Farbe in allen Proben, die **Art der
                -- Figur** aber in zwei von drei falsch (Darth Vader →
                -- „Droide", AT-AT-Fahrer → „Roboter"). Die Art steht
                -- ohnehin schon im BrickLink-Namen; sie hier noch einmal
                -- raten zu lassen brächte nur Fehler hinein.
                --
                -- Leer heißt „noch nicht angesehen", nicht „keine Farbe".
                farben TEXT NOT NULL DEFAULT '',
                -- Was für eine Figur: „Soldat", „Droide", „Alien" …
                -- Getrennt von der Farbe, damit man beides einzeln
                -- verwerfen kann, wenn ein Modell danebenliegt.
                art TEXT NOT NULL DEFAULT '',
                -- Die Figur Teil für Teil: „torso red black and yellow
                -- dragon design; cape yellow green dragon with red wings".
                --
                -- Farbe allein reichte nicht: „roter Droide" fand etwas,
                -- „roter Droide mit schwarzem Aufdruck" nicht – der Aufdruck
                -- kam im Suchtext gar nicht vor. Englisch wie der Katalog,
                -- weil die Suchbegriffe aus der Übersetzung kommen.
                --
                -- Leer heißt „noch nicht angesehen": Die Spalte ist zugleich
                -- die Warteschlange des Bilderlaufs.
                merkmale TEXT NOT NULL DEFAULT '',
                category_id TEXT,
                jahr INTEGER,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (item_no, item_type)
            );
            CREATE INDEX IF NOT EXISTS idx_katalog_such
                ON katalog_index(such);
            -- Wie weit der Anbau gekommen ist, je Präfix. Ohne das begänne
            -- ein abgebrochener Lauf wieder bei eins – bei 1.400 Nummern im
            -- Sekundentakt wäre das eine halbe Stunde für nichts.
            CREATE TABLE IF NOT EXISTS katalog_lauf (
                praefix TEXT PRIMARY KEY,
                zuletzt INTEGER NOT NULL DEFAULT 0,
                hoechste INTEGER NOT NULL DEFAULT 0,
                gefunden INTEGER NOT NULL DEFAULT 0,
                fertig_at INTEGER
            );
            -- Gemeldete Fehler. Gleichartige Fehler werden über den
            -- fingerprint zusammengefasst und nur hochgezählt.
            CREATE TABLE IF NOT EXISTS error_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL UNIQUE,
                message TEXT NOT NULL,
                detail TEXT,
                context TEXT,
                app_version TEXT,
                user_agent TEXT,
                username TEXT,
                count INTEGER NOT NULL DEFAULT 1,
                first_at INTEGER NOT NULL,
                last_at INTEGER NOT NULL,
                issue_url TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_error_last ON error_log(last_at);
            -- Hinweise, die stehen bleiben, bis sie jemand wegklickt –
            -- etwa wenn BrickLink eine Nummer aus der Sammlung umbenennt
            -- oder löscht. UNIQUE verhindert, dass derselbe Artikel bei
            -- jedem Preislauf einen neuen Hinweis erzeugt.
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                item_type TEXT,
                item_id TEXT,
                new_item_id TEXT,
                title TEXT NOT NULL,
                body TEXT,
                created_at INTEGER NOT NULL,
                dismissed_at INTEGER,
                UNIQUE(kind, item_type, item_id)
            );
            CREATE INDEX IF NOT EXISTS idx_notif_open
                ON notifications(dismissed_at, created_at);
            -- Geräte, die per Web-Push benachrichtigt werden wollen. Die
            -- Adresse (endpoint) zeigt auf den Push-Dienst des jeweiligen
            -- Browser-Herstellers und ist je Gerät und Installation eindeutig.
            -- Öffentliche Schlüssel der Gegenüber, so wie wir sie beim
            -- **ersten** Mal gesehen haben. Verteilt werden sie vom Hub –
            -- wer den kontrolliert, könnte einen eigenen unterschieben und
            -- mitlesen. Ein einmal gemerkter Schlüssel macht genau das
            -- sichtbar: Ändert er sich, stimmt etwas nicht.
            CREATE TABLE IF NOT EXISTS hub_keys (
                member_id  TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                first_seen INTEGER NOT NULL,
                name       TEXT
            );
            -- Eigene Fotos zu einem Artikel – **zusätzlich** zum Katalogbild,
            -- so wie die Bilder, die Käufer bei BrickLink beisteuern. Sie
            -- hängen am Artikel, nicht an der einzelnen Sammlungszeile: Wer
            -- dieselbe Figur zweimal hat, hat auch zweimal dieselben Fotos.
            CREATE TABLE IF NOT EXISTS item_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL,
                item_id TEXT NOT NULL,
                url TEXT NOT NULL,
                added_by INTEGER REFERENCES users(id),
                added_at INTEGER NOT NULL,
                UNIQUE (item_type, item_id, url)
            );
            CREATE INDEX IF NOT EXISTS idx_item_photos
                ON item_photos(item_type, item_id);
            -- Unter welcher Nummer BrickLink ein Teil führt. Die beiden
            -- Kataloge zählen Bedruckungen verschieden: Der Gungan-Schild
            -- heißt bei Rebrickable `2586pr0028`, bei BrickLink `2586ps1`.
            -- Die Übersetzung kostet einen Abruf nach draußen und ändert
            -- sich praktisch nie – also einmal fragen und behalten. Ein
            -- leeres `bl_no` heißt „nachgesehen, nichts gefunden" und
            -- bewahrt vor derselben vergeblichen Frage bei jedem Aufklappen.
            CREATE TABLE IF NOT EXISTS bl_nummern (
                item_id TEXT PRIMARY KEY,
                bl_no TEXT NOT NULL,
                checked_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS push_subs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                user_agent TEXT,
                created_at INTEGER NOT NULL
            );
            -- Der Primärschlüssel (set_no, fig_no) hilft nur bei Suche nach
            -- set_no. Die Sammlung fragt aber je Zeile nach fig_no ("in Sets").
            CREATE INDEX IF NOT EXISTS idx_set_contents_fig
                ON set_contents(fig_no);
            CREATE INDEX IF NOT EXISTS idx_shopping_items_list
                ON shopping_items(list_id);
            """
        )
        # Migration: frühere Scans speicherten Brickognize-Typ "fig"
        conn.execute(
            "UPDATE collection SET item_type = 'minifig' WHERE item_type = 'fig'")
        # Migration: UNIQUE-Constraint um den Zustand erweitern, damit
        # dieselbe Figur einmal neu UND einmal gebraucht existieren kann.
        # SQLite kann Constraints nicht ändern -> Tabelle einmalig umbauen.
        ddl_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' "
            "AND name = 'collection'").fetchone()
        if ddl_row and "UNIQUE (item_id, item_type)" in ddl_row["sql"] \
                and "item_type, condition" not in ddl_row["sql"]:
            # SQLite-Standardrezept: FK-Prüfung während des Umbaus aus
            conn.commit()
            conn.execute("PRAGMA foreign_keys = OFF")
            try:
                new_ddl = ddl_row["sql"].replace(
                    "UNIQUE (item_id, item_type)",
                    "UNIQUE (item_id, item_type, condition)").replace(
                    "CREATE TABLE collection", "CREATE TABLE collection_new",
                    1)
                conn.execute(new_ddl)
                conn.execute("INSERT INTO collection_new "
                             "SELECT * FROM collection")
                conn.execute("DROP TABLE collection")
                conn.execute("ALTER TABLE collection_new "
                             "RENAME TO collection")
                conn.commit()
            finally:
                conn.execute("PRAGMA foreign_keys = ON")
            print("[brickfolio] Migration: Sammlung erlaubt jetzt "
                  "getrennte Einträge je Zustand", flush=True)

        # Migration: Bildadresse im Katalog-Abzug.
        #
        # Bis 2.33.1 wurde sie nicht gespeichert – Treffer aus dem Abzug
        # kamen ohne Bild, obwohl BrickLink sie in derselben Antwort
        # mitliefert. Nachfüllen kostet **keinen** einzigen Abruf: Die
        # Adresse folgt der Nummer, und der Bildserver unterscheidet nicht
        # zwischen Groß- und Kleinschreibung (geprüft am 21.08.2026).
        kat_cols = [r["name"] for r in
                    conn.execute("PRAGMA table_info(katalog_index)")]
        if kat_cols and "img_url" not in kat_cols:
            conn.execute("ALTER TABLE katalog_index ADD COLUMN "
                         "img_url TEXT NOT NULL DEFAULT ''")
        if kat_cols and "farben" not in kat_cols:
            conn.execute("ALTER TABLE katalog_index ADD COLUMN "
                         "farben TEXT NOT NULL DEFAULT ''")
        if kat_cols and "art" not in kat_cols:
            conn.execute("ALTER TABLE katalog_index ADD COLUMN "
                         "art TEXT NOT NULL DEFAULT ''")
        # Migration: Bildadressen vom älteren `/ML/`-Muster auf `ItemImage`.
        # Das ältere gibt es nicht zu jeder Figur -- von 19.201 lieferte es
        # bei 102 einen 404 (Embo, Tee Vee, die Fabuland-Tiere, sämtliche
        # Duplo-Figuren), und in der App blieb dort der Platzhalter stehen.
        # `ItemImage` liefert auch alles, was `/ML/` liefert (26.08.2026).
        if kat_cols:
            n = conn.execute(
                "UPDATE katalog_index SET img_url ="
                " 'https://img.bricklink.com/ItemImage/MN/0/' || item_no"
                " || '.png' WHERE item_type = 'minifig'"
                " AND img_url LIKE 'https://img.bricklink.com/ML/%'").rowcount
            if n:
                print("[brickfolio] %d Bildadressen umgestellt" % n, flush=True)
        # Migration: HTML-Zeichen in Namen auflösen. Der Dateiimport aus
        # 2.46.0 gab sie unverändert weiter – in BrickLinks Ausfuhr steht
        # `&amp;#39;`, das XML macht daraus `&#39;`, und erst `unescape`
        # macht daraus ein Hochkomma. Auf einer Instanz standen dadurch
        # 3.558 Namen als `Knights&#39; Kingdom` da, und wer nach
        # „Knights' Kingdom" suchte, fand sie nicht (25.08.2026).
        #
        # `such` muss mit: Der Suchtext wird aus dem Namen abgeleitet, ein
        # berichtigter Name mit altem Suchtext wäre nur halb geheilt.
        if kat_cols:
            import html as _html
            kaputt = conn.execute(
                "SELECT item_no, item_type, name FROM katalog_index"
                " WHERE name LIKE '%&#%' OR name LIKE '%&amp;%'").fetchall()
            for r in kaputt:
                klar = _html.unescape(r["name"])
                if klar == r["name"]:
                    continue
                conn.execute(
                    "UPDATE katalog_index SET name = ?, such = ?"
                    " WHERE item_no = ? AND item_type = ?",
                    (klar, wortanfaenge(klar)[0],
                     r["item_no"], r["item_type"]))
            if kaputt:
                print("[brickfolio] %d Namen entschlüsselt" % len(kaputt),
                      flush=True)
        # Migration: Die Figur Teil für Teil – Torso, Kopf, Haare, Helm, samt
        # Aufdruck und dessen Farben. Vorher standen hier Art und bis zu drei
        # Farben; damit fand „roter Droide" zwar etwas, „roter Droide mit
        # schwarzem Aufdruck" aber nicht, weil der Aufdruck im Suchtext gar
        # nicht vorkam. Leer heißt „noch nicht angesehen" – die Spalte ist
        # deshalb zugleich die Warteschlange des Bilderlaufs, und alles
        # bisher Angesehene wird mit der neuen Frage noch einmal geholt.
        if kat_cols and "merkmale" not in kat_cols:
            conn.execute("ALTER TABLE katalog_index ADD COLUMN "
                         "merkmale TEXT NOT NULL DEFAULT ''")
        if kat_cols:
            n = conn.execute(
                "UPDATE katalog_index SET img_url = "
                "'https://img.bricklink.com/ML/' || item_no || '.jpg' "
                "WHERE img_url = ''").rowcount
            if n:
                print(f"[brickfolio] Migration: {n} Bildadressen im "
                      f"Katalog-Abzug nachgetragen", flush=True)

        # Migration: Quelle je Preisverlaufs-Punkt (auto/manuell)
        ph_cols = [r["name"] for r in
                   conn.execute("PRAGMA table_info(price_history)")]
        if "source" not in ph_cols:
            conn.execute("ALTER TABLE price_history ADD COLUMN source TEXT")

        # Migration: Preisspalten für den Sammlungswert
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(collection)")]
        for col, typ in (("price_new", "REAL"), ("price_used", "REAL"),
                         ("price_updated_at", "INTEGER"),
                         ("price_data", "TEXT"), ("year", "INTEGER"),
                         ("paid_price", "REAL"), ("paid_source", "TEXT"),
                         ("paid_at", "INTEGER")):
            if col not in cols:
                conn.execute(f"ALTER TABLE collection ADD COLUMN {col} {typ}")
        # Kaufpreis-Backfill: Einträge ohne Kaufpreis bekommen den aktuellen
        # BrickLink-Ø (passend zum Zustand) – läuft idempotent bei jedem Start
        conn.execute(
            "UPDATE collection SET paid_price = ROUND(quantity * COALESCE("
            "CASE condition WHEN 'new' THEN price_new ELSE price_used END, "
            "price_used, price_new), 2), paid_source = 'auto', "
            "paid_at = strftime('%s','now') "
            "WHERE paid_price IS NULL "
            "AND COALESCE(price_new, price_used) IS NOT NULL")
        # Bereits gefüllte Kaufpreise ohne Quelle/Datum nachziehen
        conn.execute("UPDATE collection SET paid_source = 'auto' "
                     "WHERE paid_price IS NOT NULL AND paid_source IS NULL")
        conn.execute("UPDATE collection SET paid_at = strftime('%s','now') "
                     "WHERE paid_price IS NOT NULL AND paid_at IS NULL")

        # Kaufbuch: einzelne Käufe zu einem Sammlungseintrag.
        #
        # `collection.paid_price` ist die Summe über die Zeile – zwei Exemplare
        # desselben Sets liegen in *einer* Zeile, ihre Preise addieren sich.
        # Damit stimmt zwar der Gesamtbetrag, aber „einmal 39,99 bei LEGO,
        # einmal 34,99 im Markt" war danach nicht mehr zu erkennen. Hier
        # stehen die Einzelposten; `paid_price` bleibt die Summe daraus und
        # ändert sich für Statistik, Gewinn und Listen nicht.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price REAL,          -- je Stück, NULL = unbekannt
                source TEXT NOT NULL DEFAULT '',   -- „LEGO Store", „Flohmarkt"
                bought_at INTEGER,
                note TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_purchases_entry "
                     "ON purchases(entry_id)")
        # Bestand einmalig überführen: Was heute als Summe dasteht, wird ein
        # Posten. Ohne das stünde bei allem Bisherigen ein leeres Kaufbuch.
        conn.execute(
            "INSERT INTO purchases (entry_id, quantity, unit_price, source, "
            "bought_at, note, created_at) "
            "SELECT c.id, c.quantity, "
            "  ROUND(c.paid_price / MAX(c.quantity, 1), 4), "
            "  CASE c.paid_source WHEN 'auto' THEN 'geschätzt' ELSE '' END, "
            "  c.paid_at, '', strftime('%s','now') "
            "FROM collection c WHERE c.paid_price IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM purchases p WHERE p.entry_id = c.id)")
        scols = {r[1] for r in conn.execute(
            "PRAGMA table_info(shopping_items)")}
        if scols and "paid_price" not in scols:
            conn.execute("ALTER TABLE shopping_items ADD COLUMN "
                         "paid_price REAL")
        if scols and "condition" not in scols:
            conn.execute("ALTER TABLE shopping_items ADD COLUMN "
                         "condition TEXT NOT NULL DEFAULT 'used'")
        # Als inventarisiert markierte Listen bleiben aus der Einkaufs-Summe
        # der Statistik heraus (bereits erfasst).
        slcols = {r[1] for r in conn.execute(
            "PRAGMA table_info(shopping_lists)")}
        if slcols and "inventoried" not in slcols:
            conn.execute("ALTER TABLE shopping_lists ADD COLUMN "
                         "inventoried INTEGER NOT NULL DEFAULT 0")
        # Was stelle ich ins Tausch-Netzwerk? Bewusst eine eigene Markierung –
        # „abgebbar“ (Menge > 1) ist nur ein Vorschlag, entscheiden tut man.
        ccols = {r[1] for r in conn.execute("PRAGMA table_info(collection)")}
        if ccols and "shared" not in ccols:
            conn.execute("ALTER TABLE collection ADD COLUMN shared "
                         "INTEGER NOT NULL DEFAULT 0")
        # Wie viele Exemplare biete ich an? NULL = alle vorhandenen.
        if ccols and "share_qty" not in ccols:
            conn.execute("ALTER TABLE collection ADD COLUMN share_qty INTEGER")

        tcols = {r["name"] for r in
                 conn.execute("PRAGMA table_info(trades)").fetchall()}
        # Steht der Artikel beim Gegenüber überhaupt noch drin?
        if tcols and "item_gone" not in tcols:
            conn.execute("ALTER TABLE trades ADD COLUMN item_gone "
                         "INTEGER NOT NULL DEFAULT 0")
        # Was genau wird da getauscht? Beim Anfragen wissen wir es aus dem
        # Angebot – gespeichert war bisher nur Nummer und Name. Ohne Art und
        # Bild lässt sich ein angenommener Tausch nicht sauber in die Sammlung
        # übernehmen. Ältere Vorgänge bleiben leer und werden beim Übernehmen
        # nach der Nummer geraten.
        if tcols and "item_type" not in tcols:
            for spalte in ("item_type", "img_url", "bricklink_url",
                           "condition"):
                conn.execute(f"ALTER TABLE trades ADD COLUMN {spalte} "
                             "TEXT NOT NULL DEFAULT ''")
        # Wann wurde der Artikel in die Sammlung bzw. auf eine Liste gebucht?
        if tcols and "taken_at" not in tcols:
            conn.execute("ALTER TABLE trades ADD COLUMN taken_at INTEGER")
        # Thema (Star Wars, City …) für die Sortierung der Sammlung
        for tbl in ("collection", "wanted"):
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tbl})")}
            if cols and "theme" not in cols:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN theme TEXT")
        # Bestehende Einträge gleich zuordnen, soweit es ohne Abruf geht:
        # Minifiguren über das Nummern-Kürzel (sw… = Star Wars), eigene
        # Figuren als „Custom“. Sets und Teile holt man bei Bedarf über
        # „Themen nachladen“ nach.
        import themes
        for tbl in ("collection", "wanted"):
            rows = conn.execute(
                f"SELECT id, item_id, item_type FROM {tbl} "
                "WHERE theme IS NULL OR theme = ''").fetchall()
            for r in rows:
                t = themes.for_item(r["item_id"], r["item_type"])
                if t:
                    conn.execute(f"UPDATE {tbl} SET theme = ? WHERE id = ?",
                                 (t, r["id"]))
        # BrickLink liefert Kategorienamen HTML-maskiert. Bis 1.87.0 landete
        # das ungewandelt in der Sammlung und stand dann als „LEGO Ideas
        # &#40;CUUSOO&#41;“ auf dem Bildschirm – die Oberfläche maskiert beim
        # Anzeigen ja ein zweites Mal. Einmal geradeziehen.
        import html as html_mod
        for tbl in ("collection", "wanted"):
            rows = conn.execute(
                f"SELECT id, theme FROM {tbl} WHERE theme LIKE '%&%'"
            ).fetchall()
            for r in rows:
                sauber = html_mod.unescape(r["theme"])
                if sauber != r["theme"]:
                    conn.execute(f"UPDATE {tbl} SET theme = ? WHERE id = ?",
                                 (sauber, r["id"]))

        ucols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
        # Bevorzugte Sortierung der Sammlung, je Benutzer
        if "sort_pref" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN sort_pref TEXT")
        if "is_dealer" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN is_dealer "
                         "INTEGER NOT NULL DEFAULT 0")
        # Gewähltes Design pro Benutzer (NULL = folgt dem Instanz-Standard)
        if "theme" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN theme TEXT")
        # Sprache pro Benutzer (NULL = folgt der Sprache des Browsers)
        if "lang" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN lang TEXT")
        # Zwei-Faktor-Anmeldung, freiwillig je Benutzer.
        #   totp_secret   – aktiv, sobald gesetzt (NULL = aus)
        #   totp_pending  – während der Einrichtung, noch nicht bestätigt
        #   totp_last     – zuletzt genutzter Zeitschritt (gegen Wiederverwendung)
        #   totp_recovery – Rettungscodes als JSON-Liste von Hashes
        for spalte in ("totp_secret", "totp_pending", "totp_recovery"):
            if spalte not in ucols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {spalte} TEXT")
        if "totp_last" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN totp_last INTEGER")
        # Zähler für gültige Sitzungen. Ein Sitzungs-Token ist so lange gut,
        # wie sein Zählerstand zu dem des Kontos passt. Ein Passwortwechsel
        # zählt hoch – damit enden alle bisherigen Sitzungen sofort, statt bis
        # zu 90 Tage weiterzulaufen. Bestand startet bei 0, alte Token tragen
        # keinen Stand und gelten als 0: Niemand wird durch das Update
        # ausgeloggt.
        if "token_epoch" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN token_epoch "
                         "INTEGER NOT NULL DEFAULT 0")
        # Aus welchem Preisgebiet stammt der gespeicherte Preis? Damit lässt
        # sich nach einer Umstellung gezielt nachrechnen, was noch fehlt.
        # Dasselbe für die Währung: Wer von Euro auf Pfund umstellt, hat sonst
        # alte Beträge im neuen Zeichen stehen – falsch, und nicht erkennbar.
        for tbl in ("collection", "wanted", "shopping_items"):
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tbl})")}
            if cols and "price_region" not in cols:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN price_region TEXT")
            if cols and "price_currency" not in cols:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN price_currency TEXT")
        # Name/Bild der Set-Figuren mitspeichern, damit die Übersicht der
        # fehlenden Figuren ohne BrickLink-Abruf auskommt
        sccols = {r[1] for r in conn.execute(
            "PRAGMA table_info(set_contents)")}
        if sccols and "name" not in sccols:
            conn.execute("ALTER TABLE set_contents ADD COLUMN name TEXT")
        if sccols and "img_url" not in sccols:
            conn.execute("ALTER TABLE set_contents ADD COLUMN img_url TEXT")
        # Startpunkte für den Preisverlauf aus bereits gespeicherten Preisen
        conn.execute(
            "INSERT INTO price_history (item_id, item_type, ts, price_new, "
            "price_used) SELECT c.item_id, c.item_type, c.price_updated_at, "
            "c.price_new, c.price_used FROM collection c WHERE "
            "c.price_updated_at IS NOT NULL AND NOT EXISTS ("
            "SELECT 1 FROM price_history h WHERE h.item_id = c.item_id "
            "AND h.item_type = c.item_type)")
    _bootstrap_admin()


def get_setting(name: str) -> str:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE name = ?",
                           (name,)).fetchone()
    return row["value"] if row else ""


def set_setting(name: str, value: str):
    with db() as conn:
        if value:
            conn.execute(
                "INSERT INTO settings (name, value) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
                (name, value))
        else:
            conn.execute("DELETE FROM settings WHERE name = ?", (name,))


def _bootstrap_admin():
    """Optional: Admin aus ENV anlegen (für automatisierte Setups).

    Ohne ADMIN_USER/ADMIN_PASSWORD bleibt die Datenbank leer – die App
    zeigt dann beim ersten Aufruf den Ersteinrichtungs-Bildschirm.
    """
    user = os.environ.get("ADMIN_USER")
    password = os.environ.get("ADMIN_PASSWORD")
    if not user or not password:
        return
    with db() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        if count > 0:
            return
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) "
            "VALUES (?, ?, 1, ?)",
            (user, hash_password(password), int(time.time())),
        )
        print(f"[brickfolio] Admin-Benutzer '{user}' angelegt.", flush=True)
