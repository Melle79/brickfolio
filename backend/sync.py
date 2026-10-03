"""Abgleich für externen Zugriff mit eigener Datenbank.

Wer von außen zugreift und seine Daten selbst mitführt, holt hier, was sich
seit seinem letzten Stand geändert hat, und schickt, was bei ihm geändert
wurde. Die Regeln stehen hier und in `tests/test_sync.py` – wer eine ändert,
zieht die Tests mit.

**Rückwärtskompatibel.** Alle bestehenden Endpunkte bleiben, wie sie sind.
Neu sind drei Spalten je Tabelle (`uuid`, `updated_at`, `rev`), zwei
Tabellen und Trigger. Die Trigger sind der Kern: Die Instanz schreibt an
rund 90 Stellen in die sechs Tabellen, und jede davon müsste sonst selbst
`rev` hochzählen. Eine vergessene fiele erst auf, wenn auf einem Gerät
Daten fehlen.

**Rechte wie in der Web-App.** Kaufpreise und Kaufbuch nur für
Sammlerprofis, Einkaufslisten anlegen und ändern auch; Standard-Benutzer
dürfen Artikel einer Liste nur verbuchen.
"""
import math
import secrets
import sqlite3
import time
import uuid as uuidlib

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import core

router = APIRouter()

PROTOKOLL = 1

# Millisekunden seit 1970 in SQL. `unixepoch('subsec')` wäre bequemer, gibt
# es aber erst ab SQLite 3.42 – welche Fassung im Container steckt, hängt
# von dessen Debian-Basis ab. `julianday` kann jede.
JETZT_MS = "CAST((julianday('now') - 2440587.5) * 86400000 AS INTEGER)"
UUID_SQL = ("lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' || "
            "substr(hex(randomblob(2)), 2) || '-' || "
            "substr('89ab', 1 + (abs(random()) % 4), 1) || "
            "substr(hex(randomblob(2)), 2) || '-' || hex(randomblob(6)))")

# Was je Tabelle zu wissen ist. Reihenfolge = Eltern vor Kindern.
TABELLEN = {
    "collection": {
        "zeit": "added_at * 1000",
        "benutzer": ["added_by"],
        "schluessel": ["item_id", "item_type", "condition"],
        "haendler_spalten": {"paid_price", "paid_source", "paid_at"},
    },
    "purchases": {
        "zeit": "created_at * 1000",
        "verweise": {"entry_id": ("entry_uuid", "collection")},
        "nur_haendler": True,
    },
    "wanted": {
        "zeit": "added_at * 1000",
        "benutzer": ["added_by"],
        "schluessel": ["item_id", "item_type"],
    },
    "shopping_lists": {
        "zeit": "created_at * 1000",
        "benutzer": ["created_by"],
    },
    "shopping_items": {
        "zeit": "added_at * 1000",
        "benutzer": ["done_by"],
        "verweise": {"list_id": ("list_uuid", "shopping_lists"),
                     "recv_entry_id": ("recv_entry_uuid", "collection"),
                     "recv_purchase_id": ("recv_purchase_uuid", "purchases")},
        "haendler_spalten": {"paid_price"},
    },
    "price_history": {"zeit": "ts * 1000"},
}

# Welcher Verweis ist Pflicht? Ohne ihn hängt ein Kind in der Luft.
PFLICHT_VERWEISE = {"purchases": "entry_id", "shopping_items": "list_id"}

# Was ein Standard-Benutzer an einem Listen-Artikel ändern darf: verbuchen,
# wie „Da! Ab in die Sammlung“ in der Web-App – sonst nichts.
VERBUCHEN_SPALTEN = {"done", "done_at", "done_by", "condition",
                     "recv_entry_uuid", "recv_mode", "recv_purchase_uuid"}

INTERN = {"id", "uuid", "updated_at", "rev"}
ZUKUNFT_MS = 5 * 60 * 1000


# ------------------------------------------------------------ Wanderung

def migrieren(conn) -> None:
    """Spalten, Tabellen, Trigger – idempotent, bei jedem Start.

    Die Trigger werden jedes Mal neu angelegt (DROP + CREATE): Ändert sich
    ihre Fassung mit einem Update, gilt sofort die neue.
    """
    conn.execute("CREATE TABLE IF NOT EXISTS sync_stand ("
                 "id INTEGER PRIMARY KEY CHECK (id = 1), rev INTEGER NOT NULL)")
    conn.execute("INSERT OR IGNORE INTO sync_stand (id, rev) VALUES (1, 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS sync_tombstones ("
                 "tabelle TEXT NOT NULL, uuid TEXT NOT NULL, rev INTEGER NOT NULL, "
                 "deleted_at INTEGER NOT NULL, PRIMARY KEY (tabelle, uuid))")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_tombstones_rev "
                 "ON sync_tombstones(rev)")
    if not conn.execute("SELECT 1 FROM settings WHERE name = 'sync_epoch' "
                        "AND value <> ''").fetchone():
        neues_zeitalter(conn)

    for t, info in TABELLEN.items():
        spalten = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
        if not spalten:
            continue
        for s, typ in (("uuid", "TEXT"), ("updated_at", "INTEGER"),
                       ("rev", "INTEGER")):
            if s not in spalten:
                conn.execute(f"ALTER TABLE {t} ADD COLUMN {s} {typ}")
        # Bestand füllen – vor den Triggern und mit gesetztem `rev`, damit
        # der Änderungs-Trigger (WHEN NEW.rev IS OLD.rev) nicht anschlägt.
        offen = conn.execute(f"SELECT id FROM {t} WHERE uuid IS NULL "
                             "ORDER BY id").fetchall()
        for r in offen:
            rev = _naechster_stand(conn)
            conn.execute(
                f"UPDATE {t} SET uuid = ?, rev = ?, "
                f"updated_at = COALESCE(updated_at, {info['zeit']}, {JETZT_MS}) "
                "WHERE id = ?", (str(uuidlib.uuid4()), rev, r[0]))
        conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{t}_uuid ON {t}(uuid)")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_rev ON {t}(rev)")
        _trigger(conn, t)

    # Archivieren (und Zurückholen) einer Liste berührt ihre Artikel. Für
    # Standard-Benutzer verschwindet eine archivierte Liste samt Artikeln
    # vom Gerät; kommt sie zurück, müssen auch die Artikel wiederkommen –
    # und das tun sie nur mit neuem Stand.
    conn.execute("DROP TRIGGER IF EXISTS sync_archiv_shopping_lists")
    conn.execute(
        "CREATE TRIGGER sync_archiv_shopping_lists AFTER UPDATE OF archived "
        "ON shopping_lists WHEN NEW.archived IS NOT OLD.archived BEGIN "
        "UPDATE shopping_items SET done = done WHERE list_id = NEW.id; END")


def _trigger(conn, t: str) -> None:
    stand = "(SELECT rev FROM sync_stand WHERE id = 1)"
    hoch = "UPDATE sync_stand SET rev = rev + 1 WHERE id = 1;"
    for name in ("ins", "upd", "del"):
        conn.execute(f"DROP TRIGGER IF EXISTS sync_{name}_{t}")
    conn.execute(
        f"CREATE TRIGGER sync_ins_{t} AFTER INSERT ON {t} BEGIN {hoch} "
        f"UPDATE {t} SET uuid = COALESCE(NEW.uuid, {UUID_SQL}), "
        f"updated_at = COALESCE(NEW.updated_at, {JETZT_MS}), rev = {stand} "
        "WHERE id = NEW.id; "
        # Wer wieder da ist, ist nicht gelöscht – etwa nach dem Zurückspielen
        # einer Sicherung, das erst alles löscht und dann neu einfügt.
        f"DELETE FROM sync_tombstones WHERE tabelle = '{t}' "
        f"AND uuid = (SELECT uuid FROM {t} WHERE id = NEW.id); END")
    conn.execute(
        f"CREATE TRIGGER sync_upd_{t} AFTER UPDATE ON {t} "
        # Nicht auf die eigene Nachbuchung reagieren.
        f"WHEN NEW.rev IS OLD.rev BEGIN {hoch} "
        # Hat der Schreiber `updated_at` selbst gesetzt (der Sync tut das mit
        # der Zeit des Geräts), bleibt es; sonst ist jetzt die Änderungszeit.
        f"UPDATE {t} SET updated_at = CASE WHEN NEW.updated_at IS OLD.updated_at "
        f"THEN {JETZT_MS} ELSE NEW.updated_at END, rev = {stand} "
        "WHERE id = NEW.id; END")
    conn.execute(
        f"CREATE TRIGGER sync_del_{t} AFTER DELETE ON {t} "
        f"WHEN OLD.uuid IS NOT NULL BEGIN {hoch} "
        "INSERT OR REPLACE INTO sync_tombstones (tabelle, uuid, rev, deleted_at) "
        f"VALUES ('{t}', OLD.uuid, {stand}, {JETZT_MS}); END")


def _naechster_stand(conn) -> int:
    conn.execute("UPDATE sync_stand SET rev = rev + 1 WHERE id = 1")
    return conn.execute("SELECT rev FROM sync_stand WHERE id = 1").fetchone()[0]


def neues_zeitalter(conn) -> str:
    """Nach dem Zurückspielen einer Sicherung stimmt nichts mehr, was ein
    Gerät über die Instanz weiß. Ein neues Zeitalter sagt ihm: von vorn."""
    wert = secrets.token_hex(8)
    conn.execute("INSERT INTO settings (name, value) VALUES ('sync_epoch', ?) "
                 "ON CONFLICT(name) DO UPDATE SET value = excluded.value", (wert,))
    return wert


# ------------------------------------------------------------ Übersetzen

class _Karten:
    """Nummern ↔ UUIDs und Benutzernummern ↔ Namen, je Anfrage einmal
    geladen – bei einer großen Sammlung sonst eine Abfrage je Zeile."""

    def __init__(self, conn):
        self.conn = conn
        self._uuid = {}
        self._id = {}
        self.namen = {r[0]: r[1] for r in conn.execute("SELECT id, username FROM users")}
        self.nummern = {n.lower(): i for i, n in self.namen.items()}

    def uuid_von(self, tabelle, nr):
        if nr is None:
            return None
        if tabelle not in self._uuid:
            self._uuid[tabelle] = {r[0]: r[1] for r in
                                   self.conn.execute(f"SELECT id, uuid FROM {tabelle}")}
        return self._uuid[tabelle].get(nr)

    def id_von(self, tabelle, u):
        if u is None:
            return None
        r = self.conn.execute(f"SELECT id FROM {tabelle} WHERE uuid = ?", (u,)).fetchone()
        return r[0] if r else None


def _satz(t: str, row, karten: _Karten, haendler: bool, geloescht=False) -> dict:
    """Eine Zeile als Sync-Satz."""
    d = dict(row)
    satz = {"table": t, "uuid": d["uuid"], "updated_at": d.get("updated_at") or 0,
            "rev": d["rev"]}
    if geloescht:
        satz["deleted"] = True
        return satz
    info = TABELLEN[t]
    felder = {k: v for k, v in d.items() if k not in INTERN}
    for spalte, (neu, ziel) in info.get("verweise", {}).items():
        felder[neu] = karten.uuid_von(ziel, felder.pop(spalte, None))
    for spalte in info.get("benutzer", []):
        felder[spalte] = karten.namen.get(felder.get(spalte))
    if not haendler:
        for s in info.get("haendler_spalten", ()):
            felder.pop(s, None)
    satz["fields"] = felder
    return satz


def _verborgen(t: str, row, conn, haendler: bool) -> bool:
    """Für Standard-Benutzer gibt es das Archiv nicht (wie in der Web-App):
    Eine archivierte Liste und ihre Artikel erscheinen als gelöscht."""
    if haendler:
        return False
    if t == "shopping_lists":
        return bool(row["archived"])
    if t == "shopping_items":
        r = conn.execute("SELECT archived FROM shopping_lists WHERE id = ?",
                         (row["list_id"],)).fetchone()
        return bool(r and r[0])
    return False


def _gesamt_stand(conn) -> int:
    return conn.execute("SELECT rev FROM sync_stand WHERE id = 1").fetchone()[0]


# ------------------------------------------------------------ Endpunkte

def _benutzer():
    # Spät gebunden: `main` bindet dieses Modul am Ende ein.
    import main
    return main.current_user


@router.get("/api/sync/info")
def info(user: dict = Depends(_benutzer())):
    with core.db() as conn:
        return {"protocol": PROTOKOLL, "rev": _gesamt_stand(conn),
                "epoch": core.get_setting("sync_epoch"),
                "dealer": bool(user["is_dealer"]),
                "tables": [t for t, i in TABELLEN.items()
                           if user["is_dealer"] or not i.get("nur_haendler")]}


@router.get("/api/sync/pull")
def pull(since: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=2000),
         user: dict = Depends(_benutzer())):
    """Alle Änderungen nach `since`, aufsteigend nach Stand.

    Sortiert wird nach Stand, nicht nach Tabelle: Ein Kaufposten kann vor
    seinem Eintrag kommen, wenn der Eintrag danach noch einmal geändert
    wurde. Die Gegenstelle kommt damit zurecht; umsortieren müsste man hier
    nichts.
    """
    haendler = bool(user["is_dealer"])
    with core.db() as conn:
        karten = _Karten(conn)
        jetzt = _gesamt_stand(conn)
        kandidaten = []
        for t, info in TABELLEN.items():
            if info.get("nur_haendler") and not haendler:
                continue
            for row in conn.execute(f"SELECT * FROM {t} WHERE rev > ? ORDER BY rev "
                                    "LIMIT ?", (since, limit + 1)):
                kandidaten.append((row["rev"], t, row, _verborgen(t, row, conn, haendler)))
            for row in conn.execute("SELECT uuid, rev, deleted_at AS updated_at "
                                    "FROM sync_tombstones WHERE tabelle = ? AND rev > ? "
                                    "ORDER BY rev LIMIT ?", (t, since, limit + 1)):
                kandidaten.append((row["rev"], t, row, True))
        kandidaten.sort(key=lambda k: k[0])
        mehr = len(kandidaten) > limit
        seite = kandidaten[:limit]
        saetze = [_satz(t, row, karten, haendler, geloescht) for _, t, row, geloescht in seite]
    return {"rev": seite[-1][0] if mehr else jetzt, "more": mehr, "dealer": haendler,
            "epoch": core.get_setting("sync_epoch"), "changes": saetze}


class Aenderung(BaseModel):
    table: str = Field(max_length=40)
    uuid: str = Field(min_length=1, max_length=64)
    updated_at: int = Field(ge=0)
    base_rev: int | None = None
    deleted: bool = False
    fields: dict = Field(default_factory=dict)


class PushBody(BaseModel):
    changes: list[Aenderung] = Field(max_length=2000)


class _Abgelehnt(Exception):
    def __init__(self, grund: str, meldung: str = "", server=None):
        super().__init__(meldung)
        self.grund, self.meldung, self.server = grund, meldung, server


@router.post("/api/sync/push")
def push(body: PushBody, user: dict = Depends(_benutzer())):
    """Änderungen eines Geräts übernehmen – jede für sich.

    Eine abgelehnte hält die übrigen nicht auf: Jede läuft in einem eigenen
    Sicherungspunkt, der bei einem Fehler zurückgerollt wird.
    """
    haendler = bool(user["is_dealer"])
    angenommen, abgelehnt = [], []
    with core.db() as conn:
        karten = _Karten(conn)
        # Was ab hier einen neuen Stand bekommt, hat dieses Gerät selbst
        # ausgelöst (etwa die Summe eines Eintrags, dessen Kaufposten es
        # eben geschickt hat) – das ist kein Konflikt mit ihm selbst.
        beginn = _gesamt_stand(conn)
        # Was gerade im Tausch-Netzwerk angeboten ist – um nach dem Push zu
        # erkennen, ob ein Angebot betroffen war (siehe unten).
        angeboten_vorher = {r[0] for r in conn.execute(
            "SELECT uuid FROM collection WHERE shared = 1")}
        for c in body.changes:
            if c.table not in TABELLEN:
                abgelehnt.append({"table": c.table, "uuid": c.uuid, "reason": "invalid",
                                  "message": "Unbekannte Tabelle"})
                continue
            conn.execute("SAVEPOINT aenderung")
            try:
                rev = _anwenden(conn, c, karten, user, haendler, beginn)
                conn.execute("RELEASE aenderung")
                angenommen.append({"table": c.table, "uuid": c.uuid, "rev": rev})
            except _Abgelehnt as e:
                conn.execute("ROLLBACK TO aenderung")
                conn.execute("RELEASE aenderung")
                eintrag = {"table": c.table, "uuid": c.uuid, "reason": e.grund}
                if e.meldung:
                    eintrag["message"] = e.meldung
                if e.server is not None:
                    eintrag["server"] = e.server
                abgelehnt.append(eintrag)
            except sqlite3.IntegrityError as e:
                conn.execute("ROLLBACK TO aenderung")
                conn.execute("RELEASE aenderung")
                abgelehnt.append({"table": c.table, "uuid": c.uuid, "reason": "invalid",
                                  "message": str(e)})
        geaendert = {a["uuid"] for a in angenommen if a["table"] == "collection"}
        angeboten_nachher = {r[0] for r in conn.execute(
            "SELECT uuid FROM collection WHERE shared = 1")} if geaendert else set()
    # **Angebote nachziehen, wenn ein Gerät eine angebotene Zeile geändert
    # hat** – verkauft, Menge gesenkt, aus dem Angebot genommen. Sonst stand
    # im Tausch-Netzwerk weiter, was es nicht mehr gibt, bis jemand von Hand
    # veröffentlichte; und das darf nur ein Admin (3.4.1). Wie nach einem
    # Tausch nur bei denen, die schon einmal veröffentlicht haben.
    if geaendert & (angeboten_vorher | angeboten_nachher):
        import community
        community.angebote_nachziehen_im_hintergrund()
    return {"accepted": angenommen, "rejected": abgelehnt}


def _anwenden(conn, c: Aenderung, karten: _Karten, user: dict, haendler: bool,
              beginn: int) -> int:
    t = c.table
    info = TABELLEN[t]
    if info.get("nur_haendler") and not haendler:
        raise _Abgelehnt("forbidden", "Nur für Sammlerprofis")
    row = conn.execute(f"SELECT * FROM {t} WHERE uuid = ?", (c.uuid,)).fetchone()
    stein = conn.execute("SELECT uuid, rev, deleted_at AS updated_at FROM sync_tombstones "
                         "WHERE tabelle = ? AND uuid = ?", (t, c.uuid)).fetchone()
    # Eine Uhr aus der Zukunft gewönne sonst jeden Konflikt, bis sie aufholt.
    jetzt_ms = int(time.time() * 1000)
    geaendert = min(c.updated_at, jetzt_ms + ZUKUNFT_MS)

    def server_fassung():
        if row is not None:
            return _satz(t, row, karten, haendler)
        if stein is not None:
            return _satz(t, stein, karten, haendler, geloescht=True)
        return None

    # Rechte bei Einkaufslisten: anlegen, ändern, löschen nur Profis;
    # Standard-Benutzer dürfen einen vorhandenen Artikel verbuchen.
    if not haendler and t == "shopping_lists":
        raise _Abgelehnt("forbidden", "Einkaufslisten ändern nur Sammlerprofis")
    if not haendler and t == "shopping_items":
        if row is None or c.deleted or not set(c.fields) <= VERBUCHEN_SPALTEN:
            raise _Abgelehnt("forbidden", "Einkaufslisten ändern nur Sammlerprofis")

    # Schon weg ist so gut wie gelöscht – vor der Konfliktprüfung: Ein
    # Kaufposten, dessen Eintrag eben mitgelöscht wurde, ist kein Konflikt.
    if c.deleted and row is None:
        return _gesamt_stand(conn)

    # Konflikt: Jemand hat seit dem Stand des Geräts geändert, und zwar
    # später (Gleichstand: Instanz gewinnt).
    vorhanden = row if row is not None else stein
    if vorhanden is not None and vorhanden["rev"] != c.base_rev \
            and vorhanden["rev"] <= beginn \
            and (vorhanden["updated_at"] or 0) >= geaendert:
        raise _Abgelehnt("conflict", server=server_fassung())

    if c.deleted:
        _loeschen(conn, t, row, geaendert)
        return _gesamt_stand(conn)

    # Neu vom Gerät, aber die UUID gibt es schon: ein zweites Gerät hat
    # denselben Artikel angelegt (Sammlung und Wunschliste leiten ihre UUID
    # aus dem Artikel ab). Nie überschreiben – die Gegenstelle führt zusammen.
    if c.base_rev is None and row is not None:
        raise _Abgelehnt("conflict", server=server_fassung())

    werte = _eingang(conn, t, c.fields, karten, user, haendler)
    # Doppelter Artikel unter anderer UUID? Die Gegenstelle führt zusammen, nicht
    # die Instanz – so bleibt die Regel an einer Stelle.
    schluessel = info.get("schluessel")
    if schluessel:
        kv = [werte.get(s, row[s] if row is not None else None) for s in schluessel]
        if None not in kv:
            andere = conn.execute(
                f"SELECT * FROM {t} WHERE " + " AND ".join(f"{s} = ?" for s in schluessel)
                + " AND uuid <> ?", (*kv, c.uuid)).fetchone()
            if andere is not None:
                raise _Abgelehnt("duplicate", server=_satz(t, andere, karten, haendler))

    if row is not None:
        if werte:
            spalten = ", ".join(f"{k} = ?" for k in werte)
            conn.execute(f"UPDATE {t} SET {spalten}, updated_at = ? WHERE uuid = ?",
                         (*werte.values(), geaendert, c.uuid))
        else:
            conn.execute(f"UPDATE {t} SET updated_at = ? WHERE uuid = ?", (geaendert, c.uuid))
    else:
        namen = ["uuid", *werte, "updated_at"]
        conn.execute(f"INSERT INTO {t} ({', '.join(namen)}) VALUES "
                     f"({', '.join('?' * len(namen))})", (c.uuid, *werte.values(), geaendert))

    neu = conn.execute(f"SELECT * FROM {t} WHERE uuid = ?", (c.uuid,)).fetchone()
    if t == "purchases":
        _summe_nachziehen(conn, neu["entry_id"], geaendert)
    return neu["rev"]


def _summe_nachziehen(conn, entry_id, geaendert: int) -> None:
    """`paid_price` ist die Summe des Kaufbuchs – wie `_kauf_buchen`.

    **Mit der Zeit des Geräts.** Ohne sie bekäme der Eintrag die Uhrzeit der
    Instanz und wäre damit „neuer“ als alles, was das Gerät im selben Zug
    schickt. So geschehen beim ersten Lauf gegen eine echte Instanz
    (27.09.2026): Das Gerät löschte einen Eintrag samt Kaufposten, der Posten
    zog die Summe nach, die Löschung des Eintrags galt danach als älter und
    wurde abgewiesen – und der Eintrag kam aufs Gerät zurück.
    """
    import main
    main._kaufsumme_nachziehen(conn, entry_id)
    conn.execute("UPDATE collection SET updated_at = MAX(COALESCE(updated_at, 0), ?) "
                 "WHERE id = ?", (geaendert, entry_id))


def _eingang(conn, t: str, felder: dict, karten: _Karten, user: dict, haendler: bool) -> dict:
    """Felder vom Gerät in Spalten der Instanz übersetzen und prüfen."""
    info = TABELLEN[t]
    spalten = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")} - INTERN
    werte = {}
    for neu_name, (spalte, ziel) in ((v[0], (k, v[1])) for k, v in info.get("verweise", {}).items()):
        if neu_name in felder:
            u = felder[neu_name]
            nr = karten.id_von(ziel, u)
            if nr is None and u is not None and PFLICHT_VERWEISE.get(t) == spalte:
                raise _Abgelehnt("orphan", "Verweis zeigt ins Leere")
            werte[spalte] = nr
    for k, v in felder.items():
        if k in spalten and k not in werte:
            werte[k] = v
    for s in info.get("benutzer", []):
        if s in werte:
            name = werte[s]
            # Unbekannter Name → der schickende Benutzer.
            werte[s] = None if name is None else karten.nummern.get(str(name).lower(), user["id"])
    if not haendler:
        for s in info.get("haendler_spalten", ()):
            werte.pop(s, None)
    _pruefen(t, werte)
    return werte


_PREISE = {"price_new", "price_used", "paid_price", "unit_price"}


def _pruefen(t: str, werte: dict) -> None:
    """Dieselben Grenzen wie die Web-App – vor allem keine unendlichen
    Preise: `1e999` legte dort Sammlung, Statistik und Sicherung lahm."""
    for k, v in werte.items():
        if isinstance(v, bool):
            continue
        if isinstance(v, float) and not math.isfinite(v):
            raise _Abgelehnt("invalid", f"{k} ist keine Zahl")
        if k in _PREISE and v is not None and (not isinstance(v, (int, float)) or v < 0):
            raise _Abgelehnt("invalid", f"{k} ist kein gültiger Preis")
        if isinstance(v, str) and len(v) > 5000:
            raise _Abgelehnt("invalid", f"{k} ist zu lang")
        if v is not None and not isinstance(v, (str, int, float)):
            raise _Abgelehnt("invalid", f"{k} hat einen unbekannten Typ")
    if "condition" in werte and werte["condition"] not in ("new", "used"):
        raise _Abgelehnt("invalid", "Zustand unbekannt")
    if "item_type" in werte and werte["item_type"] not in ("minifig", "part", "set"):
        raise _Abgelehnt("invalid", "Art unbekannt")
    for m in ("quantity", "qty"):
        if m in werte and (not isinstance(werte[m], int) or not 1 <= werte[m] <= 9999):
            raise _Abgelehnt("invalid", "Menge ungültig")


def _loeschen(conn, t: str, row, geaendert: int) -> None:
    """Löschen wie die Web-App: Kinder gehen mit."""
    if t == "collection":
        conn.execute("DELETE FROM purchases WHERE entry_id = ?", (row["id"],))
    if t == "shopping_lists":
        conn.execute("DELETE FROM shopping_items WHERE list_id = ?", (row["id"],))
    conn.execute(f"DELETE FROM {t} WHERE id = ?", (row["id"],))
    if t == "purchases":
        _summe_nachziehen(conn, row["entry_id"], geaendert)


# --------------------------------------------------------------- Katalog

KATALOG_SEITE = 5000


@router.get("/api/sync/katalog")
def katalog(seit: int = Query(0, ge=0), nach: str = "",
            limit: int = Query(KATALOG_SEITE, ge=1, le=KATALOG_SEITE),
            user: dict = Depends(_benutzer())):
    """Der Katalog dieser Instanz für externen Zugriff – damit er auch dann
    nachschlagen kann, wenn die Instanz einmal nicht erreichbar ist.

    **Mit den Namen.** Der öffentliche Abzug hat keine; jede Instanz trägt
    sie über ihren eigenen BrickLink-Zugang nach. Wer den Katalog von hier
    holt, bekommt sie mit, ohne selbst Schlüssel zu brauchen – die bleiben
    auf der Instanz.

    **Nur, was sich geändert hat.** `seit` ist der Stand vom letzten Mal
    (`stand` der Antwort), und es kommt nur, was danach geändert wurde.
    **Der Stand ist nie die laufende Sekunde:** Die Zeit zählt in Sekunden,
    und was in derselben Sekunde nach dem Abruf dazukäme, fehlte sonst für
    immer. Umgekehrt ginge „einschließlich“ nicht – ein ganzer Abzug trägt
    *eine* Zeit, und jedes Nachladen brächte ihn noch einmal (gut 1 MB, im
    Test gesehen). Innerhalb eines Stands wird mit `nach`
    weitergeblättert – `updated_at` ist nicht eindeutig, ein ganzer Abzug
    trägt dieselbe Zeit. Setinhalte, BrickLink-Nummern und Kategorien
    kommen auf der ersten Seite mit; sie sind klein.
    """
    # Ohne `nach`: alles nach `seit`. Mit `nach`: weiter hinter dem letzten
    # gelieferten Schlüssel derselben Abfrage.
    bedingung, werte = "updated_at > ?", [seit]
    if nach:
        teile = nach.split("|", 2)
        if len(teile) != 3 or not teile[0].isdigit():
            raise HTTPException(400, "nach ungültig")
        bedingung = "(updated_at, item_type, item_no) > (?, ?, ?)"
        werte = [int(teile[0]), teile[1], teile[2]]
    with core.db() as conn:
        zeilen = conn.execute(
            "SELECT item_no, item_type, name, img_url, farben, art, merkmale, "
            "category_id, jahr, updated_at FROM katalog_index "
            f"WHERE {bedingung} "
            "ORDER BY updated_at, item_type, item_no LIMIT ?",
            (*werte, limit + 1)).fetchall()
        mehr = len(zeilen) > limit
        zeilen = zeilen[:limit]
        antwort = {"eintraege": [dict(z) for z in zeilen], "mehr": mehr,
                   "aktiv": core.get_setting("katalog_aus") != "1"}
        if zeilen:
            z = zeilen[-1]
            antwort["weiter"] = f"{z['updated_at']}|{z['item_type']}|{z['item_no']}"
        # Bis wohin es beim nächsten Mal zählt: die jüngste gelieferte Zeit –
        # aber höchstens die vorige Sekunde, die laufende ist nicht zu Ende.
        juengste = max([seit] + [z["updated_at"] for z in zeilen])
        antwort["stand"] = max(seit, min(juengste, int(time.time()) - 1))
        if not nach:
            antwort["kategorien"] = [dict(r) for r in conn.execute(
                "SELECT id, name, parent_id FROM katalog_kategorien")]
            # Setinhalte ohne eigene Zeit – dafür steht in `set_meta`, wann
            # sie geholt wurden.
            antwort["setinhalte"] = [dict(r) for r in conn.execute(
                "SELECT c.set_no, c.fig_no, c.qty FROM set_contents c "
                "JOIN set_meta m ON m.set_no = c.set_no "
                "WHERE m.figs_fetched_at > ?", (seit,))]
            antwort["bl_nummern"] = [dict(r) for r in conn.execute(
                "SELECT item_id, bl_no FROM bl_nummern WHERE checked_at > ?",
                (seit,))]
    return antwort
