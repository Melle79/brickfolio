"""Brickfolio – Datenbank & Authentifizierung."""
import hashlib
import hmac
import os
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

APP_VERSION = "1.4.2"


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

def create_token(user_id: int, username: str, is_admin: bool) -> str:
    payload = {
        "sub": str(user_id),
        "name": username,
        "adm": bool(is_admin),
        "exp": int(time.time()) + TOKEN_DAYS * 86400,
    }
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
                UNIQUE (item_id, item_type)
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
            CREATE TABLE IF NOT EXISTS fig_sets (
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
            """
        )
        # Migration: frühere Scans speicherten Brickognize-Typ "fig"
        conn.execute(
            "UPDATE collection SET item_type = 'minifig' WHERE item_type = 'fig'")
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
        scols = {r[1] for r in conn.execute(
            "PRAGMA table_info(shopping_items)")}
        if scols and "paid_price" not in scols:
            conn.execute("ALTER TABLE shopping_items ADD COLUMN "
                         "paid_price REAL")
        if scols and "condition" not in scols:
            conn.execute("ALTER TABLE shopping_items ADD COLUMN "
                         "condition TEXT NOT NULL DEFAULT 'used'")
        ucols = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
        if "is_dealer" not in ucols:
            conn.execute("ALTER TABLE users ADD COLUMN is_dealer "
                         "INTEGER NOT NULL DEFAULT 0")
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
