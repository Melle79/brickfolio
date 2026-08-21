"""Brickfolio – FastAPI-Backend (Scan, Sammlung, Benutzer)."""
import base64
import hashlib
import html
import io
import json
import os
import re
import sqlite3
import threading
import time
import uuid

import requests
from fastapi import (Depends, FastAPI, File, HTTPException, Request,
                     Response, UploadFile)
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import core
import crypto_box
import hub
import integrations
import push
import totp
import themes

app = FastAPI(title="Brickfolio", docs_url=None, redoc_url=None)

FRONTEND_DIR = os.environ.get("FRONTEND_DIR", "/app/frontend")


# Antworten komprimieren. Die Sammlung ist eine lange Liste sehr ähnlicher
# Datensätze – so etwas schrumpft dramatisch (gemessen: 1,82 MB auf 0,03 MB).
# Betrifft auch app.js, style.css und index.html. Hinter dem Cloudflare-Tunnel
# würde Cloudflare komprimieren; im Heimnetz, wo die meisten die App
# benutzen, tat es bisher niemand.
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Grundschutz im Browser.

    Kostet nichts und nimmt drei Angriffswege aus dem Spiel: fremde Seiten
    dürfen die App nicht in einen Rahmen stecken (Klickfallen), der Browser
    darf Dateitypen nicht raten, und Adressen fließen nicht an fremde Seiten
    ab. Die Regeln für Inhalte lassen Bilder von BrickLink und Rebrickable
    ausdrücklich zu – ohne sie bliebe der halbe Katalog leer.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if not request.url.path.startswith("/api/"):
        response.headers.setdefault("Content-Security-Policy", "; ".join([
            "default-src 'self'",
            # Katalogbilder liegen bei BrickLink, Rebrickable – und, für
            # alles Gescannte, bei Brickognize. Dessen Vorschaubilder
            # liegen in einem Google-Storage-Bucket; CSP kennt keine
            # Pfade, deshalb steht hier der ganze Host. Fehlte er, blieben
            # genau die Artikel ohne Bild, die per Foto erfasst wurden.
            # `blob:` ist das gerade aufgenommene bzw. hereingezogene Foto:
            # Die Vorschau zeigt es aus dem Arbeitsspeicher, bevor es
            # überhaupt hochgeladen wird. Ohne diese Erlaubnis blockierte der
            # Browser genau das Bild, das man selbst ausgewählt hat – die
            # Vorschau blieb ein Platzhalter. Es verweist immer auf Daten
            # dieser Seite, kann also nichts von außen nachladen.
            "img-src 'self' data: blob: https://img.bricklink.com "
            "https://cdn.rebrickable.com https://*.bricklink.com "
            "https://*.rebrickable.com https://storage.googleapis.com",
            "style-src 'self' 'unsafe-inline'",
            "script-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'self'",
            "base-uri 'self'",
            "form-action 'self'",
        ]))
    return response


@app.middleware("http")
async def cache_control(request: Request, call_next):
    """Wie lange dürfen Browser Frontend-Dateien behalten?

    Adressen mit Versionsmarke (`/static/app.js?v=1.50.2`) dürfen sie
    dauerhaft behalten: Die Marke setzt die Startseite aus APP_VERSION ein,
    eine neue Version ergibt also eine neue Adresse. Das spart bei jedem
    Start mehrere Rückfragen – am Handy der spürbare Teil.

    Alles ohne Marke – die Startseite selbst, sw.js, das Manifest, Symbole –
    muss beim Server nachfragen, sonst käme ein Update nie an.
    """
    response = await call_next(request)
    path = request.url.path
    # Schriftdateien tragen ihren Schnitt im Namen und ändern sich nie – ein
    # anderer Schnitt hieße eine andere Datei. Sie dürfen deshalb ohne Marke
    # dauerhaft bleiben; das spart bei jedem Start sechs Rückfragen.
    versioniert = (request.query_params.get("v")
                   or path.startswith("/static/fonts/"))
    if path.startswith("/static/") and versioniert:
        response.headers["Cache-Control"] = \
            "public, max-age=31536000, immutable"
    elif (path == "/" or path.startswith("/static/")
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
                            "item_id NOT LIKE 'fig-%' AND item_id NOT LIKE 'manuell-%' AND item_id NOT LIKE 'custom-%' "
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
        try:
            _resolve_gone_items()
        except Exception as e:
            print(f"[brickfolio] Change-Log-Abgleich übersprungen: {e}",
                  flush=True)
        time.sleep(12 * 3600)


# ---------------------------------------------------------------- Auth-Helfer

def current_user(request: Request) -> dict:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "Nicht angemeldet")
    payload = core.decode_token(header[7:])
    if not payload:
        raise HTTPException(401, "Sitzung abgelaufen – bitte neu anmelden")
    # Die Zwischenmarke aus dem ersten Anmeldeschritt ist keine Sitzung.
    # Ohne diese Zeile käme man mit halb erledigter Anmeldung an alle Daten –
    # die Zwei-Faktor-Prüfung wäre damit wirkungslos.
    if payload.get("zweck"):
        raise HTTPException(401, "Anmeldung ist noch nicht abgeschlossen")
    with core.db() as conn:
        row = conn.execute(
            "SELECT id, username, is_admin, is_dealer, theme, sort_pref, lang, "
            "token_epoch FROM users "
            "WHERE id = ?", (int(payload["sub"]),)).fetchone()
    if not row:
        raise HTTPException(401, "Sitzung ungültig – bitte neu anmelden")
    # Rechte und Gültigkeit kommen aus der Datenbank, nicht aus dem Token:
    # Ein Passwortwechsel zählt den Stand hoch und beendet damit alle
    # bisherigen Sitzungen – sonst liefe ein abhandengekommenes Token bis zu
    # 90 Tage weiter, obwohl das Passwort längst ein anderes ist.
    if int(payload.get("tv") or 0) != int(row["token_epoch"] or 0):
        raise HTTPException(401, "Sitzung beendet – bitte neu anmelden")
    return {"id": row["id"], "name": row["username"],
            "is_admin": bool(row["is_admin"]),
            "is_dealer": bool(row["is_dealer"]),
            "theme": row["theme"], "sort_pref": row["sort_pref"],
            "lang": row["lang"]}


def dealer_user(user: dict = Depends(current_user)) -> dict:
    if not user["is_dealer"]:
        raise HTTPException(403, "Nur für Sammlerprofis")
    return user


def admin_user(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(403, "Nur für Admins")
    return user


# ---------------------------------------------------------------- Modelle

def _benutzername(roh: str) -> str:
    """Prüft einen Benutzernamen und gibt ihn aufgeräumt zurück.

    Bisher stand an drei Stellen je eine eigene, halbe Fassung: Die
    Längenprüfung von Pydantic zählt die **rohe** Eingabe, danach wurde
    gestrippt. „  " kam damit als zwei Zeichen durch und landete als leerer
    Name in der Datenbank – anmelden konnte sich damit niemand mehr, und in
    der Benutzerverwaltung stand eine namenlose Zeile.

    Steuerzeichen sind ebenfalls draußen: Ein Name mit Zeilenumbruch zerlegt
    jede Liste, in der er auftaucht.

    Doppelte Namen fängt die Datenbank ab (`UNIQUE … COLLATE NOCASE`), die
    Aufrufer prüfen zusätzlich vorher, um eine verständliche Meldung zu geben.
    """
    name = (roh or "").strip()
    if len(name) < 2:
        raise HTTPException(400, "Der Benutzername braucht mindestens "
                                 "zwei Zeichen")
    if len(name) > 60:
        raise HTTPException(400, "Der Benutzername ist zu lang "
                                 "(höchstens 60 Zeichen)")
    if any(ord(z) < 32 or ord(z) == 127 for z in name):
        raise HTTPException(400, "Der Benutzername enthält Zeichen, die "
                                 "nicht erlaubt sind")
    return name


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class UserBody(BaseModel):
    username: str = Field(min_length=2, max_length=60)
    password: str = Field(min_length=8, max_length=200)
    is_admin: bool = False


# Nur die drei Sorten, die es im Katalog gibt. `condition` wurde schon immer
# geprüft, `item_type` nicht – so landete "raumschiff" klaglos in der
# Datenbank und tauchte danach in Adressen und Auswertungen wieder auf.
ITEM_TYPE_RE = "^(minifig|set|part)$"

# Bild: entweder eine Adresse auf der eigenen Instanz oder http(s). Alles
# andere (javascript:, data:, file: …) hat hier nichts verloren.
IMG_URL_RE = r"^$|^/(uploads|catalog)/|^/catalog\?|^https?://"


class AddItemBody(BaseModel):
    item_id: str = Field(min_length=1, max_length=60)
    year: int = Field(default=0, ge=0, le=2100)
    item_type: str = Field(default="minifig", pattern=ITEM_TYPE_RE)
    name: str = Field(min_length=1, max_length=300)
    img_url: str = Field(default="", max_length=600, pattern=IMG_URL_RE)
    bricklink_url: str = Field(default="", max_length=600)
    quantity: int = Field(default=1, ge=1, le=999)
    condition: str = Field(default="used", pattern="^(new|used)$")
    notes: str = Field(default="", max_length=1000)
    paid_price: float | None = Field(default=None, ge=0)
    paid_source: str | None = Field(default=None, pattern="^(manual|set)$")


class UpdateItemBody(BaseModel):
    quantity: int | None = Field(default=None, ge=0, le=999)
    condition: str | None = Field(default=None, pattern="^(new|used)$")
    notes: str | None = Field(default=None, max_length=1000)
    item_id: str | None = Field(default=None, min_length=1, max_length=60)
    name: str | None = Field(default=None, min_length=1, max_length=300)
    img_url: str | None = Field(default=None, max_length=600)
    bricklink_url: str | None = Field(default=None, max_length=600)
    year: int | None = Field(default=None, ge=0, le=2100)
    # Von Hand gesetztes Thema. Leer heißt „Ohne Thema“ – und die
    # Automatik rührt ein vorhandenes ohnehin nicht an, ein von Hand
    # gesetztes bleibt also stehen.
    theme: str | None = Field(default=None, max_length=60)
    paid_price: float | None = Field(default=None, ge=0)


# ---------------------------------------------------------------- Auth

def _owner_name() -> str:
    """Anzeigename für Logo/Titel: DB-Einstellung, sonst ENV, sonst 'Finn'."""
    import os as _os
    name = core.get_setting("owner_name") or _os.environ.get(
        "BRICKFOLIO_NAME", "").strip()
    return name or "Finn"


@app.get("/api/setup")
def setup_status():
    """Öffentlich: Steht die Ersteinrichtung noch aus?"""
    with core.db() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    return {"needed": count == 0, "owner_name": _owner_name(),
            "default_theme": core.get_setting("default_theme") or "classic"}


class SetupBody(BaseModel):
    username: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=200)


@app.post("/api/setup")
def setup_create_admin(body: SetupBody):
    """Legt das erste Admin-Konto an – nur solange keine Benutzer existieren."""
    username = _benutzername(body.username)
    with core.db() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        if count > 0:
            raise HTTPException(409, "Die Einrichtung ist bereits "
                                     "abgeschlossen – bitte anmelden")
        # Wer die Instanz einrichtet, ist ihr Eigner – und bekommt deshalb
        # auch die Profi-Rolle. Vorher blieb er Standard-Benutzer: Kaufpreise,
        # Einkaufslisten und Verkaufsliste waren ausgeblendet, und der Weg
        # dorthin führte über die Benutzerverwaltung, wo er sich selbst zum
        # Profi machen musste. Ein Einrichtungsassistent, nach dem man sich
        # erst selbst freischaltet, ist keiner.
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, "
            "is_dealer, created_at) VALUES (?, ?, 1, 1, ?)",
            (username, core.hash_password(body.password),
             int(time.time())))
        uid = cur.lastrowid
    token = core.create_token(uid, username, True)
    return {"token": token, "username": username,
            "is_admin": True, "is_dealer": True}


@app.get("/api/me")
def whoami(user: dict = Depends(current_user)):
    return {"username": user["name"], "is_admin": user["is_admin"],
            "is_dealer": user["is_dealer"],
            "theme": user.get("theme"), "lang": user.get("lang"),
            "sort_pref": user.get("sort_pref"),
            "default_theme": core.get_setting("default_theme") or "classic"}


# --------------------------------------------- Schutz vor Passwortraten
#
# Ohne Bremse kann jemand beliebig oft raten – im Heimnetz verschmerzbar, bei
# einer Portfreigabe nicht. Gezählt wird je Konto *und* je Herkunft:
#
#   je Konto   – dagegen hilft dem Angreifer kein Wechsel der Adresse
#   je Herkunft– dagegen hilft ihm keine Liste von Benutzernamen
#
# Bewusst kein hartes Sperren des Kontos: Sonst könnte ein Fremder jeden
# aussperren, indem er absichtlich falsch rät. Nach der Wartezeit geht es
# von selbst weiter.
LOGIN_MAX = 10                 # Fehlversuche
LOGIN_WINDOW = 15 * 60         # innerhalb dieser Zeit (Sekunden)
_login_fails: dict = {}


def _login_key(request: Request) -> str:
    """Herkunft der Anfrage. Hinter einem Tunnel steht die echte Adresse im
    Header – der ist fälschbar, taugt also nur als grobe Streuung; die
    eigentliche Bremse ist die Zählung je Konto."""
    fwd = request.headers.get("cf-connecting-ip") or \
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return fwd or (request.client.host if request.client else "?")


def _login_blocked(*schluessel) -> int:
    """Wie viele Sekunden muss noch gewartet werden? 0 = freie Bahn."""
    jetzt = time.time()
    wartezeit = 0
    for s in schluessel:
        versuche = [t for t in _login_fails.get(s, []) if jetzt - t < LOGIN_WINDOW]
        _login_fails[s] = versuche
        if len(versuche) >= LOGIN_MAX:
            wartezeit = max(wartezeit, int(LOGIN_WINDOW - (jetzt - versuche[0])))
    return wartezeit


def _login_failed(*schluessel):
    jetzt = time.time()
    for s in schluessel:
        _login_fails.setdefault(s, []).append(jetzt)
    # Nicht unbegrenzt wachsen lassen – abgelaufene Einträge wegräumen.
    if len(_login_fails) > 2000:
        for s in list(_login_fails):
            _login_fails[s] = [t for t in _login_fails[s]
                               if jetzt - t < LOGIN_WINDOW]
            if not _login_fails[s]:
                del _login_fails[s]


@app.post("/api/login")
def login(body: LoginBody, request: Request):
    name = body.username.strip()
    keys = (f"u:{name.lower()}", f"i:{_login_key(request)}")
    warte = _login_blocked(*keys)
    if warte:
        raise HTTPException(429, "Zu viele Fehlversuche – bitte "
                                 f"{max(1, warte // 60)} Minuten warten")
    with core.db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (name,)
        ).fetchone()
    if not row or not core.verify_password(body.password, row["password_hash"]):
        _login_failed(*keys)
        raise HTTPException(401, "Benutzername oder Passwort falsch")
    # Geglückt: beide Zähler zurücksetzen. Auch den für die Herkunft – sonst
    # sperrt eine Familie hinter einer Adresse sich gegenseitig aus, wenn
    # jemand ein paarmal danebentippt. Wer sich erfolgreich anmeldet, hat
    # gültige Zugangsdaten; wer keine hat, kommt nie an diese Stelle.
    for k in keys:
        _login_fails.pop(k, None)

    # Zweiter Faktor, falls eingeschaltet: Das Passwort allein reicht dann
    # nicht. Statt des Sitzungs-Tokens kommt eine kurzlebige Zwischenmarke
    # zurück – sie erlaubt ausschließlich den zweiten Schritt.
    if "totp_secret" in row.keys() and row["totp_secret"]:
        return {"totp_required": True,
                "challenge": core.create_token(row["id"], row["username"],
                                               False, minutes=5,
                                               zweck="2fa")}
    return _login_antwort(row)


def _login_antwort(row) -> dict:
    token = core.create_token(row["id"], row["username"], row["is_admin"])
    is_dealer = bool(row["is_dealer"]) if "is_dealer" in row.keys() else False
    theme = row["theme"] if "theme" in row.keys() else None
    sort_pref = row["sort_pref"] if "sort_pref" in row.keys() else None
    lang = row["lang"] if "lang" in row.keys() else None
    return {"token": token, "username": row["username"],
            "is_admin": bool(row["is_admin"]), "is_dealer": is_dealer,
            "theme": theme, "sort_pref": sort_pref, "lang": lang,
            "default_theme": core.get_setting("default_theme") or "classic"}


class TotpLoginBody(BaseModel):
    challenge: str
    code: str = Field(min_length=4, max_length=40)


@app.post("/api/login/2fa")
def login_2fa(body: TotpLoginBody, request: Request):
    """Zweiter Schritt: Einmalcode oder Rettungscode."""
    daten = core.decode_token(body.challenge)
    if not daten or daten.get("zweck") != "2fa":
        raise HTTPException(401, "Anmeldung abgelaufen – bitte neu beginnen")
    uid = int(daten["sub"])
    keys = (f"t:{uid}", f"i:{_login_key(request)}")
    warte = _login_blocked(*keys)
    if warte:
        raise HTTPException(429, "Zu viele Fehlversuche – bitte "
                                 f"{max(1, warte // 60)} Minuten warten")
    with core.db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not row or not row["totp_secret"]:
        raise HTTPException(401, "Zwei-Faktor ist nicht aktiv")

    schritt = totp.pruefe(row["totp_secret"], body.code, row["totp_last"])
    if schritt is not None:
        with core.db() as conn:
            conn.execute("UPDATE users SET totp_last = ? WHERE id = ?",
                         (schritt, uid))
        for k in keys:
            _login_fails.pop(k, None)
        return _login_antwort(row)

    # Kein gültiger Einmalcode – dann vielleicht ein Rettungscode.
    rest = json.loads(row["totp_recovery"] or "[]")
    gehasht = totp.rettungscode_hash(body.code)
    if gehasht in rest:
        rest.remove(gehasht)                 # gilt genau einmal
        with core.db() as conn:
            conn.execute("UPDATE users SET totp_recovery = ? WHERE id = ?",
                         (json.dumps(rest), uid))
        for k in keys:
            _login_fails.pop(k, None)
        antwort = _login_antwort(row)
        antwort["recovery_used"] = True
        antwort["recovery_left"] = len(rest)
        return antwort

    _login_failed(*keys)
    raise HTTPException(401, "Code stimmt nicht")


THEMES = ("classic", "galaxy", "nova")


class ThemeBody(BaseModel):
    theme: str = Field(max_length=20)


@app.post("/api/me/theme")
def set_my_theme(body: ThemeBody, user: dict = Depends(current_user)):
    """Gewähltes Design im Profil speichern – gilt dann auf allen Geräten."""
    if body.theme not in THEMES:
        raise HTTPException(400, "Unbekanntes Design")
    with core.db() as conn:
        conn.execute("UPDATE users SET theme = ? WHERE id = ?",
                     (body.theme, user["id"]))
    return {"ok": True, "theme": body.theme}


LANGS = ("de", "en")


class LangBody(BaseModel):
    lang: str = Field(max_length=5)


# --------------------------------------------- Zwei-Faktor (freiwillig)

@app.get("/api/me/2fa")
def totp_status(user: dict = Depends(current_user)):
    with core.db() as conn:
        row = conn.execute("SELECT totp_secret, totp_recovery FROM users "
                           "WHERE id = ?", (user["id"],)).fetchone()
    aktiv = bool(row["totp_secret"])
    return {"active": aktiv,
            "recovery_left": len(json.loads(row["totp_recovery"] or "[]"))
            if aktiv else 0}


class TotpStartBody(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@app.post("/api/me/2fa/start")
def totp_start(body: TotpStartBody, user: dict = Depends(current_user)):
    """Einrichtung beginnen. Das Passwort wird nochmal verlangt – sonst
    könnte an einem offen stehenden Gerät jemand fremd einen zweiten Faktor
    einrichten und den Besitzer aussperren."""
    with core.db() as conn:
        row = conn.execute("SELECT password_hash, totp_secret FROM users "
                           "WHERE id = ?", (user["id"],)).fetchone()
    if not core.verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Das Passwort ist falsch")
    if row["totp_secret"]:
        raise HTTPException(409, "Zwei-Faktor ist bereits aktiv")
    secret = totp.neuer_schluessel()
    with core.db() as conn:
        conn.execute("UPDATE users SET totp_pending = ? WHERE id = ?",
                     (secret, user["id"]))
    return {"secret": secret,
            "otpauth": totp.otpauth_url(secret, user["name"], _owner_name()
                                        + "'s Brickfolio")}


@app.get("/api/me/2fa/qr")
def totp_qr(user: dict = Depends(current_user)):
    """QR-Code zur laufenden Einrichtung, als SVG.

    Bewusst erst nach dem Anmelden erreichbar und nur für den eigenen,
    noch unbestätigten Schlüssel – der Code enthält schließlich das
    Geheimnis im Klartext.
    """
    with core.db() as conn:
        row = conn.execute("SELECT totp_pending FROM users WHERE id = ?",
                           (user["id"],)).fetchone()
    if not row["totp_pending"]:
        raise HTTPException(404, "Keine Einrichtung begonnen")
    import io

    import segno
    url = totp.otpauth_url(row["totp_pending"], user["name"],
                           _owner_name() + "'s Brickfolio")
    puffer = io.BytesIO()
    segno.make(url, error="m").save(puffer, kind="svg", scale=5, border=2)
    return Response(puffer.getvalue(), media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"})


class TotpCodeBody(BaseModel):
    code: str = Field(min_length=4, max_length=40)


@app.post("/api/me/2fa/confirm")
def totp_confirm(body: TotpCodeBody, user: dict = Depends(current_user)):
    """Erst wenn ein Code aus der App stimmt, wird eingeschaltet – so kann
    sich niemand mit einem falsch übertragenen Schlüssel aussperren."""
    with core.db() as conn:
        row = conn.execute("SELECT totp_pending FROM users WHERE id = ?",
                           (user["id"],)).fetchone()
    if not row["totp_pending"]:
        raise HTTPException(400, "Keine Einrichtung begonnen")
    schritt = totp.pruefe(row["totp_pending"], body.code)
    if schritt is None:
        raise HTTPException(401, "Code stimmt nicht – Uhrzeit des Geräts prüfen")
    codes = totp.neue_rettungscodes()
    with core.db() as conn:
        conn.execute("UPDATE users SET totp_secret = totp_pending, "
                     "totp_pending = NULL, totp_last = ?, totp_recovery = ? "
                     "WHERE id = ?",
                     (schritt, json.dumps([totp.rettungscode_hash(c)
                                           for c in codes]), user["id"]))
    # Die Rettungscodes gehen genau hier einmal hinaus – danach liegen nur
    # noch ihre Hashes in der Datenbank.
    return {"ok": True, "recovery_codes": codes}


class TotpOffBody(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=4, max_length=40)


@app.post("/api/me/2fa/disable")
def totp_disable(body: TotpOffBody, user: dict = Depends(current_user)):
    """Ausschalten verlangt beides – Passwort und einen gültigen Code."""
    with core.db() as conn:
        row = conn.execute("SELECT password_hash, totp_secret, totp_last "
                           "FROM users WHERE id = ?", (user["id"],)).fetchone()
    if not row["totp_secret"]:
        raise HTTPException(400, "Zwei-Faktor ist nicht aktiv")
    if not core.verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Das Passwort ist falsch")
    if totp.pruefe(row["totp_secret"], body.code, row["totp_last"]) is None:
        raise HTTPException(401, "Code stimmt nicht")
    with core.db() as conn:
        conn.execute("UPDATE users SET totp_secret = NULL, totp_pending = NULL,"
                     " totp_last = NULL, totp_recovery = NULL WHERE id = ?",
                     (user["id"],))
    return {"ok": True}


@app.post("/api/users/{user_id}/2fa/reset")
def totp_reset(user_id: int, user: dict = Depends(admin_user)):
    """Notausgang: Der Admin nimmt den zweiten Faktor ab, wenn jemand sein
    Telefon verloren hat und keine Rettungscodes mehr besitzt. Ohne das wäre
    ein verlorenes Gerät ein verlorenes Konto."""
    with core.db() as conn:
        cur = conn.execute(
            "UPDATE users SET totp_secret = NULL, totp_pending = NULL, "
            "totp_last = NULL, totp_recovery = NULL WHERE id = ?", (user_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Benutzer nicht gefunden")
    # Der zweite Faktor fällt weg, weil ein Gerät abhandenkam – dann darf eine
    # Sitzung von genau diesem Gerät nicht einfach weiterlaufen. Nimmt ein
    # Admin ihn sich selbst ab, bekommt er eine frische Sitzung: Sich beim
    # eigenen Handgriff auszusperren wäre kein Sicherheitsgewinn.
    core.sitzungen_beenden(user_id)
    if user_id == user["id"]:
        return {"ok": True, "token": core.create_token(
            user["id"], user["name"], user["is_admin"])}
    return {"ok": True}


@app.post("/api/me/lang")
def set_my_lang(body: LangBody, user: dict = Depends(current_user)):
    """Gewählte Sprache im Profil speichern – gilt dann auf allen Geräten."""
    if body.lang not in LANGS:
        raise HTTPException(400, "Unbekannte Sprache")
    with core.db() as conn:
        conn.execute("UPDATE users SET lang = ? WHERE id = ?",
                     (body.lang, user["id"]))
    return {"ok": True, "lang": body.lang}


@app.post("/api/settings/default_theme")
def set_default_theme(body: ThemeBody, user: dict = Depends(admin_user)):
    """Standard-Design der Instanz: gilt für den Login-Bildschirm und für
    alle Benutzer, die noch keine eigene Wahl getroffen haben."""
    if body.theme not in THEMES:
        raise HTTPException(400, "Unbekanntes Design")
    core.set_setting("default_theme", body.theme)
    return {"ok": True, "default_theme": body.theme}


_UPDATE_CACHE = {"ts": 0.0, "data": None}
_UPDATE_URL = ("https://api.github.com/repos/Melle79/brickfolio/"
               "releases/latest")


def _ver_tuple(v: str):
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except (ValueError, AttributeError):
        return (0,)


@app.get("/api/price_log")
def price_log(limit: int = 50, user: dict = Depends(dealer_user)):
    """Die jüngsten Preisverlaufs-Punkte mit Artikelnamen (Profi)."""
    limit = max(1, min(limit, 200))
    with core.db() as conn:
        rows = conn.execute(
            "SELECT ph.item_id, ph.item_type, ph.ts, ph.price_new, "
            "ph.price_used, ph.source, "
            "COALESCE(c.name, w.name, si.name, ph.item_id) AS name "
            "FROM price_history ph "
            "LEFT JOIN collection c ON c.item_id = ph.item_id "
            "  AND c.item_type = ph.item_type "
            "LEFT JOIN wanted w ON w.item_id = ph.item_id "
            "  AND w.item_type = ph.item_type "
            "LEFT JOIN shopping_items si ON si.item_id = ph.item_id "
            "  AND si.item_type = ph.item_type "
            "GROUP BY ph.rowid "
            "ORDER BY ph.ts DESC LIMIT ?", (limit,)).fetchall()
        cutoff = int(time.time()) - PRICE_STALE_SECONDS
        stale = conn.execute(
            "SELECT COUNT(*) AS c FROM collection WHERE "
            "item_id NOT LIKE 'fig-%' AND item_id NOT LIKE 'manuell-%' AND item_id NOT LIKE 'custom-%' "
            "AND price_updated_at IS NOT NULL AND price_updated_at < ?",
            (cutoff,)).fetchone()["c"]
    return {"entries": [dict(r) for r in rows],
            "stale_count": stale, "stale_days": PRICE_STALE_SECONDS // 86400}


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


# Startzeit dieses Prozesses: ändert sich beim Neustart des Containers und
# ist damit das verlässliche Signal „Server ist wieder da" – auch dann, wenn
# die Versionsnummer gleich geblieben ist.
_STARTED_AT = int(time.time())


# ---------------------------------------------------------------- Fehlerberichte

ERROR_LOG_KEEP = 100          # ältere Einträge fallen automatisch weg
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Melle79/brickfolio")


class ErrorReportBody(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    detail: str | None = Field(default=None, max_length=4000)
    context: str | None = Field(default=None, max_length=500)
    app_version: str | None = Field(default=None, max_length=40)


@app.post("/api/errors")
def report_error(body: ErrorReportBody, user: dict = Depends(current_user),
                 request: Request = None):
    """Einen aufgetretenen Fehler melden – von jedem Gerät der Familie.

    Gleichartige Fehler werden zusammengefasst, damit ein wiederkehrendes
    Problem nicht die Liste flutet.
    """
    import hashlib
    # Bis 2.18.0 ging der **Detailtext** in die Kennung ein, der Ort aber
    # nicht. Genau verkehrt herum: Die Stelle im Code ist stabil, das Detail
    # ist der wechselnde Teil – bei „Script error." steht dort die Spur der
    # letzten Schritte, die jedes Mal anders aussieht. Derselbe Fehler
    # erzeugte so bei jedem Auftreten einen neuen Eintrag, und das
    # Zusammenfassen, das die Liste sauber halten soll, lief ins Leere.
    fp = hashlib.sha256(
        (body.message + "|" + (body.context or "")).encode()).hexdigest()[:32]
    now = int(time.time())
    neu = False
    agent = (request.headers.get("User-Agent", "")[:200] if request else "")
    with core.db() as conn:
        row = conn.execute("SELECT id FROM error_log WHERE fingerprint = ?",
                           (fp,)).fetchone()
        if row:
            conn.execute("UPDATE error_log SET count = count + 1, last_at = ? "
                         "WHERE id = ?", (now, row["id"]))
        else:
            conn.execute(
                "INSERT INTO error_log (fingerprint, message, detail, context, "
                "app_version, user_agent, username, first_at, last_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (fp, body.message[:500], (body.detail or "")[:4000],
                 body.context, body.app_version or core.APP_VERSION,
                 agent, user["name"], now, now))
            conn.execute(
                "DELETE FROM error_log WHERE issue_url IS NULL AND id NOT IN "
                "(SELECT id FROM error_log ORDER BY last_at DESC LIMIT ?)",
                (ERROR_LOG_KEEP,))
            neu = True
    if neu:
        _note_error(body.message, fp)
    return {"ok": True}


class CrashReportBody(BaseModel):
    # Der Verlauf, genau wie er vor dem Senden gezeigt wurde. Kein Objekt,
    # sondern Text: Was der Absender liest, ist dann auch das, was ankommt.
    payload: str = Field(min_length=1, max_length=200_000)
    crashes: int = Field(default=0, ge=0, le=10_000)
    views: str = Field(default="", max_length=200)


@app.get("/api/diag/report")
def crash_report_status(user: dict = Depends(current_user)):
    """Kann diese Instanz Fehlerberichte abliefern?

    Die Antwort entscheidet, was der Knopf im Verlauf tut: senden oder zum
    Kopieren anbieten. Von vier Instanzen im Haushalt hatten zwei keinen
    Hub-Zugang – ohne diese Auskunft wäre der Knopf dort tot gewesen, ohne
    dass es jemandem auffällt.
    """
    return {"can_send": hub.report_enabled()}


@app.post("/api/diag/report")
def send_crash_report(body: CrashReportBody,
                      user: dict = Depends(current_user)):
    """Fehlerbericht an den Hub geben. Darf jeder, der die App benutzt –
    es sind seine eigenen Messwerte, und er hat sie vorher gesehen."""
    if not hub.report_enabled():
        raise HTTPException(409, "Für diese Instanz ist kein Berichts-Token "
                                 "hinterlegt")
    try:
        hub.send_crash_report(body.payload, app_version=core.APP_VERSION,
                              crashes=body.crashes, views=body.views)
    except hub.HubError as e:
        raise HTTPException(502, f"Der Hub nahm den Bericht nicht an: "
                                 f"{scrub(e.message)}")
    except requests.RequestException:
        raise HTTPException(502, "Der Hub ist nicht erreichbar")
    return {"ok": True}


class CrashTokenBody(BaseModel):
    token: str = Field(default="", max_length=200)


@app.post("/api/settings/crash_token")
def set_crash_token(body: CrashTokenBody, user: dict = Depends(admin_user)):
    """Berichts-Token hinterlegen. Leer bedeutet: Kanal wieder abschalten."""
    core.set_setting("crash_token", body.token.strip())
    return {"ok": True, "can_send": hub.report_enabled()}


@app.get("/api/errors")
def list_errors(user: dict = Depends(admin_user)):
    with core.db() as conn:
        rows = conn.execute(
            "SELECT * FROM error_log ORDER BY last_at DESC LIMIT 50").fetchall()
    token = core.get_setting("github_token")
    return {"items": [dict(r) for r in rows],
            "can_report": bool(token),
            # Wie bei den API-Schlüsseln: maskiert zeigen, dass etwas da ist.
            # „Gespeichert?" war bisher nur daran zu erkennen, ob der
            # Melden-Knopf erschien – und das sieht man erst mit einem Fehler.
            "token_masked": _mask(token) if token else "",
            "repo": GITHUB_REPO}


@app.delete("/api/errors")
def clear_errors(user: dict = Depends(admin_user)):
    """Bericht leeren – und die Zettel dazu gleich mit.

    Sie blieben bisher stehen und zeigten danach auf Fehler, die es nicht
    mehr gab: „Ein Fehler wurde aufgezeichnet", und der Bericht dahinter
    leer. Wer den Bericht wegräumt, will auch den Hinweis darauf los sein.
    """
    with core.db() as conn:
        conn.execute("DELETE FROM error_log")
        conn.execute("UPDATE notifications SET dismissed_at = ? "
                     "WHERE kind = 'error' AND dismissed_at IS NULL",
                     (int(time.time()),))
    return {"ok": True}


def _issue_body(e: dict) -> str:
    """Meldung für GitHub – bewusst ohne Benutzernamen und ohne Schlüssel."""
    when = time.strftime("%d.%m.%Y %H:%M", time.localtime(e["last_at"]))
    parts = [
        f"**Fehler:** {e['message']}",
        "",
        f"- Version: `{e.get('app_version') or '?'}`",
        f"- Aufgetreten: {e['count']}×, zuletzt {when}",
    ]
    if e.get("context"):
        parts.append(f"- Stelle: `{e['context']}`")
    if e.get("user_agent"):
        parts.append(f"- Browser: `{e['user_agent']}`")
    if e.get("detail"):
        parts += ["", "<details><summary>Details</summary>", "",
                  "```", scrub(e["detail"], 3000), "```", "", "</details>"]
    parts += ["", "*Automatisch aus Brickfolio gemeldet.*"]
    return "\n".join(parts)


@app.post("/api/errors/{error_id}/issue")
def create_issue(error_id: int, user: dict = Depends(admin_user)):
    """Aus einem Fehler ein GitHub-Issue anlegen."""
    token = core.get_setting("github_token")
    if not token:
        raise HTTPException(501, "Kein GitHub-Token hinterlegt "
                                 "(Mehr → Fehlerbericht).")
    with core.db() as conn:
        row = conn.execute("SELECT * FROM error_log WHERE id = ?",
                           (error_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Fehler nicht gefunden")
    e = dict(row)
    if e.get("issue_url"):
        return {"ok": True, "url": e["issue_url"], "existed": True}
    try:
        resp = requests.post(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json"},
            json={"title": f"Fehler: {e['message'][:80]}",
                  "body": _issue_body(e)},
            timeout=20)
    except requests.RequestException:
        raise HTTPException(502, "GitHub nicht erreichbar")
    if resp.status_code == 401:
        raise HTTPException(401, "GitHub-Token ungültig oder abgelaufen")
    if resp.status_code == 403:
        raise HTTPException(403, "Token darf keine Issues anlegen – "
                                 "Berechtigung „Issues: Read and write“ nötig")
    if resp.status_code >= 400:
        raise HTTPException(502, f"GitHub-Fehler ({resp.status_code})")
    url = resp.json().get("html_url", "")
    with core.db() as conn:
        conn.execute("UPDATE error_log SET issue_url = ? WHERE id = ?",
                     (url, error_id))
    return {"ok": True, "url": url, "existed": False}


# ------------------------------------------------- Benachrichtigung aufs Gerät

class PushSubBody(BaseModel):
    subscription: dict


class PushOffBody(BaseModel):
    endpoint: str = Field(min_length=10, max_length=600)


@app.get("/api/push")
def push_status(request: Request, user: dict = Depends(admin_user)):
    """Öffentlicher Schlüssel und die Geräte, die schon eingetragen sind."""
    if not push.verfuegbar():
        return {"available": False, "devices": []}
    return {"available": True, "key": push.public_key(),
            "devices": [{"id": d["id"], "name": d["user_agent"] or "?",
                         "created_at": d["created_at"]}
                        for d in push.geraete(user["id"])]}


@app.post("/api/push/subscribe")
def push_subscribe(body: PushSubBody, request: Request,
                   user: dict = Depends(admin_user)):
    if not push.verfuegbar():
        raise HTTPException(501, "Push ist auf diesem Server nicht verfügbar")
    if not body.subscription.get("endpoint"):
        raise HTTPException(400, "Ungültiges Abonnement")
    push.abonnieren(user["id"], body.subscription,
                    request.headers.get("User-Agent", "") if request else "")
    return {"ok": True}


@app.post("/api/push/unsubscribe")
def push_unsubscribe(body: PushOffBody, user: dict = Depends(admin_user)):
    push.abbestellen(body.endpoint)
    return {"ok": True}


@app.post("/api/push/test")
def push_test(user: dict = Depends(admin_user)):
    """Eine Probemeldung – sonst merkt man erst beim echten Fehler, dass
    unterwegs etwas klemmt."""
    if not push.verfuegbar():
        raise HTTPException(501, "Push ist auf diesem Server nicht verfügbar")
    n = push.senden("🧱 Brickfolio", "Probemeldung – die Zustellung klappt.", "/")
    return {"ok": True, "sent": n}


class GithubTokenBody(BaseModel):
    token: str = Field(default="", max_length=200)


@app.post("/api/settings/github_token")
def set_github_token(body: GithubTokenBody, user: dict = Depends(admin_user)):
    token = body.token.strip()
    core.set_setting("github_token", token)
    return {"ok": True, "set": bool(token),
            "masked": _mask(token) if token else ""}


@app.post("/api/settings/github_token/test")
def test_github_token(user: dict = Depends(admin_user)):
    """Prüft, ob der hinterlegte Token das Repository sehen darf.

    Bewusst nur lesend: Ob er *schreiben* darf, ließe sich nur beweisen,
    indem man ein Issue anlegt – und Müll im Repo als Nebenwirkung einer
    Prüfung wäre ein schlechter Tausch. Die Antwort sagt das auch so.
    """
    token = core.get_setting("github_token")
    if not token:
        return {"ok": False, "info": "Kein Token hinterlegt."}
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json"}, timeout=15)
    except requests.RequestException:
        return {"ok": False, "info": "GitHub nicht erreichbar."}
    if resp.status_code == 401:
        return {"ok": False, "info": "Token ungültig oder abgelaufen."}
    # Der Repository-Name steht als Platzhalter drin, nicht im Satz: Er ist
    # über GITHUB_REPO einstellbar, und ein eingebauter Name hätte für jede
    # abweichende Einstellung einen eigenen Katalogeintrag gebraucht.
    if resp.status_code == 404:
        return {"ok": False, "repo": GITHUB_REPO,
                "info": "Token gültig, aber {repo} ist für ihn nicht "
                        "freigegeben (Repository access)."}
    if resp.status_code >= 400:
        return {"ok": False, "code": resp.status_code,
                "info": "GitHub antwortet mit {code}."}
    return {"ok": True, "repo": GITHUB_REPO,
            "info": "Token gültig, {repo} erreichbar. Ob er Issues anlegen "
                    "darf, zeigt sich beim ersten Melden – das prüft GitHub "
                    "erst beim Schreiben."}


# ------------------------------------------------------- Benachrichtigungen

TYPE_LABEL = {"set": "Set", "minifig": "Figur", "part": "Teil"}


def _notify(kind: str, title: str, body: str = "", item_type: str = None,
            item_id: str = None, new_item_id: str = None) -> None:
    """Hinweis hinterlegen. Bleibt stehen, bis ihn jemand wegklickt.

    Gibt es ihn schon (gleiche Art, gleicher Artikel), passiert nichts – auch
    dann nicht, wenn er bereits weggeklickt wurde: Wer den Hinweis gesehen und
    entschieden hat, soll ihn nicht bei jedem Preislauf erneut bekommen.
    """
    with core.db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO notifications (kind, item_type, item_id, "
            "new_item_id, title, body, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kind, item_type, item_id, new_item_id, title, body,
             int(time.time())))


# Hinweise, die nur Admins etwas angehen. Der Fehlerbericht liegt in einer
# Admin-Karte – ein Zettel dorthin wäre für alle anderen eine Sackgasse.
ADMIN_NOTES = ("error",)


def _note_error(message: str, fp: str) -> None:
    """Auf einen neu aufgezeichneten Fehler hinweisen.

    Höchstens **ein** offener Zettel gleichzeitig: Ein Problem löst oft
    mehrere verschiedene Fehler aus, und zehn Karten übereinander helfen
    niemandem. Ist der eine weggeklickt, meldet sich der nächste neue Fehler
    wieder – die Fingerabdruck-Kennung sorgt dafür, dass es wirklich ein
    neuer ist und nicht derselbe zum zweiten Mal.
    """
    with core.db() as conn:
        # Nur ein Zettel blockiert, dessen Fehler es **noch gibt**.
        #
        # Vorher genügte irgendein offener Zettel. Wer den Bericht leerte,
        # ließ damit einen verwaisten stehen – er zeigte auf einen Fehler,
        # den es nicht mehr gab („Ein Fehler wurde aufgezeichnet", Bericht
        # leer), und verhinderte obendrein **jede weitere** Meldung. Der
        # Zettel, der auf Probleme hinweisen soll, machte die App also
        # stumm, und zwar für immer.
        verwaist = conn.execute(
            "SELECT n.id FROM notifications n LEFT JOIN error_log e "
            "ON e.fingerprint = n.item_id WHERE n.kind = 'error' "
            "AND n.dismissed_at IS NULL AND e.id IS NULL").fetchall()
        for r in verwaist:
            conn.execute("UPDATE notifications SET dismissed_at = ? "
                         "WHERE id = ?", (int(time.time()), r["id"]))
        offen = conn.execute(
            "SELECT 1 FROM notifications n JOIN error_log e "
            "ON e.fingerprint = n.item_id WHERE n.kind = 'error' "
            "AND n.dismissed_at IS NULL LIMIT 1").fetchone()
    if offen:
        return
    # Auch aufs Gerät, wenn jemand das eingeschaltet hat. Bewusst nach dem
    # „höchstens einer offen"-Riegel: Sonst käme bei einem kaputten Update
    # ein Dutzend Meldungen hintereinander.
    try:
        push.senden("🐞 Brickfolio", "Ein Fehler wurde aufgezeichnet.", "/")
    except Exception:
        pass          # Melden darf nie stören
    _notify("error", "🐞 Ein Fehler wurde aufgezeichnet",
            f"„{message[:140]}“ – nachzulesen unter Mehr → Wartung → "
            "Fehlerbericht. Von dort lässt sich daraus ein GitHub-Issue "
            "anlegen; von allein geht nichts nach außen.",
            "error", fp)


def _note_item_gone(entry: dict) -> None:
    """BrickLink kennt eine Nummer aus der Sammlung nicht mehr."""
    label = TYPE_LABEL.get(entry.get("item_type"), "Artikel")
    name = entry.get("name") or entry.get("item_id")
    _notify(
        "item_gone",
        f"{label} {entry['item_id']} gibt es bei BrickLink nicht mehr",
        f"„{name}“ liefert seit dem letzten Preisabruf keine Daten mehr. "
        "BrickLink hat die Nummer vermutlich geändert oder den Eintrag "
        "gelöscht. Der Preis bleibt so lange auf dem alten Stand.",
        entry.get("item_type"), entry["item_id"])


def _resolve_gone_items() -> None:
    """Für verschwundene Nummern die neue im Change Log suchen.

    BrickLink hat dafür keine API, nur die öffentliche Log-Seite – deshalb
    wird sie nur angefasst, wenn tatsächlich etwas fehlt.
    """
    with core.db() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE kind = 'item_gone' "
            "AND new_item_id IS NULL AND dismissed_at IS NULL LIMIT 5").fetchall()
    for row in rows:
        with core.db() as conn:
            prev = conn.execute(
                "SELECT MAX(price_updated_at) AS t FROM collection "
                "WHERE item_id = ?", (row["item_id"],)).fetchone()
        since = (prev["t"] if prev and prev["t"] else row["created_at"]) - 86400
        try:
            hit = integrations.find_number_change(row["item_id"], since)
        except Exception:
            continue
        if not hit:
            continue
        label = TYPE_LABEL.get(row["item_type"], "Artikel")
        was = ("zusammengelegt" if hit["kind"] == "merged" else "umbenannt")
        with core.db() as conn:
            conn.execute(
                "UPDATE notifications SET new_item_id = ?, title = ?, body = ? "
                "WHERE id = ?",
                (hit["new_id"],
                 f"{label} {row['item_id']} heißt bei BrickLink jetzt "
                 f"{hit['new_id']}",
                 f"BrickLink hat den Eintrag {was}. Mit „Nummer übernehmen“ "
                 "wird die neue Nummer überall eingetragen – in Sammlung, "
                 "Wunschliste und Einkaufslisten – und der Preisabruf "
                 "funktioniert wieder.",
                 row["id"]))


def _apply_new_number(old_id: str, new_id: str) -> int:
    """Neue BrickLink-Nummer überall eintragen. Gibt geänderte Zeilen zurück."""
    changed = 0
    with core.db() as conn:
        for table in PRICE_TABLES:
            cur = conn.execute(
                f"UPDATE {table} SET item_id = ?, price_updated_at = NULL "
                "WHERE item_id = ?", (new_id, old_id))
            changed += cur.rowcount
        # Set-Verknüpfungen ziehen mit, sonst zeigt „👥 3/4" ins Leere
        conn.execute("UPDATE set_contents SET fig_no = ? WHERE fig_no = ?",
                     (new_id, old_id))
        conn.execute("UPDATE set_contents SET set_no = ? WHERE set_no = ?",
                     (new_id, old_id))
        conn.execute("UPDATE price_history SET item_id = ? WHERE item_id = ?",
                     (new_id, old_id))
    return changed


# ------------------------------------------------- Dieselbe Nummer, zweimal
#
# Auf der Packung steht `21306`, BrickLink führt dasselbe Set als `21306-1`.
# Wer eines von Hand erfasst und das andere scannt, hat zwei Zeilen für ein
# Set – und die Sammlung zählt es doppelt. Zusammenführen kann die App das
# nicht von sich aus: Ob jemand wirklich zwei besitzt oder nur zweimal
# erfasst hat, weiß nur er selbst.

def _bricklink_nummer(item_id: str, item_type: str, name: str = "") -> tuple:
    """Nummer und Namen auf den BrickLink-Stand bringen.

    Auf der Packung steht `21306`, im Katalog heißt dasselbe Set `21306-1`.
    Wer von Hand erfasst, tippt die Zahl von der Packung – und hat danach
    eine Zeile, die zu keiner gescannten passt. Deshalb wird die Endung hier
    ergänzt, bevor irgendetwas gespeichert wird.

    Sind die BrickLink-Schlüssel hinterlegt, wird zusätzlich nachgefragt:
    Dann gilt der Name aus dem Katalog. Er ist der, unter dem alle anderen
    dasselbe Set führen – „Yellow Submarine" statt „gelbes U-Boot vom
    Flohmarkt". Ohne Schlüssel bleibt der eingetippte Name stehen.

    Gibt der Katalog nichts her (falsche Nummer, Dienst weg), bleibt alles
    wie eingetippt: Eine Erfassung soll nicht daran scheitern.
    """
    nummer = (item_id or "").strip()
    if item_type != "set" or not re.fullmatch(r"\d{2,8}", nummer):
        return nummer, name
    nummer = f"{nummer}-1"
    if not integrations.bricklink_enabled():
        return nummer, name
    try:
        d = integrations.bricklink_item("set", nummer)
    except Exception:
        return nummer, name          # Nummer ergänzt, Rest wie eingetippt
    return d.get("item_id") or nummer, d.get("name") or name


def _nummer_kern(item_id: str) -> str:
    """Nummer ohne die BrickLink-Endung. `21306-1` und `21306` werden gleich.

    Nur die Endung `-<Ziffern>` fällt weg. Figurennummern wie `sw0312`
    bleiben unangetastet, und `fig-001234` (Rebrickable) ebenfalls – dort
    steht die Ziffernfolge nicht am Ende einer Variante, sondern *ist* die
    Nummer.
    """
    kern = (item_id or "").strip().lower()
    if kern.startswith(("fig-", "manuell-", "custom-")):
        return kern
    return re.sub(r"-\d+$", "", kern)


def _dubletten_suchen(conn) -> list:
    """Paare finden, die sich nur in der Endung unterscheiden."""
    rows = conn.execute(
        "SELECT id, item_id, item_type, name, quantity, condition "
        "FROM collection ORDER BY id").fetchall()
    nach_kern = {}
    for r in rows:
        schluessel = (r["item_type"], _nummer_kern(r["item_id"]))
        nach_kern.setdefault(schluessel, []).append(r)
    paare = []
    for (typ, kern), gruppe in nach_kern.items():
        if len(gruppe) < 2:
            continue
        # Die Zeile mit der BrickLink-Endung ist die belastbarere: Sie hat
        # Preise, Set-Inhalte und passt zum Katalog.
        mit = [g for g in gruppe if re.search(r"-\d+$", g["item_id"] or "")]
        ohne = [g for g in gruppe if g not in mit]
        if not mit or not ohne:
            continue          # zwei echte Varianten – da mischt sich niemand ein
        paare.append({"behalten": mit[0], "aufgeben": ohne[0], "typ": typ})
    return paare


def dubletten_pruefen() -> int:
    """Hinweise für gefundene Paare hinterlegen. Gibt die Zahl zurück."""
    with core.db() as conn:
        paare = _dubletten_suchen(conn)
    for p in paare:
        a, b = p["behalten"], p["aufgeben"]
        _notify("dublette",
              "Dasselbe Set zweimal erfasst?",
              f"\u201e{b['name']}\u201c ist als {b['item_id']} und als "
              f"{a['item_id']} in der Sammlung \u2013 bei BrickLink ist das "
              f"dieselbe Nummer, die Endung geh\u00f6rt dort dazu.",
              item_type=p["typ"], item_id=b["item_id"], new_item_id=a["item_id"])
    return len(paare)


class DubletteBody(BaseModel):
    modus: str = Field(pattern="^(zusammen|ersetzen)$")


@app.post("/api/notifications/{note_id}/merge")
def dublette_zusammenfuehren(note_id: int, body: DubletteBody,
                             user: dict = Depends(current_user)):
    """Zwei Zeilen zu einer machen.

    `zusammen` addiert die Stückzahlen – für den Fall, dass wirklich zwei
    Exemplare da sind. `ersetzen` behält die Stückzahl der bleibenden Zeile,
    wenn dasselbe Set schlicht zweimal erfasst wurde.
    """
    with core.db() as conn:
        note = conn.execute("SELECT * FROM notifications WHERE id = ?",
                            (note_id,)).fetchone()
        if not note or note["kind"] != "dublette":
            raise HTTPException(404, "Hinweis nicht gefunden")
        alt = conn.execute(
            "SELECT * FROM collection WHERE item_id = ? AND item_type = ?",
            (note["item_id"], note["item_type"])).fetchall()
        neu = conn.execute(
            "SELECT * FROM collection WHERE item_id = ? AND item_type = ?",
            (note["new_item_id"], note["item_type"])).fetchall()
        if not alt or not neu:
            conn.execute("UPDATE notifications SET dismissed_at = ? WHERE id = ?",
                         (int(time.time()), note_id))
            raise HTTPException(400, "Einer der beiden Einträge gibt es nicht "
                                     "mehr – der Hinweis ist erledigt.")
        menge = 0
        for a in alt:
            # Zielzeile mit passendem Zustand suchen, sonst die erste
            ziel = next((n for n in neu if n["condition"] == a["condition"]), neu[0])
            if body.modus == "zusammen":
                conn.execute("UPDATE collection SET quantity = quantity + ? "
                             "WHERE id = ?", (a["quantity"], ziel["id"]))
                conn.execute("UPDATE purchases SET entry_id = ? "
                             "WHERE entry_id = ?", (ziel["id"], a["id"]))
                menge += a["quantity"]
            else:
                # Beim Ersetzen zählt nur, was die bleibende Zeile hat – das
                # Kaufbuch der aufgegebenen stünde sonst für einen Kasten
                # zweimal drin. Erst löschen, dann die Zeile: umgekehrt wären
                # die Posten schon umgezogen.
                conn.execute("DELETE FROM purchases WHERE entry_id = ?",
                             (a["id"],))
            conn.execute("DELETE FROM collection WHERE id = ?", (a["id"],))
            _kaufsumme_nachziehen(conn, ziel["id"])
        # Der Katalogname gilt. Die bleibende Zeile trägt ihn schon – hier
        # steht es trotzdem ausdrücklich, damit ein späterer Umbau der
        # Auswahl ihn nicht versehentlich mitnimmt.
        conn.execute("UPDATE collection SET name = COALESCE(NULLIF(name, ''), ?) "
                     "WHERE id = ?", (alt[0]["name"], neu[0]["id"]))
        conn.execute("UPDATE notifications SET dismissed_at = ? WHERE id = ?",
                     (int(time.time()), note_id))
    return {"ok": True, "modus": body.modus, "uebernommen": menge}


@app.get("/api/notifications")
def list_notifications(user: dict = Depends(current_user)):
    dubletten_pruefen()
    with core.db() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE dismissed_at IS NULL "
            "ORDER BY created_at DESC LIMIT 20").fetchall()
    items = [dict(r) for r in rows]
    if not user["is_admin"]:
        items = [i for i in items if i["kind"] not in ADMIN_NOTES]
    return {"items": items}


@app.delete("/api/notifications/{note_id}")
def dismiss_notification(note_id: int, user: dict = Depends(current_user)):
    with core.db() as conn:
        conn.execute("UPDATE notifications SET dismissed_at = ? WHERE id = ?",
                     (int(time.time()), note_id))
    return {"ok": True}


@app.post("/api/notifications/{note_id}/apply")
def apply_notification(note_id: int, user: dict = Depends(current_user)):
    """Die im Hinweis genannte neue Nummer übernehmen."""
    with core.db() as conn:
        row = conn.execute("SELECT * FROM notifications WHERE id = ?",
                           (note_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Hinweis nicht gefunden")
    if not row["new_item_id"]:
        raise HTTPException(400, "Zu diesem Hinweis ist keine neue Nummer "
                                 "bekannt")
    changed = _apply_new_number(row["item_id"], row["new_item_id"])
    with core.db() as conn:
        conn.execute("UPDATE notifications SET dismissed_at = ? WHERE id = ?",
                     (int(time.time()), note_id))
    return {"ok": True, "changed": changed, "new_item_id": row["new_item_id"]}


# Preise, die nicht mehr zur Einstellung passen – nach Gebiet *oder*
# Währung. Beides steckt in derselben Bedingung, damit „umrechnen" nach einem
# Wechsel der Währung genauso greift wie nach einem Wechsel des Gebiets. Alte
# Bestände haben keine Währung gespeichert; die galten immer als Euro.
_STALE = ("item_id NOT LIKE 'fig-%' AND item_id NOT LIKE 'manuell-%' "
          "AND item_id NOT LIKE 'custom-%' AND price_updated_at IS NOT NULL "
          "AND (COALESCE(price_region, '') != ? "
          "OR COALESCE(price_currency, 'EUR') != ?)")


def _prices_pending(conn, region: str, waehrung: str = None) -> int:
    """Wie viele Sammlungs-Artikel haben noch Preise aus einem anderen Gebiet
    oder in einer anderen Währung?"""
    waehrung = integrations.currency() if waehrung is None else waehrung
    return conn.execute(
        f"SELECT COUNT(*) AS c FROM collection WHERE {_STALE}",
        (region, waehrung)).fetchone()["c"]


# Artikel, die zwar abgefragt wurden, aber weder für neu noch für gebraucht
# einen Preis haben. Meist, weil im gewählten Gebiet nichts verkauft wurde –
# genau diese profitieren vom Rückfall Europa → weltweit.
# `price_updated_at IS NOT NULL` stand hier bis 2.18.0 mit drin – gedacht als
# „schon einmal versucht, nichts gefunden". Damit blieben aber ausgerechnet
# die Artikel außen vor, die **noch nie** versucht wurden: Ein CSV-Import legt
# sie ohne Preisstand an, und „Preislose erneut abrufen" fand sie nie. Sie
# standen für immer ohne Preis da.
_NO_PRICE = ("item_id NOT LIKE 'fig-%' AND item_id NOT LIKE 'manuell-%' AND item_id NOT LIKE 'custom-%' "
             "AND COALESCE(price_new, 0) = 0 AND COALESCE(price_used, 0) = 0")


def _prices_missing(conn, before: int = None) -> int:
    """Sammlungs-Artikel ganz ohne Preis. `before` grenzt auf die ein, die
    im laufenden Durchgang noch nicht neu versucht wurden."""
    sql = f"SELECT COUNT(*) AS c FROM collection WHERE {_NO_PRICE}"
    args: tuple = ()
    if before is not None:
        sql += " AND COALESCE(price_updated_at, 0) < ?"
        args = (before,)
    return conn.execute(sql, args).fetchone()["c"]


@app.get("/api/settings/price_region")
def get_price_region(user: dict = Depends(current_user)):
    """Gebiet, Währung, Auswahllisten und offener Nachrechen-Bedarf."""
    region = integrations.price_region()
    waehrung = integrations.currency()
    with core.db() as conn:
        pending = _prices_pending(conn, region, waehrung)
        missing = _prices_missing(conn)
    return {"region": region,
            "currency": waehrung,
            "options": [{"value": k, "label": v}
                        for k, v in integrations.PRICE_REGIONS.items()],
            "currencies": [{"value": k, "label": v}
                           for k, v in integrations.CURRENCIES.items()],
            "suggested": integrations.LAND_WAEHRUNG,
            "pending": pending,
            "missing": missing,
            "can_fetch": integrations.bricklink_enabled()}


class PriceRegionBody(BaseModel):
    region: str = Field(default="", max_length=20)
    currency: str | None = Field(default=None, max_length=3)


@app.post("/api/settings/price_region")
def set_price_region(body: PriceRegionBody, user: dict = Depends(admin_user)):
    if body.region not in integrations.PRICE_REGIONS:
        raise HTTPException(400, "Unbekanntes Preisgebiet")
    if body.currency is not None and body.currency not in integrations.CURRENCIES:
        raise HTTPException(400, "Unbekannte Währung")
    core.set_setting("price_region", body.region)
    if body.currency is not None:
        core.set_setting("currency", body.currency)
    waehrung = integrations.currency()
    with core.db() as conn:
        pending = _prices_pending(conn, body.region, waehrung)
    return {"ok": True, "region": body.region, "currency": waehrung,
            "pending": pending}


@app.post("/api/prices/refresh_region")
def refresh_prices_region(limit: int = 20, user: dict = Depends(admin_user)):
    """Preise schrittweise auf das eingestellte Gebiet umrechnen.

    Läuft in Häppchen: Jeder Artikel kostet zwei BrickLink-Abrufe (neu und
    gebraucht), und BrickLink hat ein Tageskontingent. Die Antwort sagt, wie
    viele noch offen sind – die App ruft so lange nach, wie es sinnvoll ist.
    """
    if not integrations.bricklink_enabled():
        raise HTTPException(501, "BrickLink-API nicht konfiguriert")
    limit = max(1, min(limit, 50))
    region = integrations.price_region()
    waehrung = integrations.currency()
    with core.db() as conn:
        rows = conn.execute(
            f"SELECT * FROM collection WHERE {_STALE} "
            "ORDER BY price_updated_at LIMIT ?",
            (region, waehrung, limit)).fetchall()
    done, failed = 0, []
    for r in rows:
        try:
            _fetch_and_store_prices(dict(r), "collection")
            done += 1
        except Exception as e:
            failed.append({"item_id": r["item_id"], "error": scrub(str(e))[:120]})
            # Trotzdem als bearbeitet markieren, sonst hängt der Lauf ewig an
            # derselben Nummer (z. B. wenn BrickLink sie nicht kennt).
            with core.db() as conn:
                conn.execute("UPDATE collection SET price_region = ?, "
                             "price_currency = ? WHERE id = ?",
                             (region, waehrung, r["id"]))
    with core.db() as conn:
        pending = _prices_pending(conn, region, waehrung)
    return {"ok": True, "updated": done, "remaining": pending, "failed": failed}


@app.post("/api/prices/refresh_missing")
def refresh_prices_missing(limit: int = 20, user: dict = Depends(admin_user)):
    """Preislose Artikel erneut abrufen – jetzt mit dem Rückfall Europa → weltweit.

    Jeder Artikel wird pro Durchgang nur einmal versucht: `price_updated_at`
    wird bei jedem Versuch hochgesetzt (auch ohne Treffer), und gezählt werden
    nur die, deren Stand älter ist als der Beginn dieses Durchgangs. So dreht
    sich der Lauf nicht endlos an Artikeln, die wirklich nirgends verkauft
    wurden.
    """
    if not integrations.bricklink_enabled():
        raise HTTPException(501, "BrickLink-API nicht konfiguriert")
    limit = max(1, min(limit, 50))
    started = int(time.time())
    with core.db() as conn:
        rows = conn.execute(
            f"SELECT * FROM collection WHERE {_NO_PRICE} "
            "AND COALESCE(price_updated_at, 0) < ? "
            "ORDER BY COALESCE(price_updated_at, 0) LIMIT ?",
            (started, limit)).fetchall()
    done, filled, failed = 0, 0, []
    for r in rows:
        try:
            res = _fetch_and_store_prices(dict(r), "collection")
            done += 1
            if (res.get("new") and res["new"].get("avg")) or \
               (res.get("used") and res["used"].get("avg")):
                filled += 1
        except Exception as e:
            failed.append({"item_id": r["item_id"], "error": scrub(str(e))[:120]})
            # Versuch vermerken, sonst bleibt der Artikel im nächsten Häppchen
            # sofort wieder ganz vorn (z. B. wenn BrickLink die Nummer nicht kennt).
            with core.db() as conn:
                conn.execute(
                    "UPDATE collection SET price_updated_at = ? WHERE id = ?",
                    (started, r["id"]))
    with core.db() as conn:
        remaining = _prices_missing(conn, before=started)
    return {"ok": True, "updated": done, "filled": filled,
            "remaining": remaining, "failed": failed}


def _update_flag_path() -> str:
    """Markierungsdatei im geteilten Datenverzeichnis (Host sieht sie auch)."""
    return os.path.join(os.path.dirname(core.DB_PATH), "update-requested.json")


# Der Helfer auf dem Server hinterlässt bei jedem Lauf ein Lebenszeichen.
# Ist es frisch, läuft er – nur dann bietet die App das Update an.
HELPER_MAX_AGE = 300


def _helper_seen_at() -> int | None:
    path = os.path.join(os.path.dirname(core.DB_PATH), "update-watch-alive")
    try:
        return int(os.path.getmtime(path))
    except OSError:
        return None


def _read_update_flag() -> dict | None:
    try:
        with open(_update_flag_path(), "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return data
    except (OSError, ValueError):
        return None


class UpdateRequestBody(BaseModel):
    # Karenzzeit, damit laufende Eingaben abgeschlossen werden können
    delay: int = Field(default=60, ge=0, le=3600)


@app.post("/api/update/request")
def request_update(body: UpdateRequestBody, user: dict = Depends(admin_user)):
    """Update anfordern. Ausgeführt wird es vom Helfer auf dem Server.

    Die App selbst rührt Docker nicht an – sie legt nur eine Markierung im
    Datenverzeichnis ab. `execute_after` sorgt dafür, dass die Karenzzeit
    auch dann eingehalten wird, wenn der Browser zwischendurch zugeht.
    """
    seen = _helper_seen_at()
    if not (seen and int(time.time()) - seen < HELPER_MAX_AGE):
        # Ohne Helfer würde die App auf ein Update warten, das nie kommt.
        raise HTTPException(409, "Der Update-Helfer läuft nicht auf dem "
                                 "Server. Ohne ihn bliebe die App hängen – "
                                 "siehe README (update-watch.sh als Aufgabe "
                                 "einrichten).")
    now = int(time.time())
    data = {"requested_at": now, "execute_after": now + body.delay,
            "by": user["name"], "version": core.APP_VERSION}
    try:
        with open(_update_flag_path(), "w") as f:
            json.dump(data, f)
    except OSError as e:
        raise HTTPException(500, f"Markierung nicht schreibbar: {scrub(str(e))}")
    return {"ok": True, **data}


@app.post("/api/update/cancel")
def cancel_update(user: dict = Depends(admin_user)):
    try:
        os.remove(_update_flag_path())
    except FileNotFoundError:
        pass
    except OSError as e:
        raise HTTPException(500, f"Markierung nicht löschbar: {scrub(str(e))}")
    return {"ok": True}


@app.get("/api/update/status")
def update_status(user: dict = Depends(current_user)):
    """Läuft gleich ein Update? Wird von allen Browsern kurz abgefragt."""
    seen = _helper_seen_at()
    base = {"version": core.APP_VERSION, "started_at": _STARTED_AT,
            "helper_seen_at": seen,
            "helper_active": bool(seen
                                  and int(time.time()) - seen < HELPER_MAX_AGE)}
    flag = _read_update_flag()
    if not flag:
        return {"pending": False, **base}
    left = int(flag.get("execute_after", 0)) - int(time.time())
    return {"pending": True,
            "seconds_left": max(0, left),
            "execute_after": flag.get("execute_after"),
            "by": flag.get("by", ""),
            **base}


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
            "offer_percent": _offer_percent(),
            "owner_name": _owner_name(),
            "currency": integrations.currency(),
            "price_region": integrations.price_region(),
            "ki_suche": integrations.ollama_enabled(),
            "hub_connected": hub.enabled()}


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

    def hole(nr: str) -> tuple:
        """(Treffer, Fehler) – „kennt BrickLink nicht" ist beides nicht.

        `requests.HTTPError` ist eine Unterklasse von `RequestException`.
        Ohne eigenen Zweig davor landete ein schlichtes 404 im Ast
        „BrickLink nicht erreichbar" – am ↻ neben dem Bild stand deshalb
        **Fehler 502**, wo in Wahrheit nur die Nummer nicht passte.
        """
        try:
            return integrations.bricklink_item(item_type, nr), None
        except LookupError:
            return None, None
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code == 404:
                return None, None
            return None, HTTPException(502, f"BrickLink-Fehler ({code})")
        except requests.Timeout:
            return None, HTTPException(504, "BrickLink antwortet nicht")
        except requests.RequestException:
            return None, HTTPException(502, "BrickLink nicht erreichbar")
        except ValueError as e:
            return None, HTTPException(400, str(e))

    nummer = item_no.strip()
    treffer, fehler = hole(nummer)
    if fehler:
        raise fehler
    if treffer:
        return treffer
    # Bedruckte Teile heißen bei BrickLink anders (`2586pr0028` → `2586ps1`).
    # Dieselbe Übersetzung wie beim Preis – sonst holt das ↻ nie ein Bild.
    ersatz = _bl_nummer(item_type, nummer)
    if ersatz and ersatz != nummer:
        treffer, fehler = hole(ersatz)
        if fehler:
            raise fehler
        if treffer:
            return treffer
    raise HTTPException(404, _unbekannt_meldung(nummer, katalog=True))


@app.get("/api/search")
def catalog_search(q: str = "", item_type: str = "minifig", page: int = 1,
                   user: dict = Depends(current_user)):
    if not integrations.rebrickable_enabled():
        raise HTTPException(501, "Katalogsuche nicht konfiguriert "
                                 "(REBRICKABLE_KEY in docker-compose setzen)")
    q = q.strip()
    if len(q) < 3:
        return {"items": [], "count": 0, "page": 1, "has_more": False}
    page = max(1, min(page, 200))
    try:
        return integrations.search_catalog(q, item_type, page=page)
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
    name = _benutzername(body.username)
    with core.db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (name,)).fetchone()
        if exists:
            raise HTTPException(409, "Benutzername ist schon vergeben")
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) "
            "VALUES (?, ?, ?, ?)",
            (name, core.hash_password(body.password),
             int(body.is_admin), int(time.time())),
        )
    return {"ok": True}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(admin_user)):
    if user_id == user["id"]:
        raise HTTPException(400, "Du kannst dich nicht selbst löschen")
    with core.db() as conn:
        # Was der Sammlung gehört, bleibt der Sammlung – nur der Name des
        # Einstellers fällt weg. Sonst nähme das Löschen eines Benutzers
        # Stücke, Wünsche und Listen mit, die alle gemeinsam pflegen.
        for tabelle, spalte in (("collection", "added_by"),
                                ("wanted", "added_by"),
                                ("shopping_lists", "created_by"),
                                ("shopping_items", "done_by")):
            conn.execute(f"UPDATE {tabelle} SET {spalte} = NULL "
                         f"WHERE {spalte} = ?", (user_id,))
        # Die Push-Anmeldung gehört dagegen nur ihm und geht mit – sonst
        # bekäme sein Gerät weiter Meldungen dieser Instanz.
        conn.execute("DELETE FROM push_subs WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return {"ok": True}


class PasswordBody(BaseModel):
    password: str = Field(min_length=8, max_length=200)


class OwnPasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class UsernameBody(BaseModel):
    username: str = Field(min_length=2, max_length=60)


@app.post("/api/me/username")
def change_own_username(body: UsernameBody,
                        user: dict = Depends(current_user)):
    name = _benutzername(body.username)
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
    core.sitzungen_beenden(user["id"])
    # Wer gerade das Passwort geändert hat, soll nicht selbst rausfliegen –
    # er bekommt eine frische Sitzung mit dem neuen Stand.
    return {"ok": True,
            "token": core.create_token(user["id"], user["name"],
                                       user["is_admin"])}


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


class AdminBody(BaseModel):
    is_admin: bool


@app.post("/api/users/{user_id}/admin")
def set_admin(user_id: int, body: AdminBody, user: dict = Depends(admin_user)):
    """Admin-Rechte vergeben oder entziehen. Der letzte Admin bleibt Admin,
    sonst könnte sich niemand mehr um die Instanz kümmern."""
    with core.db() as conn:
        row = conn.execute("SELECT id, is_admin FROM users WHERE id = ?",
                           (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Benutzer nicht gefunden")
        if row["is_admin"] and not body.is_admin:
            admins = conn.execute(
                "SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
            if admins <= 1:
                raise HTTPException(
                    400, "Das ist der einzige Admin – die Rechte lassen sich "
                         "nicht entziehen. Zuerst jemand anderen zum Admin machen.")
        conn.execute("UPDATE users SET is_admin = ? WHERE id = ?",
                     (int(body.is_admin), user_id))
    return {"ok": True, "is_admin": body.is_admin}


@app.post("/api/users/{user_id}/password")
def reset_user_password(user_id: int, body: PasswordBody,
                        user: dict = Depends(admin_user)):
    with core.db() as conn:
        cur = conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                           (core.hash_password(body.password), user_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Benutzer nicht gefunden")
    # Setzt ein Admin ein Passwort zurück, weil ein Gerät weg ist, muss die
    # alte Sitzung enden – sonst war das Zurücksetzen wirkungslos.
    core.sitzungen_beenden(user_id)
    return {"ok": True}


def _set_bound_map(conn) -> dict:
    """Wie viele Exemplare je Figuren-Zeile stecken in eigenen Sets?

    Ergebnis: {collection.id: gebundene_Menge}. Grundlage ist der
    Set-Inhalt (set_contents) mal der Anzahl der besessenen Sets.
    Zuerst werden zustandsgleiche Figuren-Zeilen gebunden.
    """
    sets = conn.execute(
        "SELECT item_id, quantity, condition FROM collection "
        "WHERE item_type = 'set'").fetchall()
    if not sets:
        return {}
    contents: dict = {}
    for r in conn.execute("SELECT set_no, fig_no, qty FROM set_contents"):
        contents.setdefault(r["set_no"], []).append(
            (r["fig_no"], r["qty"] or 1))
    need: dict = {}
    for s in sets:
        for fig_no, q in contents.get(s["item_id"], []):
            need.setdefault(fig_no, {})
            need[fig_no][s["condition"]] = (
                need[fig_no].get(s["condition"], 0) + q * s["quantity"])
    if not need:
        return {}
    by_fig: dict = {}
    for r in conn.execute(
            "SELECT id, item_id, quantity, condition FROM collection "
            "WHERE item_type = 'minifig'").fetchall():
        by_fig.setdefault(r["item_id"], []).append(r)
    bound: dict = {}
    for fig_no, conds in need.items():
        rows = by_fig.get(fig_no)
        if not rows:
            continue
        for cond, amount in conds.items():
            remaining = amount
            ordered = sorted(
                rows, key=lambda x: 0 if x["condition"] == cond else 1)
            for r in ordered:
                if remaining <= 0:
                    break
                free = r["quantity"] - bound.get(r["id"], 0)
                if free <= 0:
                    continue
                take = min(free, remaining)
                bound[r["id"]] = bound.get(r["id"], 0) + take
                remaining -= take
    return bound


@app.get("/api/stats/dashboard")
def stats_dashboard(user: dict = Depends(current_user)):
    with core.db() as conn:
        items = conn.execute(
            "SELECT id, item_id, item_type, name, img_url, quantity, "
            "condition, year, price_new, price_used, paid_price, "
            "paid_source FROM collection").fetchall()
        hist = conn.execute(
            "SELECT item_id, item_type, ts, price_new, price_used "
            "FROM price_history ORDER BY ts").fetchall()
        bound = _set_bound_map(conn)
        # Einkaufspreise je Liste (offen UND archiviert). Als inventarisiert
        # markierte Listen bleiben aus der Summe heraus, tauchen im Popup aber
        # weiter auf, damit man sie wieder mitzählen kann.
        lrows = conn.execute(
            "SELECT l.id, l.name, l.archived, l.inventoried, "
            "COALESCE(SUM(si.paid_price), 0) AS paid "
            "FROM shopping_lists l "
            "LEFT JOIN shopping_items si ON si.list_id = l.id "
            "AND si.paid_price IS NOT NULL "
            "GROUP BY l.id HAVING paid > 0 "
            "ORDER BY l.inventoried, l.archived, l.created_at DESC").fetchall()

    total_value = 0.0
    paid_sum = 0.0
    value_of_paid_items = 0.0
    pieces = 0
    top = []
    winners = []
    by_type: dict = {}
    by_cond: dict = {}
    by_year: dict = {}
    bound_value = 0.0
    paid_estimated = 0.0
    for r in items:
        unit = _unit_price(r["condition"], r["price_new"], r["price_used"])
        value = round((unit or 0) * r["quantity"], 2)
        # In eigenen Sets steckende Figuren nicht doppelt zählen
        in_sets = bound.get(r["id"], 0)
        net = round((unit or 0) * max(0, r["quantity"] - in_sets), 2)
        bound_value += value - net
        pieces += r["quantity"]
        total_value += net
        bt = by_type.setdefault(r["item_type"], {"pieces": 0, "value": 0.0})
        bt["pieces"] += r["quantity"]
        bt["value"] += net
        bc = by_cond.setdefault(r["condition"], {"pieces": 0, "value": 0.0})
        bc["pieces"] += r["quantity"]
        bc["value"] += net
        if r["year"]:
            by = by_year.setdefault(r["year"], {"pieces": 0, "value": 0.0})
            by["pieces"] += r["quantity"]
            by["value"] += net
        # „bezahlt": alles zählt – auch ⚙️ geschätzte Preise, denn bezahlt
        # wurde ja irgendwann etwas. Ausnahme: Figuren, die in einem eigenen
        # Set stecken UND deren Preis nur automatisch ermittelt wurde – die
        # deckt der Set-Preis bereits ab. Selbst eingetragene (✏️) Preise
        # zählen immer, auch bei Set-Figuren (separat dazugekauft).
        skip_paid = (r["item_type"] == "minifig"
                     and in_sets > 0
                     and (r["paid_source"] or "auto") != "manual")
        if r["paid_price"] is not None and not skip_paid:
            paid_sum += r["paid_price"]
            value_of_paid_items += value
            winners.append({"item_id": r["item_id"], "name": r["name"],
                            "img_url": r["img_url"],
                            "item_type": r["item_type"],
                            "gain": round(value - r["paid_price"], 2)})
        elif r["paid_price"] is not None:
            paid_estimated += r["paid_price"]
        if value > 0:
            top.append({"item_id": r["item_id"], "name": r["name"],
                        "img_url": r["img_url"], "item_type": r["item_type"],
                        "quantity": r["quantity"], "value": value})
    top.sort(key=lambda x: x["value"], reverse=True)
    winners.sort(key=lambda x: x["gain"], reverse=True)
    # Verluste bekommen eine eigene Liste. Vorher rutschten sie unten in die
    # „Besten Wertsteigerungen" – aber nur dann, wenn es weniger als fünf
    # Gewinner gab. Wer viel gewonnen *und* viel verloren hatte, sah seine
    # Verluste nie; wer wenig gewonnen hatte, fand sie unter einer
    # Überschrift, die das Gegenteil versprach.
    #
    # Getrennt heißt auch: In den Gewinnen steht ab jetzt nur Gewinn. Ein
    # rotes Minus unter „Beste Wertsteigerungen" war immer schon seltsam.
    losers = sorted((w for w in winners if w["gain"] < 0),
                    key=lambda x: x["gain"])
    winners = [w for w in winners if w["gain"] > 0]

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
            qty = max(0, r["quantity"] - bound.get(r["id"], 0))
            s += (u or 0) * qty
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
                       "in_sets_value": round(bound_value, 2),
                       "paid_estimated": round(paid_estimated, 2),
                       "avg_piece": round(total_value / pieces, 2)
                       if pieces else 0,
                       "paid": round(paid_sum, 2),
                       "profit": round(value_of_paid_items - paid_sum, 2),
                       # Kennzahl auf der Übersicht: nur offene Listen
                       # (archivierte sieht man im Popup).
                       "lists_paid": round(
                           sum(r["paid"] for r in lrows
                               if not r["inventoried"] and not r["archived"]),
                           2),
                       "lists_count": sum(
                           1 for r in lrows
                           if not r["inventoried"] and not r["archived"])},
            "lists_breakdown": [
                {"id": r["id"], "name": r["name"],
                 "archived": bool(r["archived"]),
                 "inventoried": bool(r["inventoried"]),
                 "paid": round(r["paid"], 2)} for r in lrows],
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
            "winners": winners[:5],
            "losers": losers[:5]}


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
    # Ein einzelnes offenes Anführungszeichen macht aus dem ganzen Rest der
    # Datei ein Feld. Python bricht dann bei 128 KB ab – bisher mit einem
    # nackten „Internal Server Error", bei dem niemand ahnt, woran es liegt.
    try:
        rows = list(csvmod.reader(io.StringIO(text), delimiter=delim))
    except csvmod.Error:
        raise HTTPException(400, "Die Datei lässt sich nicht lesen. Häufigste "
                                 "Ursache: ein einzelnes Anführungszeichen, "
                                 "das nicht wieder geschlossen wird.")
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
           # `item_type` gehört dazu, seit `item_id` als Nummer gilt: Wer die
           # eine Schreibweise nimmt, nimmt auch die andere. Fehlte die
           # Spalte, wurde still „Figur" angenommen – ein Set landete als
           # Minifigur, und Preise, Themen und Filter stimmten nie wieder.
           "type": col("typ", "type", "item_type", "art"),
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
            # Auch hier: Nummern aus fremden Listen tragen oft die Zahl von
            # der Packung. Ohne Endung landeten sie neben den gescannten.
            num, name = _bricklink_nummer(num, typ, name)
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
                "AND item_type = ? AND condition = ?",
                (num, typ, cond)).fetchone()
            if ex:
                conn.execute("UPDATE collection SET quantity = quantity + ? "
                             "WHERE id = ?", (qty, ex["id"]))
                if paid is not None:
                    _kauf_buchen(conn, ex["id"], qty, paid, "CSV-Import", now)
                merged += 1
            else:
                cur_csv = conn.execute(
                    "INSERT INTO collection (item_id, item_type, name, "
                    "img_url, bricklink_url, quantity, condition, notes, "
                    "year, paid_price, paid_source, paid_at, added_by, "
                    "added_at) VALUES (?, ?, ?, '', '', ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?)",
                    (num, typ, name, qty, cond, notes, year, paid,
                     "manual" if paid is not None else None,
                     now if paid is not None else None, user["id"], now))
                if paid is not None:
                    _kauf_buchen(conn, cur_csv.lastrowid, qty, paid,
                                 "CSV-Import", now)
                created += 1
    return {"ok": True, "created": created, "merged": merged,
            "errors": errors[:20], "error_count": len(errors)}


# ---------------------------------------------------------------- Sicherung (Admin)

# `purchases` fehlte hier bis 2.18.0 – das Kaufbuch war damit nach jeder
# Wiederherstellung leer, während der aufsummierte Kaufpreis an der Zeile
# stehen blieb. Wer wissen wollte, was er wann und wo bezahlt hat, hatte es
# verloren, ohne dass es jemandem auffiel.
BACKUP_TABLES = ["users", "collection", "purchases", "wanted",
                 "shopping_lists", "shopping_items", "price_history",
                 "set_contents", "set_meta", "fig_sets", "fig_parts",
                 "item_photos", "settings"]


class OwnerNameBody(BaseModel):
    name: str = Field(default="", max_length=40)


@app.post("/api/settings/owner_name")
def set_owner_name(body: OwnerNameBody, user: dict = Depends(admin_user)):
    """Anzeigename anpassen (leer = zurück auf Standard 'Finn')."""
    core.set_setting("owner_name", body.name.strip())
    return {"ok": True, "owner_name": _owner_name()}


@app.get("/api/stand")
def datenstand(user: dict = Depends(current_user)):
    """Ein billiger Fingerabdruck der Daten – „hat sich etwas geändert?".

    Gedacht zum häufigen Abfragen: Die Oberfläche holt das alle paar
    Sekunden und lädt die Ansicht **nur dann** neu, wenn sich die Zahl
    geändert hat. Damit sieht man, was ein anderes Gerät oder ein Werkzeug
    an der Schnittstelle angelegt hat, ohne dafür ständig ganze Listen zu
    übertragen.

    Gezählt wird nicht nur die Anzahl: Ein Artikel, der weggeht, und einer,
    der dazukommt, ergäben dieselbe. Die Summe der Schlüssel ändert sich
    dabei aber – und die Summen von Menge, Haken und Preis fangen auch das
    Ändern einer bestehenden Zeile.
    """
    def fingerabdruck(conn, tabelle: str, felder: tuple) -> str:
        teile = ["COUNT(*)", "COALESCE(SUM(id), 0)"]
        teile += [f"COALESCE(SUM({f}), 0)" for f in felder]
        zeile = conn.execute(
            f"SELECT {', '.join(teile)} FROM {tabelle}").fetchone()
        return "-".join(str(w) for w in zeile)

    with core.db() as conn:
        return {
            "collection": fingerabdruck(
                conn, "collection",
                ("quantity", "CAST(COALESCE(paid_price, 0) * 100 AS INTEGER)")),
            "wanted": fingerabdruck(conn, "wanted", ()),
            "lists": fingerabdruck(conn, "shopping_lists", ("archived",))
            + "|" + fingerabdruck(
                conn, "shopping_items",
                ("qty", "done",
                 "CAST(COALESCE(paid_price, 0) * 100 AS INTEGER)")),
        }


@app.get("/api/backup_info")
def backup_info(user: dict = Depends(admin_user)):
    files = _backup_list()
    return {"keep": BACKUP_KEEP, "count": len(files),
            "latest": files[-1]["name"] if files else None,
            "files": list(reversed(files))}


@app.get("/api/backup_file/{name}")
def backup_file(name: str, user: dict = Depends(admin_user)):
    """Einen automatischen Tagesstand herunterladen (Admin)."""
    from fastapi.responses import FileResponse
    valid = {f["name"] for f in _backup_list()}
    if name not in valid:
        raise HTTPException(404, "Sicherung nicht gefunden")
    bdir = os.path.join(os.path.dirname(core.DB_PATH), "backups")
    return FileResponse(os.path.join(bdir, name),
                        media_type="application/octet-stream",
                        filename=name)


class RestoreFileBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@app.post("/api/backup_restore_file")
def backup_restore_file(body: RestoreFileBody,
                        user: dict = Depends(admin_user)):
    """Stellt einen automatischen Tagesstand wieder her (Admin).

    Vorher wird der aktuelle Stand als zusätzliche Sicherung weggeschrieben,
    die Aktion ist also selbst wieder umkehrbar.
    """
    import datetime
    valid = {f["name"] for f in _backup_list()}
    if body.name not in valid:
        raise HTTPException(404, "Sicherung nicht gefunden")
    bdir = os.path.join(os.path.dirname(core.DB_PATH), "backups")
    snap_path = os.path.join(bdir, body.name)

    # Schnappschuss prüfen: lesbar + enthält mindestens einen Admin
    try:
        check = sqlite3.connect(f"file:{snap_path}?mode=ro", uri=True)
        admins = check.execute(
            "SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
        check.close()
    except sqlite3.Error:
        raise HTTPException(400, "Sicherung ist beschädigt oder kein "
                                 "Brickfolio-Stand")
    if admins < 1:
        raise HTTPException(400, "Sicherung enthält keinen Admin – "
                                 "Wiederherstellung würde aussperren")

    # Sicherheitskopie des aktuellen Stands
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    safety = os.path.join(bdir, f"brickfolio-manuell-{stamp}.db")
    live = sqlite3.connect(core.DB_PATH)
    dst = sqlite3.connect(safety)
    try:
        live.backup(dst)
    finally:
        dst.close()

    # Schnappschuss in die laufende Datenbank zurückspielen
    snap = sqlite3.connect(snap_path)
    try:
        snap.backup(live)
    finally:
        snap.close()
        live.close()
    print(f"[brickfolio] Wiederhergestellt: {body.name} "
          f"(Sicherheitskopie: {os.path.basename(safety)})", flush=True)
    return {"ok": True, "restored": body.name,
            "safety": os.path.basename(safety)}


# Eigene Bilder sind Dateien, keine Datenbankzeilen – ohne sie trüge die
# Sicherung nur den Verweis, und nach einem Umzug zeigten die Artikel ins
# Leere. Mitgenommen werden sie deshalb als Base64 im selben Dokument: Eine
# Datei bleibt eine Datei, und der Weg zum Einspielen (auch der aus der
# Ersteinrichtung) muss nichts Neues können.
UPLOAD_NAME = re.compile(r"^[0-9a-f]{32}\.jpg$")
UPLOADS_MAX = 150 * 1024 * 1024      # darüber wird die JSON-Datei unhandlich
UPLOAD_EINZEL_MAX = 8 * 1024 * 1024


def _uploads_liste() -> list:
    """Vorhandene eigene Bilder mit ihrer Größe."""
    d = _uploads_dir()
    raus = []
    for name in sorted(os.listdir(d)):
        if not UPLOAD_NAME.match(name):
            continue
        try:
            raus.append({"name": name,
                         "bytes": os.path.getsize(os.path.join(d, name))})
        except OSError:
            pass
    return raus


@app.get("/api/uploads_info")
def uploads_info(user: dict = Depends(admin_user)):
    """Wie viele eigene Bilder liegen hier, und wie schwer wiegen sie?"""
    dateien = _uploads_liste()
    return {"count": len(dateien), "bytes": sum(f["bytes"] for f in dateien),
            "max_bytes": UPLOADS_MAX}


@app.get("/api/backup")
def download_backup(images: int = 0, user: dict = Depends(admin_user)):
    dump = {"app": "brickfolio", "version": 1,
            "created_at": int(time.time()), "tables": {}}
    with core.db() as conn:
        for t in BACKUP_TABLES:
            rows = conn.execute(f"SELECT * FROM {t}").fetchall()
            dump["tables"][t] = [dict(r) for r in rows]
    if images:
        dateien = _uploads_liste()
        gesamt = sum(f["bytes"] for f in dateien)
        if gesamt > UPLOADS_MAX:
            raise HTTPException(413, "Die eigenen Bilder sind zusammen zu "
                                     "groß für eine Sicherungsdatei. Sichert "
                                     "stattdessen den Ordner data/uploads/ "
                                     "als Ganzes.")
        d = _uploads_dir()
        dump["uploads"] = {}
        for f in dateien:
            try:
                with open(os.path.join(d, f["name"]), "rb") as fh:
                    dump["uploads"][f["name"]] = base64.b64encode(
                        fh.read()).decode("ascii")
            except OSError:
                pass                 # eine fehlende Datei kippt nicht alles
    return dump


class RestoreBody(BaseModel):
    app: str = ""
    version: int = 0
    tables: dict
    # Ältere Sicherungen haben das nicht – dann bleibt es eben leer.
    uploads: dict = {}


def _sicherung_pruefen(body: "RestoreBody") -> list:
    """Ist das eine brauchbare Sicherung? Gibt die Benutzer daraus zurück."""
    if body.app != "brickfolio" or body.version != 1             or not isinstance(body.tables, dict)             or "collection" not in body.tables:
        raise HTTPException(400, "Das ist keine gültige Brickfolio-Sicherung")
    users = body.tables.get("users") or []
    if not any(u.get("is_admin") for u in users):
        raise HTTPException(400, "Sicherung enthält keinen Admin-Benutzer – "
                                 "Einspielen abgebrochen")
    return users


def _sicherung_einspielen(body: "RestoreBody") -> dict:
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
    counts["uploads"] = _bilder_zurueckschreiben(body.uploads)
    return counts


def _bilder_zurueckschreiben(uploads: dict) -> int:
    """Eigene Bilder aus der Sicherung wieder als Dateien anlegen.

    Der Name ist zugleich der Verweis aus der Datenbank – er muss also genau
    so wiederkommen. Deshalb wird er streng geprüft: Was nicht wie ein von
    uns vergebener Name aussieht, wird übergangen. Sonst könnte eine
    manipulierte Sicherungsdatei irgendwohin schreiben.
    """
    if not isinstance(uploads, dict) or not uploads:
        return 0
    d = _uploads_dir()
    n = 0
    for name, roh in uploads.items():
        if not isinstance(name, str) or not UPLOAD_NAME.match(name):
            continue
        if not isinstance(roh, str) or len(roh) > UPLOAD_EINZEL_MAX * 4 // 3 + 8:
            continue
        try:
            daten = base64.b64decode(roh, validate=True)
        except Exception:
            continue
        if not daten or len(daten) > UPLOAD_EINZEL_MAX:
            continue
        try:
            with open(os.path.join(d, name), "wb") as f:
                f.write(daten)
            n += 1
        except OSError:
            pass
    return n


@app.post("/api/restore")
def restore_backup(body: RestoreBody, user: dict = Depends(admin_user)):
    _sicherung_pruefen(body)
    return {"ok": True, "restored": _sicherung_einspielen(body)}


@app.post("/api/setup/restore")
def setup_restore(body: RestoreBody):
    """Eine Sicherung einspielen, *bevor* es ein Konto gibt.

    Der übliche Weg (Mehr → Sicherung) verlangt einen Admin – auf einer
    frischen Instanz gibt es aber keinen, und ein eben angelegter würde vom
    Einspielen sofort wieder überschrieben. Wer umzieht, soll deshalb gleich
    hier ankommen können.

    Ohne Anmeldung, aber **nur solange die Instanz leer ist**: Wer sie in
    diesem Zustand erreicht, könnte ohnehin über `/api/setup` das erste
    Admin-Konto anlegen und wäre damit Herr über alles. Dieser Weg gibt also
    nichts preis, was nicht schon offenstünde – und sobald ein Benutzer
    existiert, ist er zu.
    """
    with core.db() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    if count > 0:
        raise HTTPException(409, "Die Einrichtung ist bereits abgeschlossen – "
                                 "eine Sicherung spielt der Admin unter "
                                 "Mehr → Sicherung ein")
    _sicherung_pruefen(body)
    # Bewusst ohne die Benutzernamen aus der Sicherung: Der Anmeldebogen
    # danach ist eine Seite, an der noch niemand angemeldet ist – dort haben
    # fremde Namen nichts zu suchen, auch nicht als Hilfestellung.
    return {"ok": True, "restored": _sicherung_einspielen(body)}


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


# ---------------------------------------------------------------- Lokale KI (Admin)

@app.get("/api/settings/ollama")
def get_ollama(user: dict = Depends(admin_user)):
    """Adresse und Modell im Klartext – anders als bei den API-Schlüsseln.

    Eine Adresse muss man beim Einrichten sehen können, sonst tippt man sie
    bei jeder Korrektur neu. Aus Fehlerberichten wird sie trotzdem entfernt,
    dafür steht sie in `GEHEIME_SETTINGS`.
    """
    return {"url": integrations.ollama_setting("ollama_url"),
            "model": integrations.ollama_setting("ollama_model"),
            "default_model": integrations.OLLAMA_STD_MODELL,
            "bild_model": core.get_setting("ollama_bild_model"),
            "bild_default": integrations.OLLAMA_BILD_STD,
            "enabled": integrations.ollama_enabled()}


class OllamaBody(BaseModel):
    url: str = Field(default="", max_length=200)
    model: str = Field(default="", max_length=100)
    # Getrennt vom Textmodell: Das eine übersetzt Begriffe, das andere sieht
    # sich Bilder an. Gemessen taugen dafür ganz verschiedene – `gemma3:12b`
    # erkennt die Art der Figur in 2 von 3 Proben, `minicpm-v` in keiner.
    bild_model: str = Field(default="", max_length=100)


@app.post("/api/settings/ollama")
def set_ollama(body: OllamaBody, user: dict = Depends(admin_user)):
    url = body.url.strip()
    if url and not re.match(r"^https?://", url):
        raise HTTPException(400, "Die Adresse muss mit http:// oder https:// "
                                 "beginnen")
    core.set_setting("ollama_url", url)
    core.set_setting("ollama_model", body.model.strip())
    core.set_setting("ollama_bild_model", body.bild_model.strip())
    # Der Zwischenspeicher hängt am alten Dienst – nach einem Wechsel wäre
    # sonst nicht nachvollziehbar, warum die neue Adresse nichts ändert.
    integrations._begriff_cache.clear()
    return {"ok": True, "enabled": integrations.ollama_enabled()}


class BegriffBody(BaseModel):
    begriff: str = Field(min_length=1, max_length=60)
    begriffe: str = Field(default="", max_length=300)


BEGRIFFE_SEITE = 25

# ------------------------------------------------------- Katalog-Anbau
#
# Ein lokaler Abzug des BrickLink-Katalogs, damit die Suche nach dem
# Aussehen funktioniert: „Protokolldroide" findet `R-3PO Protocol Droid`,
# ohne dass irgendein Modell die Figur kennen muss.
#
# Gedrosselt, ausdrücklich. Gemessen braucht ein Abruf 0,5 s; mit einer
# Sekunde Abstand dauert Star Wars rund 25 Minuten. Das ist der Punkt: Der
# BrickLink-Zugang ist derselbe, über den die Preise laufen. Ein Durchlauf
# mit Vollgas könnte das Tageskontingent aufbrauchen, und dann steht der
# Scanner ohne Preise da – für eine Bequemlichkeit bei der Suche.
KATALOG_TAKT = 1.0            # Sekunden zwischen zwei Abrufen
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
                  "jw", "sp", "ww", "lor", "iaj", "gen"]

_katalog_lauf = {"aktiv": False, "praefix": "", "nummer": 0, "gefunden": 0,
                 "neu": 0, "stop": False, "fehler": "", "seit": 0,
                 "warteschlange": []}


def _katalog_eintragen(item_no: str, daten: dict) -> bool:
    """Eine Figur in den Index schreiben. Wahr, wenn sie neu war."""
    name = (daten.get("name") or "").strip()
    if not name:
        return False
    jetzt = int(time.time())
    with core.db() as conn:
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
            (item_no, name, _wortanfaenge(name)[0],
             # Fehlt sie in der Antwort, aus der Nummer bilden: Die
             # Adresse folgt ihr, und der Bildserver unterscheidet nicht
             # zwischen Groß- und Kleinschreibung. Ohne den Rückfall bekäme
             # so eine Figur nie ein Bild – und damit auch nie eine Farbe.
             ((daten.get("img_url") or "").strip()
              or "https://img.bricklink.com/ML/%s.jpg" % item_no),
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
                integrations.bricklink_item("minifig",
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
        with core.db() as conn:
            r = conn.execute("SELECT zuletzt FROM katalog_lauf WHERE "
                             "praefix = ?", (praefix,)).fetchone()
        nummer = (r["zuletzt"] if r else 0) + 1
        breite = _katalog_breite(praefix)
        luecke = 0
        while nummer <= KATALOG_MAX and luecke < KATALOG_LUECKE:
            if _katalog_lauf["stop"]:
                break
            item_no = "%s%0*d" % (praefix, breite, nummer)
            _katalog_lauf["nummer"] = nummer
            try:
                daten = integrations.bricklink_item("minifig", item_no)
                if _katalog_eintragen(item_no, daten):
                    _katalog_lauf["neu"] += 1
                _katalog_lauf["gefunden"] += 1
                luecke = 0
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
            with core.db() as conn:
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
            with core.db() as conn:
                conn.execute("UPDATE katalog_lauf SET zuletzt = hoechste, "
                             "fertig_at = ? WHERE praefix = ?",
                             (int(time.time()), praefix))
            print(f"[brickfolio] Katalog-Anbau {praefix}: fertig, "
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

_farb_lauf = {"aktiv": False, "getan": 0, "gefunden": 0, "offen": 0,
              "stop": False, "fehler": ""}


def _katalog_farben(grenze: int = 0):
    _farb_lauf.update({"aktiv": True, "getan": 0, "gefunden": 0,
                       "stop": False, "fehler": ""})
    try:
        while not _farb_lauf["stop"]:
            with core.db() as conn:
                rows = conn.execute(
                    "SELECT item_no, img_url FROM katalog_index "
                    "WHERE farben = '' AND img_url != '' LIMIT 25").fetchall()
                _farb_lauf["offen"] = conn.execute(
                    "SELECT COUNT(*) AS n FROM katalog_index WHERE "
                    "farben = '' AND img_url != ''").fetchone()["n"]
            if not rows:
                break
            for r in rows:
                if _farb_lauf["stop"]:
                    break
                try:
                    roh = integrations.fetch_catalog_image(
                        r["img_url"], integrations.BILD_HOSTS)
                    m = integrations.bild_merkmale(
                        integrations.prepare_image(roh, 512))
                except Exception:
                    m = {"art": "", "farben": []}
                # Auch ein leeres Ergebnis festhalten – sonst versucht der
                # nächste Lauf dieselbe Figur wieder und käme nie ans Ende.
                with core.db() as conn:
                    conn.execute("UPDATE katalog_index SET farben = ?, "
                                 "art = ? WHERE item_no = ?",
                                 (", ".join(m["farben"]) or "–",
                                  m["art"], r["item_no"]))
                _farb_lauf["getan"] += 1
                if m["farben"] or m["art"]:
                    _farb_lauf["gefunden"] += 1
                if grenze and _farb_lauf["getan"] >= grenze:
                    return
                time.sleep(KATALOG_FARB_TAKT)
    finally:
        _farb_lauf["aktiv"] = False


@app.post("/api/katalog/farben")
def katalog_farben_start(user: dict = Depends(admin_user)):
    if not integrations.ollama_enabled():
        raise HTTPException(400, "Keine lokale KI eingerichtet")
    if _farb_lauf["aktiv"]:
        return {"ok": True, "info": "läuft bereits"}
    threading.Thread(target=_katalog_farben, daemon=True).start()
    return {"ok": True}


@app.post("/api/katalog/farben/stop")
def katalog_farben_stop(user: dict = Depends(admin_user)):
    _farb_lauf["stop"] = True
    return {"ok": True}


def _katalog_suchen(begriff: str, hoechstens: int = 20) -> list:
    """Im eigenen Abzug suchen – mit derselben Elle wie die Sammlung.

    Nicht per SQL-LIKE: `_passt` wirft Satzzeichen weg und verlangt alle
    Wörter. „c3 po" findet damit `C-3PO`, und „Knight Hunter" zieht nicht
    jeden Ritter herein. Genau daran hing 2.28.1.
    """
    woerter = _such_woerter(begriff)
    if not woerter:
        return []
    with core.db() as conn:
        # Vorauswahl über das längste Wort, damit nicht der ganze Index
        # durch Python muss: Bei 1.400 Figuren egal, bei allen Themen nicht.
        laengstes = max(woerter, key=len)
        # Farben zählen mit: „R-3PO Protocol Droid" sagt nirgends „rot",
        # das steht nur im Bild. Deshalb greift der Vorfilter auf beides zu.
        rows = conn.execute(
            "SELECT item_no, name, jahr, img_url, farben, art "
            "FROM katalog_index WHERE such LIKE ? OR farben LIKE ? "
            "OR art LIKE ? LIMIT 400",
            ("%" + laengstes + "%",) * 3).fetchall()
    treffer = []
    for r in rows:
        # Name **und** Farben als ein Text: „roter Protokolldroide" braucht
        # beides – die Art aus dem Namen, die Farbe aus dem Bild.
        volltext = " ".join((r["name"] or "", r["farben"] or "",
                             r["art"] or ""))
        if not _passt(begriff, volltext):
            continue
        treffer.append({"item_id": r["item_no"], "item_type": "minifig",
                        "name": r["name"], "img_url": r["img_url"] or "",
                        "sub": str(r["jahr"] or ""), "year": r["jahr"] or 0,
                        "bricklink_url":
                            "https://www.bricklink.com/v2/catalog/"
                            "catalogitem.page?M=" + r["item_no"]})
        if len(treffer) >= hoechstens:
            break
    return treffer


@app.get("/api/katalog/status")
def katalog_status(user: dict = Depends(admin_user)):
    with core.db() as conn:
        anzahl = conn.execute("SELECT COUNT(*) AS n FROM "
                              "katalog_index").fetchone()["n"]
        laeufe = conn.execute("SELECT * FROM katalog_lauf").fetchall()
    return {"anzahl": anzahl,
            "laeuft": _katalog_lauf["aktiv"],
            "praefix": _katalog_lauf["praefix"],
            "nummer": _katalog_lauf["nummer"],
            "neu": _katalog_lauf["neu"],
            "fehler": _katalog_lauf["fehler"],
            "warteschlange": _katalog_lauf["warteschlange"],
            "farben": {"laeuft": _farb_lauf["aktiv"],
                       "getan": _farb_lauf["getan"],
                       "gefunden": _farb_lauf["gefunden"],
                       "offen": _farb_lauf["offen"]},
            "themen": KATALOG_THEMEN,
            "takt": KATALOG_TAKT,
            "laeufe": [{"praefix": r["praefix"], "zuletzt": r["zuletzt"],
                        "gefunden": r["gefunden"],
                        "fertig_at": r["fertig_at"]} for r in laeufe]}


def _katalog_reihe(praefixe: list):
    """Ein Thema nach dem anderen – nicht nebeneinander.

    Parallel liefe schneller und wäre genau falsch: Alle Läufe teilen sich
    denselben BrickLink-Zugang. Zwei gleichzeitig hieße doppelter Takt,
    also die Drosselung ausgehebelt, für die es hier gute Gründe gibt.
    """
    for p in praefixe:
        if _katalog_lauf["stop"]:
            break
        _katalog_lauf["warteschlange"] = [x for x in praefixe
                                          if x != p and praefixe.index(x)
                                          > praefixe.index(p)]
        _katalog_anbau(p)
        # Ein Abbruch aus dem Lauf heraus (429, falscher Zugang) gilt für
        # alle folgenden Themen mit – der Zugang ist derselbe.
        if _katalog_lauf["fehler"]:
            break
    _katalog_lauf["warteschlange"] = []


class KatalogBody(BaseModel):
    themen: str = Field(default="sw", max_length=200)


@app.post("/api/katalog/start")
def katalog_start(body: KatalogBody | None = None,
                  user: dict = Depends(admin_user)):
    if not integrations.bricklink_enabled():
        raise HTTPException(400, "BrickLink ist nicht eingerichtet")
    if _katalog_lauf["aktiv"]:
        return {"ok": True, "info": "läuft bereits"}
    # Nur Buchstaben: Das Präfix wandert in eine Adresse, und „../" oder ein
    # Fragezeichen hätten dort nichts zu suchen.
    themen = (body.themen if body else "") or "sw"
    praefixe = [t.strip().lower() for t in themen.split(",")]
    praefixe = [t for t in praefixe if t and re.fullmatch(r"[a-z]{2,6}", t)]
    if not praefixe:
        raise HTTPException(400, "Kein gültiges Thema angegeben")
    _katalog_lauf["stop"] = False
    _katalog_lauf["fehler"] = ""
    threading.Thread(target=_katalog_reihe, args=(praefixe,),
                     daemon=True).start()
    return {"ok": True, "themen": praefixe}


@app.post("/api/katalog/stop")
def katalog_stop(user: dict = Depends(admin_user)):
    """Jederzeit anhalten – der Fortschritt bleibt stehen.

    Wichtiger als es klingt: Der Lauf teilt sich das BrickLink-Kontingent
    mit den Preisen. Wer merkt, dass es knapp wird, muss ihn stoppen können,
    ohne den Container neu zu starten.
    """
    _katalog_lauf["stop"] = True
    return {"ok": True}


@app.get("/api/settings/begriffe")
def get_begriffe(q: str = "", nur: str = "", limit: int = BEGRIFFE_SEITE,
                 offset: int = 0, user: dict = Depends(admin_user)):
    """Was die Suche gelernt hat – von Hand Gepflegtes zuerst.

    Sichtbar zu machen ist der halbe Zweck: Bis 2.31.0 lag diese Zuordnung
    nur im Arbeitsspeicher, und man konnte nicht nachsehen, warum „roter
    c3po" ausgerechnet C-3PO-Varianten ergab.

    **Seitenweise und durchsuchbar**, nicht am Stück: Die Liste wächst mit
    jedem Suchlauf, und ein geplanter Durchlauf über die BrickLink-Nummern
    brächte Tausende Zeilen auf einen Schlag. Vollständig ausgegeben würde
    sie die Einstellungen unbrauchbar machen – und die Antwort nebenbei
    megabyteweise aufblähen.

    Gesucht wird in beiden Richtungen: „ritter" findet man über den
    deutschen Begriff, „Knight" über das, was dabei herauskommt.
    """
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    wo, werte = [], []
    if q.strip():
        wo.append("(begriff LIKE ? OR begriffe LIKE ?)")
        werte += ["%" + q.strip() + "%"] * 2
    if nur in ("hand", "ki"):
        wo.append("quelle = ?")
        werte.append(nur)
    bedingung = (" WHERE " + " AND ".join(wo)) if wo else ""
    with core.db() as conn:
        gesamt = conn.execute("SELECT COUNT(*) AS n FROM suchbegriffe"
                              + bedingung, werte).fetchone()["n"]
        # Die beiden Zahlen für die Übersicht gelten immer für alles, nicht
        # für die gefilterte Sicht – sonst sagt „12 eigene" plötzlich etwas
        # anderes, nur weil jemand etwas ins Suchfeld getippt hat.
        alle = conn.execute("SELECT COUNT(*) AS n, "
                            "SUM(quelle = 'hand') AS eigene "
                            "FROM suchbegriffe").fetchone()
        rows = conn.execute(
            "SELECT begriff, begriffe, quelle, created_at FROM suchbegriffe"
            + bedingung + " ORDER BY quelle = 'ki', begriff LIMIT ? OFFSET ?",
            werte + [limit, offset]).fetchall()
    return {"begriffe": [{"begriff": r["begriff"],
                          "begriffe": json.loads(r["begriffe"]),
                          "quelle": r["quelle"],
                          "created_at": r["created_at"]} for r in rows],
            "gefunden": gesamt,
            "mehr": offset + len(rows) < gesamt,
            "gesamt": alle["n"] or 0,
            "eigene": alle["eigene"] or 0}


@app.post("/api/settings/begriffe")
def set_begriff(body: BegriffBody, user: dict = Depends(admin_user)):
    """Eine Zeile von Hand eintragen oder korrigieren.

    `quelle = 'hand'`, damit das Modell sie nicht wieder überschreibt – und
    damit sie auch dann gilt, wenn gar keine KI eingerichtet ist.
    """
    liste = [t.strip() for t in body.begriffe.split(",") if t.strip()][:8]
    if not liste:
        raise HTTPException(400, "Mindestens ein Begriff, mit Komma getrennt")
    integrations.begriffe_merken(body.begriff, liste, "hand")
    integrations._begriff_cache.pop(body.begriff.casefold().strip(), None)
    return {"ok": True}


@app.delete("/api/settings/begriffe/{begriff}")
def del_begriff(begriff: str, user: dict = Depends(admin_user)):
    with core.db() as conn:
        conn.execute("DELETE FROM suchbegriffe WHERE begriff = ?",
                     (begriff.casefold().strip(),))
    integrations._begriff_cache.pop(begriff.casefold().strip(), None)
    return {"ok": True}


@app.get("/api/settings/ollama/models")
def ollama_models(url: str = "", user: dict = Depends(admin_user)):
    """Die auf dem Server liegenden Modelle zur Auswahl anbieten.

    Vorher stand hier ein leeres Textfeld, in das man den Namen exakt so
    tippen musste, wie Ollama ihn führt – `qwen2.5:14b`, nicht `qwen2.5-14b`
    und nicht `qwen 2.5`. Ein Tippfehler sah aus wie ein kaputter Dienst:
    Die Verbindung stand, nur das Modell gab es nicht.

    `url` fragt eine noch nicht gespeicherte Adresse ab – sonst müsste man
    erst sichern, um zu sehen, was zur Wahl steht.
    """
    url = (url or "").strip()
    if url and not re.match(r"^https?://", url):
        raise HTTPException(400, "Die Adresse muss mit http:// oder https:// "
                                 "beginnen")
    d = integrations.ollama_modelle(url)
    return {"models": d["models"],
            # Welche sich selbst als bildfähig melden. **Nur zum Sortieren**,
            # nicht zum Ausschließen: `gemma3:12b` meldet es nicht und ist
            # trotzdem das beste im Haus (gemessen 21.08.2026 – Art der Figur
            # in 2 von 3 Proben richtig, wo `minicpm-v` in keiner lag). Wer
            # hart nach dem Merkmal filtert, versteckt den Sieger.
            "vision": d["vision"],
            "current": integrations.ollama_setting("ollama_model"),
            "bild_current": core.get_setting("ollama_bild_model"),
            "default_model": integrations.OLLAMA_STD_MODELL,
            "bild_default": integrations.OLLAMA_BILD_STD}


@app.post("/api/settings/ollama/test")
def test_ollama(user: dict = Depends(admin_user)):
    """Einmal wirklich fragen statt nur die Adresse anzuschauen.

    Geprüft wird mit einem festen deutschen Begriff: Kommt „Knight" zurück,
    stimmen Adresse, Modell und Antwortform.
    """
    if not integrations.ollama_enabled():
        return {"ok": False, "info": "Keine Adresse hinterlegt"}
    integrations._begriff_cache.pop("ritter", None)
    begriffe = integrations.suchbegriffe("Ritter")
    if not begriffe:
        return {"ok": False,
                "info": f"{integrations.ollama_modell()} antwortet nicht "
                        "(Adresse, Modellname oder Dienst prüfen)"}
    return {"ok": True,
            "info": f"Verbunden mit {integrations.ollama_modell()} – "
                    f"„Ritter“ ergibt: {', '.join(begriffe)}"}


def scrub(msg: str, limit: int = 200) -> str:
    """Geheimnisse aus Fehlermeldungen entfernen, bevor sie nach außen gehen.

    Der Bezugspunkt ist `GEHEIME_SETTINGS` – **eine** Liste, nicht mehrere
    verstreute Sonderfälle. Vorher deckte diese Funktion nur die
    API-Schlüssel und den GitHub-Token ab; der Hub-Token, der private
    Hub-Schlüssel und der Push-Schlüssel wären in einer Fehlermeldung
    stehen geblieben – und die kann als Issue öffentlich werden.
    """
    for name in integrations.GEHEIME_SETTINGS:
        wert = core.get_setting(name)
        if not wert and name in integrations.SETTING_ENV:
            wert = integrations.setting(name)
        # Kurze Werte nicht ersetzen: Ein zweistelliges „Geheimnis" käme in
        # jedem zweiten Wort vor und machte die Meldung unlesbar.
        if wert and len(wert) >= 8:
            msg = msg.replace(wert, "***")
    return msg[:limit]


@app.post("/api/settings/test")
def test_settings(user: dict = Depends(admin_user)):
    results = {}
    if integrations.bricklink_enabled():
        try:
            item = integrations.bricklink_item("minifig", "sw0815")
            results["bricklink"] = {"ok": True,
                                    "info": f'Verbunden – Test: {item["name"]}'}
        except Exception as e:
            results["bricklink"] = {"ok": False, "info": scrub(str(e))}
    else:
        missing = integrations.bricklink_missing()
        results["bricklink"] = {
            "ok": False,
            "info": "Keine Schlüssel hinterlegt" if len(missing) == 4
                    else "Es fehlt noch: " + ", ".join(missing)}
    if integrations.rebrickable_enabled():
        try:
            hits = integrations.search_catalog("stormtrooper", "minifig",
                                               page=1, page_size=1)
            results["rebrickable"] = {"ok": True,
                                      "info": f"Verbunden – {hits['count']} "
                                              "Treffer im Test"}
        except Exception as e:
            results["rebrickable"] = {"ok": False, "info": scrub(str(e))}
    else:
        results["rebrickable"] = {"ok": False, "info": "Kein Schlüssel hinterlegt"}
    return results


class SuggestInfoItem(BaseModel):
    item_id: str = Field(min_length=1, max_length=60)
    item_type: str = Field(default="minifig", pattern=ITEM_TYPE_RE)


class SuggestInfoBody(BaseModel):
    # Die Grundangaben (vorhanden? gemerkt? in welchen eigenen Sets?) sind
    # reine SQLite-Abfragen und dürfen für alle sichtbaren Treffer kommen.
    # Die teuren BrickLink-Details bleiben unabhängig davon gedeckelt.
    items: list[SuggestInfoItem] = Field(max_length=60)


FIG_SETS_TTL = 30 * 86400
COLORS_TTL = 90 * 86400
_category_cache: dict = {"at": 0, "map": {}}


def _bl_category_map() -> dict:
    """BrickLink-Kategorien {id: (Name, Eltern-ID)}, wie die Farben gecacht."""
    now = int(time.time())
    if _category_cache["map"] and now - _category_cache["at"] < COLORS_TTL:
        return _category_cache["map"]
    raw = core.get_setting("bl_categories")
    if raw:
        try:
            obj = json.loads(raw)
            if obj.get("map") and now - obj.get("at", 0) < COLORS_TTL:
                _category_cache.update(at=obj["at"], map=obj["map"])
                return _category_cache["map"]
        except ValueError:
            pass
    try:
        cmap = integrations.bricklink_categories()
    except Exception:
        return _category_cache["map"] or {}
    _category_cache.update(at=now, map=cmap)
    core.set_setting("bl_categories", json.dumps({"at": now, "map": cmap}))
    return cmap


def _top_category(cat_id: str) -> str | None:
    """Oberste Kategorie zu einer ID – das ist das Thema (z. B. „Star Wars")."""
    cmap = _bl_category_map()
    seen = set()
    cur = str(cat_id)
    while cur and cur in cmap and cur not in seen:
        seen.add(cur)
        name, parent = cmap[cur]
        if not parent or parent in ("0", "") or parent not in cmap:
            # Auch hier entmaskieren: In einer schon gespeicherten
            # Kategorieliste steckt noch „LEGO Ideas &#40;CUUSOO&#41;".
            return html.unescape(name) if name else None
        cur = parent
    return None


def _theme_aus_figuren(set_no: str) -> str | None:
    """Thema eines Sets aus den Figuren, die drinstecken.

    Der Weg über die BrickLink-Kategorie versagt vereinzelt: Die Kategorie-ID
    eines Sets taucht nicht immer in der Kategorieliste auf, und dann bleibt
    die Kette gleich am ersten Glied stehen. Genau ein Set stand deshalb unter
    „Ohne Thema", während 787 andere richtig einsortiert waren.

    Die Figuren wissen es aber ohnehin: `sw0xxx` heißt Star Wars, ganz ohne
    Abruf. Es zählt, was am häufigsten vorkommt – ein Set mit sechs
    Star-Wars-Figuren und einer Sammelfigur ist Star Wars.
    """
    with core.db() as conn:
        figs = [r["fig_no"] for r in conn.execute(
            "SELECT fig_no FROM set_contents WHERE set_no = ?", (set_no,))]
    if not figs:
        return None
    zaehler: dict = {}
    for f in figs:
        t = themes.from_minifig_number(f)
        if t:
            zaehler[t] = zaehler.get(t, 0) + 1
    if not zaehler:
        return None
    return max(zaehler.items(), key=lambda kv: kv[1])[0]


def _bl_teil(item_id: str) -> tuple:
    """Katalogeintrag eines Teils holen – notfalls über die andere Nummer.

    Die beiden Kataloge zählen Bedruckungen unterschiedlich: Bei Rebrickable
    heißt der Gungan-Schild `2586pr0028`, bei BrickLink `2586ps1`. Wer mit der
    einen Nummer beim anderen anfragt, bekommt nichts – **und zwar für alles**:
    weder Zweitnummer noch Kategorie. Deshalb wird die Nummer **einmal**
    geklärt und danach für beides verwendet.

    Zurück kommt (Nummer, Daten) – Daten ist None, wenn der Katalog nichts
    hergibt.
    """
    if not integrations.bricklink_enabled():
        return item_id, None
    nummern = [item_id]
    if integrations.rebrickable_enabled():
        try:
            bl = integrations.bricklink_nummer_fuer_teil(item_id)
        except Exception:
            bl = ""
        if bl and bl != item_id:
            nummern.append(bl)
    for nr in nummern:
        try:
            return nr, integrations.bricklink_item("part", nr)
        except Exception:
            continue
    return item_id, None


def _thema_aus_zweitnummer(item_id: str, daten: dict | None = None) -> str | None:
    """Thema eines **Teils** über seine Zweitnummer im BrickLink-Katalog.

    Die Kategorie eines Teils sagt nichts über das Thema: BrickLink sortiert
    Teile nach Form („Minifigure, Utensil, Decorated"). Bedruckte Teile tragen
    dort aber oft eine zweite Nummer – die der Figur, zu der sie gehören. Beim
    Karbonitblock steht `sw0978` daneben, und `sw…` heißt Star Wars.

    Nicht jedes Teil hat eine: Der Gungan-Schild `2586ps1` steht dort ohne.
    Dann bleibt die Kategorie – siehe `_theme_nachschlagen`.
    """
    d = daten if daten is not None else _bl_teil(item_id)[1]
    if not d:
        return None
    for stueck in re.split(r"[,;\s]+", d.get("alternate_no") or ""):
        thema = themes.from_minifig_number(stueck.strip())
        if thema:
            return thema
    return None


def _theme_nachschlagen(item_id: str, item_type: str) -> str | None:
    """Thema für Sets und Teile – erst BrickLink, dann die eigenen Daten.

    Der Rückfall über die Figuren steht **außerhalb** der BrickLink-Prüfung:
    Er braucht keinen Abruf, die Set-Inhalte liegen längst hier. Stand er
    innerhalb, blieb ein Set ohne Thema, sobald die Schlüssel fehlten oder
    abgelaufen waren – obwohl die Antwort in der eigenen Datenbank stand.
    """
    if item_id.startswith(("fig-", "manuell-", "custom-")):
        return None
    thema = None
    nummer, daten = (item_id, None)
    if (item_type or "").lower() == "part":
        # Nummer einmal klären, dann für beide Wege benutzen.
        nummer, daten = _bl_teil(item_id)
        # Zuerst die Zweitnummer: Sie nennt ein echtes Thema („Star Wars"),
        # während die Kategorie nur die Form beschreibt („Minifigure, Shield").
        thema = _thema_aus_zweitnummer(nummer, daten)
    if not thema and integrations.bricklink_enabled():
        cid = daten.get("category_id") if daten else None
        if cid is None:
            try:
                cid = integrations.bricklink_category_id(item_type, nummer)
            except Exception:
                cid = None
        thema = _top_category(cid) if cid else None
    if not thema and (item_type or "").lower() == "set":
        thema = _theme_aus_figuren(item_id)
    return thema


# Alter Name, damit Bestandsaufrufe (und Tests) weiter funktionieren.
_theme_from_bricklink = _theme_nachschlagen
_color_cache = {"at": 0, "map": {}}


def _bl_color_map() -> dict:
    """BrickLink-Farben {id: name}, im Speicher und in settings gecacht.
    Bei Problemen (kein Schlüssel, API weg) lieber leer als laut."""
    now = int(time.time())
    if _color_cache["map"] and now - _color_cache["at"] < COLORS_TTL:
        return _color_cache["map"]
    raw = core.get_setting("bl_colors")
    if raw:
        try:
            obj = json.loads(raw)
            if obj.get("map") and now - obj.get("at", 0) < COLORS_TTL:
                _color_cache.update(at=obj["at"], map=obj["map"])
                return _color_cache["map"]
        except ValueError:
            pass
    try:
        cmap = integrations.bricklink_colors()
    except Exception:
        # abgelaufener Cache ist besser als gar keine Namen
        return _color_cache["map"] or (json.loads(raw)["map"] if raw else {})
    _color_cache.update(at=now, map=cmap)
    core.set_setting("bl_colors", json.dumps({"at": now, "map": cmap}))
    return cmap


def _fill_part_colors(parts: list) -> list:
    """Fehlende Farbnamen aus der BrickLink-Farbtabelle ergänzen."""
    if not any(not p.get("color_name") for p in parts):
        return parts
    cmap = _bl_color_map()
    for p in parts:
        if not p.get("color_name"):
            p["color_name"] = cmap.get(str(p.get("color_id")), "")
    return parts


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


@app.get("/api/fig_sets/{fig_no}")
def fig_sets(fig_no: str, user: dict = Depends(current_user)):
    """Alle Sets, in denen diese Figur vorkommt (BrickLink-Supersets) – auch
    solche, die man selbst nicht besitzt. Ohne BrickLink-Nummer oder -Schlüssel
    gibt es nichts zu holen."""
    if fig_no.startswith(("fig-", "manuell-", "custom-")) \
            or not integrations.bricklink_enabled():
        return {"sets": []}
    try:
        return {"sets": _fig_sets_cached(fig_no)}
    except Exception:
        return {"sets": []}


def _fig_parts_cached(fig_no: str) -> list:
    """Teile einer Figur, mit 30-Tage-Cache in der DB (analog fig_sets)."""
    now = int(time.time())
    with core.db() as conn:
        row = conn.execute("SELECT data, fetched_at FROM fig_parts "
                           "WHERE fig_no = ?", (fig_no,)).fetchone()
    if row and now - row["fetched_at"] < FIG_SETS_TTL:
        try:
            return json.loads(row["data"])
        except ValueError:
            pass
    parts = integrations.bricklink_minifig_parts(fig_no)
    with core.db() as conn:
        conn.execute(
            "INSERT INTO fig_parts (fig_no, data, fetched_at) VALUES (?, ?, ?) "
            "ON CONFLICT(fig_no) DO UPDATE SET data = excluded.data, "
            "fetched_at = excluded.fetched_at",
            (fig_no, json.dumps(parts), now))
    return parts


@app.get("/api/fig_parts/{fig_no}")
def fig_parts(fig_no: str, user: dict = Depends(current_user)):
    """Aus welchen Teilen besteht diese Minifigur? (BrickLink-Subsets,
    30-Tage-Cache). Ohne BrickLink-Nummer oder -Schlüssel gibt es nichts."""
    if fig_no.startswith(("fig-", "manuell-", "custom-")) \
            or not integrations.bricklink_enabled():
        return {"items": []}
    try:
        return {"items": _fill_part_colors(_fig_parts_cached(fig_no))}
    except LookupError as e:
        raise HTTPException(404, str(e))
    except requests.Timeout:
        raise HTTPException(504, "BrickLink antwortet nicht")
    except requests.HTTPError as e:
        # Ohne eigenen Zweig fiele auch das in „nicht erreichbar" – ein 404
        # heißt aber nur: zu dieser Figur führt BrickLink keine Teile.
        code = e.response.status_code if e.response is not None else 0
        if code == 404:
            raise HTTPException(404, "BrickLink führt zu dieser Figur keine Teile")
        raise HTTPException(502, f"BrickLink-Fehler ({code})")
    except requests.RequestException:
        raise HTTPException(502, "BrickLink nicht erreichbar")


@app.post("/api/suggest_info")
def suggest_info(body: SuggestInfoBody, detail: int = 0,
                 user: dict = Depends(current_user)):
    """Vorschläge anreichern: schon vorhanden? Jahr? Ø-Preise?"""
    out = {}
    with core.db() as conn:
        for it in body.items:
            row = conn.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS quantity, MAX(year) "
                "AS year, MAX(price_new) AS price_new, MAX(price_used) "
                "AS price_used FROM collection "
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
                    pg = integrations.price_guide(it.item_type, it.item_id,
                                                  cond, use_cache=True)
                    if pg.get("avg"):
                        info[key] = float(pg["avg"])
                except Exception:
                    pass

        todo = [it for it in body.items
                if not it.item_id.startswith(("fig-", "manuell-", "custom-"))
                and not all(k in out[it.item_id] for k in ("year", "new", "used"))
                ][:5]
        if todo:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=5) as pool:
                list(pool.map(enrich, todo))
    return out


# ---------------------------------------------------------------- Scan

# Brickognize stellt seine Erkennung kostenlos bereit – ein einzelner Dienst,
# keine bezahlte Schnittstelle. Ein Foto kostet normalerweise eine Anfrage, mit
# Ausschnitten ein paar mehr. Was hier verhindert wird, ist der Ausreißer: eine
# Schleife, die aus einem Regalfoto vierzig Anfragen im Sekundentakt macht.
# Die Grenze sitzt bewusst **hier** und nicht nur in der Oberfläche – sie gilt
# damit für alle Benutzer der Instanz und auch dann, wenn jemand am Browser
# vorbei anfragt.
SCAN_FENSTER = 60           # Sekunden
SCAN_MAX = 40               # Anfragen je Fenster, über die ganze Instanz
_scan_zeiten: list = []
_scan_sperre = threading.Lock()


def _scan_kontingent() -> None:
    """Eine Anfrage buchen – oder mit 429 abweisen."""
    jetzt = time.time()
    with _scan_sperre:
        while _scan_zeiten and jetzt - _scan_zeiten[0] > SCAN_FENSTER:
            _scan_zeiten.pop(0)
        if len(_scan_zeiten) >= SCAN_MAX:
            # Bewusst ohne eingesetzte Sekundenzahl: Der Satz ist der
            # Übersetzungsschlüssel, und ein eingebauter Zahlenwert fände dort
            # nie seine Entsprechung.
            raise HTTPException(429, "Zu viele Erkennungen in kurzer Zeit. Der "
                                     "Dienst wird kostenlos bereitgestellt – "
                                     "bitte eine Minute warten.")
        _scan_zeiten.append(jetzt)


@app.post("/api/scan")
def scan(file: UploadFile = File(...), user: dict = Depends(current_user)):
    _scan_kontingent()
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


# ------------------------------------------------- Eigene Bilder (Custom)

def _uploads_dir() -> str:
    """Ordner für selbst hochgeladene Bilder – liegt neben der Datenbank,
    landet damit automatisch im Docker-Volume."""
    d = os.path.join(os.path.dirname(core.DB_PATH), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


# --------------------------------------------- Katalogbilder auf der Instanz
#
# Gespeichert war bisher nur die *Adresse* eines Katalogbildes; geholt hat es
# der Browser bei BrickLink, Rebrickable oder Brickognize. Dorthin ging zwar
# nichts aus der Sammlung, aber eben doch bei jedem Blättern ein Abruf – und
# die Adresse nennt die Teilenummer. Wer die Instanz betreibt, damit die Daten
# zu Hause bleiben, erwartet das nicht.
#
# Deshalb holt der Server das Bild einmal, verkleinert es und legt es neben
# der Datenbank ab. Danach fragt der Browser nur noch die eigene Instanz.
# Bewusst eng gehalten: nur Artikel, die wirklich in der Sammlung stehen,
# nur verkleinert, kein Abzug des Katalogs.

BILD_KANTE = 400              # Pixel je Seite – reicht für Karte und Popup


def _katalog_dir() -> str:
    d = os.path.join(os.path.dirname(core.DB_PATH), "catalog")
    os.makedirs(d, exist_ok=True)
    return d


def _katalog_name(url: str) -> str:
    """Dateiname für eine Bildadresse.

    Über `_img_key` fallen die verschiedenen BrickLink-Endpunkte derselben
    Figur zusammen – ein Motiv, eine Datei. Der Schlüssel der Instanz geht in
    den Hash ein: Sonst könnte jemand, der die App im Netz erreicht, aus einer
    Teilenummer den Dateinamen ausrechnen und so erfahren, was hier steht.
    """
    roh = (_img_key(url) + "|" + core.SECRET_KEY).encode()
    return hashlib.sha256(roh).hexdigest() + ".jpg"


def _katalog_bild(url: str, holen: bool = True) -> str | None:
    """Lokaler Pfad zum Bild – bei Bedarf wird es einmal geholt.

    Gibt None zurück, wenn die Adresse nicht erlaubt ist oder der Abruf nicht
    klappt. Fehlschläge werden **nicht** gemerkt: Ein Aussetzer beim CDN soll
    ein Bild nicht dauerhaft verschwinden lassen.
    """
    if not url or not url.startswith(("http://", "https://", "//")):
        return None
    if url.startswith("//"):
        url = "https:" + url
    pfad = os.path.join(_katalog_dir(), _katalog_name(url))
    if os.path.isfile(pfad):
        return pfad
    if not holen:
        return None
    # Einmal nachfassen: Ein einzelner Aussetzer beim CDN – Zeitüberschreitung,
    # kurzer Netzhänger – ließ das Bild sonst als Platzhalter stehen, bis
    # jemand die Seite neu lud. Zwei Versuche kosten wenig und decken den
    # Großteil dieser Fälle ab.
    roh = None
    for versuch in (1, 2):
        try:
            roh = integrations.fetch_catalog_image(url, integrations.BILD_HOSTS)
            break
        except ValueError:
            return None          # Adresse nicht erlaubt – kein zweiter Versuch
        except Exception:
            if versuch == 2:
                return None
            time.sleep(0.6)
    try:
        klein = integrations.prepare_image(roh, max_side=BILD_KANTE)
    except Exception:
        return None
    # Erst vollständig schreiben, dann umbenennen: Ein abgebrochener Abruf
    # hinterlässt sonst eine halbe Datei, die für immer als „fertig" gilt.
    temp = pfad + f".{os.getpid()}.part"
    try:
        with open(temp, "wb") as f:
            f.write(klein)
        os.replace(temp, pfad)
    except OSError:
        return None
    return pfad


def _bild_holen_async(url: str) -> None:
    """Bild für einen neuen Eintrag im Hintergrund holen.

    Es ginge auch ohne: `/catalog` holt beim ersten Anzeigen nach. Aber genau
    dieses erste Anzeigen wäre dann langsam – und beim Scannen kommt es
    unmittelbar. Also gleich beim Erfassen, ohne die Antwort aufzuhalten.
    """
    if not url or not url.startswith(("http://", "https://", "//")):
        return

    def run():
        try:
            _katalog_bild(url)
        except Exception:
            pass          # Bild ist nice-to-have, der Eintrag zählt

    threading.Thread(target=run, daemon=True).start()


# Erlaubte Daumennagel-Größen. Keine freie Zahl: Sonst könnte jemand mit
# 500 Anfragen 500 Dateien erzeugen lassen.
DAUMEN_GROESSEN = (160,)


def _daumennagel(pfad: str, kante: int) -> str | None:
    """Eine kleinere Fassung des Katalogbildes – einmal erzeugt, dann da.

    **Warum das zählt:** Abgelegt wird mit 400 px, angezeigt in den Karten
    mit 72. Der Browser entpackt aber die volle Größe – 400x400 sind gut
    0,6 MB je Bild, und zwar **außerhalb** des JS-Speichers, wo keine
    Messung sie sieht. Bei 130 Karten sind das rund 80 MB, die niemand
    bemerkt. Mit 160 px bleiben davon 13 MB.
    """
    if kante not in DAUMEN_GROESSEN:
        return None
    ziel = f"{pfad}.{kante}.jpg"
    if os.path.isfile(ziel):
        return ziel
    try:
        with open(pfad, "rb") as f:
            klein = integrations.prepare_image(f.read(), max_side=kante)
        temp = ziel + f".{os.getpid()}.part"
        with open(temp, "wb") as f:
            f.write(klein)
        os.replace(temp, ziel)
        return ziel
    except Exception:
        return None


@app.get("/catalog")
def serve_katalogbild(u: str, s: int = 0):
    """Katalogbild ausliefern – aus dem eigenen Speicher.

    Die Oberfläche schickt jedes fremde Bild hierüber. Liegt es schon da, geht
    es sofort raus; sonst holt der Server es einmal, verkleinert es und behält
    es. Danach fragt der Browser nie wieder nach draußen.

    Bewusst ohne Login: Ein `<img>` trägt keinen Token, und wer die App im Netz
    erreicht, ist ohnehin angemeldet. Geholt werden kann nur von den vier
    festen Katalog-Hosts – als Weg nach außen taugt das nicht.
    """
    pfad = _katalog_bild(u)
    if not pfad:
        # Kein Bild – die Oberfläche setzt daraufhin ihren Platzhalter. Kein
        # Verweis auf die Originaladresse: Das wäre genau der Abruf nach
        # außen, den dieser Endpunkt vermeiden soll.
        raise HTTPException(404, "Bild nicht verfügbar")
    if s:
        pfad = _daumennagel(pfad, s) or pfad
    return FileResponse(pfad, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=31536000"})


# Was noch kein Bild auf der Instanz hat. Gezählt wird über alle drei
# Bestände – Sammlung, Wunschliste und Einkaufslisten –, damit der Knopf in
# den Einstellungen dieselbe Zahl nennt, die er danach abarbeitet.
_BILD_QUELLEN = ("collection", "wanted", "shopping_items")


def _bild_urls(conn, nur_offene: bool = True, limit: int | None = None) -> list:
    urls, gesehen = [], set()
    for tabelle in _BILD_QUELLEN:
        for r in conn.execute(
                f"SELECT img_url FROM {tabelle} WHERE img_url IS NOT NULL "
                "AND img_url != ''"):
            u = r["img_url"]
            if not u.startswith(("http://", "https://", "//")):
                continue        # eigene Uploads liegen längst hier
            if u in gesehen:
                continue
            gesehen.add(u)
            if nur_offene and _katalog_bild(u, holen=False):
                continue
            urls.append(u)
            if limit and len(urls) >= limit:
                return urls
    return urls


# Artikel ganz ohne Bildadresse.
#
# Bis 2.18.0 gab es für sie **keinen Weg**. `_bild_urls` sammelt nur, was
# schon eine Adresse hat – „🖼 Bilder jetzt holen" spiegelte also vorhandene
# Bilder auf die Instanz, fand aber keine neuen. Wer per CSV importiert,
# legt genau solche Zeilen an: Der Import schreibt `img_url = ''`, und der
# nächtliche Lauf trägt Jahr und Preis nach, aber kein Bild. Die Artikel
# blieben für immer beim Platzhalter – nur wer jede Karte einzeln aufmachte
# und das ↻ drückte, kam an eins.
#
# Eigenbauten (`custom-`, `manuell-`, `fig-`) bleiben außen vor: Für die hat
# BrickLink nichts, und ein Abruf je Durchgang wäre reine Wartezeit.
_OHNE_BILD = ("(img_url IS NULL OR img_url = '') "
              "AND item_id NOT LIKE 'fig-%' AND item_id NOT LIKE 'manuell-%' "
              "AND item_id NOT LIKE 'custom-%'")


def _ohne_bild(conn, limit: int | None = None) -> list:
    sql = (f"SELECT id, item_type, item_id FROM collection WHERE {_OHNE_BILD}")
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [dict(r) for r in conn.execute(sql)]


def _bildadressen_nachtragen(limit: int) -> int:
    """Fehlende Bildadressen im Katalog nachschlagen und eintragen."""
    if not integrations.bricklink_enabled():
        return 0
    with core.db() as conn:
        offen = _ohne_bild(conn, limit)
    getroffen = 0
    for r in offen:
        try:
            d = integrations.bricklink_item(r["item_type"], r["item_id"])
        except Exception:
            continue                 # unbekannte Nummer, Dienst weg: später
        if not d.get("img_url"):
            continue
        with core.db() as conn:
            conn.execute("UPDATE collection SET img_url = ? WHERE id = ?",
                         (d["img_url"], r["id"]))
        getroffen += 1
    return getroffen


@app.get("/api/images/status")
def bilder_status(user: dict = Depends(current_user)):
    """Wie viele Bilder liegen noch nicht auf der Instanz?"""
    with core.db() as conn:
        offen = len(_bild_urls(conn)) + len(_ohne_bild(conn))
        gesamt = len(_bild_urls(conn, nur_offene=False)) + len(_ohne_bild(conn))
    return {"pending": offen, "total": gesamt}


@app.post("/api/images/fetch")
def bilder_holen(limit: int = 25, user: dict = Depends(admin_user)):
    """Fehlende Katalogbilder holen – in Häppchen, wie beim Umrechnen.

    Jedes Bild ist ein Abruf beim CDN; bei einer großen Sammlung wäre alles
    auf einmal unhöflich und würde die Antwort ewig blockieren. Die Antwort
    sagt, wie viele noch offen sind, und die Oberfläche ruft nach.
    """
    limit = max(1, min(limit, 100))
    # Erst die Adressen klären, die gar keine haben – sonst hätte der Lauf
    # für einen CSV-Import nichts zu tun und meldete „fertig", während jede
    # Karte weiter den Platzhalter zeigt.
    nachgetragen = _bildadressen_nachtragen(limit)
    with core.db() as conn:
        urls = _bild_urls(conn, limit=limit)
    geholt = sum(1 for u in urls if _katalog_bild(u))
    with core.db() as conn:
        offen = len(_bild_urls(conn)) + len(_ohne_bild(conn))
    return {"ok": True, "fetched": geholt, "tried": len(urls),
            "resolved": nachgetragen, "remaining": offen}


@app.get("/api/themes/status")
def themes_status(user: dict = Depends(current_user)):
    """Wie viele Einträge haben noch kein Thema?"""
    with core.db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM collection WHERE (theme IS NULL OR "
            "theme = '') AND item_id NOT LIKE 'fig-%' "
            "AND item_id NOT LIKE 'manuell-%' "
            "AND item_id NOT LIKE 'custom-%'").fetchone()
    return {"pending": row["c"], "can_fetch": integrations.bricklink_enabled()}


@app.post("/api/themes/refresh")
def refresh_themes(limit: int = 25, user: dict = Depends(current_user)):
    """Fehlende Themen bestimmen: Minifiguren aus der Nummer (ohne Abruf),
    Sets und Teile über die BrickLink-Kategorie. Läuft in Häppchen, damit die
    App Rückmeldung geben kann."""
    limit = max(1, min(limit, 100))
    with core.db() as conn:
        rows = conn.execute(
            "SELECT id, item_id, item_type FROM collection "
            "WHERE (theme IS NULL OR theme = '') "
            "AND item_id NOT LIKE 'fig-%' AND item_id NOT LIKE 'manuell-%' "
            "AND item_id NOT LIKE 'custom-%' ORDER BY id").fetchall()
    done = 0
    offen: list = []
    for r in rows[:limit]:
        theme = themes.for_item(r["item_id"], r["item_type"])
        if not theme:
            theme = _theme_nachschlagen(r["item_id"], r["item_type"])
        if not theme:
            # Merken statt still übergehen: Sonst steht dort für immer „1
            # Eintrag offen", ohne dass jemand erfährt, welcher.
            offen.append(r["item_id"])
            continue
        with core.db() as conn:
            conn.execute("UPDATE collection SET theme = ? WHERE id = ?",
                         (theme, r["id"]))
        done += 1
    with core.db() as conn:
        left = conn.execute(
            "SELECT COUNT(*) AS c FROM collection WHERE (theme IS NULL OR "
            "theme = '') AND item_id NOT LIKE 'fig-%' "
            "AND item_id NOT LIKE 'manuell-%' "
            "AND item_id NOT LIKE 'custom-%'").fetchone()["c"]
    return {"ok": True, "updated": done, "remaining": left,
            "unresolved": offen[:20]}


# Erlaubte Sortierungen der Sammlung (Reihenfolge wie in der Oberfläche)
COLLECTION_SORTS = ("added", "year_desc", "year_asc", "name", "number",
                    "value_desc", "value_asc", "theme")


class SortPrefBody(BaseModel):
    sort: str = Field(min_length=1, max_length=20)


@app.post("/api/me/sort")
def set_sort_pref(body: SortPrefBody, user: dict = Depends(current_user)):
    """Bevorzugte Sortierung der Sammlung – je Benutzer gespeichert."""
    if body.sort not in COLLECTION_SORTS:
        raise HTTPException(400, "Unbekannte Sortierung")
    with core.db() as conn:
        conn.execute("UPDATE users SET sort_pref = ? WHERE id = ?",
                     (body.sort, user["id"]))
    return {"ok": True, "sort": body.sort}


@app.get("/api/next_custom_id")
def next_custom_id(user: dict = Depends(current_user)):
    """Nächste freie Nummer für eine eigene Figur, z. B. custom-003.

    Schaut in Sammlung, Wunschliste und Einkaufslisten nach der höchsten
    bereits vergebenen Zahl – so bleiben Nummern auch dann eindeutig, wenn
    ein Eintrag wieder gelöscht wurde.
    """
    highest = 0
    with core.db() as conn:
        for table in ("collection", "wanted", "shopping_items"):
            for r in conn.execute(
                    f"SELECT item_id FROM {table} "
                    "WHERE item_id LIKE 'custom-%'"):
                m = re.fullmatch(r"custom-0*(\d+)", r["item_id"])
                if m:
                    highest = max(highest, int(m.group(1)))
    return {"item_id": f"custom-{highest + 1:03d}",
            "number": f"{highest + 1:03d}"}


@app.post("/api/upload_image")
def upload_image(file: UploadFile = File(...),
                 user: dict = Depends(current_user)):
    """Eigenes Bild für eine Custom-Figur speichern.

    Wird verkleinert und als JPEG abgelegt – das begrenzt den Platzbedarf und
    entfernt nebenbei EXIF-Daten (z. B. GPS aus Handyfotos).
    """
    raw = file.file.read()
    if not raw:
        raise HTTPException(400, "Kein Bild empfangen")
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "Bild zu groß (max. 25 MB)")
    try:
        data = integrations.prepare_image(raw, max_side=800)
    except Exception:
        raise HTTPException(400, "Datei ist kein lesbares Bild")
    name = f"{uuid.uuid4().hex}.jpg"
    with open(os.path.join(_uploads_dir(), name), "wb") as f:
        f.write(data)
    return {"url": f"/uploads/{name}"}


class ItemPhotoBody(BaseModel):
    item_type: str = Field(min_length=1, max_length=20)
    item_id: str = Field(min_length=1, max_length=60)
    url: str = Field(min_length=10, max_length=200)


@app.post("/api/item_photos")
def add_item_photo(body: ItemPhotoBody, user: dict = Depends(current_user)):
    """Ein eigenes Foto an einen Artikel hängen – neben das Katalogbild.

    Angenommen wird nur, was diese Instanz selbst abgelegt hat: Sonst könnte
    hier jede beliebige fremde Adresse landen, und die Galerie holte beim
    Anschauen unbemerkt etwas von außen.
    """
    name = body.url.rsplit("/", 1)[-1]
    if not body.url.startswith("/uploads/") or not UPLOAD_NAME.match(name):
        raise HTTPException(400, "Nur eigene Bilder dieser Instanz")
    if not os.path.isfile(os.path.join(_uploads_dir(), name)):
        raise HTTPException(404, "Bild nicht gefunden")
    with core.db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO item_photos (item_type, item_id, url,"
            " added_by, added_at) VALUES (?, ?, ?, ?, ?)",
            (body.item_type, body.item_id, body.url, user["id"],
             int(time.time())))
        row = conn.execute(
            "SELECT id FROM item_photos WHERE item_type = ? AND item_id = ?"
            " AND url = ?", (body.item_type, body.item_id, body.url)).fetchone()
    return {"ok": True, "id": row["id"] if row else None}


@app.delete("/api/item_photos/{photo_id}")
def delete_item_photo(photo_id: int, user: dict = Depends(current_user)):
    """Foto vom Artikel lösen.

    Die Datei bleibt, solange **irgendein** Artikel noch auf sie zeigt – eine
    Aufnahme kann an mehreren hängen, und einem anderen Artikel das Bild
    wegzureißen wäre schlimmer als eine verwaiste Datei. Zeigt niemand mehr
    darauf, ist sie durch nichts mehr erreichbar und kann weg.
    """
    with core.db() as conn:
        row = conn.execute("SELECT url FROM item_photos WHERE id = ?",
                           (photo_id,)).fetchone()
        cur = conn.execute("DELETE FROM item_photos WHERE id = ?", (photo_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Foto nicht gefunden")
    return {"ok": True, "file_removed": _datei_wegwerfen(row["url"])}


_BILD_DA_CACHE: dict = {}
BILD_DA_TTL_JA = 24 * 3600      # gibt es das Bild, ändert sich das kaum
BILD_DA_TTL_NEIN = 10 * 60      # ein Aussetzer beim CDN soll nichts festnageln


def _bild_fehlt_sicher(url: str) -> bool:
    """Sagt der Server ausdrücklich, dass es dieses Bild **nicht** gibt?

    Die ItemImage-Adresse wird aus Typ und Nummer zusammengebaut – das ist
    eine Vermutung, keine Auskunft. Stimmt sie nicht (andere Bildkennung,
    Artikel ohne Katalogbild), stand ein toter Verweis in der Galerie: ein
    leerer Rahmen zum Durchblättern, den niemand erklären konnte.

    Gefragt wird deshalb nach – aber die Beweislast liegt beim Weglassen.
    Nur ein klares „gibt es nicht" (404/410) wirft die Adresse raus. Eine
    Zeitüberschreitung, ein abgelehnter HEAD oder gar kein Netz heißen
    *unbekannt*, und dann bleibt die Vermutung stehen: Ein Bild, das
    vielleicht lädt, ist besser als eine leere Galerie, nur weil das CDN
    gerade hustet.

    Geprüft wird nur, was nicht ohnehin schon im Katalog liegt. Das Ergebnis
    wird gemerkt, sonst fragt jede geöffnete Galerie erneut nach – ein „gibt
    es nicht" allerdings deutlich kürzer als ein „gibt es".
    """
    if not url:
        return False
    try:
        if os.path.isfile(os.path.join(_katalog_dir(), _katalog_name(url))):
            return False                  # liegt hier, also gibt es das
    except Exception:
        pass
    jetzt = time.time()
    merk = _BILD_DA_CACHE.get(url)
    if merk and jetzt - merk[0] < (BILD_DA_TTL_NEIN if merk[1]
                                   else BILD_DA_TTL_JA):
        return merk[1]
    fehlt = False
    try:
        antwort = requests.head(url, timeout=4, allow_redirects=True)
        # Nicht jeder Server mag HEAD. Wer es ablehnt, wird gefragt, ob er
        # den Anfang der Datei herausrückt – gelesen wird davon nichts.
        if antwort.status_code in (405, 501):
            antwort = requests.get(url, timeout=4, stream=True)
            antwort.close()
        fehlt = antwort.status_code in (404, 410)
    except requests.RequestException:
        return False                      # unbekannt – nicht merken, nicht werfen
    _BILD_DA_CACHE[url] = (jetzt, fehlt)
    return fehlt


def _datei_wegwerfen(url: str) -> bool:
    """Löscht die hochgeladene Datei hinter `url` – aber nur, wenn kein
    Artikel mehr auf sie zeigt. Dieselbe Aufnahme kann an mehreren Artikeln
    hängen; wer das übersieht, reißt einem anderen Artikel das Bild weg."""
    if not url or "/uploads/" not in url:
        return False                      # kein eigenes Foto, nichts zu tun
    with core.db() as conn:
        noch_da = conn.execute(
            "SELECT 1 FROM item_photos WHERE url = ? LIMIT 1", (url,)).fetchone()
    if noch_da:
        return False
    name = url.rsplit("/", 1)[-1]
    if not re.fullmatch(r"[0-9a-f]{32}\.jpg", name):
        return False                      # nichts löschen, was wir nicht kennen
    try:
        os.remove(os.path.join(_uploads_dir(), name))
        return True
    except OSError:
        return False


def _fotos_aufraeumen(item_type: str, item_id: str) -> int:
    """Fotos eines Artikels wegräumen, **wenn** ihn niemand mehr führt.

    Aus dem Betrieb: Wer einen Artikel aus der Sammlung löschte, ließ seine
    Fotos liegen – die Zeilen in `item_photos` **und** die Dateien. Sichtbar
    war das nirgends, erreichbar auch nicht: Ohne Artikel gibt es keine
    Galerie, in der sie auftauchen könnten. Nur der Platz auf der Platte
    wuchs weiter.

    Gelöscht wird trotzdem erst, wenn der Artikel **überall** weg ist. Das
    Foto hängt am Artikel, nicht an der Zeile (Handbuch 5.6): Dieselbe Figur
    kann ein zweites Mal in der Sammlung stehen – in anderem Zustand –, auf
    der Wunschliste liegen oder auf einer Einkaufsliste warten. In all diesen
    Fällen will man das Foto behalten.
    """
    with core.db() as conn:
        for tabelle in ("collection", "wanted", "shopping_items"):
            if conn.execute(
                    f"SELECT 1 FROM {tabelle} WHERE item_id = ? "
                    "AND item_type = ? LIMIT 1",
                    (item_id, item_type)).fetchone():
                return 0                  # es gibt ihn noch woanders
        urls = [r["url"] for r in conn.execute(
            "SELECT url FROM item_photos WHERE item_type = ? AND item_id = ?",
            (item_type, item_id))]
        if not urls:
            return 0
        conn.execute("DELETE FROM item_photos WHERE item_type = ? "
                     "AND item_id = ?", (item_type, item_id))
    # Erst nach dem Löschen der Zeilen fragen, ob die Datei noch gebraucht
    # wird – sonst zählt man sich selbst mit.
    for u in urls:
        _datei_wegwerfen(u)
    return len(urls)


def _eigene_fotos(item_type: str, item_id: str) -> list:
    with core.db() as conn:
        rows = conn.execute(
            "SELECT id, url FROM item_photos WHERE item_type = ? AND"
            " item_id = ? ORDER BY added_at, id", (item_type, item_id)
        ).fetchall()
    return [{"id": r["id"], "url": r["url"]} for r in rows]


@app.get("/uploads/{name}")
def serve_upload(name: str):
    """Hochgeladenes Bild ausliefern. Bewusst ohne Login, damit die Bilder
    wie andere Katalogbilder eingebettet werden können – der Dateiname ist
    zufällig und nicht erratbar."""
    if not re.fullmatch(r"[0-9a-f]{32}\.jpg", name):
        raise HTTPException(404, "Nicht gefunden")
    path = os.path.join(_uploads_dir(), name)
    if not os.path.isfile(path):
        raise HTTPException(404, "Nicht gefunden")
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=31536000"})


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

_BL_IMG_RE = re.compile(
    r"^img\.bricklink\.com/.*/([^/]+?)(?:\.t\d+)?\.(?:png|jpe?g|gif)$")


def _img_key(u: str) -> str:
    """Vergleichsschlüssel für Bilder. BrickLink liefert dieselbe Figur unter
    mehreren Endpunkten – alle bekommen über die Artikelnummer denselben
    Schlüssel, damit nur eins übrig bleibt. Andere Quellen: Protokoll weg."""
    k = re.sub(r"^https?://", "", u.strip().lower())
    k = re.sub(r"^//", "", k)
    m = _BL_IMG_RE.match(k)
    return "bl:" + m.group(1) if m else k


@app.get("/api/images/{item_type}/{item_no}")
def item_images(item_type: str, item_no: str,
                user: dict = Depends(current_user)):
    """Katalogbilder einer Figur (BrickLink + Rebrickable) – ohne Dubletten.

    Dieselbe Figur liefert BrickLink über verschiedene Endpunkte/Auflösungen
    (ItemImage, ML, das API-`image_url`) – alles dasselbe Motiv. Solche werden
    über die Artikelnummer zusammengefasst; übrig bleibt ein Bild pro Quelle,
    mehrere nur, wenn sie sich wirklich unterscheiden.
    """
    urls: list[str] = []
    seen: set[str] = set()

    def add(u):
        if not u:
            return
        u = u.strip()
        if u.startswith("//"):
            u = "https:" + u
        key = _img_key(u)
        if key in seen:
            return
        seen.add(key)
        urls.append(u)

    if item_no.startswith("fig-"):
        if integrations.rebrickable_enabled():
            try:
                add(integrations.rebrickable_minifig_image(item_no))
            except Exception:
                pass
    elif not item_no.startswith(("manuell-", "custom-")):
        # Bevorzugt das Bild aus der BrickLink-API (meist bessere Auflösung),
        # das konstruierte ItemImage als Rückfall – gleiche Nummer, gleiches
        # Motiv, wird zusammengefasst.
        if integrations.bricklink_enabled():
            try:
                add(integrations.bricklink_item(item_type, item_no).get("img_url"))
            except Exception:
                pass
        code = _BL_IMG_CODE.get(item_type.lower())
        if code:
            safe = requests.utils.quote(item_no)
            geraten = f"https://img.bricklink.com/ItemImage/{code}/0/{safe}.png"
            # Die Adresse ist geraten – raus fliegt sie nur, wenn der Server
            # ausdrücklich sagt, dass es das Bild nicht gibt. Steht ohnehin
            # schon eine aus der API in der Liste, fasst `add` beide zusammen
            # und der Abruf ist gespart.
            if _img_key(geraten) in seen or not _bild_fehlt_sicher(geraten):
                add(geraten)
    # Eigene Fotos ans Ende, nicht an den Anfang: Das Katalogbild zeigt die
    # Figur sauber freigestellt und bleibt das erste, was man sieht. Getrennt
    # ausgewiesen, damit die Galerie sie kennzeichnen und löschen lassen kann.
    eigene = _eigene_fotos(item_type, item_no)
    for f in eigene:
        if f["url"] not in urls:
            urls.append(f["url"])
    return {"images": urls, "own": eigene}


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
        "number": "c.item_id COLLATE NOCASE ASC, c.name COLLATE NOCASE",
        "value_desc": f"{_value_known}, {_unit_value} DESC, c.name COLLATE NOCASE",
        "value_asc": f"{_value_known}, {_unit_value} ASC, c.name COLLATE NOCASE",
        # Ohne erkanntes Thema ans Ende, innerhalb des Themas nach Name
        "theme": ("CASE WHEN c.theme IS NULL OR c.theme = '' THEN 1 ELSE 0 END, "
                  "c.theme COLLATE NOCASE ASC, c.name COLLATE NOCASE ASC"),
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
        # Einmal ermitteln, zweimal gebraucht: für die Kopfsumme und für den
        # Wert je Eintrag. Beim Typfilter braucht es die Aufstellung nicht.
        bound = _set_bound_map(conn) if not item_type else {}
        stats = conn.execute(
            "SELECT COUNT(*) AS unique_items, "
            "COALESCE(SUM(quantity),0) AS total, "
            f"COALESCE(SUM(quantity * {value_expr}), 0) AS total_value, "
            f"COALESCE(SUM(CASE WHEN {value_expr} IS NULL THEN 1 ELSE 0 END), 0) "
            f"AS unpriced FROM collection{stats_where}", stats_params
        ).fetchone()
        stats = dict(stats)
        stats["in_sets_value"] = 0.0
        # Nur in der Gesamtansicht (Sets UND Figuren) doppelt gezählte
        # Set-Figuren herausrechnen – beim Filter "Figuren" bleibt der
        # volle Figurenwert stehen.
        if not item_type:
            if bound:
                dedup = 0.0
                for r in conn.execute(
                        "SELECT id, condition, price_new, price_used "
                        "FROM collection WHERE item_type = 'minifig'"):
                    n = bound.get(r["id"], 0)
                    if not n:
                        continue
                    unit = _unit_price(r["condition"], r["price_new"],
                                       r["price_used"])
                    dedup += (unit or 0) * n
                stats["in_sets_value"] = round(dedup, 2)
                stats["total_value"] = round(
                    max(0.0, (stats["total_value"] or 0) - dedup), 2)

        # Wert je Eintrag mitliefern – nach derselben Regel wie die Kopfsumme.
        # Sonst rechnet die Oberfläche (z. B. die Themenkarten) anders als der
        # Kopf, und die Summen passen nicht zusammen.
        items = []
        for r in rows:
            d = dict(r)
            unit = _unit_price(d["condition"], d["price_new"], d["price_used"])
            in_sets = bound.get(d["id"], 0) if d["item_type"] == "minifig" else 0
            d["unit_price"] = unit
            d["bound_qty"] = in_sets
            d["value"] = round((unit or 0) * d["quantity"], 2) if unit else None
            d["net_value"] = (round((unit or 0)
                                    * max(0, d["quantity"] - in_sets), 2)
                              if unit else None)
            items.append(d)
    return {"items": items, "stats": stats}


# Wie viele Zeilen ein Vorschlag höchstens zurückgibt. „Ritter" kann über die
# Oberbegriffe halbe Themen einsammeln – die Liste soll eine Hilfe bleiben und
# nicht die eigentliche Suche verdrängen.
SUGGEST_MAX = 200


def _such_norm(text: str) -> str:
    """Alles außer Buchstaben und Ziffern weg, klein geschrieben.

    BrickLink schreibt `C-3PO` und `R2-D2` mit Bindestrichen, getippt wird
    „c3 po" oder „r2d2". Ein einfaches LIKE fand deshalb nichts – und das
    ausgerechnet bei den bekanntesten Figuren überhaupt.
    """
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _such_woerter(text: str) -> list:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) >= 2]


def _wortanfaenge(name: str) -> tuple:
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


def _passt(begriff: str, name: str) -> bool:
    """Trifft ein vorgeschlagener Begriff diesen Artikelnamen?

    Zwei Wege, und der zweite ist nicht bloß Feinschliff: Das Modell liefert
    je nach Anfrage „C-3PO red" (dann greift der erste) oder „Blue-Ninja",
    während der Artikel „Ninja - Blue" heißt (dann greift der zweite).
    Mehrere Wörter müssen **alle** vorkommen – sonst zöge „Knight Hunter"
    jeden Ritter herein, obwohl es den Begriff so nicht gibt.
    """
    ganz_name, anfaenge = _wortanfaenge(name)
    if not ganz_name:
        return False

    def steht_da(teil: str) -> bool:
        """Kommt der Teil vor – und beginnt dort auch ein Wort?"""
        stelle = ganz_name.find(teil)
        while stelle != -1:
            if stelle in anfaenge:
                return True
            stelle = ganz_name.find(teil, stelle + 1)
        return False

    ganz = _such_norm(begriff)
    if ganz and steht_da(ganz):
        return True
    woerter = _such_woerter(begriff)
    return len(woerter) >= 2 and all(steht_da(w) for w in woerter)


@app.get("/api/collection/suggest")
def suggest_collection(q: str = "", item_type: str = "",
                       user: dict = Depends(current_user)):
    """Zweiter Versuch für eine Suche, die nichts gefunden hat.

    Die Namen in der Sammlung kommen von BrickLink und sind englisch; die
    Oberfläche ist deutsch. Wer „Ritter" sucht, bekam bisher nichts, obwohl
    die Figuren als „Knight" in der Datenbank liegen. Die lokale KI übersetzt
    nur den **Suchbegriff** – gefunden wird weiterhin ausschließlich in der
    eigenen Datenbank, und gemeldet werden nur Begriffe, die wirklich etwas
    getroffen haben.

    Ohne eingerichtete KI ist die Antwort leer; die Oberfläche zeigt dann
    denselben Hinweis wie vorher.
    """
    if not q.strip() or not integrations.ollama_enabled():
        return {"begriffe": [], "items": []}
    begriffe = integrations.suchbegriffe(q)
    if not begriffe:
        return {"begriffe": [], "items": []}
    # Einmal alles holen und in Python vergleichen: Der Vergleich ignoriert
    # Satzzeichen, das bekäme SQL nur mit verschachtelten replace() hin – und
    # der Zweig läuft ohnehin nur, wenn die gewöhnliche Suche nichts fand.
    alle = get_collection(q="", sort="name", item_type=item_type,
                          user=user)["items"]
    gesehen: set = set()
    items: list = []
    treffer: list = []
    # Der genaueste Begriff zuerst, nicht der vom Modell zuerst genannte.
    # „roter c3 po" ergibt `C-3PO` und `C-3PO (red)`; in Modellreihenfolge
    # sammelte der breite Begriff alle C-3POs ein, und die Farbvariante kam
    # auf null neue Treffer – die Eingrenzung verpuffte.
    #
    # **Nur** nach Wortzahl, ausdrücklich nicht nach Länge: „Ritter" ergibt
    # `Knight, Minifigure, Hero, Character`, und mit der Länge als zweitem
    # Maß lief `Minifigure` vor `Knight`. In einer echten Sammlung stand
    # daraufhin Greedo unter den Rittern. Innerhalb gleicher Wortzahl bleibt
    # deshalb die Reihenfolge des Modells stehen – es nennt den Eigennamen
    # zuerst und die Oberbegriffe zuletzt.
    begriffe.sort(key=lambda b: len(_such_woerter(b)), reverse=True)
    for begriff in begriffe:
        neu = 0
        for eintrag in alle:
            if eintrag["id"] in gesehen:
                continue
            if not _passt(begriff, eintrag["name"] or ""):
                continue
            gesehen.add(eintrag["id"])
            items.append(eintrag)
            neu += 1
        if neu:
            treffer.append(begriff)
        if len(items) >= SUGGEST_MAX:
            break
    return {"begriffe": treffer, "items": items[:SUGGEST_MAX]}


# Wie viele übersetzte Begriffe im Katalog wirklich versucht werden.
#
# In der Sammlung ist ein Begriff mehr fast gratis – die Einträge liegen
# schon im Speicher. Hier geht jeder Versuch als eigene Anfrage zu
# Rebrickable: mehr Wartezeit für den Tippenden und mehr Last auf einem
# fremden Kontingent. Zwei decken den Fall ab, für den das hier gebaut wurde
# („roter c3 po" → `C-3PO`, dann `C-3PO red`), ohne aus einer Suche fünf zu
# machen.
KATALOG_KI_VERSUCHE = 2


@app.get("/api/search/suggest")
def suggest_catalog(q: str = "", item_type: str = "minifig",
                    user: dict = Depends(current_user)):
    """Zweiter Versuch für eine Katalogsuche, die nichts gefunden hat.

    Das Gegenstück zu `/api/collection/suggest`, und aus demselben Grund:
    Rebrickable kennt nur englische Namen. Wer beim manuellen Erfassen
    „Roter c3po" eintippt, bekam eine leere Liste – dabei ist genau das der
    Ort, an dem eine Übersetzung am meisten hilft. In der Sammlung sucht man
    etwas, das man schon hat und notfalls durchblättern kann; im Katalog
    sucht man etwas Unbekanntes, und ohne Treffer hat man gar nichts.

    Gemeldet wird nur der Begriff, der wirklich etwas gefunden hat – ein vom
    Modell erfundener bleibt unsichtbar, weil er im Katalog nichts trifft.
    """
    if not q.strip() or not integrations.ollama_enabled():
        return {"begriffe": [], "items": []}
    if not integrations.rebrickable_enabled():
        return {"begriffe": [], "items": []}
    begriffe = integrations.suchbegriffe(q)
    if not begriffe:
        return {"begriffe": [], "items": []}
    # Dieselbe Sortierung wie in der Sammlung: der genaueste Begriff zuerst,
    # nach Wortzahl und ausdrücklich nicht nach Länge. Sonst liefe wieder
    # `Minifigure` vor `Knight`.
    begriffe.sort(key=lambda b: len(_such_woerter(b)), reverse=True)
    gesehen: set = set()
    items: list = []
    treffer: list = []
    # **Zuerst der eigene Index.** Er kostet nichts, kennt die beschreibenden
    # BrickLink-Namen und findet damit, was Rebrickable nicht hergibt:
    # `R-3PO` heißt dort nur so, bei BrickLink „R-3PO Protocol Droid".
    for begriff in begriffe:
        for eintrag in _katalog_suchen(begriff):
            kennung = (eintrag["item_id"], eintrag["item_type"])
            if kennung in gesehen:
                continue
            gesehen.add(kennung)
            items.append(eintrag)
            if begriff not in treffer:
                treffer.append(begriff)
        if len(items) >= SUGGEST_MAX:
            break
    # Hat der eigene Abzug etwas, ist Rebrickable nicht mehr nötig: Die
    # Antwort ist da, kostenlos und mit den beschreibenden Namen. Jede
    # weitere Anfrage wäre nur Wartezeit für den Tippenden und Last auf
    # einem fremden Kontingent.
    if items:
        return {"begriffe": treffer, "items": items[:SUGGEST_MAX]}
    for begriff in begriffe[:KATALOG_KI_VERSUCHE]:
        try:
            gefunden = integrations.search_catalog(begriff, item_type, page=1)
        except (requests.RequestException, ValueError):
            # Ein Fehlschlag beim Zusatzversuch darf die Suche nicht mit
            # einem Fehler beenden – ohne KI stand hier vorher schlicht eine
            # leere Liste, und dabei soll es bleiben.
            continue
        neu = 0
        for eintrag in gefunden.get("items", []):
            kennung = (eintrag.get("item_id"), eintrag.get("item_type"))
            if kennung in gesehen:
                continue
            gesehen.add(kennung)
            items.append(eintrag)
            neu += 1
        if neu:
            treffer.append(begriff)
        if len(items) >= SUGGEST_MAX:
            break
    return {"begriffe": treffer, "items": items[:SUGGEST_MAX]}


@app.post("/api/collection")
def add_item(body: AddItemBody, user: dict = Depends(current_user)):
    # Vor allem anderen: Nummer und Name auf den Katalogstand bringen. Damit
    # landet eine von Hand getippte `21306` in derselben Zeile wie die
    # gescannte `21306-1`, statt daneben.
    body.item_id, body.name = _bricklink_nummer(
        body.item_id, body.item_type, body.name)
    with core.db() as conn:
        row = conn.execute(
            "SELECT id, quantity, paid_price, condition, price_new, "
            "price_used FROM collection WHERE item_id = ? AND item_type = ? "
            "AND condition = ?",
            (body.item_id, body.item_type, body.condition),
        ).fetchone()
        if row:
            conn.execute("UPDATE collection SET quantity = quantity + ? WHERE id = ?",
                         (body.quantity, row["id"]))
            if body.paid_price is not None:
                # Ein angegebener Preis gehört als eigener Posten ins Buch –
                # genau der Fall „dasselbe Set, anderswo, anderer Preis".
                _kauf_buchen(conn, row["id"], body.quantity, body.paid_price,
                             body.paid_source or "")
            elif row["paid_price"] is not None and body.paid_source != "set":
                unit = _unit_price(row["condition"], row["price_new"],
                                   row["price_used"])
                if unit:
                    _kauf_buchen(conn, row["id"], body.quantity,
                                 round(unit * body.quantity, 2), "geschätzt")
            return {"ok": True, "merged": True,
                    "quantity": row["quantity"] + body.quantity}
        try:
            cur = conn.execute(
                "INSERT INTO collection (item_id, item_type, name, img_url, "
                "bricklink_url, quantity, condition, notes, year, paid_price, "
                "paid_source, paid_at, theme, added_by, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (body.item_id, body.item_type, body.name, body.img_url,
                 body.bricklink_url, body.quantity, body.condition, body.notes,
                 body.year or None, body.paid_price,
                 ((body.paid_source or "manual")
                  if body.paid_price is not None else None),
                 int(time.time()) if body.paid_price is not None else None,
                 themes.for_item(body.item_id, body.item_type),
                 user["id"], int(time.time())),
            )
            if body.paid_price is not None:
                _kauf_buchen(conn, cur.lastrowid, body.quantity,
                             body.paid_price, body.paid_source or "")
        except sqlite3.IntegrityError:
            # Zwei Anfragen für denselben, noch nicht vorhandenen Artikel
            # gleichzeitig: Beide sahen oben keine Zeile, eine legt sie an,
            # die zweite lief in die eindeutige Bedingung – und der Anwender
            # bekam einen Serverfehler, während sein Stück verschwand.
            # Jetzt wird daraus nachträglich das Zusammenführen.
            conn.execute(
                "UPDATE collection SET quantity = quantity + ? WHERE "
                "item_id = ? AND item_type = ? AND condition = ?",
                (body.quantity, body.item_id, body.item_type, body.condition))
            neu = conn.execute(
                "SELECT id, quantity FROM collection WHERE item_id = ? AND "
                "item_type = ? AND condition = ?",
                (body.item_id, body.item_type, body.condition)).fetchone()
            return {"ok": True, "merged": True,
                    "quantity": neu["quantity"] if neu else body.quantity}
        new_id = cur.lastrowid
    _maybe_fetch_prices_async(new_id, body.item_id)
    _bild_holen_async(body.img_url)
    _maybe_fetch_theme_async(body.item_id, body.item_type)
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
                "AND condition = ? AND id != ?",
                (body.item_id, row["item_type"],
                 body.condition or row["condition"], entry_id),
            ).fetchone()
            if dup:
                raise HTTPException(409, "Diese Nummer ist schon in der Sammlung "
                                         "– lösche stattdessen diesen Eintrag und "
                                         "erhöhe dort die Anzahl")
        if body.condition and body.condition != row["condition"]:
            other = conn.execute(
                "SELECT id, quantity, paid_price, paid_source FROM collection "
                "WHERE item_id = ? AND item_type = ? AND condition = ? "
                "AND id != ?",
                (body.item_id or row["item_id"], row["item_type"],
                 body.condition, entry_id)).fetchone()
            if other:
                # Zielzustand existiert schon: Einträge zusammenführen
                paid_sum = None
                if row["paid_price"] is not None or other["paid_price"] is not None:
                    paid_sum = round((row["paid_price"] or 0)
                                     + (other["paid_price"] or 0), 2)
                src_manual = (row["paid_source"] == "manual"
                              or other["paid_source"] == "manual")
                conn.execute(
                    "UPDATE collection SET quantity = quantity + ?, "
                    "paid_price = ?, paid_source = ?, paid_at = ? "
                    "WHERE id = ?",
                    (row["quantity"], paid_sum,
                     ("manual" if src_manual else "auto")
                     if paid_sum is not None else None,
                     int(time.time()) if paid_sum is not None else None,
                     other["id"]))
                # Das Kaufbuch zieht mit um – sonst verlöre die
                # zusammengeführte Zeile ihre Einzelposten.
                conn.execute("UPDATE purchases SET entry_id = ? WHERE "
                             "entry_id = ?", (other["id"], entry_id))
                conn.execute("DELETE FROM collection WHERE id = ?",
                             (entry_id,))
                _kaufsumme_nachziehen(conn, other["id"])
                return {"ok": True, "merged": True,
                        "merged_into": other["id"]}
        fields, params = [], []
        for key in ("quantity", "condition", "notes", "item_id", "name",
                    "img_url", "bricklink_url", "year", "paid_price",
                    "theme"):
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
        if body.paid_price is not None:
            # Von Hand gesetzt heißt: Das ist ab jetzt der Betrag für diese
            # Zeile. Das Buch wird auf einen Posten zurückgesetzt, sonst
            # stünde daneben eine Aufstellung, die etwas anderes ergibt.
            menge = conn.execute("SELECT quantity FROM collection WHERE id = ?",
                                 (entry_id,)).fetchone()
            conn.execute("DELETE FROM purchases WHERE entry_id = ?", (entry_id,))
            _kauf_buchen(conn, entry_id, menge["quantity"] if menge else 1,
                         body.paid_price, "manual")
        if body.quantity == 0:
            conn.execute("DELETE FROM collection WHERE id = ?", (entry_id,))
            conn.execute("DELETE FROM purchases WHERE entry_id = ?", (entry_id,))
            return {"ok": True, "deleted": True}
    if body.item_id:
        _maybe_fetch_prices_async(entry_id, body.item_id)
    return {"ok": True}


class KaufBody(BaseModel):
    quantity: int = Field(default=1, ge=1, le=999)
    price: float | None = Field(default=None, ge=0)   # Gesamtpreis des Kaufs
    source: str = Field(default="", max_length=80)
    bought_at: int | None = Field(default=None, ge=0)
    note: str = Field(default="", max_length=300)


@app.get("/api/collection/{entry_id}/purchases")
def kaeufe_lesen(entry_id: int, user: dict = Depends(current_user)):
    """Die einzelnen Käufe zu einem Eintrag – neueste zuerst."""
    with core.db() as conn:
        rows = conn.execute(
            "SELECT id, quantity, unit_price, source, bought_at, note "
            "FROM purchases WHERE entry_id = ? "
            "ORDER BY COALESCE(bought_at, created_at) DESC, id DESC",
            (entry_id,)).fetchall()
    return {"purchases": [dict(r) for r in rows]}


@app.post("/api/collection/{entry_id}/purchases")
def kauf_anlegen(entry_id: int, body: KaufBody,
                 user: dict = Depends(dealer_user)):
    """Einen weiteren Kauf eintragen – dasselbe Set, anderswo, anderer Preis.

    Die Stückzahl des Eintrags wächst mit: Wer einen zweiten Kauf einträgt,
    hat auch ein zweites Exemplar.
    """
    with core.db() as conn:
        row = conn.execute("SELECT id FROM collection WHERE id = ?",
                           (entry_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Eintrag nicht gefunden")
        conn.execute("UPDATE collection SET quantity = quantity + ? WHERE id = ?",
                     (body.quantity, entry_id))
        _kauf_buchen(conn, entry_id, body.quantity, body.price,
                     body.source, body.bought_at, body.note)
        stand = conn.execute(
            "SELECT quantity, paid_price FROM collection WHERE id = ?",
            (entry_id,)).fetchone()
    return {"ok": True, "quantity": stand["quantity"],
            "paid_price": stand["paid_price"]}


@app.delete("/api/collection/{entry_id}/purchases/{kauf_id}")
def kauf_loeschen(entry_id: int, kauf_id: int,
                  user: dict = Depends(dealer_user)):
    """Einen Kauf zurücknehmen – die Stückzahl geht mit zurück."""
    with core.db() as conn:
        k = conn.execute(
            "SELECT quantity FROM purchases WHERE id = ? AND entry_id = ?",
            (kauf_id, entry_id)).fetchone()
        if not k:
            raise HTTPException(404, "Kauf nicht gefunden")
        conn.execute("DELETE FROM purchases WHERE id = ?", (kauf_id,))
        # Nie unter ein Stück: Der Eintrag selbst wird hier nicht gelöscht,
        # dafür gibt es den Papierkorb an der Karte.
        conn.execute("UPDATE collection SET quantity = MAX(1, quantity - ?) "
                     "WHERE id = ?", (k["quantity"], entry_id))
        _kaufsumme_nachziehen(conn, entry_id)
        stand = conn.execute(
            "SELECT quantity, paid_price FROM collection WHERE id = ?",
            (entry_id,)).fetchone()
    return {"ok": True, "quantity": stand["quantity"],
            "paid_price": stand["paid_price"] if stand else None}


@app.delete("/api/collection/{entry_id}")
def delete_item(entry_id: int, user: dict = Depends(current_user)):
    with core.db() as conn:
        row = conn.execute(
            "SELECT item_id, item_type FROM collection WHERE id = ?",
            (entry_id,)).fetchone()
        cur = conn.execute("DELETE FROM collection WHERE id = ?", (entry_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Eintrag nicht gefunden")
        # Das Kaufbuch gehört zum Eintrag – sonst bliebe es als Waise liegen
        # und tauchte bei einer neu angelegten Zeile mit derselben Nummer
        # wieder auf.
        conn.execute("DELETE FROM purchases WHERE entry_id = ?", (entry_id,))
    fotos = _fotos_aufraeumen(row["item_type"], row["item_id"]) if row else 0
    return {"ok": True, "photos_removed": fotos}


# ---------------------------------------------------------------- Wunschliste

class WantedBody(BaseModel):
    item_id: str = Field(min_length=1, max_length=60)
    item_type: str = Field(default="minifig", pattern=ITEM_TYPE_RE)
    name: str = Field(min_length=1, max_length=300)
    img_url: str = Field(default="", max_length=600, pattern=IMG_URL_RE)
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
            "AND c.item_type = w.item_type) AS owned, "
            "(SELECT GROUP_CONCAT(c2.item_id || '|' || c2.name || '|' || sc.qty, ';;') "
            " FROM set_contents sc JOIN collection c2 "
            " ON c2.item_type = 'set' AND c2.item_id = sc.set_no "
            " WHERE sc.fig_no = w.item_id AND w.item_type = 'minifig') AS in_sets "
            "FROM wanted w "
            "LEFT JOIN users u ON u.id = w.added_by "
            "ORDER BY w.added_at DESC").fetchall()
        # Steht der Wunsch schon auf einer offenen Einkaufsliste, ist er
        # unterwegs – das gehört an die Karte, sonst kauft ihn jemand zweimal.
        auf_listen: dict = {}
        for r in conn.execute(
                "SELECT i.item_id, i.item_type, i.qty, l.name "
                "FROM shopping_items i "
                "JOIN shopping_lists l ON l.id = i.list_id "
                "WHERE i.done = 0 AND l.archived = 0"):
            e = auf_listen.setdefault((r["item_id"], r["item_type"]),
                                      {"qty": 0, "names": []})
            e["qty"] += r["qty"] or 1
            if r["name"] not in e["names"]:
                e["names"].append(r["name"])
        stats = conn.execute(
            "SELECT COUNT(*) AS count, "
            "COALESCE(SUM(COALESCE(price_used, price_new)), 0) AS est_cost, "
            "COALESCE(SUM(COALESCE(price_new, price_used)), 0) AS est_cost_new "
            "FROM wanted").fetchone()
    items = []
    for r in rows:
        d = dict(r)
        e = auf_listen.get((d["item_id"], d["item_type"]))
        d["on_lists"] = e["names"] if e else []
        d["on_lists_qty"] = e["qty"] if e else 0
        items.append(d)
    return {"items": items, "stats": dict(stats)}


@app.post("/api/wanted")
def add_wanted(body: WantedBody, user: dict = Depends(current_user)):
    body.item_id, body.name = _bricklink_nummer(
        body.item_id, body.item_type, body.name)
    with core.db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM wanted WHERE item_id = ? AND item_type = ?",
            (body.item_id, body.item_type)).fetchone()
        if exists:
            return {"ok": True, "exists": True}
        owned = conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS quantity FROM collection "
            "WHERE item_id = ? AND item_type = ?",
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
    if entry["item_id"].startswith(("fig-", "manuell-", "custom-")):
        raise HTTPException(400, "Ohne BrickLink-Nummer kein Preis")
    try:
        _fetch_and_store_prices(entry, "wanted", source="manuell")
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
        row = conn.execute(
            "SELECT item_id, item_type FROM wanted WHERE id = ?",
            (wanted_id,)).fetchone()
        cur = conn.execute("DELETE FROM wanted WHERE id = ?", (wanted_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Eintrag nicht gefunden")
    fotos = _fotos_aufraeumen(row["item_type"], row["item_id"]) if row else 0
    return {"ok": True, "photos_removed": fotos}


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
            "AND item_type = ? AND condition = ?",
            (w["item_id"], w["item_type"], body.condition)).fetchone()
        if row:
            conn.execute("UPDATE collection SET quantity = quantity + 1 "
                         "WHERE id = ?", (row["id"],))
            if manual:
                _kauf_buchen(conn, row["id"], 1, paid_val, "manual", now)
            elif row["paid_price"] is not None and unit:
                _kauf_buchen(conn, row["id"], 1, round(unit, 2), "geschätzt", now)
        else:
            cur_neu = conn.execute(
                "INSERT INTO collection (item_id, item_type, name, img_url, "
                "bricklink_url, quantity, condition, notes, year, price_new, "
                "price_used, price_updated_at, price_data, price_region, "
                "price_currency, paid_price, "
                "paid_source, paid_at, added_by, added_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?)",
                (w["item_id"], w["item_type"], w["name"], w["img_url"],
                 w["bricklink_url"], body.condition, w["notes"], w["year"],
                 w["price_new"], w["price_used"], w["price_updated_at"],
                 w["price_data"], w["price_region"], w["price_currency"],
                 paid_val,
                 ("manual" if manual else "auto") if paid_val is not None else None,
                 now if paid_val is not None else None,
                 user["id"], now))
            if paid_val is not None:
                _kauf_buchen(conn, cur_neu.lastrowid, 1, paid_val,
                             "manual" if manual else "geschätzt", now)
        conn.execute("DELETE FROM wanted WHERE id = ?", (wanted_id,))
    return {"ok": True, "merged": bool(row)}


def _store_set_contents(set_no: str, figs: list):
    with core.db() as conn:
        conn.execute("DELETE FROM set_contents WHERE set_no = ?", (set_no,))
        for f in figs:
            conn.execute(
                "INSERT OR REPLACE INTO set_contents "
                "(set_no, fig_no, qty, name, img_url) VALUES (?, ?, ?, ?, ?)",
                (set_no, f["item_id"], f.get("qty", 1),
                 f.get("name") or None, f.get("img_url") or None))
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
            return
        # Jetzt erst kann der Rückfall über die Figuren greifen – vorher gab
        # es die Set-Inhalte noch gar nicht.
        _thema_nachtragen(set_no, "set")

    threading.Thread(target=run, daemon=True).start()


def _thema_nachtragen(item_id: str, item_type: str) -> None:
    """Thema für einen Eintrag bestimmen und speichern, falls noch keins da
    ist. Läuft im Hintergrund, weil dahinter ein BrickLink-Abruf steckt."""
    try:
        thema = _theme_nachschlagen(item_id, item_type)
    except Exception:
        return
    if not thema:
        return
    with core.db() as conn:
        conn.execute(
            "UPDATE collection SET theme = ? WHERE item_id = ? "
            "AND item_type = ? AND (theme IS NULL OR theme = '')",
            (thema, item_id, item_type))


def _maybe_fetch_theme_async(item_id: str, item_type: str):
    """Neu erfasste Sets und Teile bekommen ihr Thema von selbst.

    Bei Minifiguren steht es schon in der Nummer und wird beim Einfügen
    gesetzt. Für Sets und Teile braucht es einen Abruf – der lief bisher
    nur, wenn jemand von Hand „Themen nachladen" drückte. Wer das nicht
    wusste, sammelte nach und nach Einträge unter „Ohne Thema".
    """
    if (item_type or "").lower() == "minifig":
        return          # steht in der Nummer, ist schon gesetzt
    if item_id.startswith(("fig-", "manuell-", "custom-")):
        return
    threading.Thread(target=_thema_nachtragen, args=(item_id, item_type),
                     daemon=True).start()


@app.get("/api/set_figs/{set_no}")
def get_set_figs(set_no: str, user: dict = Depends(current_user)):
    """Welche Minifiguren stecken in diesem Set?"""
    # Eigene/manuelle Sets kennt BrickLink nicht – gar nicht erst anfragen.
    if set_no.startswith(("custom-", "manuell-")):
        return {"items": []}
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


@app.get("/api/set_figs_owned/{set_no}")
def set_figs_owned(set_no: str, user: dict = Depends(current_user)):
    """Welche Figuren dieses Sets sind in der Sammlung – und wie viele
    Exemplare gehören rechnerisch zu diesem Set?

    Arbeitet rein lokal auf set_contents (kein BrickLink-Abruf), damit die
    Rückfrage beim Löschen auch ohne API-Schlüssel funktioniert.
    """
    with core.db() as conn:
        srow = conn.execute(
            "SELECT quantity, condition FROM collection "
            "WHERE item_type = 'set' AND item_id = ?", (set_no,)).fetchone()
        set_qty = srow["quantity"] if srow else 1
        set_cond = srow["condition"] if srow else "used"
        contents = conn.execute(
            "SELECT fig_no, qty FROM set_contents WHERE set_no = ?",
            (set_no,)).fetchall()
        out = []
        for c in contents:
            need = (c["qty"] or 1) * max(1, set_qty)
            rows = conn.execute(
                "SELECT id, item_id, name, img_url, condition, quantity "
                "FROM collection WHERE item_type = 'minifig' AND item_id = ?",
                (c["fig_no"],)).fetchall()
            # zuerst zustandsgleiche Zeilen abbauen
            for r in sorted(rows, key=lambda x: 0
                            if x["condition"] == set_cond else 1):
                if need <= 0:
                    break
                take = min(r["quantity"], need)
                need -= take
                out.append({"id": r["id"], "item_id": r["item_id"],
                            "name": r["name"], "img_url": r["img_url"],
                            "condition": r["condition"],
                            "quantity": r["quantity"], "remove": take})
    return {"items": out}


@app.get("/api/missing_set_figs")
def missing_set_figs(user: dict = Depends(current_user)):
    """Welche Minifiguren fehlen über alle eigenen Sets hinweg?

    Rechnet rein lokal: Bedarf = Set-Inhalt × Anzahl besessener Sets,
    summiert über alle Sets. Davon wird der Bestand abgezogen; was übrig
    bleibt, fehlt. Preise kommen aus der Wunschliste bzw. dem Preisverlauf.
    """
    with core.db() as conn:
        sets = conn.execute(
            "SELECT item_id, name, quantity FROM collection "
            "WHERE item_type = 'set'").fetchall()
        contents = conn.execute(
            "SELECT set_no, fig_no, qty, name, img_url "
            "FROM set_contents").fetchall()
        owned = {r["item_id"]: r["n"] for r in conn.execute(
            "SELECT item_id, COALESCE(SUM(quantity), 0) AS n FROM collection "
            "WHERE item_type = 'minifig' GROUP BY item_id")}
        wanted = {r["item_id"]: r for r in conn.execute(
            "SELECT item_id, price_new, price_used FROM wanted "
            "WHERE item_type = 'minifig'")}

        # Namen aus Sammlung/Wunschliste als Rückfall, falls der Set-Inhalt
        # noch aus einer Version ohne Namensspalte stammt
        known = {r["item_id"]: r for r in conn.execute(
            "SELECT item_id, name, img_url FROM collection "
            "WHERE item_type = 'minifig' "
            "UNION SELECT item_id, name, img_url FROM wanted "
            "WHERE item_type = 'minifig'")}

        # Steht die fehlende Figur schon auf einer Einkaufsliste (z. B.
        # „Flohmarkt")? Dann ist sie unterwegs – das gehört an die Karte.
        on_lists: dict = {}
        for r in conn.execute(
                "SELECT i.item_id, l.name AS list_name, i.qty "
                "FROM shopping_items i "
                "JOIN shopping_lists l ON l.id = i.list_id "
                "WHERE i.item_type = 'minifig' AND i.done = 0 "
                "AND l.archived = 0"):
            e = on_lists.setdefault(r["item_id"], {"qty": 0, "lists": []})
            e["qty"] += r["qty"] or 1
            if r["list_name"] not in e["lists"]:
                e["lists"].append(r["list_name"])

        by_set: dict = {}
        stale = set()
        for c in contents:
            by_set.setdefault(c["set_no"], []).append(c)
            if not c["name"]:
                stale.add(c["set_no"])

        need: dict = {}
        for s in sets:
            for c in by_set.get(s["item_id"], []):
                e = need.setdefault(c["fig_no"], {
                    "needed": 0, "name": None, "img_url": None, "sets": []})
                e["needed"] += (c["qty"] or 1) * max(1, s["quantity"])
                e["name"] = e["name"] or c["name"]
                e["img_url"] = e["img_url"] or c["img_url"]
                e["sets"].append({"no": s["item_id"], "name": s["name"],
                                  "qty": c["qty"] or 1})

        items = []
        est_cost = 0.0
        incomplete = set()
        for fig_no, e in need.items():
            have = owned.get(fig_no, 0)
            missing = e["needed"] - have
            if missing <= 0:
                continue
            for s in e["sets"]:
                incomplete.add(s["no"])
            w = wanted.get(fig_no)
            price_new = w["price_new"] if w else None
            price_used = w["price_used"] if w else None
            if price_new is None and price_used is None:
                prow = conn.execute(
                    "SELECT price_new, price_used FROM price_history "
                    "WHERE item_id = ? AND item_type = 'minifig' "
                    "ORDER BY ts DESC LIMIT 1", (fig_no,)).fetchone()
                if prow:
                    price_new, price_used = prow["price_new"], prow["price_used"]
            unit = price_used or price_new
            if unit:
                est_cost += unit * missing
            k = known.get(fig_no)
            items.append({
                "item_id": fig_no,
                "name": e["name"] or (k["name"] if k else None) or fig_no,
                "img_url": e["img_url"] or (k["img_url"] if k else "") or "",
                "bricklink_url": (
                    "https://www.bricklink.com/v2/catalog/catalogitem.page?M="
                    + requests.utils.quote(fig_no)),
                "needed": e["needed"], "owned": have, "missing": missing,
                "sets": e["sets"], "wanted": fig_no in wanted,
                "price_new": price_new, "price_used": price_used,
                "unit_price": unit,
                "on_lists": on_lists.get(fig_no, {}).get("lists", []),
                "on_lists_qty": on_lists.get(fig_no, {}).get("qty", 0),
            })
    # Set-Inhalte ohne Namen stammen aus einer älteren Version. Wie viele
    # Sets noch Details brauchen, meldet die Antwort mit – nachladen kann
    # man sie gezielt über /api/set_contents/refresh.
    owned_nos = {s["item_id"] for s in sets}
    pending = sorted(stale & owned_nos)

    items.sort(key=lambda x: x["name"].lower())
    return {"items": items,
            "stats": {"figs": len(items),
                      "pieces": sum(i["missing"] for i in items),
                      "est_cost": round(est_cost, 2),
                      "sets_incomplete": len(incomplete),
                      "sets_total": len(sets),
                      "details_pending": len(pending),
                      "can_fetch": integrations.bricklink_enabled()}}


@app.post("/api/set_contents/refresh")
def refresh_set_contents(limit: int = 10, user: dict = Depends(current_user)):
    """Namen und Bilder der Set-Figuren von BrickLink nachladen.

    Arbeitet die Sets ab, deren gespeicherter Inhalt noch keine Namen hat
    (Altbestand). Läuft bewusst synchron und in Häppchen, damit die App
    Rückmeldung geben kann, statt still im Hintergrund zu werkeln.
    """
    if not integrations.bricklink_enabled():
        raise HTTPException(501, "BrickLink-API nicht konfiguriert "
                                 "(Schlüssel unter Mehr → API-Schlüssel)")
    limit = max(1, min(limit, 25))
    with core.db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT sc.set_no FROM set_contents sc "
            "JOIN collection c ON c.item_type = 'set' AND c.item_id = sc.set_no "
            "WHERE sc.name IS NULL OR sc.name = '' "
            "ORDER BY sc.set_no").fetchall()
    todo = [r["set_no"] for r in rows]
    done, failed = 0, []
    for set_no in todo[:limit]:
        try:
            _store_set_contents(set_no, integrations.bricklink_subsets(set_no))
            done += 1
        except Exception as e:                      # einzelne Sets überspringen
            failed.append({"set_no": set_no, "error": scrub(str(e))[:120]})
    return {"ok": True, "updated": done,
            "remaining": max(0, len(todo) - done),
            "failed": failed}


@app.get("/api/duplicates")
def get_duplicates(user: dict = Depends(dealer_user)):
    """Alles mit Menge > 1: pro Eintrag bleibt eins, der Rest ist abgebbar."""
    return _duplicate_items()


def _duplicate_items() -> dict:
    """Abgebbarer Bestand (Menge > 1 minus Behalten/Set-Reservierung)."""
    with core.db() as conn:
        rows = conn.execute(
            "SELECT c.*, "
            "(SELECT COALESCE(SUM(sc.qty * c2.quantity), 0) "
            " FROM set_contents sc JOIN collection c2 "
            " ON c2.item_type = 'set' AND c2.item_id = sc.set_no "
            " WHERE sc.fig_no = c.item_id) AS reserved "
            "FROM collection c "
            "ORDER BY c.name COLLATE NOCASE").fetchall()
    # Zeilen je Artikel gruppieren: Reservierung gilt pro Artikel,
    # nicht pro Zustands-Zeile. Behalten wird bevorzugt "Neu",
    # abgebbar sind zuerst die gebrauchten Exemplare.
    groups = {}
    for r in rows:
        groups.setdefault((r["item_id"], r["item_type"]), []).append(r)
    items = []
    total_value = 0.0
    total_pieces = 0
    for group in groups.values():
        total_qty = sum(r["quantity"] for r in group)
        keep = max(group[0]["reserved"] or 0, 1)
        if total_qty - keep <= 0:
            continue
        # Wie viele werden WIRKLICH für eigene Sets gebraucht?
        set_need = group[0]["reserved"] or 0
        # Behalten-Kontingent zuerst auf Neu-Zeilen anrechnen; dabei
        # trennen, was für Sets reserviert ist und was nur die Behalte-1 ist
        remaining_keep = keep
        remaining_set = set_need
        for r in sorted(group, key=lambda x: 0 if x["condition"] == "new"
                        else 1):
            alloc = min(r["quantity"], remaining_keep)
            remaining_keep -= alloc
            set_alloc = min(alloc, remaining_set)
            remaining_set -= set_alloc
            surplus = r["quantity"] - alloc
            if surplus <= 0:
                continue
            unit = _unit_price(r["condition"], r["price_new"],
                               r["price_used"])
            value = round(unit * surplus, 2) if unit else None
            items.append({
                "id": r["id"], "item_id": r["item_id"],
                "item_type": r["item_type"], "name": r["name"],
                "img_url": r["img_url"], "bricklink_url": r["bricklink_url"],
                "condition": r["condition"], "quantity": r["quantity"],
                "reserved": min(r["quantity"], alloc),
                "set_reserved": set_alloc, "surplus": surplus,
                "unit_price": unit, "value": value,
            })
            total_pieces += surplus
            if value:
                total_value += value
    items.sort(key=lambda x: (x["name"] or "").lower())
    return {"items": items,
            "stats": {"pieces": total_pieces,
                      "value": round(total_value, 2)}}


# ---------------------------------------------------------------- Tausch-Hub

class HubConnectBody(BaseModel):
    token: str | None = Field(default=None, max_length=200)
    invite_code: str | None = Field(default=None, max_length=200)
    display_name: str | None = Field(default=None, max_length=80)


class HubInviteBody(BaseModel):
    note: str = Field(default="", max_length=120)
    expires_in_days: int = Field(default=0, ge=0, le=365)


def _hub_status(refresh: bool = False) -> dict:
    """Verbindungsstatus – ohne den Token nach außen zu geben. `refresh` holt
    Name/Admin-Status live vom Hub (best-effort, damit Änderungen am Hub – etwa
    ein umbenanntes Konto – auch ohne Reconnect ankommen)."""
    if refresh and hub.enabled():
        try:
            hub.refresh()
            # Instanzen aus früheren Versionen haben noch keinen Schlüssel
            # hinterlegt – das holen wir hier beiläufig nach.
            _ensure_key_published()
        except Exception:
            pass                        # Cache bleibt, wenn der Hub grad klemmt
    c = hub.config()
    return {"connected": hub.enabled(), "url": c["url"],
            "member_id": c["member_id"], "display_name": c["display_name"],
            "is_admin": c["is_admin"], "last_publish": hub.last_publish(),
            "blocked": hub.blocked()}


@app.get("/api/hub")
def hub_status(refresh: int = 0, user: dict = Depends(current_user)):
    return _hub_status(refresh=bool(refresh))




@app.post("/api/hub/connect")
def hub_connect(body: HubConnectBody, user: dict = Depends(admin_user)):
    try:
        if body.token:
            hub.connect_with_token(body.token.strip())
        elif body.invite_code and body.display_name:
            hub.connect_with_invite(body.invite_code.strip(),
                                    body.display_name.strip())
        else:
            raise HTTPException(400, "Token oder Einladungscode + Anzeigename nötig")
        # Schlüssel gleich hinterlegen, damit uns andere sofort schreiben können
        try:
            _ensure_key_published()
        except Exception:
            pass
        return _hub_status()
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


@app.post("/api/hub/disconnect")
def hub_disconnect(user: dict = Depends(admin_user)):
    hub.disconnect()
    return {"connected": False}


class ShareBody(BaseModel):
    shared: bool
    qty: int | None = Field(default=None, ge=1, le=9999)


@app.post("/api/collection/{entry_id}/share")
def set_shared(entry_id: int, body: ShareBody,
               user: dict = Depends(current_user)):
    """Einzelnen Eintrag für die Tauschbörse an- oder abwählen. `qty` sagt,
    wie viele Exemplare angeboten werden – ohne Angabe alle vorhandenen."""
    with core.db() as conn:
        row = conn.execute("SELECT quantity FROM collection WHERE id = ?",
                           (entry_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Eintrag nicht gefunden")
        qty = body.qty
        if qty is not None:
            qty = max(1, min(qty, row["quantity"]))
        conn.execute("UPDATE collection SET shared = ?, share_qty = ? "
                     "WHERE id = ?",
                     (1 if body.shared else 0,
                      qty if body.shared else None, entry_id))
    return {"ok": True, "shared": body.shared, "qty": qty}


def _shared_rows(conn):
    return conn.execute(
        "SELECT id, item_id, item_type, name, img_url, bricklink_url, "
        "condition, quantity, share_qty FROM collection WHERE shared = 1 "
        "ORDER BY name COLLATE NOCASE").fetchall()


@app.get("/api/share/status")
def share_status(user: dict = Depends(current_user)):
    """Was ist ausgewählt, was davon ist schon veröffentlicht – und was liegt
    noch beim Hub, das beim nächsten Veröffentlichen verschwindet?"""
    with core.db() as conn:
        rows = _shared_rows(conn)
    chosen = [{"id": r["id"], "item_id": r["item_id"], "name": r["name"],
               "item_type": r["item_type"], "img_url": r["img_url"],
               "condition": r["condition"], "quantity": r["quantity"],
               "share_qty": r["share_qty"] or r["quantity"]} for r in rows]

    published, stale, live = [], [], None
    if hub.enabled():
        try:
            live = hub.offers({"mine": "1"})
        except Exception:
            live = None
    if live is not None:
        by_item = {o["item_id"]: o for o in live}
        for c in chosen:
            o = by_item.get(c["item_id"])
            c["published"] = bool(o)
            c["published_qty"] = o["qty"] if o else None
            if o:
                published.append(c["item_id"])
        chosen_ids = {c["item_id"] for c in chosen}
        stale = [{"item_id": o["item_id"], "name": o["name"], "qty": o["qty"]}
                 for o in live if o["item_id"] not in chosen_ids]
    return {"shared": len(chosen), "suggested": len(_duplicate_items()["items"]),
            "items": chosen, "known_state": live is not None,
            "published": len(published), "stale": stale}


@app.post("/api/share/from_duplicates")
def share_from_duplicates(user: dict = Depends(current_user)):
    """Bequemlichkeit: alles aus der Abgabeliste auswählen."""
    ids = [it["id"] for it in _duplicate_items()["items"]]
    with core.db() as conn:
        for i in ids:
            conn.execute("UPDATE collection SET shared = 1 WHERE id = ?", (i,))
    return {"ok": True, "added": len(ids)}


@app.post("/api/share/clear")
def share_clear(user: dict = Depends(current_user)):
    """Auswahl komplett zurücknehmen."""
    with core.db() as conn:
        conn.execute("UPDATE collection SET shared = 0")
    return {"ok": True}


THUMB_MAX_CHARS = 30000       # Obergrenze je Vorschaubild (Base64)


def _offer_thumb(img_url: str) -> str | None:
    """Kleines Vorschaubild für eigene Bilder.

    Custom-Figuren haben nur einen lokalen Pfad (/uploads/…) – der zeigt beim
    Empfänger auf dessen eigene Instanz und wäre dort wertlos. Deshalb reist
    bei ihnen ein verkleinertes Bild als Daten-URL mit; alles andere hat eine
    öffentliche BrickLink-/Rebrickable-Adresse und braucht das nicht.
    """
    if not img_url or not img_url.startswith("/uploads/"):
        return None
    name = os.path.basename(img_url)
    if not re.fullmatch(r"[0-9a-f]{32}\.jpg", name):
        return None
    path = os.path.join(_uploads_dir(), name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            small = integrations.prepare_image(f.read(), max_side=200)
    except Exception:
        return None
    data = "data:image/jpeg;base64," + base64.b64encode(small).decode()
    return data if len(data) <= THUMB_MAX_CHARS else None


@app.post("/api/hub/publish")
def hub_publish(user: dict = Depends(admin_user)):
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    with core.db() as conn:
        rows = _shared_rows(conn)
    offers = []
    for r in rows:
        thumb = _offer_thumb(r["img_url"])
        offers.append({
            "item_id": r["item_id"], "item_type": r["item_type"],
            "name": r["name"],
            # Lokale Pfade nicht mitschicken – sie gelten nur bei uns
            "img_url": "" if thumb else (r["img_url"] or ""),
            "img_data": thumb,
            "bricklink_url": r["bricklink_url"], "condition": r["condition"],
            # Nur so viele anbieten, wie ausgewählt (Standard: alle)
            "qty": min(r["share_qty"] or r["quantity"], r["quantity"]),
        })
    try:
        res = hub.publish(offers)
        return {"ok": True, "count": res.get("count", len(offers))}
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


@app.get("/api/hub/offers")
def hub_offers(q: str = "", member: str = "",
               user: dict = Depends(current_user)):
    if not hub.enabled():
        return {"offers": []}
    try:
        return {"offers": hub.offers({"q": q, "member": member})}
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


@app.get("/api/hub/members")
def hub_members(user: dict = Depends(current_user)):
    if not hub.enabled():
        return {"members": []}
    try:
        return {"members": hub.members()}
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


# ------------------------------------------------- Tausch-Vorgänge (E2E)

def _ensure_key_published():
    """Öffentlichen Schlüssel beim Hub hinterlegen (einmalig, danach gemerkt)."""
    if core.get_setting("hub_key_sent") == crypto_box.public_key():
        return
    hub.put_key(crypto_box.public_key())
    core.set_setting("hub_key_sent", crypto_box.public_key())


def _sync_trade(trade_id: str) -> int:
    """Nachrichten eines Vorgangs holen, entschlüsseln und lokal ablegen.
    Gibt zurück, wie viele neu waren."""
    data = hub.fetch_messages(trade_id)
    new = 0
    with core.db() as conn:
        for m in data.get("messages", []):
            exists = conn.execute(
                "SELECT 1 FROM trade_messages WHERE trade_id = ? AND hub_id = ?"
                " AND mine = 0", (trade_id, m["id"])).fetchone()
            if exists:
                continue
            try:
                body = crypto_box.open_box(m["box"])
            except Exception:
                body = "(Nachricht konnte nicht entschlüsselt werden)"
            conn.execute(
                "INSERT INTO trade_messages (trade_id, hub_id, mine, body, "
                "created_at, delivered) VALUES (?, ?, 0, ?, ?, 1)",
                (trade_id, m["id"], body, m["created_at"]))
            new += 1
        # Zustellstatus der eigenen Nachrichten nachziehen
        for s in data.get("sent", []):
            if s.get("fetched_at"):
                conn.execute(
                    "UPDATE trade_messages SET delivered = 1 "
                    "WHERE trade_id = ? AND hub_id = ? AND mine = 1",
                    (trade_id, s["id"]))
    return new


@app.post("/api/hub/trades/sync")
def hub_sync_trades(focus: str = "", user: dict = Depends(current_user)):
    """Vorgänge und neue Nachrichten vom Hub holen.

    Abgeholt wird nur, wo es sich lohnt: Der Hub sagt je Vorgang, wie viele
    Umschläge für uns bereitliegen. Ohne das würde regelmäßiges Nachladen mit
    jedem Vorgang eine eigene Anfrage kosten. `focus` holt zusätzlich einen
    bestimmten Vorgang (das offene Gespräch – dort interessiert auch der
    Zustellstatus der eigenen Nachrichten).
    """
    if not hub.enabled():
        return {"trades": 0, "new_messages": 0}
    try:
        _ensure_key_published()
        me = hub.config()["member_id"]
        remote = hub.trades()
        new_msgs = 0
        with core.db() as conn:
            for t in remote:
                mine = t["from_member"] == me
                other_id = t["to_member"] if mine else t["from_member"]
                other_name = (t.get("to_name") if mine
                              else t.get("from_name")) or "?"
                conn.execute(
                    "INSERT INTO trades (id, direction, other_id, other_name, "
                    "item_id, item_name, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET status = excluded.status, "
                    "updated_at = excluded.updated_at, "
                    "other_name = excluded.other_name",
                    (t["id"], "out" if mine else "in", other_id, other_name,
                     t["item_id"], t["item_name"], t["status"],
                     t["created_at"], t["updated_at"]))
                # Nur bei Anfragen an andere sagt der Hub etwas darüber, ob
                # das Angebot noch steht – bei eingehenden ist es mein eigenes.
                if mine and "item_available" in t:
                    conn.execute("UPDATE trades SET item_gone = ? WHERE id = ?",
                                 (0 if t["item_available"] else 1, t["id"]))
        for t in remote:
            if t.get("unread") or t["id"] == focus:
                new_msgs += _sync_trade(t["id"])
        return {"trades": len(remote), "new_messages": new_msgs}
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


@app.get("/api/hub/trades")
def hub_trades(user: dict = Depends(current_user)):
    """Lokale Vorgangsliste – funktioniert auch, wenn der Hub gerade klemmt."""
    with core.db() as conn:
        rows = conn.execute(
            "SELECT t.*, (SELECT COUNT(*) FROM trade_messages m "
            " WHERE m.trade_id = t.id AND m.mine = 0 "
            " AND (t.read_at IS NULL OR m.created_at > t.read_at)) AS unread, "
            "(SELECT body FROM trade_messages m WHERE m.trade_id = t.id "
            " ORDER BY m.created_at DESC, m.id DESC LIMIT 1) AS last_body "
            "FROM trades t ORDER BY t.updated_at DESC").fetchall()
    return {"trades": [dict(r) for r in rows]}


@app.get("/api/hub/trades/{trade_id}")
def hub_trade_detail(trade_id: str, user: dict = Depends(current_user)):
    with core.db() as conn:
        t = conn.execute("SELECT * FROM trades WHERE id = ?",
                         (trade_id,)).fetchone()
        if not t:
            raise HTTPException(404, "Vorgang nicht gefunden")
        msgs = conn.execute(
            "SELECT id, mine, body, created_at, delivered FROM trade_messages "
            "WHERE trade_id = ? ORDER BY created_at, id", (trade_id,)).fetchall()
        conn.execute("UPDATE trades SET read_at = ? WHERE id = ?",
                     (int(time.time()), trade_id))
    return {"trade": dict(t), "messages": [dict(m) for m in msgs]}


class TradeStartBody(BaseModel):
    to: str = Field(min_length=1, max_length=80)
    item_id: str = Field(min_length=1, max_length=60)
    item_name: str = Field(default="", max_length=200)
    text: str = Field(min_length=1, max_length=2000)
    # Aus dem Angebot mitgenommen, damit ein angenommener Tausch später ohne
    # Rückfrage in der Sammlung landen kann. Das Bild darf hier auch eine
    # fremde Adresse sein – es kommt vom Hub, nicht aus dem eigenen Katalog.
    item_type: str = Field(default="", max_length=20)
    img_url: str = Field(default="", max_length=600)
    bricklink_url: str = Field(default="", max_length=600)
    condition: str = Field(default="", max_length=10)


def _fremder_schluessel(member_id: str, name: str = "") -> str:
    """Öffentlichen Schlüssel eines Gegenübers holen – und wiedererkennen.

    Der Hub verteilt diese Schlüssel. Nähme man sie jedes Mal ungeprüft
    hin, stünde er in der Lage, einen eigenen unterzuschieben und
    mitzulesen. Deshalb zählt der zuerst gesehene.
    """
    daten = hub.member_key(member_id)
    schluessel = daten["public_key"]
    try:
        crypto_box.remember_key(member_id, schluessel,
                                daten.get("display_name") or name)
    except crypto_box.KeyChanged as e:
        raise HTTPException(409,
            f"Der Verschlüsselungs-Schlüssel von {e.name} hat sich geändert. "
            "Solange das nicht geklärt ist, wird nichts verschickt – ein "
            "solcher Wechsel kann bedeuten, dass die Instanz neu aufgesetzt "
            "wurde, oder dass jemand mitlesen will. Frag nach und vergleiche "
            "die Sicherheitsnummer; danach unter „Schlüssel neu annehmen“ "
            "bestätigen.")
    return schluessel


class KeyAcceptBody(BaseModel):
    member_id: str = Field(min_length=3, max_length=80)


@app.get("/api/hub/key/{member_id}")
def hub_key_info(member_id: str, user: dict = Depends(current_user)):
    """Sicherheitsnummer für ein Gegenüber – zum Vergleichen am Telefon."""
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    with core.db() as conn:
        row = conn.execute(
            "SELECT public_key, first_seen FROM hub_keys WHERE member_id = ?",
            (member_id,)).fetchone()
    eigen = crypto_box.fingerprint(crypto_box.public_key())
    if not row:
        return {"known": False, "mine": eigen}
    return {"known": True, "mine": eigen,
            "theirs": crypto_box.fingerprint(row["public_key"]),
            "since": row["first_seen"]}


@app.post("/api/hub/key/accept")
def hub_key_accept(body: KeyAcceptBody, user: dict = Depends(admin_user)):
    """Einen geänderten Schlüssel annehmen – nach der Rückfrage.

    Bewusst Admin-Sache: Wer hier bestätigt, erklärt, dass er nachgefragt
    hat. Das ist keine Kleinigkeit, die nebenbei weggeklickt gehört.
    """
    crypto_box.forget_key(body.member_id)
    return {"ok": True}


@app.post("/api/hub/trades")
def hub_start_trade(body: TradeStartBody, user: dict = Depends(current_user)):
    """Interesse an einem Angebot anmelden – mit erster Nachricht."""
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    try:
        _ensure_key_published()
        key = _fremder_schluessel(body.to)
        box = crypto_box.seal(key, body.text)
        res = hub.create_trade(body.to, body.item_id, body.item_name, box)
        tid = res["trade_id"]
        now_ts = int(time.time())
        with core.db() as conn:
            conn.execute(
                "INSERT INTO trades (id, direction, other_id, other_name, "
                "item_id, item_name, status, created_at, updated_at, read_at, "
                "item_type, img_url, bricklink_url, condition) "
                "VALUES (?, 'out', ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?)",
                (tid, body.to, "", body.item_id, body.item_name,
                 now_ts, now_ts, now_ts,
                 body.item_type if body.item_type in
                 ("minifig", "set", "part") else "",
                 body.img_url if body.img_url.startswith(
                     ("http://", "https://")) else "",
                 body.bricklink_url if body.bricklink_url.startswith("http")
                 else "",
                 body.condition if body.condition in ("new", "used") else ""))
            conn.execute(
                "INSERT INTO trade_messages (trade_id, hub_id, mine, body, "
                "created_at) VALUES (?, ?, 1, ?, ?)",
                (tid, res.get("message_id"), body.text, now_ts))
        return {"ok": True, "trade_id": tid}
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


class TradeMessageBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@app.post("/api/hub/trades/{trade_id}/messages")
def hub_send_message(trade_id: str, body: TradeMessageBody,
                     user: dict = Depends(current_user)):
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    with core.db() as conn:
        t = conn.execute("SELECT other_id FROM trades WHERE id = ?",
                         (trade_id,)).fetchone()
    if not t:
        raise HTTPException(404, "Vorgang nicht gefunden")
    try:
        key = _fremder_schluessel(t["other_id"])
        sent = hub.send_message(trade_id, crypto_box.seal(key, body.text))
        now_ts = int(time.time())
        with core.db() as conn:
            conn.execute(
                "INSERT INTO trade_messages (trade_id, hub_id, mine, body, "
                "created_at) VALUES (?, ?, 1, ?, ?)",
                (trade_id, sent.get("message_id"), body.text, now_ts))
            conn.execute("UPDATE trades SET updated_at = ?, read_at = ? "
                         "WHERE id = ?", (now_ts, now_ts, trade_id))
        return {"ok": True}
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


@app.delete("/api/hub/trades/{trade_id}")
def hub_delete_trade(trade_id: str, user: dict = Depends(current_user)):
    """Unterhaltung löschen – hier und, soweit erreichbar, auch im Hub.
    Lokal wird auch dann gelöscht, wenn der Hub gerade klemmt; beim nächsten
    Abgleich käme der Vorgang sonst wieder zurück, deshalb der Versuch zuerst."""
    if hub.enabled():
        try:
            hub.delete_trade(trade_id)
        except hub.HubError as e:
            if e.status != 404:
                raise HTTPException(502, f"Hub: {e.message}")
        except requests.RequestException:
            raise HTTPException(502, "Hub nicht erreichbar")
    with core.db() as conn:
        conn.execute("DELETE FROM trade_messages WHERE trade_id = ?", (trade_id,))
        conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    return {"ok": True}


class TradeStatusBody(BaseModel):
    status: str = Field(pattern="^(open|accepted|declined|closed)$")


@app.post("/api/hub/trades/{trade_id}/status")
def hub_trade_status(trade_id: str, body: TradeStatusBody,
                     user: dict = Depends(current_user)):
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    try:
        hub.set_trade_status(trade_id, body.status)
        with core.db() as conn:
            conn.execute("UPDATE trades SET status = ? WHERE id = ?",
                         (body.status, trade_id))
        return {"ok": True, "status": body.status}
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


class TradeTakeBody(BaseModel):
    ziel: str = Field(default="sammlung", pattern="^(sammlung|liste)$")
    list_id: int | None = Field(default=None, ge=1)
    quantity: int = Field(default=1, ge=1, le=999)
    condition: str = Field(default="used", pattern="^(new|used)$")
    paid_price: float | None = Field(default=None, ge=0)


def _art_raten(item_id: str) -> str:
    """Set oder Figur? Für Vorgänge, die noch ohne Art gespeichert wurden.

    Setnummern sind reine Ziffern, gern mit Variante dahinter (`21306-1`).
    Alles andere (`sw0001`, `TX-20`) ist im Zweifel eine Minifigur – das ist
    die häufigere Sorte und im Zweifelsfall in zwei Handgriffen korrigiert.
    """
    return "set" if re.fullmatch(r"\d{2,7}(-\d{1,2})?", item_id) else "minifig"


@app.post("/api/hub/trades/{trade_id}/take")
def hub_trade_take(trade_id: str, body: TradeTakeBody,
                   user: dict = Depends(current_user)):
    """Einen angenommenen Tausch verbuchen: in die Sammlung oder auf eine Liste.

    Bis hierher war „Annehmen" nur eine Zusage im Gespräch – der Artikel selbst
    blieb außen vor und musste von Hand nachgetragen werden. Gebucht wird
    bewusst erst auf Knopfdruck: Zwischen Zusage und Karton in der Hand liegen
    beim Tauschen oft Tage.
    """
    with core.db() as conn:
        t = conn.execute("SELECT * FROM trades WHERE id = ?",
                         (trade_id,)).fetchone()
    if not t:
        raise HTTPException(404, "Vorgang nicht gefunden")
    if t["direction"] != "out":
        raise HTTPException(400, "Das ist ein eigener Artikel, der weggeht.")
    if t["status"] != "accepted":
        raise HTTPException(400, "Der Tausch ist noch nicht angenommen.")

    art = t["item_type"] or _art_raten(t["item_id"])
    name = t["item_name"] or t["item_id"]
    bild = t["img_url"] if t["img_url"].startswith(("http://", "https://")) \
        else ""
    if body.ziel == "liste":
        if not user["is_dealer"]:
            raise HTTPException(403, "Listen gibt es nur für Sammlerprofis")
        if not body.list_id:
            raise HTTPException(400, "Keine Liste ausgewählt")
        ergebnis = add_list_item(body.list_id, ListItemBody(
            item_id=t["item_id"], item_type=art, name=name, img_url=bild,
            bricklink_url=t["bricklink_url"], qty=min(99, body.quantity),
            condition=body.condition, paid_price=body.paid_price), user)
    else:
        ergebnis = add_item(AddItemBody(
            item_id=t["item_id"], item_type=art, name=name, img_url=bild,
            bricklink_url=t["bricklink_url"], quantity=body.quantity,
            condition=body.condition, paid_price=body.paid_price,
            paid_source="manual" if body.paid_price is not None else None,
            notes=f"Tausch mit {t['other_name'] or t['other_id']}"), user)
    with core.db() as conn:
        conn.execute("UPDATE trades SET taken_at = ? WHERE id = ?",
                     (int(time.time()), trade_id))
    return {"ok": True, "ziel": body.ziel, "item_type": art,
            "ergebnis": ergebnis}


class TradeGiveBody(BaseModel):
    quantity: int = Field(default=1, ge=1, le=999)
    # Ohne Angabe nur dann, wenn es die Nummer genau einmal gibt – sonst
    # wüsste niemand, ob das neue oder das gebrauchte Stück weggeht.
    condition: str | None = Field(default=None, pattern="^(new|used)$")


@app.get("/api/hub/trades/{trade_id}/candidates")
def hub_trade_candidates(trade_id: str, user: dict = Depends(current_user)):
    """Welche Zeilen der Sammlung kommen für diesen Vorgang infrage?

    Dieselbe Nummer kann zweimal dastehen – einmal neu, einmal gebraucht.
    Vor dem Austragen muss klar sein, welches Stück gemeint ist.
    """
    with core.db() as conn:
        t = conn.execute("SELECT * FROM trades WHERE id = ?",
                         (trade_id,)).fetchone()
        if not t:
            raise HTTPException(404, "Vorgang nicht gefunden")
        rows = conn.execute(
            "SELECT id, item_type, name, condition, quantity FROM collection "
            "WHERE item_id = ? ORDER BY condition", (t["item_id"],)).fetchall()
    return {"candidates": [dict(r) for r in rows]}


@app.post("/api/hub/trades/{trade_id}/give")
def hub_trade_give(trade_id: str, body: TradeGiveBody,
                   user: dict = Depends(current_user)):
    """Gegenstück zum Übernehmen: ein zugesagtes Stück austragen.

    Hier geht etwas weg, deshalb passiert nichts von allein und nichts ohne
    Rückfrage in der Oberfläche. Bleibt nichts übrig, verschwindet die Zeile
    ganz – wie beim Austragen über die Karte, samt Kaufbuch.
    """
    with core.db() as conn:
        t = conn.execute("SELECT * FROM trades WHERE id = ?",
                         (trade_id,)).fetchone()
        if not t:
            raise HTTPException(404, "Vorgang nicht gefunden")
        if t["direction"] != "in":
            raise HTTPException(400, "Dieser Artikel kommt zu dir.")
        if t["status"] != "accepted":
            raise HTTPException(400, "Der Tausch ist noch nicht angenommen.")
        wo = "SELECT * FROM collection WHERE item_id = ?"
        werte = [t["item_id"]]
        if body.condition:
            wo += " AND condition = ?"
            werte.append(body.condition)
        rows = conn.execute(wo + " ORDER BY condition", werte).fetchall()
    if not rows:
        raise HTTPException(404, "Der Artikel steht nicht in deiner Sammlung.")
    if len(rows) > 1:
        raise HTTPException(400, "Bitte den Zustand angeben – die Nummer "
                                 "steht neu und gebraucht in der Sammlung.")
    row = rows[0]
    if row["quantity"] < body.quantity:
        raise HTTPException(400, "So viele stehen gar nicht in der Sammlung.")
    rest = row["quantity"] - body.quantity
    ergebnis = update_item(row["id"], UpdateItemBody(quantity=rest), user)
    with core.db() as conn:
        conn.execute("UPDATE trades SET taken_at = ? WHERE id = ?",
                     (int(time.time()), trade_id))
    return {"ok": True, "rest": rest, "geloescht": rest == 0,
            "condition": row["condition"], "ergebnis": ergebnis}


class TradeReportBody(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    include_history: bool = True


@app.post("/api/hub/trades/{trade_id}/report")
def hub_report_trade(trade_id: str, body: TradeReportBody,
                     user: dict = Depends(current_user)):
    """Gegenüber melden. Der Verlauf wird nur mitgeschickt, wenn man das
    ausdrücklich will – er ist sonst für niemanden lesbar."""
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    with core.db() as conn:
        t = conn.execute("SELECT * FROM trades WHERE id = ?",
                         (trade_id,)).fetchone()
        if not t:
            raise HTTPException(404, "Vorgang nicht gefunden")
        msgs = conn.execute(
            "SELECT mine, body, created_at FROM trade_messages "
            "WHERE trade_id = ? ORDER BY created_at, id", (trade_id,)).fetchall()
    disclosed = None
    if body.include_history:
        me = hub.config()["display_name"] or "ich"
        disclosed = [{"von": me if m["mine"] else t["other_name"],
                      "text": m["body"], "ts": m["created_at"]} for m in msgs]
    try:
        hub.report(t["other_id"], body.reason, trade_id, disclosed)
        return {"ok": True}
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


@app.get("/api/hub/invite_quota")
def hub_invite_quota(user: dict = Depends(current_user)):
    if not hub.enabled():
        return {"used": 0, "quota": 0, "left": 0, "pending_request": None}
    try:
        return hub.invite_quota()
    except (hub.HubError, requests.RequestException):
        return {"used": 0, "quota": 0, "left": 0, "pending_request": None}


class InviteRequestBody(BaseModel):
    want: int = Field(default=3, ge=1, le=50)
    reason: str = Field(default="", max_length=300)


@app.post("/api/hub/invite_request")
def hub_invite_request(body: InviteRequestBody,
                       user: dict = Depends(current_user)):
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    try:
        return hub.request_invites(body.want, body.reason)
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


@app.post("/api/hub/invite")
def hub_invite(body: HubInviteBody, user: dict = Depends(current_user)):
    # Einladen darf jeder angemeldete Nutzer der verbundenen Instanz.
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    try:
        return hub.create_invite(body.note, body.expires_in_days)
    except hub.HubError as e:
        raise HTTPException(502, f"Hub: {e.message}")
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


# ---------------------------------------------------------------- Einkaufslisten

class ListBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ListArchiveBody(BaseModel):
    archived: bool = True


class ListItemBody(BaseModel):
    item_id: str = Field(min_length=1, max_length=60)
    item_type: str = Field(default="minifig", pattern=ITEM_TYPE_RE)
    name: str = Field(min_length=1, max_length=300)
    img_url: str = Field(default="", max_length=600, pattern=IMG_URL_RE)
    bricklink_url: str = Field(default="", max_length=600)
    year: int = Field(default=0, ge=0, le=2100)
    qty: int = Field(default=1, ge=1, le=99)
    condition: str = Field(default="used", pattern="^(new|used)$")
    paid_price: float | None = Field(default=None, ge=0)


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


class InventoriedBody(BaseModel):
    inventoried: bool


@app.post("/api/lists/{list_id}/inventoried")
def set_list_inventoried(list_id: int, body: InventoriedBody,
                         user: dict = Depends(dealer_user)):
    """Liste als inventarisiert markieren – dann zählt ihr Einkauf nicht mehr
    in der Statistik-Summe mit (bereits erfasst)."""
    with core.db() as conn:
        cur = conn.execute(
            "UPDATE shopping_lists SET inventoried = ? WHERE id = ?",
            (int(body.inventoried), list_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Liste nicht gefunden")
    return {"ok": True, "inventoried": body.inventoried}


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
            if body.paid_price is not None:
                conn.execute(
                    "UPDATE shopping_items SET paid_price = "
                    "COALESCE(paid_price, 0) + ? WHERE id = ?",
                    (round(body.paid_price, 2), ex["id"]))
            return {"ok": True, "merged": True, "qty": ex["qty"] + body.qty}
        cur = conn.execute(
            "INSERT INTO shopping_items (list_id, item_id, item_type, name, "
            "img_url, bricklink_url, year, qty, condition, paid_price, "
            "added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (list_id, body.item_id, body.item_type, body.name, body.img_url,
             body.bricklink_url, body.year or None, body.qty, body.condition,
             round(body.paid_price, 2) if body.paid_price is not None
             else None,
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
        row = conn.execute(
            "SELECT list_id, item_id AS nr, item_type FROM shopping_items "
            "WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Artikel nicht gefunden")
        conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
    fotos = _fotos_aufraeumen(row["item_type"], row["nr"])
    _maybe_autoarchive(row["list_id"])
    return {"ok": True, "photos_removed": fotos}


class OfferBody(BaseModel):
    total: float = Field(ge=0)


def _distribute_offer_shares(total: float, values: list) -> list:
    """Verteilt `total` anteilig nach Marktwert auf die Artikel.

    `values` ist der Marktwert je Artikel (Ø-Preis × Menge) in Reihenfolge.
    Artikel ohne Wert (<= 0) bekommen als Gewicht den Ø der bewerteten
    Artikel; sind alle ohne Wert, wird gleichmäßig verteilt. Der
    Rundungsrest landet beim letzten Artikel, sodass die Summe exakt
    `total` ergibt. Gibt die Anteile in derselben Reihenfolge zurück.
    """
    priced = [v for v in values if v > 0]
    fallback = (sum(priced) / len(priced)) if priced else 1.0
    weights = [(v if v > 0 else fallback) for v in values]
    total_w = sum(weights) or 1.0
    shares = []
    assigned = 0.0
    for i, w in enumerate(weights):
        if i == len(values) - 1:         # Rundungsrest am letzten Artikel
            share = round(total - assigned, 2)
        else:
            share = round(total * w / total_w, 2)
            assigned = round(assigned + share, 2)
        shares.append(share)
    return shares


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
        values = [(_unit_price(r["condition"], r["price_new"],
                               r["price_used"]) or 0) * r["qty"]
                  for r in items]
        share_vals = _distribute_offer_shares(body.total, values)
        shares = list(zip(share_vals, [r["id"] for r in items]))
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
        lst = conn.execute("SELECT name FROM shopping_lists WHERE id = ?",
                           (it["list_id"],)).fetchone()
        list_name = lst["name"] if lst else ""
        import datetime as _dt
        _d = _dt.datetime.fromtimestamp(now).strftime("%d.%m.%Y")
        note_line = f"Von Liste »{list_name}« ({_d})" if list_name else ""
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
            "item_id = ? AND item_type = ? AND condition = ?",
            (it["item_id"], it["item_type"], body.condition)).fetchone()
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
                "price_used, price_updated_at, price_data, price_region, "
                "price_currency, paid_price, "
                "paid_source, paid_at, added_by, added_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?)",
                (it["item_id"], it["item_type"], it["name"], it["img_url"],
                 it["bricklink_url"], it["qty"], body.condition, it["year"],
                 it["price_new"], it["price_used"], it["price_updated_at"],
                 it["price_data"], it["price_region"], it["price_currency"],
                 paid_val,
                 ("manual" if manual else "auto") if paid_val is not None
                 else None,
                 now if paid_val is not None else None, user["id"], now))
        # Listenname in die Notizen der betroffenen Sammlung-Zeile übernehmen
        if note_line:
            target_id = row["id"] if row else conn.execute(
                "SELECT last_insert_rowid() AS id").fetchone()["id"]
            cur = conn.execute("SELECT notes FROM collection WHERE id = ?",
                               (target_id,)).fetchone()
            notes = (cur["notes"] if cur else "") or ""
            marker = f"Von Liste »{list_name}«"
            if marker not in notes:
                merged_notes = (notes + ("\n" if notes else "")
                                + note_line).strip()[:1000]
                conn.execute("UPDATE collection SET notes = ? WHERE id = ?",
                             (merged_notes, target_id))
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
             "size": os.path.getsize(f),
             "mtime": int(os.path.getmtime(f))} for f in files]


def _unit_price(condition, price_new, price_used):
    """Ø-Stückpreis passend zum Zustand, mit Fallback auf den anderen."""
    prefer = price_new if condition == "new" else price_used
    return prefer or price_used or price_new


# ------------------------------------------------------------- Kaufbuch
#
# `collection.paid_price` ist die Summe über die Zeile. Sie wurde bisher an
# sechs Stellen einzeln fortgeschrieben – beim Anlegen, Zusammenführen,
# CSV-Import, Zustandswechsel, Bearbeiten und Verbuchen aus der Liste. Damit
# Summe und Einzelposten nicht auseinanderlaufen, geht das jetzt überall
# durch diese beiden Funktionen.

def _kauf_buchen(conn, entry_id: int, quantity: int, betrag: float | None,
                 quelle: str = "", wann: int | None = None,
                 notiz: str = "") -> None:
    """Einen Kauf ins Buch schreiben und die Summe nachziehen.

    `betrag` ist der **Gesamtpreis** dieses Kaufs, nicht der Stückpreis –
    so steht es auf dem Kassenzettel.
    """
    stueck = max(1, int(quantity or 1))
    einzel = None if betrag is None else round(float(betrag) / stueck, 4)
    conn.execute(
        "INSERT INTO purchases (entry_id, quantity, unit_price, source, "
        "bought_at, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (entry_id, stueck, einzel, quelle or "",
         wann or int(time.time()), notiz or "", int(time.time())))
    _kaufsumme_nachziehen(conn, entry_id)


def _kaufsumme_nachziehen(conn, entry_id: int) -> None:
    """`paid_price` = Summe des Kaufbuchs. Ohne Posten bleibt sie leer."""
    row = conn.execute(
        "SELECT ROUND(SUM(quantity * unit_price), 2) AS summe, "
        "MAX(bought_at) AS zuletzt, COUNT(unit_price) AS mit_preis "
        "FROM purchases WHERE entry_id = ?", (entry_id,)).fetchone()
    if not row or not row["mit_preis"]:
        conn.execute("UPDATE collection SET paid_price = NULL, paid_at = NULL "
                     "WHERE id = ?", (entry_id,))
        return
    conn.execute("UPDATE collection SET paid_price = ?, paid_at = ? "
                 "WHERE id = ?", (row["summe"], row["zuletzt"], entry_id))


def _maybe_fetch_prices_async(entry_id: int, item_id: str,
                              table: str = "collection"):
    """Preise für einen neuen/korrigierten Eintrag im Hintergrund holen."""
    if table not in PRICE_TABLES or not integrations.bricklink_enabled():
        return
    if item_id.startswith(("fig-", "manuell-", "custom-")):
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


BL_NUMMER_TTL = 30 * 24 * 3600      # ein Fehlschlag wird irgendwann neu geprüft


def _bl_nummer(item_type: str, item_id: str) -> str:
    """Unter welcher Nummer BrickLink dieses **Teil** führt.

    Die beiden Kataloge zählen Bedruckungen unterschiedlich: Der Gungan-Schild
    heißt bei Rebrickable `2586pr0028` und bei BrickLink `2586ps1`, der
    Karbonitblock `87561pr0001` bzw. `87561pb01`. Fürs Thema wird das seit
    jeher übersetzt (`_bl_teil`), beim Preis nicht – und deshalb stand bei
    genau diesen Teilen „BrickLink kennt diese Nummer nicht", obwohl der
    Katalog sie sehr wohl führt.

    Gefragt wird erst, wenn die eigene Nummer nichts ergeben hat. Das Ergebnis
    bleibt gespeichert, auch ein leeres: Sonst ginge dieselbe vergebliche
    Frage bei jedem Aufklappen erneut nach draußen.
    """
    if (item_type or "").lower() != "part":
        return ""
    jetzt = int(time.time())
    with core.db() as conn:
        row = conn.execute("SELECT bl_no, checked_at FROM bl_nummern "
                           "WHERE item_id = ?", (item_id,)).fetchone()
    if row and (row["bl_no"] or jetzt - row["checked_at"] < BL_NUMMER_TTL):
        return row["bl_no"]
    nummer = _bl_teil(item_id)[0]
    if nummer == item_id:
        nummer = ""                 # nichts Besseres gefunden
    with core.db() as conn:
        conn.execute(
            "INSERT INTO bl_nummern (item_id, bl_no, checked_at) "
            "VALUES (?, ?, ?) ON CONFLICT(item_id) DO UPDATE SET "
            "bl_no = excluded.bl_no, checked_at = excluded.checked_at",
            (item_id, nummer, jetzt))
    return nummer


def _unbekannt_meldung(item_id: str, katalog: bool = False) -> str:
    """Was man tun kann, wenn BrickLink zu einer Nummer nichts hergibt.

    Der alte Text schob es pauschal auf eine Rebrickable-Figurennummer und
    verwies auf „BrickLink-Nr. setzen“ – ein Feld, das die Oberfläche nur bei
    `fig-`, `manuell-` und `custom-` überhaupt anbietet. Bei einem Teil stand
    dort also ein falscher Grund und ein Rat, den man nicht befolgen kann.

    `katalog` unterscheidet die beiden Fälle: Beim Preis fehlen **Verkäufe**,
    beim Bild fehlt der **Eintrag**. Stand am Bild die Preis-Fassung, klang
    es, als wäre nur gerade nichts verkauft worden – dabei kennt der Katalog
    die Nummer schlicht nicht.
    """
    if item_id.startswith(("fig-", "manuell-", "custom-")):
        return ("BrickLink kennt diese Nummer nicht – vermutlich eine "
                "Rebrickable-Nummer (fig-…). „BrickLink-Nr. setzen“ nutzen.")
    if katalog:
        return ("BrickLink kennt diese Nummer nicht – auch nicht unter einer "
                "Zweitnummer.")
    return ("BrickLink führt zu dieser Nummer keine verkauften Artikel – "
            "auch nicht unter einer Zweitnummer.")


def _preise_beider_zustaende(item_type: str, item_no: str,
                             use_cache: bool = False) -> tuple:
    """(Ergebnis, Anzahl 404) für „neu" und „gebraucht".

    Alles außer 404 fliegt weiter – ein Zeitüberlauf ist keine unbekannte
    Nummer und darf nicht als solche durchgehen.
    """
    result, not_found = {}, 0
    for cond, key in (("N", "new"), ("U", "used")):
        try:
            result[key] = integrations.price_guide(item_type, item_no, cond,
                                                   use_cache=use_cache)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else 0
            if code != 404:
                raise
            not_found += 1
            result[key] = None
    return result, not_found


def _preise_mit_zweitnummer(item_type: str, item_no: str,
                            use_cache: bool = False) -> tuple:
    """Preise holen und bei einem Teil notfalls die BrickLink-Nummer nehmen.

    Zurück kommt (Ergebnis, Anzahl 404, benutzte Nummer).
    """
    result, not_found = _preise_beider_zustaende(item_type, item_no, use_cache)
    if not_found < 2:
        return result, not_found, item_no
    ersatz = _bl_nummer(item_type, item_no)
    if not ersatz:
        return result, not_found, item_no
    zweit, fehlt = _preise_beider_zustaende(item_type, ersatz, use_cache)
    if fehlt == 2:
        return result, not_found, item_no
    return zweit, fehlt, ersatz


def _fetch_and_store_prices(entry: dict, table: str = "collection",
                            source: str = "auto") -> dict:
    """Beide Zustände von BrickLink holen und Ø-Preise am Eintrag speichern."""
    assert table in PRICE_TABLES
    result, not_found, benutzt = _preise_mit_zweitnummer(
        entry["item_type"], entry["item_id"])
    if not_found == 2:
        # Hatte der Artikel schon einmal einen Preis, kannte BrickLink die
        # Nummer früher – dann ist sie jetzt umbenannt oder gelöscht worden
        # und das ist ein Hinweis wert. Ohne früheren Preis ist es dagegen
        # meist eine von Hand falsch eingetippte oder eine Rebrickable-Nummer.
        if entry.get("price_updated_at"):
            _note_item_gone(entry)
        raise LookupError(_unbekannt_meldung(entry["item_id"]))

    def avg(d):
        try:
            value = float(d["avg"]) if d and d.get("avg") else None
            return value if value else None
        except (TypeError, ValueError):
            return None

    now = int(time.time())
    payload = json.dumps({"new": result.get("new"), "used": result.get("used")})
    # Gebiet mitschreiben, damit nach einer Umstellung erkennbar ist, welche
    # Preise noch aus dem alten Gebiet stammen.
    region = integrations.price_region()
    waehrung = integrations.currency()
    with core.db() as conn:
        conn.execute(
            f"UPDATE {table} SET price_new = ?, price_used = ?, "
            "price_updated_at = ?, price_data = ?, price_region = ?, "
            "price_currency = ? WHERE id = ?",
            (avg(result.get("new")), avg(result.get("used")), now, payload,
             region, waehrung, entry["id"]))
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
            "SELECT id, ts FROM price_history WHERE item_id = ? AND "
            "item_type = ? ORDER BY ts DESC LIMIT 1",
            (entry["item_id"], entry["item_type"])).fetchone()
        if not last or now - last["ts"] > 20 * 3600:
            conn.execute(
                "INSERT INTO price_history (item_id, item_type, ts, "
                "price_new, price_used, source) VALUES (?, ?, ?, ?, ?, ?)",
                (entry["item_id"], entry["item_type"], now,
                 avg(result.get("new")), avg(result.get("used")), source))
        elif source == "manuell":
            # Innerhalb der 20h: jüngsten Punkt aktualisieren statt
            # verwerfen – so stimmt das Protokoll, das Chart bleibt sauber
            conn.execute(
                "UPDATE price_history SET ts = ?, price_new = ?, "
                "price_used = ?, source = 'manuell' WHERE id = ?",
                (now, avg(result.get("new")), avg(result.get("used")),
                 last["id"]))
    result["updated_at"] = now
    # Kam der Preis unter der BrickLink-Nummer, gehört die dazugesagt: Sonst
    # steht im Popup ein Preis, den man auf BrickLink unter der eigenen
    # Nummer nirgends wiederfindet.
    if benutzt != entry["item_id"]:
        result["bl_no"] = benutzt
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
    if entry["item_id"].startswith(("fig-", "manuell-", "custom-")):
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
        return _fetch_and_store_prices(entry, source="manuell")
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
    try:
        result, not_found, benutzt = _preise_mit_zweitnummer(
            item_type, item_no, use_cache=True)
    except requests.Timeout:
        raise HTTPException(504, "BrickLink antwortet nicht")
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        raise HTTPException(502, f"BrickLink-Fehler ({code})")
    except requests.RequestException:
        raise HTTPException(502, "BrickLink nicht erreichbar")
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    if not_found == 2:
        raise HTTPException(404, _unbekannt_meldung(item_no))
    # Kam der Preis unter der BrickLink-Nummer, gehört die dazugesagt: Sonst
    # steht im Popup ein Preis, den man auf BrickLink unter der eigenen
    # Nummer nirgends wiederfindet.
    if benutzt != item_no:
        result["bl_no"] = benutzt
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
    """Name der Installation aus der Einstellung, nicht aus einer Datei.

    Legt man die App aufs Handy, steht dort der Name aus dem Manifest – bisher
    fest „Finn's Brickfolio", auch wenn die Instanz längst anders heißt. Das
    Manifest wird deshalb erzeugt statt ausgeliefert.
    """
    wer = _owner_name()
    return JSONResponse({
        "name": f"{wer}'s Brickfolio – Deine LEGO-Sammlung",
        "short_name": f"{wer}'s Brickfolio",
        "description": "LEGO Minifiguren scannen, erkennen und "
                       "gemeinsam verwalten",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#E9EBEE",
        "theme_color": "#FFCF00",
        "lang": "de",
        "icons": [
            {"src": "/icon/192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon/512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }, media_type="application/manifest+json")


# Erzeugte Symbole je Name und Größe. Die Zeichnung ist immer dieselbe, nur
# der Schriftzug wechselt – gerechnet wird deshalb einmal und dann gemerkt.
_icon_cache: dict = {}


@app.get("/icon/{groesse}.png")
def icon(groesse: int):
    """App-Symbol mit dem Namen der Instanz statt eines festen „FINN"."""
    if groesse not in (180, 192, 512):
        raise HTTPException(404, "Nicht gefunden")
    wer = _owner_name().upper()[:12]
    schluessel = (wer, groesse)
    if schluessel not in _icon_cache:
        _icon_cache.clear()          # Name geändert: alte Größen sind hinfällig
        _icon_cache[schluessel] = _icon_bauen(wer, groesse)
    return Response(_icon_cache[schluessel], media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


def _icon_bauen(wer: str, groesse: int) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    basis = os.path.join(FRONTEND_DIR, "icons", "icon-basis.png")
    im = Image.open(basis).convert("RGBA")
    d = ImageDraw.Draw(im)
    # Größte Schrift, die in das freie Feld über dem Kopf passt.
    breite, kasten = 0, 372
    for gr in range(96, 20, -4):
        f = ImageFont.load_default(size=gr)
        l, t, r, b = d.textbbox((0, 0), wer, font=f)
        breite = r - l
        if breite <= kasten:
            break
    # Strichstärke: Die mitgelieferte Schrift ist dünner als der ursprüngliche
    # Zug – ein Rand in derselben Farbe macht sie wieder kräftig.
    d.text(((im.width - breite) / 2 - l, 105 - (b - t) / 2 - t), wer, font=f,
           fill=(255, 255, 255, 255), stroke_width=max(1, gr // 28),
           stroke_fill=(255, 255, 255, 255))
    if groesse != im.width:
        im = im.resize((groesse, groesse), Image.LANCZOS)
    raus = io.BytesIO()
    im.save(raus, "PNG")
    return raus.getvalue()


@app.get("/sw.js")
def service_worker():
    return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"),
                        media_type="application/javascript")


@app.get("/")
def index():
    """Startseite mit eingesetzter Versionsnummer.

    Die Marke `?v=` an den Adressen von app.js, style.css und fonts.css kommt
    aus APP_VERSION, statt in der Datei zu stehen. Damit erneuert jede neue
    Version den Zwischenspeicher der Browser von selbst – und niemand kann
    vergessen, die Zahl von Hand hochzusetzen. Genau darauf beruht das lange
    Cachen der versionierten Dateien (siehe cache_control).
    """
    with open(os.path.join(FRONTEND_DIR, "index.html"), encoding="utf-8") as f:
        html = (f.read().replace("__APPVERSION__", core.APP_VERSION)
                .replace("__OWNER__", _owner_name()))
    return HTMLResponse(html)
