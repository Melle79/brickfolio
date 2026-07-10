"""Brickfolio – FastAPI-Backend (Scan, Sammlung, Benutzer)."""
import json
import os
import sqlite3
import threading
import time

import requests
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import core
import integrations

app = FastAPI(title="Brickfolio", docs_url=None, redoc_url=None)

FRONTEND_DIR = os.environ.get("FRONTEND_DIR", "/app/frontend")


@app.middleware("http")
async def cache_control(request: Request, call_next):
    """Frontend-Dateien immer beim Server revalidieren (Updates sofort sichtbar)."""
    response = await call_next(request)
    path = request.url.path
    if (path == "/" or path.startswith("/static/")
            or path in ("/sw.js", "/manifest.webmanifest")):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.on_event("startup")
def startup():
    core.init_db()
    threading.Thread(target=_price_refresher, daemon=True).start()


def _price_refresher():
    """Frischt Ø-Preise auf, die älter als 7 Tage sind (max. 40 pro Lauf)."""
    time.sleep(120)   # Start nicht ausbremsen
    while True:
        try:
            _auto_backup()
        except Exception as e:
            print(f"[brickfolio] Auto-Sicherung übersprungen: {e}",
                  flush=True)
        try:
            if integrations.bricklink_enabled():
                for table in PRICE_TABLES:
                    # Fehlende Erscheinungsjahre nachtragen (NULL = nie geprüft)
                    with core.db() as conn:
                        yrows = conn.execute(
                            f"SELECT id, item_type, item_id FROM {table} WHERE "
                            "year IS NULL AND item_id NOT LIKE 'fig-%' "
                            "AND item_id NOT LIKE 'manuell-%' LIMIT 60").fetchall()
                    filled = 0
                    for r in yrows:
                        try:
                            item = integrations.bricklink_item(r["item_type"],
                                                               r["item_id"])
                            year = item.get("year") or 0
                        except LookupError:
                            year = 0    # geprüft, BrickLink kennt kein Jahr
                        except Exception:
                            time.sleep(1.5)
                            continue
                        with core.db() as conn:
                            conn.execute(
                                f"UPDATE {table} SET year = ? WHERE id = ?",
                                (year, r["id"]))
                        filled += 1
                        time.sleep(1.5)
                    if filled:
                        print(f"[brickfolio] Jahres-Nachtrag ({table}): "
                              f"{filled} Einträge", flush=True)
                    cutoff = int(time.time()) - PRICE_STALE_SECONDS
                    with core.db() as conn:
                        rows = conn.execute(
                            f"SELECT * FROM {table} WHERE "
                            "item_id NOT LIKE 'fig-%' AND item_id NOT LIKE 'manuell-%' "
                            "AND (price_updated_at IS NULL OR price_updated_at < ?) "
                            "LIMIT 40", (cutoff,)).fetchall()
                    for row in rows:
                        try:
                            _fetch_and_store_prices(dict(row), table)
                        except Exception:
                            pass
                        time.sleep(2)   # BrickLink nicht fluten
                    if rows:
                        print(f"[brickfolio] Preis-Refresh ({table}): "
                              f"{len(rows)} Einträge", flush=True)
                with core.db() as conn:
                    srows = conn.execute(
                        "SELECT DISTINCT item_id FROM collection WHERE "
                        "item_type = 'set' AND item_id NOT LIKE 'manuell-%' "
                        "AND item_id NOT IN (SELECT set_no FROM set_meta) "
                        "LIMIT 10").fetchall()
                for r in srows:
                    try:
                        _store_set_contents(
                            r["item_id"],
                            integrations.bricklink_subsets(r["item_id"]))
                    except Exception:
                        pass
                    time.sleep(2)
                if srows:
                    print(f"[brickfolio] Set-Inhalte: {len(srows)} Sets "
                          f"geladen", flush=True)
        except Exception as e:
            print(f"[brickfolio] Preis-Refresh übersprungen: {e}", flush=True)
        time.sleep(12 * 3600)


# ---------------------------------------------------------------- Auth-Helfer

def current_user(request: Request) -> dict:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "Nicht angemeldet")
    payload = core.decode_token(header[7:])
    if not payload:
        raise HTTPException(401, "Sitzung abgelaufen – bitte neu anmelden")
    with core.db() as conn:
        row = conn.execute(
            "SELECT id, username, is_admin, is_dealer FROM users WHERE id = ?",
            (int(payload["sub"]),)).fetchone()
    if not row:
        raise HTTPException(401, "Sitzung ungültig – bitte neu anmelden")
    return {"id": row["id"], "name": row["username"],
            "is_admin": bool(row["is_admin"]),
            "is_dealer": bool(row["is_dealer"])}


def dealer_user(user: dict = Depends(current_user)) -> dict:
    if not user["is_dealer"]:
        raise HTTPException(403, "Nur für Sammlerprofis")
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(403, "Nur für Admins")
    return user


# ---------------------------------------------------------------- Modelle

class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class UserBody(BaseModel):
    username: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=4, max_length=200)
    is_admin: bool = False


class AddItemBody(BaseModel):
    item_id: str = Field(min_length=1, max_length=60)
    year: int = Field(default=0, ge=0, le=2100)
    item_type: str = Field(default="minifig", max_length=20)
    name: str = Field(min_length=1, max_length=300)
    img_url: str = Field(default="", max_length=600)
    bricklink_url: str = Field(default="", max_length=600)
    quantity: int = Field(default=1, ge=1, le=999)
    condition: str = Field(default="used", pattern="^(new|used)$")
    notes: str = Field(default="", max_length=1000)
    paid_price: float | None = Field(default=None, ge=0)


class UpdateItemBody(BaseModel):
    quantity: int | None = Field(default=None, ge=0, le=999)
    condition: str | None = Field(default=None, pattern="^(new|used)$")
    notes: str | None = Field(default=None, max_length=1000)
    item_id: str | None = Field(default=None, min_length=1, max_length=60)
    name: str | None = Field(default=None, min_length=1, max_length=300)
    img_url: str | None = Field(default=None, max_length=600)
    bricklink_url: str | None = Field(default=None, max_length=600)
    year: int | None = Field(default=None, ge=0, le=2100)
    paid_price: float | None = Field(default=None, ge=0)


# ---------------------------------------------------------------- Auth

@app.get("/api/setup")
def setup_status():
    """Öffentlich: Steht die Ersteinrichtung noch aus?"""
    with core.db() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    return {"needed": count == 0}


class SetupBody(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=4, max_length=200)


@app.post("/api/setup")
def setup_create_admin(body: SetupBody):
    """Legt das erste Admin-Konto an – nur solange keine Benutzer existieren."""
    username = body.username.strip()
    if not username:
        raise HTTPException(400, "Bitte einen Benutzernamen eingeben")
    with core.db() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        if count > 0:
            raise HTTPException(409, "Die Einrichtung ist bereits "
                                     "abgeschlossen – bitte anmelden")
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, "
            "created_at) VALUES (?, ?, 1, ?)",
            (username, core.hash_password(body.password),
             int(time.time())))
        uid = cur.lastrowid
    token = core.create_token(uid, username, True)
    return {"token": token, "username": username,
            "is_admin": True, "is_dealer": False}


@app.get("/api/me")
def whoami(user: dict = Depends(current_user)):
    return {"username": user["name"], "is_admin": user["is_admin"],
            "is_dealer": user["is_dealer"]}


@app.post("/api/login")
def login(body: LoginBody):
    with core.db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (body.username.strip(),)
        ).fetchone()
    if not row or not core.verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Benutzername oder Passwort falsch")
    token = core.create_token(row["id"], row["username"], row["is_admin"])
    is_dealer = bool(row["is_dealer"]) if "is_dealer" in row.keys() else False
    return {"token": token, "username": row["username"],
            "is_admin": bool(row["is_admin"]), "is_dealer": is_dealer}


@app.get("/api/setup")
def setup_status():
    """Öffentlich: Steht die Ersteinrichtung noch aus?"""
    with core.db() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    return {"needed": count == 0}


class SetupBody(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=4, max_length=200)


@app.post("/api/setup")
def setup_create_admin(body: SetupBody):
    """Legt das erste Admin-Konto an – nur solange keine Benutzer existieren."""
    username = body.username.strip()
    if not username:
        raise HTTPException(400, "Bitte einen Benutzernamen eingeben")
    with core.db() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        if count > 0:
            raise HTTPException(409, "Die Einrichtung ist bereits "
                                     "abgeschlossen – bitte anmelden")
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, "
            "created_at) VALUES (?, ?, 1, ?)",
            (username, core.hash_password(body.password),
             int(time.time())))
        uid = cur.lastrowid
    token = core.create_token(uid, username, True)
    return {"token": token, "username": username,
            "is_admin": True, "is_dealer": False}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


_UPDATE_CACHE = {"ts": 0.0, "data": None}
_UPDATE_URL = ("https://api.github.com/repos/Melle79/brickfolio/"
               "releases/latest")


def _ver_tuple(v: str):
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except (ValueError, AttributeError):
        return (0,)


@app.get("/api/update_check")
def update_check(force: int = 0, user: dict = Depends(admin_user)):
    """Prüft gegen das neueste GitHub-Release (gecacht, max. alle 6 h)."""
    now = time.time()
    if not force and _UPDATE_CACHE["data"] \
            and now - _UPDATE_CACHE["ts"] < 6 * 3600:
        return _UPDATE_CACHE["data"]
    data = {"current": core.APP_VERSION, "latest": None,
            "update_available": False, "url": "", "notes": ""}
    try:
        r = requests.get(_UPDATE_URL, timeout=10,
                         headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        rel = r.json()
        latest = (rel.get("tag_name") or "").lstrip("v")
        data.update({
            "latest": latest or None,
            "update_available": bool(latest) and
            _ver_tuple(latest) > _ver_tuple(core.APP_VERSION),
            "url": rel.get("html_url") or "",
            "notes": (rel.get("body") or "")[:1500],
        })
    except requests.RequestException:
        data["error"] = "GitHub gerade nicht erreichbar"
        return data          # Fehler nicht cachen – nächster Aufruf probiert neu
    _UPDATE_CACHE["ts"] = now
    _UPDATE_CACHE["data"] = data
    return data


@app.get("/favicon.ico")
def favicon():
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(FRONTEND_DIR, "icons", "favicon.ico"),
                        media_type="image/x-icon")


def _offer_percent() -> int:
    try:
        val = int(core.get_setting("offer_percent") or 60)
        return val if 1 <= val <= 100 else 60
    except (TypeError, ValueError):
        return 60


@app.get("/api/config")
def config(user: dict = Depends(current_user)):
    return {"bricklink_prices": integrations.bricklink_enabled(),
            "bricklink_lookup": integrations.bricklink_enabled(),
            "catalog_search": integrations.rebrickable_enabled(),
            "offer_percent": _offer_percent()}


class OfferPercentBody(BaseModel):
    percent: int = Field(ge=1, le=100)


@app.post("/api/settings/offer_percent")
def set_offer_percent(body: OfferPercentBody,
                      user: dict = Depends(dealer_user)):
    core.set_setting("offer_percent", str(body.percent))
    return {"ok": True, "percent": body.percent}


@app.get("/api/lookup/{item_type}/{item_no}")
def bricklink_lookup(item_type: str, item_no: str,
                     user: dict = Depends(current_user)):
    if not integrations.bricklink_enabled():
        raise HTTPException(501, "BrickLink-API nicht konfiguriert "
                                 "(BL_CONSUMER_KEY usw. in docker-compose setzen)")
    try:
        return integrations.bricklink_item(item_type, item_no.strip())
    except LookupError as e:
        raise HTTPException(404, str(e))
    except requests.Timeout:
        raise HTTPException(504, "BrickLink antwortet nicht")
    except requests.RequestException:
        raise HTTPException(502, "BrickLink nicht erreichbar")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/search")
def catalog_search(q: str = "", item_type: str = "minifig",
                   user: dict = Depends(current_user)):
    if not integrations.rebrickable_enabled():
        raise HTTPException(501, "Katalogsuche nicht konfiguriert "
                                 "(REBRICKABLE_KEY in docker-compose setzen)")
    q = q.strip()
    if len(q) < 2:
        return {"items": []}
    try:
        return {"items": integrations.search_catalog(q, item_type)}
    except requests.Timeout:
        raise HTTPException(504, "Rebrickable antwortet nicht")
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        msg = ("Rebrickable-Key ungültig oder abgelaufen"
               if code in (401, 403) else f"Rebrickable-Fehler ({code})")
        raise HTTPException(502, msg)
    except requests.RequestException:
        raise HTTPException(502, "Rebrickable nicht erreichbar")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------- Benutzer (Admin)

@app.get("/api/users")
def list_users(user: dict = Depends(admin_user)):
    with core.db() as conn:
        rows = conn.execute(
            "SELECT id, username, is_admin, is_dealer FROM users "
            "ORDER BY username"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/users")
def create_user(body: UserBody, user: dict = Depends(admin_user)):
    with core.db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (body.username.strip(),)
        ).fetchone()
        if exists:
            raise HTTPException(409, "Benutzername ist schon vergeben")
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) "
            "VALUES (?, ?, ?, ?)",
            (body.username.strip(), core.hash_password(body.password),
             int(body.is_admin), int(time.time())),
        )
    return {"ok": True}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(admin_user)):
    if user_id == user["id"]:
        raise HTTPException(400, "Du kannst dich nicht selbst löschen")
    with core.db() as conn:
        conn.execute("UPDATE collection SET added_by = NULL WHERE added_by = ?",
                     (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return {"ok": True}


class PasswordBody(BaseModel):
    password: str = Field(min_length=4, max_length=200)


class OwnPasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=4, max_length=200)


class UsernameBody(BaseModel):
    username: str = Field(min_length=2, max_length=60)


@app.post("/api/me/username")
def change_own_username(body: UsernameBody,
                        user: dict = Depends(current_user)):
    name = body.username.strip()
    if len(name) < 2:
        raise HTTPException(400, "Name ist zu kurz")
    with core.db() as conn:
        row = conn.execute("SELECT id FROM users WHERE username = ?",
                           (name,)).fetchone()
        if row and row["id"] != user["id"]:
            raise HTTPException(409, "Dieser Benutzername ist schon vergeben")
        conn.execute("UPDATE users SET username = ? WHERE id = ?",
                     (name, user["id"]))
        urow = conn.execute("SELECT * FROM users WHERE id = ?",
                            (user["id"],)).fetchone()
    token = core.create_token(urow["id"], urow["username"], urow["is_admin"])
    return {"ok": True, "token": token, "username": urow["username"],
            "is_admin": bool(urow["is_admin"])}


@app.post("/api/me/password")
def change_own_password(body: OwnPasswordBody,
                        user: dict = Depends(current_user)):
    with core.db() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?",
                           (user["id"],)).fetchone()
        if not row or not core.verify_password(body.current_password,
                                               row["password_hash"]):
            raise HTTPException(403, "Das aktuelle Passwort ist falsch")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                     (core.hash_password(body.new_password), user["id"]))
    return {"ok": True}


class DealerBody(BaseModel):
    is_dealer: bool


@app.post("/api/users/{user_id}/dealer")
def set_dealer(user_id: int, body: DealerBody,
               user: dict = Depends(admin_user)):
    with core.db() as conn:
        cur = conn.execute("UPDATE users SET is_dealer = ? WHERE id = ?",
                           (int(body.is_dealer), user_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Benutzer nicht gefunden")
    return {"ok": True, "is_dealer": body.is_dealer}


@app.post("/api/users/{user_id}/password")
def reset_user_password(user_id: int, body: PasswordBody,
                        user: dict = Depends(admin_user)):
    with core.db() as conn:
        cur = conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                           (core.hash_password(body.password), user_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Benutzer nicht gefunden")
    return {"ok": True}


@app.get("/api/stats/dashboard")
def stats_dashboard(user: dict = Depends(current_user)):
    with core.db() as conn:
        items = conn.execute(
            "SELECT item_id, item_type, name, img_url, quantity, condition, "
            "year, price_new, price_used, paid_price "
            "FROM collection").fetchall()
        hist = conn.execute(
            "SELECT item_id, item_type, ts, price_new, price_used "
            "FROM price_history ORDER BY ts").fetchall()

    total_value = 0.0
    paid_sum = 0.0
    value_of_paid_items = 0.0
    pieces = 0
    top = []
    winners = []
    by_type: dict = {}
    by_cond: dict = {}
    by_year: dict = {}
    for r in items:
        unit = _unit_price(r["condition"], r["price_new"], r["price_used"])
        value = round((unit or 0) * r["quantity"], 2)
        pieces += r["quantity"]
        total_value += value
        bt = by_type.setdefault(r["item_type"], {"pieces": 0, "value": 0.0})
        bt["pieces"] += r["quantity"]
        bt["value"] += value
        bc = by_cond.setdefault(r["condition"], {"pieces": 0, "value": 0.0})
        bc["pieces"] += r["quantity"]
        bc["value"] += value
        if r["year"]:
            by = by_year.setdefault(r["year"], {"pieces": 0, "value": 0.0})
            by["pieces"] += r["quantity"]
            by["value"] += value
        if r["paid_price"] is not None:
            paid_sum += r["paid_price"]
            value_of_paid_items += value
            winners.append({"item_id": r["item_id"], "name": r["name"],
                            "img_url": r["img_url"],
                            "item_type": r["item_type"],
                            "gain": round(value - r["paid_price"], 2)})
        if value > 0:
            top.append({"item_id": r["item_id"], "name": r["name"],
                        "img_url": r["img_url"], "item_type": r["item_type"],
                        "quantity": r["quantity"], "value": value})
    top.sort(key=lambda x: x["value"], reverse=True)
    winners.sort(key=lambda x: x["gain"], reverse=True)

    # Zeitreihe: pro Tag mit Preisdaten der Gesamtwert der heutigen Sammlung
    coll = {(r["item_id"], r["item_type"]): r for r in items}
    latest: dict = {}
    timeline = []
    day = None

    def _snapshot():
        s = 0.0
        for k, prices in latest.items():
            r = coll[k]
            u = _unit_price(r["condition"], prices[0], prices[1])
            s += (u or 0) * r["quantity"]
        return round(s, 2)

    for h in hist:
        key = (h["item_id"], h["item_type"])
        if key not in coll:
            continue
        d = h["ts"] // 86400
        if day is not None and d != day:
            timeline.append({"ts": day * 86400 + 43200, "value": _snapshot()})
        latest[key] = (h["price_new"], h["price_used"])
        day = d
    if day is not None:
        timeline.append({"ts": day * 86400 + 43200, "value": _snapshot()})

    return {"totals": {"pieces": pieces,
                       "unique": len(items),
                       "value": round(total_value, 2),
                       "avg_piece": round(total_value / pieces, 2)
                       if pieces else 0,
                       "paid": round(paid_sum, 2),
                       "profit": round(value_of_paid_items - paid_sum, 2)},
            "by_type": {k: {"pieces": v["pieces"],
                            "value": round(v["value"], 2)}
                        for k, v in by_type.items()},
            "by_condition": {k: {"pieces": v["pieces"],
                                 "value": round(v["value"], 2)}
                             for k, v in by_cond.items()},
            "by_year": [{"year": y, "pieces": v["pieces"],
                         "value": round(v["value"], 2)}
                        for y, v in sorted(by_year.items())],
            "timeline": timeline[-240:],
            "top": top[:10],
            "winners": winners[:5]}


class CsvImportBody(BaseModel):
    csv: str = Field(min_length=1, max_length=2_000_000)


CSV_TYPE_MAP = {"figur": "minifig", "minifig": "minifig", "fig": "minifig",
                "set": "set", "teil": "part", "part": "part"}
CSV_COND_MAP = {"neu": "new", "new": "new",
                "gebraucht": "used", "used": "used"}


@app.post("/api/import/csv")
def import_csv(body: CsvImportBody, user: dict = Depends(dealer_user)):
    import csv as csvmod
    import io
    text = body.csv.lstrip("\ufeff").strip()
    if not text:
        raise HTTPException(400, "Die Datei ist leer")
    first = text.splitlines()[0]
    delim = ";" if first.count(";") >= first.count(",") else ","
    rows = list(csvmod.reader(io.StringIO(text), delimiter=delim))
    if len(rows) < 2:
        raise HTTPException(400, "Keine Datenzeilen gefunden (Kopfzeile + "
                                 "mindestens eine Zeile nötig)")
    header = [h.strip().lower() for h in rows[0]]

    def col(*names):
        for i, h in enumerate(header):
            if h in names:
                return i
        return None

    idx = {"num": col("nummer", "item_id", "no", "number"),
           "type": col("typ", "type"),
           "name": col("name"),
           "qty": col("anzahl", "menge", "qty", "quantity"),
           "cond": col("zustand", "condition"),
           "paid": col("bezahlt", "kaufpreis", "einkauf", "paid"),
           "year": col("jahr", "year"),
           "notes": col("notizen", "notes", "bemerkung")}
    if idx["num"] is None:
        raise HTTPException(400, "Spalte 'Nummer' fehlt in der Kopfzeile")

    def cell(row, key):
        i = idx[key]
        return row[i].strip() if i is not None and i < len(row) else ""

    created = merged = 0
    errors = []
    now = int(time.time())
    with core.db() as conn:
        for line_no, row in enumerate(rows[1:], start=2):
            if not any(c.strip() for c in row):
                continue
            num = cell(row, "num")
            if not num:
                errors.append({"line": line_no, "error": "Nummer fehlt"})
                continue
            typ = CSV_TYPE_MAP.get(cell(row, "type").lower(), "minifig")
            name = cell(row, "name") or num
            cond = CSV_COND_MAP.get(cell(row, "cond").lower(), "used")
            try:
                qty = int(cell(row, "qty") or 1)
                if not 1 <= qty <= 999:
                    raise ValueError
            except ValueError:
                errors.append({"line": line_no,
                               "error": f"Ungültige Anzahl bei {num}"})
                continue
            paid = None
            raw_paid = cell(row, "paid").replace("€", "").strip()
            if raw_paid:
                try:
                    paid = round(float(raw_paid.replace(".", "")
                                       .replace(",", ".")
                                       if "," in raw_paid
                                       else raw_paid), 2)
                    if paid < 0:
                        raise ValueError
                except ValueError:
                    errors.append({"line": line_no,
                                   "error": f"Ungültiger Preis bei {num}"})
                    continue
            year = None
            if cell(row, "year"):
                try:
                    year = int(cell(row, "year"))
                    if not 1900 <= year <= 2100:
                        year = None
                except ValueError:
                    year = None
            notes = cell(row, "notes")[:500]

            ex = conn.execute(
                "SELECT id, paid_price FROM collection WHERE item_id = ? "
                "AND item_type = ?", (num, typ)).fetchone()
            if ex:
                conn.execute("UPDATE collection SET quantity = quantity + ? "
                             "WHERE id = ?", (qty, ex["id"]))
                if paid is not None:
                    if ex["paid_price"] is None:
                        conn.execute(
                            "UPDATE collection SET paid_price = ?, "
                            "paid_source = 'manual', paid_at = ? "
                            "WHERE id = ?", (paid, now, ex["id"]))
                    else:
                        conn.execute(
                            "UPDATE collection SET paid_price = "
                            "paid_price + ?, paid_source = 'manual', "
                            "paid_at = ? WHERE id = ?",
                            (paid, now, ex["id"]))
                merged += 1
            else:
                conn.execute(
                    "INSERT INTO collection (item_id, item_type, name, "
                    "img_url, bricklink_url, quantity, condition, notes, "
                    "year, paid_price, paid_source, paid_at, added_by, "
                    "added_at) VALUES (?, ?, ?, '', '', ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?)",
                    (num, typ, name, qty, cond, notes, year, paid,
                     "manual" if paid is not None else None,
                     now if paid is not None else None, user["id"], now))
                created += 1
    return {"ok": True, "created": created, "merged": merged,
            "errors": errors[:20], "error_count": len(errors)}


# ---------------------------------------------------------------- Sicherung (Admin)

BACKUP_TABLES = ["users", "collection", "wanted", "shopping_lists",
                 "shopping_items", "price_history",
                 "set_contents", "set_meta", "fig_sets", "settings"]


@app.get("/api/backup_info")
def backup_info(user: dict = Depends(admin_user)):
    files = _backup_list()
    return {"keep": BACKUP_KEEP, "count": len(files),
            "latest": files[-1]["name"] if files else None}


@app.get("/api/backup")
def download_backup(user: dict = Depends(admin_user)):
    dump = {"app": "brickfolio", "version": 1,
            "created_at": int(time.time()), "tables": {}}
    with core.db() as conn:
        for t in BACKUP_TABLES:
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            dump["tables"][t] = [dict(r) for r in rows]
    return dump


class RestoreBody(BaseModel):
    app: str = ""
    version: int = 0
    tables: dict


@app.post("/api/restore")
def restore_backup(body: RestoreBody, user: dict = Depends(admin_user)):
    if body.app != "brickfolio" or body.version != 1             or not isinstance(body.tables, dict)             or "collection" not in body.tables:
        raise HTTPException(400, "Das ist keine gültige Brickfolio-Sicherung")
    users = body.tables.get("users") or []
    if not any(u.get("is_admin") for u in users):
        raise HTTPException(400, "Sicherung enthält keinen Admin-Benutzer – "
                                 "Einspielen abgebrochen")
    counts = {}
    with core.db() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for t in BACKUP_TABLES:
            rows = body.tables.get(t)
            if rows is None:
                continue
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
            conn.execute(f"DELETE FROM {t}")
            n = 0
            for row in rows:
                keys = [k for k in row if k in cols]
                if not keys:
                    continue
                conn.execute(
                    f"INSERT INTO {t} ({', '.join(keys)}) "
                    f"VALUES ({', '.join(['?'] * len(keys))})",
                    [row[k] for k in keys])
                n += 1
            counts[t] = n
        conn.execute("PRAGMA foreign_keys = ON")
    return {"ok": True, "restored": counts}


# ---------------------------------------------------------------- API-Schlüssel (Admin)

class SettingsBody(BaseModel):
    rebrickable_key: str | None = Field(default=None, max_length=200)
    bl_consumer_key: str | None = Field(default=None, max_length=200)
    bl_consumer_secret: str | None = Field(default=None, max_length=200)
    bl_token: str | None = Field(default=None, max_length=200)
    bl_token_secret: str | None = Field(default=None, max_length=200)


def _mask(value: str) -> str:
    return ("…" + value[-4:]) if len(value) >= 4 else ("•" * len(value))


def _config_flags() -> dict:
    return {"bricklink_prices": integrations.bricklink_enabled(),
            "bricklink_lookup": integrations.bricklink_enabled(),
            "catalog_search": integrations.rebrickable_enabled()}


@app.get("/api/settings")
def get_settings(user: dict = Depends(admin_user)):
    out = {}
    for name in integrations.SETTING_ENV:
        value = integrations.setting(name)
        out[name] = {"set": bool(value), "masked": _mask(value),
                     "from_env": bool(value) and not core.get_setting(name)}
    out["flags"] = _config_flags()
    return out


@app.put("/api/settings")
def save_settings(body: SettingsBody, user: dict = Depends(admin_user)):
    changed = 0
    for name in integrations.SETTING_ENV:
        value = getattr(body, name)
        if value is not None:
            core.set_setting(name, value.strip())
            changed += 1
    return {"ok": True, "changed": changed, "flags": _config_flags()}


@app.post("/api/settings/test")
def test_settings(user: dict = Depends(admin_user)):
    def scrub(msg: str) -> str:
        for name in integrations.SETTING_ENV:
            value = integrations.setting(name)
            if value:
                msg = msg.replace(value, "***")
        return msg[:200]

    results = {}
    if integrations.bricklink_enabled():
        try:
            item = integrations.bricklink_item("minifig", "sw0815")
            results["bricklink"] = {"ok": True,
                                    "info": f'Verbunden – Test: {item["name"]}'}
        except Exception as e:
            results["bricklink"] = {"ok": False, "info": scrub(str(e))}
    else:
        results["bricklink"] = {"ok": False, "info": "Keine Schlüssel hinterlegt"}
    if integrations.rebrickable_enabled():
        try:
            hits = integrations.search_catalog("stormtrooper", "minifig", 1)
            results["rebrickable"] = {"ok": True,
                                      "info": f"Verbunden – {len(hits)} Treffer im Test"}
        except Exception as e:
            results["rebrickable"] = {"ok": False, "info": scrub(str(e))}
    else:
        results["rebrickable"] = {"ok": False, "info": "Kein Schlüssel hinterlegt"}
    return results


class SuggestInfoItem(BaseModel):
    item_id: str = Field(min_length=1, max_length=60)
    item_type: str = Field(default="minifig", max_length=20)


class SuggestInfoBody(BaseModel):
    items: list[SuggestInfoItem] = Field(max_length=8)


FIG_SETS_TTL = 30 * 86400


def _fig_sets_cached(fig_no: str) -> list:
    """Alle Sets einer Figur, mit 30-Tage-Cache in der DB."""
    now = int(time.time())
    with core.db() as conn:
        row = conn.execute("SELECT data, fetched_at FROM fig_sets "
                           "WHERE fig_no = ?", (fig_no,)).fetchone()
    if row and now - row["fetched_at"] < FIG_SETS_TTL:
        try:
            return json.loads(row["data"])
        except ValueError:
            pass
    sets = integrations.bricklink_supersets(fig_no)
    with core.db() as conn:
        conn.execute(
            "INSERT INTO fig_sets (fig_no, data, fetched_at) VALUES (?, ?, ?) "
            "ON CONFLICT(fig_no) DO UPDATE SET data = excluded.data, "
            "fetched_at = excluded.fetched_at",
            (fig_no, json.dumps(sets), now))
    return sets


@app.post("/api/suggest_info")
def suggest_info(body: SuggestInfoBody, detail: int = 0,
                 user: dict = Depends(current_user)):
    """Vorschläge anreichern: schon vorhanden? Jahr? Ø-Preise?"""
    out = {}
    with core.db() as conn:
        for it in body.items:
            row = conn.execute(
                "SELECT quantity, year, price_new, price_used FROM collection "
                "WHERE item_id = ? AND item_type = ?",
                (it.item_id, it.item_type)).fetchone()
            info = {"owned": row["quantity"] if row else 0}
            wrow = conn.execute(
                "SELECT 1 FROM wanted WHERE item_id = ? AND item_type = ?",
                (it.item_id, it.item_type)).fetchone()
            info["wanted"] = bool(wrow)
            lrows = conn.execute(
                "SELECT DISTINCT l.name FROM shopping_items i "
                "JOIN shopping_lists l ON l.id = i.list_id "
                "WHERE i.item_id = ? AND i.item_type = ? "
                "AND i.done = 0 AND l.archived = 0",
                (it.item_id, it.item_type)).fetchall()
            if lrows:
                info["on_lists"] = [r["name"] for r in lrows]
            srow = conn.execute(
                "SELECT GROUP_CONCAT(c2.item_id || '|' || c2.name || '|' || "
                "sc.qty, ';;') AS s FROM set_contents sc JOIN collection c2 "
                "ON c2.item_type = 'set' AND c2.item_id = sc.set_no "
                "WHERE sc.fig_no = ?", (it.item_id,)).fetchone()
            if srow and srow["s"]:
                info["in_sets"] = srow["s"]
            if row:   # gespeicherte Werte sofort wiederverwenden
                if row["year"]:
                    info["year"] = row["year"]
                if row["price_new"]:
                    info["new"] = row["price_new"]
                if row["price_used"]:
                    info["used"] = row["price_used"]
            out[it.item_id] = info

    if detail and integrations.bricklink_enabled():
        def enrich(it):
            info = out[it.item_id]
            if it.item_type == "minifig":
                try:
                    info["all_sets"] = _fig_sets_cached(it.item_id)[:12]
                except Exception:
                    pass
            if "year" not in info:
                try:
                    bl = integrations.bricklink_item(it.item_type, it.item_id)
                    if bl.get("year"):
                        info["year"] = bl["year"]
                except Exception:
                    pass
            for cond, key in (("N", "new"), ("U", "used")):
                if key in info:
                    continue
                try:
                    pg = integrations.price_guide(it.item_type, it.item_id, cond)
                    if pg.get("avg"):
                        info[key] = float(pg["avg"])
                except Exception:
                    pass

        todo = [it for it in body.items
                if not it.item_id.startswith(("fig-", "manuell-"))
                and not all(k in out[it.item_id] for k in ("year", "new", "used"))
                ][:5]
        if todo:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=5) as pool:
                list(pool.map(enrich, todo))
    return out


# ---------------------------------------------------------------- Scan

@app.post("/api/scan")
def scan(file: UploadFile = File(...), user: dict = Depends(current_user)):
    raw = file.file.read()
    if not raw:
        raise HTTPException(400, "Kein Bild empfangen")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "Bild zu groß (max. 25 MB)")
    try:
        result = integrations.recognize(raw)
    except requests.Timeout:
        raise HTTPException(504, "Brickognize antwortet nicht – später erneut versuchen")
    except requests.RequestException as e:
        raise HTTPException(502, f"Erkennung fehlgeschlagen: {e}")
    except Exception:
        raise HTTPException(400, "Bild konnte nicht verarbeitet werden")
    return result


class ResolveBody(BaseModel):
    img_url: str = Field(min_length=10, max_length=600)


@app.post("/api/resolve")
def resolve_bricklink(body: ResolveBody, user: dict = Depends(current_user)):
    """Katalogbild durch Brickognize schicken, um die BrickLink-Nummer zu finden."""
    try:
        raw = integrations.fetch_catalog_image(body.img_url)
        return integrations.recognize(raw)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except requests.Timeout:
        raise HTTPException(504, "Erkennungsdienst antwortet nicht")
    except requests.RequestException:
        raise HTTPException(502, "Nummern-Suche fehlgeschlagen – später erneut versuchen")


_BL_IMG_CODE = {"minifig": "MN", "part": "PN", "set": "SN"}


@app.get("/api/images/{item_type}/{item_no}")
def item_images(item_type: str, item_no: str,
                user: dict = Depends(current_user)):
    """Alle bekannten Katalogbilder einer Figur (BrickLink + Rebrickable)."""
    urls: list[str] = []

    def add(u):
        if u and u not in urls:
            urls.append(u)

    if item_no.startswith("fig-"):
        if integrations.rebrickable_enabled():
            try:
                add(integrations.rebrickable_minifig_image(item_no))
            except Exception:
                pass
    elif not item_no.startswith("manuell-"):
        code = _BL_IMG_CODE.get(item_type.lower())
        if code:
            safe = requests.utils.quote(item_no)
            add(f"https://img.bricklink.com/ItemImage/{code}/0/{safe}.png")
            add(f"https://img.bricklink.com/ML/{safe}.jpg")
        if integrations.bricklink_enabled():
            try:
                bl = integrations.bricklink_item(item_type, item_no)
                add(bl.get("img_url"))
            except Exception:
                pass
    return {"images": urls}


# ---------------------------------------------------------------- Sammlung

@app.get("/api/collection")
def get_collection(q: str = "", sort: str = "added", item_type: str = "",
                   user: dict = Depends(current_user)):
    sql = ("SELECT c.*, u.username AS added_by_name, "
           "(SELECT GROUP_CONCAT(c2.item_id || '|' || c2.name || '|' || sc.qty, ';;') "
           " FROM set_contents sc JOIN collection c2 "
           " ON c2.item_type = 'set' AND c2.item_id = sc.set_no "
           " WHERE sc.fig_no = c.item_id) AS in_sets, "
           "(SELECT COUNT(*) FROM set_contents sc WHERE "
           "sc.set_no = c.item_id) AS figs_total, "
           "(SELECT COUNT(*) FROM set_contents sc WHERE "
           "sc.set_no = c.item_id AND EXISTS (SELECT 1 FROM collection c3 "
           "WHERE c3.item_type = 'minifig' AND c3.item_id = sc.fig_no)) "
           "AS figs_owned "
           "FROM collection c "
           "LEFT JOIN users u ON u.id = c.added_by")
    where, params_list = [], []
    if q.strip():
        like = f"%{q.strip()}%"
        where.append("(c.name LIKE ? OR c.item_id LIKE ?)")
        params_list += [like, like]
    if item_type in ("minifig", "part", "set"):
        where.append("c.item_type = ?")
        params_list.append(item_type)
    if where:
        sql += " WHERE " + " AND ".join(where)
    params: tuple = tuple(params_list)
    _year_known = "CASE WHEN c.year IS NULL OR c.year = 0 THEN 1 ELSE 0 END"
    _unit_value = ("CASE WHEN c.condition = 'new' "
                   "THEN COALESCE(c.price_new, c.price_used) "
                   "ELSE COALESCE(c.price_used, c.price_new) END")
    _value_known = f"CASE WHEN {_unit_value} IS NULL THEN 1 ELSE 0 END"
    orders = {
        "added": "c.added_at DESC",
        "year_desc": f"{_year_known}, c.year DESC, c.name COLLATE NOCASE",
        "year_asc": f"{_year_known}, c.year ASC, c.name COLLATE NOCASE",
        "name": "c.name COLLATE NOCASE ASC",
        "value_desc": f"{_value_known}, {_unit_value} DESC, c.name COLLATE NOCASE",
        "value_asc": f"{_value_known}, {_unit_value} ASC, c.name COLLATE NOCASE",
    }
    sql += " ORDER BY " + orders.get(sort, orders["added"])
    value_expr = ("CASE WHEN condition = 'new' "
                  "THEN COALESCE(price_new, price_used) "
                  "ELSE COALESCE(price_used, price_new) END")
    stats_where = ""
    stats_params: tuple = ()
    if item_type in ("minifig", "part", "set"):
        stats_where = " WHERE item_type = ?"
        stats_params = (item_type,)
    with core.db() as conn:
        rows = conn.execute(sql, params).fetchall()
        stats = conn.execute(
            "SELECT COUNT(*) AS unique_items, "
            "COALESCE(SUM(quantity),0) AS total, "
            f"COALESCE(SUM(quantity * {value_expr}), 0) AS total_value, "
            f"COALESCE(SUM(CASE WHEN {value_expr} IS NULL THEN 1 ELSE 0 END), 0) "
            f"AS unpriced FROM collection{stats_where}", stats_params
        ).fetchone()
    return {"items": [dict(r) for r in rows], "stats": dict(stats)}


@app.post("/api/collection")
def add_item(body: AddItemBody, user: dict = Depends(current_user)):
    with core.db() as conn:
        row = conn.execute(
            "SELECT id, quantity, paid_price, condition, price_new, "
            "price_used FROM collection WHERE item_id = ? AND item_type = ?",
            (body.item_id, body.item_type),
        ).fetchone()
        if row:
            conn.execute("UPDATE collection SET quantity = quantity + ? WHERE id = ?",
                         (body.quantity, row["id"]))
            if row["paid_price"] is not None:
                unit = _unit_price(row["condition"], row["price_new"],
                                   row["price_used"])
                if unit:
                    conn.execute(
                        "UPDATE collection SET paid_price = paid_price + ? "
                        "WHERE id = ?",
                        (round(unit * body.quantity, 2), row["id"]))
            return {"ok": True, "merged": True,
                    "quantity": row["quantity"] + body.quantity}
        cur = conn.execute(
            "INSERT INTO collection (item_id, item_type, name, img_url, "
            "bricklink_url, quantity, condition, notes, year, paid_price, "
            "paid_source, paid_at, added_by, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (body.item_id, body.item_type, body.name, body.img_url,
             body.bricklink_url, body.quantity, body.condition, body.notes,
             body.year or None, body.paid_price,
             "manual" if body.paid_price is not None else None,
             int(time.time()) if body.paid_price is not None else None,
             user["id"], int(time.time())),
        )
        new_id = cur.lastrowid
    _maybe_fetch_prices_async(new_id, body.item_id)
    if body.item_type == "set":
        _maybe_fetch_set_contents_async(body.item_id)
    return {"ok": True, "merged": False, "quantity": body.quantity}


@app.patch("/api/collection/{entry_id}")
def update_item(entry_id: int, body: UpdateItemBody,
                user: dict = Depends(current_user)):
    with core.db() as conn:
        row = conn.execute("SELECT * FROM collection WHERE id = ?",
                           (entry_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Eintrag nicht gefunden")
        if body.item_id and body.item_id != row["item_id"]:
            dup = conn.execute(
                "SELECT 1 FROM collection WHERE item_id = ? AND item_type = ? "
                "AND id != ?", (body.item_id, row["item_type"], entry_id),
            ).fetchone()
            if dup:
                raise HTTPException(409, "Diese Nummer ist schon in der Sammlung "
                                         "– lösche stattdessen diesen Eintrag und "
                                         "erhöhe dort die Anzahl")
        fields, params = [], []
        for key in ("quantity", "condition", "notes", "item_id", "name",
                    "img_url", "bricklink_url", "year", "paid_price"):
            value = getattr(body, key)
            if value is not None:
                fields.append(f"{key} = ?")
                params.append(value)
        if body.paid_price is not None:
            fields.append("paid_source = ?")
            params.append("manual")
            fields.append("paid_at = ?")
            params.append(int(time.time()))
        if not fields:
            return {"ok": True}
        params.append(entry_id)
        conn.execute(
            f"UPDATE collection SET {', '.join(fields)} WHERE id = ?", params)
        if body.quantity == 0:
            conn.execute("DELETE FROM collection WHERE id = ?", (entry_id,))
            return {"ok": True, "deleted": True}
    if body.item_id:
        _maybe_fetch_prices_async(entry_id, body.item_id)
    return {"ok": True}


@app.delete("/api/collection/{entry_id}")
def delete_item(entry_id: int, user: dict = Depends(current_user)):
    with core.db() as conn:
        cur = conn.execute("DELETE FROM collection WHERE id = ?", (entry_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Eintrag nicht gefunden")
    return {"ok": True}


# ---------------------------------------------------------------- Wunschliste

class WantedBody(BaseModel):
    item_id: str = Field(min_length=1, max_length=60)
    item_type: str = Field(default="minifig", max_length=20)
    name: str = Field(min_length=1, max_length=300)
    img_url: str = Field(default="", max_length=600)
    bricklink_url: str = Field(default="", max_length=600)
    year: int = Field(default=0, ge=0, le=2100)
    notes: str = Field(default="", max_length=1000)


class AcquireBody(BaseModel):
    condition: str = Field(default="used", pattern="^(new|used)$")
    paid_price: float | None = Field(default=None, ge=0)


@app.get("/api/wanted")
def get_wanted(user: dict = Depends(current_user)):
    with core.db() as conn:
        rows = conn.execute(
            "SELECT w.*, u.username AS added_by_name, "
            "(SELECT c.quantity FROM collection c WHERE c.item_id = w.item_id "
            "AND c.item_type = w.item_type) AS owned "
            "FROM wanted w "
            "LEFT JOIN users u ON u.id = w.added_by "
            "ORDER BY w.added_at DESC").fetchall()
        stats = conn.execute(
            "SELECT COUNT(*) AS count, "
            "COALESCE(SUM(COALESCE(price_used, price_new)), 0) AS est_cost, "
            "COALESCE(SUM(COALESCE(price_new, price_used)), 0) AS est_cost_new "
            "FROM wanted").fetchone()
    return {"items": [dict(r) for r in rows], "stats": dict(stats)}


@app.post("/api/wanted")
def add_wanted(body: WantedBody, user: dict = Depends(current_user)):
    with core.db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM wanted WHERE item_id = ? AND item_type = ?",
            (body.item_id, body.item_type)).fetchone()
        if exists:
            return {"ok": True, "exists": True}
        owned = conn.execute(
            "SELECT quantity FROM collection WHERE item_id = ? AND item_type = ?",
            (body.item_id, body.item_type)).fetchone()
        cur = conn.execute(
            "INSERT INTO wanted (item_id, item_type, name, img_url, "
            "bricklink_url, year, notes, added_by, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (body.item_id, body.item_type, body.name, body.img_url,
             body.bricklink_url, body.year or None, body.notes,
             user["id"], int(time.time())))
        new_id = cur.lastrowid
    _maybe_fetch_prices_async(new_id, body.item_id, table="wanted")
    return {"ok": True, "exists": False,
            "owned": owned["quantity"] if owned else 0}


class WantedUpdateBody(BaseModel):
    item_id: str | None = Field(default=None, min_length=1, max_length=60)
    name: str | None = Field(default=None, min_length=1, max_length=300)
    img_url: str | None = Field(default=None, max_length=600)
    bricklink_url: str | None = Field(default=None, max_length=600)
    year: int | None = Field(default=None, ge=0, le=2100)
    notes: str | None = Field(default=None, max_length=1000)


@app.patch("/api/wanted/{wanted_id}")
def update_wanted(wanted_id: int, body: WantedUpdateBody,
                  user: dict = Depends(current_user)):
    with core.db() as conn:
        row = conn.execute("SELECT * FROM wanted WHERE id = ?",
                           (wanted_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Eintrag nicht gefunden")
        if body.item_id and body.item_id != row["item_id"]:
            dup = conn.execute(
                "SELECT 1 FROM wanted WHERE item_id = ? AND item_type = ? "
                "AND id != ?",
                (body.item_id, row["item_type"], wanted_id)).fetchone()
            if dup:
                raise HTTPException(409, "Diese Nummer steht schon auf der "
                                         "Wunschliste")
        fields, params = [], []
        for key in ("item_id", "name", "img_url", "bricklink_url", "year",
                    "notes"):
            value = getattr(body, key)
            if value is not None:
                fields.append(f"{key} = ?")
                params.append(value)
        if fields:
            params.append(wanted_id)
            conn.execute(f"UPDATE wanted SET {', '.join(fields)} WHERE id = ?",
                         params)
    if body.item_id:
        _maybe_fetch_prices_async(wanted_id, body.item_id, table="wanted")
    return {"ok": True}


@app.post("/api/wanted/{wanted_id}/refresh_prices")
def refresh_wanted_prices(wanted_id: int, user: dict = Depends(current_user)):
    if not integrations.bricklink_enabled():
        raise HTTPException(501, "BrickLink-API nicht konfiguriert")
    with core.db() as conn:
        row = conn.execute("SELECT * FROM wanted WHERE id = ?",
                           (wanted_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Eintrag nicht gefunden")
    entry = dict(row)
    if entry["item_id"].startswith(("fig-", "manuell-")):
        raise HTTPException(400, "Ohne BrickLink-Nummer kein Preis")
    try:
        _fetch_and_store_prices(entry, "wanted")
        return {"ok": True}
    except LookupError as e:
        raise HTTPException(404, str(e))
    except requests.Timeout:
        raise HTTPException(504, "BrickLink antwortet nicht")
    except requests.RequestException:
        raise HTTPException(502, "BrickLink nicht erreichbar")


@app.delete("/api/wanted/{wanted_id}")
def delete_wanted(wanted_id: int, user: dict = Depends(current_user)):
    with core.db() as conn:
        cur = conn.execute("DELETE FROM wanted WHERE id = ?", (wanted_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Eintrag nicht gefunden")
    return {"ok": True}


@app.post("/api/wanted/{wanted_id}/acquire")
def acquire_wanted(wanted_id: int, body: AcquireBody,
                   user: dict = Depends(current_user)):
    """Gekauft! Wunsch in die Sammlung verschieben."""
    with core.db() as conn:
        w = conn.execute("SELECT * FROM wanted WHERE id = ?",
                         (wanted_id,)).fetchone()
        if not w:
            raise HTTPException(404, "Eintrag nicht gefunden")
        unit = _unit_price(body.condition, w["price_new"], w["price_used"])
        manual = body.paid_price is not None
        paid_val = round(body.paid_price, 2) if manual \
            else (round(unit, 2) if unit else None)
        now = int(time.time())
        row = conn.execute(
            "SELECT id, paid_price FROM collection WHERE item_id = ? "
            "AND item_type = ?",
            (w["item_id"], w["item_type"])).fetchone()
        if row:
            conn.execute("UPDATE collection SET quantity = quantity + 1 "
                         "WHERE id = ?", (row["id"],))
            if manual:
                if row["paid_price"] is None:
                    conn.execute(
                        "UPDATE collection SET paid_price = ?, "
                        "paid_source = 'manual', paid_at = ? WHERE id = ?",
                        (paid_val, now, row["id"]))
                else:
                    conn.execute(
                        "UPDATE collection SET paid_price = paid_price + ?, "
                        "paid_source = 'manual', paid_at = ? WHERE id = ?",
                        (paid_val, now, row["id"]))
            elif row["paid_price"] is not None and unit:
                conn.execute(
                    "UPDATE collection SET paid_price = paid_price + ? "
                    "WHERE id = ?", (round(unit, 2), row["id"]))
        else:
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, img_url, "
                "bricklink_url, quantity, condition, notes, year, price_new, "
                "price_used, price_updated_at, price_data, paid_price, "
                "paid_source, paid_at, added_by, added_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (w["item_id"], w["item_type"], w["name"], w["img_url"],
                 w["bricklink_url"], body.condition, w["notes"], w["year"],
                 w["price_new"], w["price_used"], w["price_updated_at"],
                 w["price_data"], paid_val,
                 ("manual" if manual else "auto") if paid_val is not None else None,
                 now if paid_val is not None else None,
                 user["id"], now))
        conn.execute("DELETE FROM wanted WHERE id = ?", (wanted_id,))
    return {"ok": True, "merged": bool(row)}


def _store_set_contents(set_no: str, figs: list):
    with core.db() as conn:
        conn.execute("DELETE FROM set_contents WHERE set_no = ?", (set_no,))
        for f in figs:
            conn.execute(
                "INSERT OR REPLACE INTO set_contents (set_no, fig_no, qty) "
                "VALUES (?, ?, ?)", (set_no, f["item_id"], f.get("qty", 1)))
        conn.execute(
            "INSERT INTO set_meta (set_no, figs_fetched_at) VALUES (?, ?) "
            "ON CONFLICT(set_no) DO UPDATE SET figs_fetched_at = excluded.figs_fetched_at",
            (set_no, int(time.time())))


def _maybe_fetch_set_contents_async(set_no: str):
    if not integrations.bricklink_enabled() or set_no.startswith("manuell-"):
        return

    def run():
        try:
            _store_set_contents(set_no, integrations.bricklink_subsets(set_no))
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()


@app.get("/api/set_figs/{set_no}")
def get_set_figs(set_no: str, user: dict = Depends(current_user)):
    """Welche Minifiguren stecken in diesem Set?"""
    if not integrations.bricklink_enabled():
        raise HTTPException(501, "BrickLink-API nicht konfiguriert "
                                 "(Schlüssel unter Mehr → API-Schlüssel eintragen)")
    try:
        figs = integrations.bricklink_subsets(set_no)
        _store_set_contents(set_no, figs)
        return {"items": figs}
    except LookupError as e:
        raise HTTPException(404, str(e))
    except requests.Timeout:
        raise HTTPException(504, "BrickLink antwortet nicht")
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        raise HTTPException(502, f"BrickLink-Fehler ({code})")
    except requests.RequestException:
        raise HTTPException(502, "BrickLink nicht erreichbar")


@app.get("/api/duplicates")
def get_duplicates(user: dict = Depends(dealer_user)):
    """Alles mit Menge > 1: pro Eintrag bleibt eins, der Rest ist abgebbar."""
    with core.db() as conn:
        rows = conn.execute(
            "SELECT c.*, "
            "(SELECT COALESCE(SUM(sc.qty * c2.quantity), 0) "
            " FROM set_contents sc JOIN collection c2 "
            " ON c2.item_type = 'set' AND c2.item_id = sc.set_no "
            " WHERE sc.fig_no = c.item_id) AS reserved "
            "FROM collection c WHERE c.quantity > 1 "
            "ORDER BY c.name COLLATE NOCASE").fetchall()
    items = []
    total_value = 0.0
    total_pieces = 0
    for r in rows:
        reserved = r["reserved"] or 0
        keep = max(reserved, 1)          # Sets bleiben vollständig, 1 bleibt immer
        surplus = r["quantity"] - keep
        if surplus <= 0:
            continue
        unit = _unit_price(r["condition"], r["price_new"], r["price_used"])
        value = round(unit * surplus, 2) if unit else None
        items.append({
            "id": r["id"], "item_id": r["item_id"],
            "item_type": r["item_type"], "name": r["name"],
            "img_url": r["img_url"], "bricklink_url": r["bricklink_url"],
            "condition": r["condition"], "quantity": r["quantity"],
            "reserved": reserved, "surplus": surplus,
            "unit_price": unit, "value": value,
        })
        total_pieces += surplus
        if value:
            total_value += value
    return {"items": items,
            "stats": {"pieces": total_pieces,
                      "value": round(total_value, 2)}}

# ---------------------------------------------------------------- Einkaufslisten

class ListBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ListArchiveBody(BaseModel):
    archived: bool = True


class ListItemBody(BaseModel):
    item_id: str = Field(min_length=1, max_length=60)
    item_type: str = Field(default="minifig", max_length=20)
    name: str = Field(min_length=1, max_length=300)
    img_url: str = Field(default="", max_length=600)
    bricklink_url: str = Field(default="", max_length=600)
    year: int = Field(default=0, ge=0, le=2100)
    qty: int = Field(default=1, ge=1, le=99)
    condition: str = Field(default="used", pattern="^(new|used)$")


class ReceiveBody(BaseModel):
    condition: str = Field(default="used", pattern="^(new|used)$")
    paid_price: float | None = Field(default=None, ge=0)
    mode: str | None = Field(default=None, pattern="^(add|replace)$")


def _maybe_autoarchive(list_id: int) -> bool:
    """Liste automatisch archivieren, wenn alle Artikel abgearbeitet sind."""
    with core.db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c, "
            "SUM(CASE WHEN done = 0 THEN 1 ELSE 0 END) AS o "
            "FROM shopping_items WHERE list_id = ?", (list_id,)).fetchone()
        if row["c"] and (row["o"] or 0) == 0:
            cur = conn.execute(
                "UPDATE shopping_lists SET archived = 1, archived_at = ? "
                "WHERE id = ? AND archived = 0",
                (int(time.time()), list_id))
            return cur.rowcount > 0
    return False


@app.get("/api/lists")
def get_lists(archived: int = 0, user: dict = Depends(current_user)):
    if archived and not user["is_dealer"]:
        raise HTTPException(403, "Das Archiv ist nur für Sammlerprofis")
    with core.db() as conn:
        lists = conn.execute(
            "SELECT l.*, u.username AS created_by_name FROM shopping_lists l "
            "LEFT JOIN users u ON u.id = l.created_by "
            "WHERE l.archived = ? ORDER BY l.created_at DESC",
            (1 if archived else 0,)).fetchall()
        out = []
        for entry in lists:
            items = conn.execute(
                "SELECT i.*, u.username AS done_by_name FROM shopping_items i "
                "LEFT JOIN users u ON u.id = i.done_by "
                "WHERE i.list_id = ? ORDER BY i.done, i.added_at",
                (entry["id"],)).fetchall()
            est_used = sum((r["price_used"] or r["price_new"] or 0) * r["qty"]
                           for r in items)
            est_new = sum((r["price_new"] or r["price_used"] or 0) * r["qty"]
                          for r in items)
            est = sum((_unit_price(r["condition"], r["price_new"],
                                   r["price_used"]) or 0) * r["qty"]
                      for r in items)
            open_n = sum(1 for r in items if not r["done"])
            paid_sum = sum(r["paid_price"] or 0 for r in items)
            out.append({**dict(entry),
                        "items": [dict(r) for r in items],
                        "stats": {"count": len(items), "open": open_n,
                                  "est": round(est, 2),
                                  "est_used": round(est_used, 2),
                                  "est_new": round(est_new, 2),
                                  "paid_sum": round(paid_sum, 2)}})
    return {"lists": out}


@app.post("/api/lists")
def create_list(body: ListBody, user: dict = Depends(dealer_user)):
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO shopping_lists (name, created_by, created_at) "
            "VALUES (?, ?, ?)",
            (body.name.strip(), user["id"], int(time.time())))
    return {"ok": True, "id": cur.lastrowid}


class RenameListBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@app.post("/api/lists/{list_id}/rename")
def rename_list(list_id: int, body: RenameListBody,
                user: dict = Depends(dealer_user)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Bitte einen Namen eingeben")
    with core.db() as conn:
        row = conn.execute("SELECT id FROM shopping_lists WHERE id = ?",
                           (list_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Liste nicht gefunden")
        conn.execute("UPDATE shopping_lists SET name = ? WHERE id = ?",
                     (name, list_id))
    return {"ok": True, "name": name}


@app.post("/api/lists/{list_id}/archive")
def archive_list(list_id: int, body: ListArchiveBody,
                 user: dict = Depends(dealer_user)):
    with core.db() as conn:
        cur = conn.execute(
            "UPDATE shopping_lists SET archived = ?, archived_at = ? "
            "WHERE id = ?",
            (int(body.archived),
             int(time.time()) if body.archived else None, list_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Liste nicht gefunden")
    return {"ok": True}


@app.delete("/api/lists/{list_id}")
def delete_list(list_id: int, user: dict = Depends(dealer_user)):
    with core.db() as conn:
        conn.execute("DELETE FROM shopping_items WHERE list_id = ?",
                     (list_id,))
        cur = conn.execute("DELETE FROM shopping_lists WHERE id = ?",
                           (list_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Liste nicht gefunden")
    return {"ok": True}


@app.post("/api/lists/{list_id}/items")
def add_list_item(list_id: int, body: ListItemBody,
                  user: dict = Depends(dealer_user)):
    with core.db() as conn:
        lst = conn.execute("SELECT archived FROM shopping_lists WHERE id = ?",
                           (list_id,)).fetchone()
        if not lst:
            raise HTTPException(404, "Liste nicht gefunden")
        if lst["archived"]:
            raise HTTPException(400, "Liste ist archiviert")
        ex = conn.execute(
            "SELECT id, qty FROM shopping_items WHERE list_id = ? AND "
            "item_id = ? AND item_type = ? AND condition = ? AND done = 0",
            (list_id, body.item_id, body.item_type,
             body.condition)).fetchone()
        if ex:
            conn.execute("UPDATE shopping_items SET qty = qty + ? "
                         "WHERE id = ?", (body.qty, ex["id"]))
            return {"ok": True, "merged": True, "qty": ex["qty"] + body.qty}
        cur = conn.execute(
            "INSERT INTO shopping_items (list_id, item_id, item_type, name, "
            "img_url, bricklink_url, year, qty, condition, added_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (list_id, body.item_id, body.item_type, body.name, body.img_url,
             body.bricklink_url, body.year or None, body.qty, body.condition,
             int(time.time())))
        new_id = cur.lastrowid
    _maybe_fetch_prices_async(new_id, body.item_id, table="shopping_items")
    return {"ok": True, "merged": False}


class ItemPriceBody(BaseModel):
    paid_price: float | None = Field(default=None, ge=0)
    condition: str | None = Field(default=None, pattern="^(new|used)$")


@app.patch("/api/lists/items/{item_id}")
def update_list_item(item_id: int, body: ItemPriceBody,
                     user: dict = Depends(dealer_user)):
    fields, params = [], []
    if body.paid_price is not None:
        fields.append("paid_price = ?")
        params.append(round(body.paid_price, 2))
    if body.condition is not None:
        fields.append("condition = ?")
        params.append(body.condition)
    if not fields:
        return {"ok": True}
    params.append(item_id)
    with core.db() as conn:
        cur = conn.execute(
            f"UPDATE shopping_items SET {', '.join(fields)} WHERE id = ?",
            params)
        if cur.rowcount == 0:
            raise HTTPException(404, "Artikel nicht gefunden")
    return {"ok": True}


@app.delete("/api/lists/items/{item_id}")
def delete_list_item(item_id: int, user: dict = Depends(dealer_user)):
    with core.db() as conn:
        row = conn.execute("SELECT list_id FROM shopping_items WHERE id = ?",
                           (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Artikel nicht gefunden")
        conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
    _maybe_autoarchive(row["list_id"])
    return {"ok": True}


class OfferBody(BaseModel):
    total: float = Field(ge=0)


@app.post("/api/lists/{list_id}/offer")
def distribute_offer(list_id: int, body: OfferBody,
                     user: dict = Depends(dealer_user)):
    """Gesamtpreis anteilig nach BrickLink-Wert auf offene Artikel verteilen."""
    with core.db() as conn:
        lst = conn.execute("SELECT archived FROM shopping_lists WHERE id = ?",
                           (list_id,)).fetchone()
        if not lst:
            raise HTTPException(404, "Liste nicht gefunden")
        if lst["archived"]:
            raise HTTPException(400, "Liste ist archiviert")
        items = conn.execute(
            "SELECT id, qty, condition, price_new, price_used "
            "FROM shopping_items WHERE list_id = ? AND done = 0 ORDER BY id",
            (list_id,)).fetchall()
        if not items:
            raise HTTPException(400, "Keine offenen Artikel in der Liste")

        # Gewicht = Marktwert passend zum Zustand; ohne Preis: Ø der übrigen
        raw = [((_unit_price(r["condition"], r["price_new"],
                             r["price_used"]) or 0) * r["qty"], r)
               for r in items]
        priced = [v for v, _ in raw if v > 0]
        fallback = (sum(priced) / len(priced)) if priced else 1.0
        weights = [(v if v > 0 else fallback) for v, _ in raw]
        total_w = sum(weights) or 1.0

        shares = []
        assigned = 0.0
        for i, (w, (_, r)) in enumerate(zip(weights, raw)):
            if i == len(items) - 1:      # Rundungsrest am letzten Artikel
                share = round(body.total - assigned, 2)
            else:
                share = round(body.total * w / total_w, 2)
                assigned = round(assigned + share, 2)
            shares.append((share, r["id"]))
        for share, iid in shares:
            conn.execute("UPDATE shopping_items SET paid_price = ? "
                         "WHERE id = ?", (share, iid))
    return {"ok": True, "count": len(shares),
            "shares": [{"id": iid, "paid_price": s} for s, iid in shares]}


@app.post("/api/lists/items/{item_id}/receive")
def receive_list_item(item_id: int, body: ReceiveBody,
                      user: dict = Depends(current_user)):
    """Artikel ist da: in die Sammlung verschieben (darf jeder)."""
    now = int(time.time())
    with core.db() as conn:
        it = conn.execute("SELECT * FROM shopping_items WHERE id = ?",
                          (item_id,)).fetchone()
        if not it:
            raise HTTPException(404, "Artikel nicht gefunden")
        if it["done"]:
            raise HTTPException(409, "Artikel ist schon in der Sammlung")
        unit = _unit_price(body.condition, it["price_new"], it["price_used"])
        if body.paid_price is not None and user["is_dealer"]:
            paid_val, manual = round(body.paid_price, 2), True
        elif it["paid_price"] is not None:
            paid_val, manual = round(it["paid_price"], 2), True
        else:
            paid_val = round(unit * it["qty"], 2) if unit else None
            manual = False
        row = conn.execute(
            "SELECT id, quantity, paid_price FROM collection WHERE "
            "item_id = ? AND item_type = ?",
            (it["item_id"], it["item_type"])).fetchone()
        if row and body.mode is None:
            # Schon vorhanden: Frontend soll nachfragen
            return {"ok": False, "need_mode": True,
                    "owned": row["quantity"]}
        if row and body.mode == "replace":
            conn.execute(
                "UPDATE collection SET quantity = ?, condition = ?, "
                "name = ?, img_url = ?, bricklink_url = ?, "
                "year = COALESCE(?, year), "
                "price_new = COALESCE(?, price_new), "
                "price_used = COALESCE(?, price_used), "
                "paid_price = ?, paid_source = ?, paid_at = ? WHERE id = ?",
                (it["qty"], body.condition, it["name"], it["img_url"],
                 it["bricklink_url"], it["year"], it["price_new"],
                 it["price_used"], paid_val,
                 ("manual" if manual else "auto") if paid_val is not None
                 else None,
                 now if paid_val is not None else None, row["id"]))
        elif row:   # mode == "add": Menge erhöhen, Einkaufspreis mitteln
            conn.execute("UPDATE collection SET quantity = quantity + ? "
                         "WHERE id = ?", (it["qty"], row["id"]))
            if paid_val is not None:
                if row["paid_price"] is None:
                    new_paid = paid_val
                else:
                    new_paid = round((row["paid_price"] + paid_val) / 2, 2)
                conn.execute(
                    "UPDATE collection SET paid_price = ?, "
                    "paid_source = CASE WHEN ? THEN 'manual' "
                    "ELSE COALESCE(paid_source, 'auto') END, "
                    "paid_at = ? WHERE id = ?",
                    (new_paid, int(manual), now, row["id"]))
        else:
            conn.execute(
                "INSERT INTO collection (item_id, item_type, name, img_url, "
                "bricklink_url, quantity, condition, notes, year, price_new, "
                "price_used, price_updated_at, price_data, paid_price, "
                "paid_source, paid_at, added_by, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?)",
                (it["item_id"], it["item_type"], it["name"], it["img_url"],
                 it["bricklink_url"], it["qty"], body.condition, it["year"],
                 it["price_new"], it["price_used"], it["price_updated_at"],
                 it["price_data"], paid_val,
                 ("manual" if manual else "auto") if paid_val is not None
                 else None,
                 now if paid_val is not None else None, user["id"], now))
        conn.execute("UPDATE shopping_items SET done = 1, done_at = ?, "
                     "done_by = ? WHERE id = ?", (now, user["id"], item_id))
        list_id = it["list_id"]
    archived = _maybe_autoarchive(list_id)
    if it["item_type"] == "set":
        _maybe_fetch_set_contents_async(it["item_id"])
    return {"ok": True, "merged": bool(row), "list_archived": archived}


@app.post("/api/lists/items/{item_id}/undo")
def undo_list_item(item_id: int, user: dict = Depends(dealer_user)):
    with core.db() as conn:
        row = conn.execute("SELECT list_id, done FROM shopping_items "
                           "WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Artikel nicht gefunden")
        if not row["done"]:
            return {"ok": True}
        conn.execute("UPDATE shopping_items SET done = 0, done_at = NULL, "
                     "done_by = NULL WHERE id = ?", (item_id,))
        conn.execute("UPDATE shopping_lists SET archived = 0, "
                     "archived_at = NULL WHERE id = ?", (row["list_id"],))
    return {"ok": True}


# ---------------------------------------------------------------- Preise

PRICE_STALE_SECONDS = 7 * 86400      # Hintergrund-Refresh: älter als 7 Tage


PRICE_TABLES = ("collection", "wanted", "shopping_items")

BACKUP_KEEP = int(os.environ.get("BACKUP_KEEP", "14"))


def _auto_backup():
    """Tägliche Sicherung der Datenbank (konsistent via SQLite-Backup-API).

    Läuft im Hintergrundjob; legt höchstens eine Sicherung pro Tag an und
    behält die letzten BACKUP_KEEP Tagesstände. BACKUP_KEEP=0 schaltet ab.
    """
    if BACKUP_KEEP <= 0:
        return
    import glob
    import datetime
    bdir = os.path.join(os.path.dirname(core.DB_PATH), "backups")
    os.makedirs(bdir, exist_ok=True)
    target = os.path.join(
        bdir, f"brickfolio-{datetime.date.today().isoformat()}.db")
    if os.path.exists(target):
        return
    src_conn = sqlite3.connect(core.DB_PATH)
    dst_conn = sqlite3.connect(target)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    old_files = sorted(glob.glob(os.path.join(bdir, "brickfolio-*.db")))
    for f in old_files[:-BACKUP_KEEP]:
        os.remove(f)
    print(f"[brickfolio] Auto-Sicherung angelegt: {target}", flush=True)


def _backup_list():
    import glob
    bdir = os.path.join(os.path.dirname(core.DB_PATH), "backups")
    files = sorted(glob.glob(os.path.join(bdir, "brickfolio-*.db")))
    return [{"name": os.path.basename(f),
             "size": os.path.getsize(f)} for f in files]


def _unit_price(condition, price_new, price_used):
    """Ø-Stückpreis passend zum Zustand, mit Fallback auf den anderen."""
    prefer = price_new if condition == "new" else price_used
    return prefer or price_used or price_new


def _maybe_fetch_prices_async(entry_id: int, item_id: str,
                              table: str = "collection"):
    """Preise für einen neuen/korrigierten Eintrag im Hintergrund holen."""
    if table not in PRICE_TABLES or not integrations.bricklink_enabled():
        return
    if item_id.startswith(("fig-", "manuell-")):
        return

    def run():
        try:
            with core.db() as conn:
                row = conn.execute(f"SELECT * FROM {table} WHERE id = ?",
                                   (entry_id,)).fetchone()
            if row:
                _fetch_and_store_prices(dict(row), table)
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()


def _fetch_and_store_prices(entry: dict, table: str = "collection") -> dict:
    """Beide Zustände von BrickLink holen und Ø-Preise am Eintrag speichern."""
    assert table in PRICE_TABLES
    result = {}
    not_found = 0
    for cond, key in (("N", "new"), ("U", "used")):
        try:
            result[key] = integrations.price_guide(
                entry["item_type"], entry["item_id"], cond)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code == 404:
                not_found += 1
                result[key] = None
                continue
            raise
    if not_found == 2:
        raise LookupError("BrickLink kennt diese Nummer nicht – vermutlich eine "
                          "Rebrickable-Nummer (fig-…). „BrickLink-Nr. setzen“ nutzen.")

    def avg(d):
        try:
            value = float(d["avg"]) if d and d.get("avg") else None
            return value if value else None
        except (TypeError, ValueError):
            return None

    now = int(time.time())
    payload = json.dumps({"new": result.get("new"), "used": result.get("used")})
    with core.db() as conn:
        conn.execute(
            f"UPDATE {table} SET price_new = ?, price_used = ?, "
            "price_updated_at = ?, price_data = ? WHERE id = ?",
            (avg(result.get("new")), avg(result.get("used")), now, payload,
             entry["id"]))
    if not entry.get("year"):
        try:
            item = integrations.bricklink_item(entry["item_type"], entry["item_id"])
            with core.db() as conn:
                conn.execute(f"UPDATE {table} SET year = ? WHERE id = ?",
                             (item.get("year") or 0, entry["id"]))
        except Exception:
            pass   # Jahr ist nice-to-have, Preise sind wichtiger
    if table == "collection":
        with core.db() as conn:
            r = conn.execute(
                "SELECT id, paid_price, quantity, condition FROM collection "
                "WHERE id = ?", (entry["id"],)).fetchone()
            if r and r["paid_price"] is None:
                unit = _unit_price(r["condition"], avg(result.get("new")),
                                   avg(result.get("used")))
                if unit:
                    conn.execute(
                        "UPDATE collection SET paid_price = ?, "
                        "paid_source = 'auto', paid_at = ? WHERE id = ?",
                        (round(unit * r["quantity"], 2), now, r["id"]))
    with core.db() as conn:
        last = conn.execute(
            "SELECT ts FROM price_history WHERE item_id = ? AND item_type = ? "
            "ORDER BY ts DESC LIMIT 1",
            (entry["item_id"], entry["item_type"])).fetchone()
        if not last or now - last["ts"] > 20 * 3600:
            conn.execute(
                "INSERT INTO price_history (item_id, item_type, ts, "
                "price_new, price_used) VALUES (?, ?, ?, ?, ?)",
                (entry["item_id"], entry["item_type"], now,
                 avg(result.get("new")), avg(result.get("used"))))
    result["updated_at"] = now
    return result


@app.get("/api/collection/{entry_id}/price")
def entry_price(entry_id: int, refresh: int = 0,
                user: dict = Depends(current_user)):
    if not integrations.bricklink_enabled():
        raise HTTPException(501, "BrickLink-API nicht konfiguriert "
                                 "(Schlüssel unter Mehr → API-Schlüssel eintragen)")
    with core.db() as conn:
        row = conn.execute("SELECT * FROM collection WHERE id = ?",
                           (entry_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Eintrag nicht gefunden")
    entry = dict(row)
    if entry["item_id"].startswith(("fig-", "manuell-")):
        raise HTTPException(400, "Ohne BrickLink-Nummer kein Preis – "
                                 "„BrickLink-Nr. setzen“ in den Details nutzen.")

    if not refresh:
        if entry.get("price_data"):
            try:
                data = json.loads(entry["price_data"])
            except ValueError:
                data = {}
            return {"new": data.get("new"), "used": data.get("used"),
                    "updated_at": entry.get("price_updated_at"), "cached": True}
        return {"new": {"avg": entry["price_new"]} if entry.get("price_new") else None,
                "used": {"avg": entry["price_used"]} if entry.get("price_used") else None,
                "updated_at": entry.get("price_updated_at"), "cached": True}
    try:
        return _fetch_and_store_prices(entry)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except requests.Timeout:
        raise HTTPException(504, "BrickLink antwortet nicht")
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        raise HTTPException(502, f"BrickLink-Fehler ({code})")
    except requests.RequestException:
        raise HTTPException(502, "BrickLink nicht erreichbar")


@app.get("/api/price/{item_type}/{item_no}")
def get_price(item_type: str, item_no: str,
              user: dict = Depends(current_user)):
    if not integrations.bricklink_enabled():
        raise HTTPException(501, "BrickLink-API nicht konfiguriert "
                                 "(Schlüssel unter Mehr → API-Schlüssel eintragen)")
    result = {}
    not_found = 0
    for cond, key in (("N", "new"), ("U", "used")):
        try:
            result[key] = integrations.price_guide(item_type, item_no, cond)
        except requests.Timeout:
            raise HTTPException(504, "BrickLink antwortet nicht")
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code == 404:
                not_found += 1
                result[key] = None
                continue
            raise HTTPException(502, f"BrickLink-Fehler ({code})")
        except requests.RequestException:
            raise HTTPException(502, "BrickLink nicht erreichbar")
        except (ValueError, RuntimeError) as e:
            raise HTTPException(400, str(e))
    if not_found == 2:
        raise HTTPException(404, "BrickLink kennt diese Nummer nicht – "
                                 "vermutlich eine Rebrickable-Nummer (fig-…). "
                                 "In den Details „BrickLink-Nr. setzen“ nutzen.")
    return result


@app.get("/api/history/{item_type}/{item_no}")
def get_price_history(item_type: str, item_no: str,
                      user: dict = Depends(current_user)):
    with core.db() as conn:
        rows = conn.execute(
            "SELECT ts, price_new, price_used FROM price_history "
            "WHERE item_id = ? AND item_type = ? ORDER BY ts ASC LIMIT 400",
            (item_no, item_type)).fetchall()
    return {"points": [dict(r) for r in rows]}


# ---------------------------------------------------------------- Frontend

@app.exception_handler(HTTPException)
def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(os.path.join(FRONTEND_DIR, "manifest.webmanifest"),
                        media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"),
                        media_type="application/javascript")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
