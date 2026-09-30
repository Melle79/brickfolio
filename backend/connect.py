"""Externer Zugriff ohne Portfreigabe (Nupplo Connect).

Die Instanz hält eine **ausgehende** Leitung zu einem Vermittler offen
(Vorgabe `wss://connect.nupplo.com`). Externe Geräte verbinden sich ebenfalls
dorthin, und der Vermittler reicht durch. Am Router muss nichts freigegeben
werden, und es braucht weder Domain noch Tunnel – wie QuickConnect bei
Synology.

**Der Vermittler liest nichts mit.** Jedes Gerät spricht Ende zu Ende
verschlüsselt mit der Instanz (Noise IK, `connect_noise.py`). Den statischen
Schlüssel der Instanz kennt es aus dem QR-Code beim Koppeln; ein Vermittler,
der sich dazwischensetzen wollte, fiele schon bei der ersten Nachricht auf.

**Nur gekoppelte Geräte kommen durch.** Ein Gerät, dessen Schlüssel die
Instanz nicht kennt und das keinen gültigen Einmalcode mitbringt, bekommt
nicht einmal die Anmeldeseite zu sehen. Das ist strenger als eine
Portfreigabe, bei der die Anmeldung für das ganze Internet offen steht.
Angemeldet wird danach trotzdem wie immer – das Koppeln ersetzt kein
Passwort.

Die Anfragen gehen **im Prozess** an den Server selbst (ASGI), nicht über einen
Umweg an 127.0.0.1: So fügt niemand Kopfzeilen hinzu. Im Probelauf hängte
eine HTTP-Bibliothek von sich aus `Accept-Encoding: gzip` an, und Fotos
kamen gepackt an, obwohl niemand danach gefragt hatte.

Protokoll (Rahmen, Ströme, Nachweis): siehe `docs/CONNECT.md`.
Aus, bis ein Admin es einschaltet.
"""
import asyncio
import base64
import hashlib
import ipaddress
import json
import os
import random
import secrets
import time
import urllib.parse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

import connect_noise as noise
import core

router = APIRouter()

VORGABE_VERMITTLER = "wss://connect.nupplo.com"
KONTEXT = "nupplo-connect-v1"
PROLOG = KONTEXT.encode()

# Rahmen des Vermittlers
OEFFNEN, DATEN, SCHLIESSEN, FEHLER = 1, 2, 3, 4
# Ströme in der verschlüsselten Nutzlast
KOPF, KOERPER, ENDE, ABBRUCH = 1, 2, 3, 4
# Noise erlaubt höchstens 65 535 Byte je Nachricht – ein Stück bleibt
# darunter, samt Strom-Kopf und Tag.
STUECK = 60 * 1024
CODE_FRIST = 10 * 60
LEBENSZEICHEN = 30
# Kopfzeilen, die nur für eine Verbindung gelten.
VERBINDUNGSKOPF = {"host", "connection", "keep-alive", "transfer-encoding",
                   "content-length", "upgrade", "proxy-connection", "te"}
# Woran die Instanz erkennt, dass eine Anfrage über Connect kam: ein Eintrag
# im ASGI-Scope, keine Kopfzeile – die ließe sich von außen fälschen.
SCOPE_MARKE = "nupplo.connect"


def log(*teile):
    print("[connect]", *teile, flush=True)


# ------------------------------------------------------------- Schlüssel

def _schluesseldatei() -> str:
    # Neben dem Geheimnis der Instanz, nicht in der Datenbank: Sicherungen
    # wandern herum, und wer den Schlüssel hat, könnte sich gegenüber den
    # gekoppelten Geräten als diese Instanz ausgeben.
    return os.path.join(os.path.dirname(core.SECRET_KEY_FILE) or ".", "connect.key")


def schluessel():
    """(Ed25519 für den Vermittler, X25519 für Noise) – beim ersten Mal angelegt."""
    pfad = _schluesseldatei()
    if os.path.exists(pfad):
        with open(pfad) as f:
            d = json.load(f)
        return (Ed25519PrivateKey.from_private_bytes(base64.b64decode(d["ed25519"])),
                X25519PrivateKey.from_private_bytes(base64.b64decode(d["x25519"])))
    ed, x = Ed25519PrivateKey.generate(), X25519PrivateKey.generate()
    roh = lambda k: base64.b64encode(k.private_bytes(  # noqa: E731
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
        serialization.NoEncryption())).decode()
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    fd = os.open(pfad, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"ed25519": roh(ed), "x25519": roh(x)}, f)
    return ed, x


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _oeffentlich(k) -> bytes:
    return k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def instanz_id(ed: Ed25519PrivateKey) -> str:
    """Base32 (klein) der ersten 130 Bit des SHA-256 des öffentlichen
    Schlüssels. Selbstbeglaubigend – vergeben wird nichts."""
    return base64.b32encode(hashlib.sha256(_oeffentlich(ed)).digest()).decode().lower()[:26]


def nachweis(ed: Ed25519PrivateKey) -> str:
    """Abfrage für die Anmeldung beim Vermittler, bei jedem Versuch neu.
    Der Zufall ist Pflicht: Ed25519 unterschreibt gleichen Inhalt gleich,
    und der Vermittler nimmt jede Unterschrift nur einmal."""
    iid, zeit, zufall = instanz_id(ed), str(int(time.time())), _b64url(secrets.token_bytes(16))
    sig = ed.sign(f"{KONTEXT}\n{iid}\n{zeit}\n{zufall}".encode())
    return f"pub={_b64url(_oeffentlich(ed))}&zeit={zeit}&zufall={zufall}&sig={_b64url(sig)}"


# ------------------------------------------------------------- Datenbank

def migrieren(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS connect_geraete (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schluessel TEXT UNIQUE NOT NULL,   -- X25519 des Geräts, base64
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            gekoppelt INTEGER NOT NULL,
            zuletzt INTEGER
        );
        CREATE TABLE IF NOT EXISTS connect_codes (
            code TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            ablauf INTEGER NOT NULL
        );
    """)


# Ohne 0/O, 1/I/L – der Code wird zur Not abgetippt.
CODE_ZEICHEN = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def code_erzeugen(user_id: int) -> tuple[str, int]:
    code = "".join(secrets.choice(CODE_ZEICHEN) for _ in range(8))
    ablauf = int(time.time()) + CODE_FRIST
    with core.db() as conn:
        conn.execute("DELETE FROM connect_codes WHERE ablauf < ?", (int(time.time()),))
        conn.execute("INSERT INTO connect_codes (code, user_id, ablauf) VALUES (?, ?, ?)",
                     (code, user_id, ablauf))
    return code, ablauf


def geraet_pruefen(schluessel_b64: str, nutzlast: dict):
    """Kennt die Instanz das Gerät, oder bringt es einen gültigen Code mit?
    Gibt None zurück, wenn es durch darf, sonst den Grund. Ein Code gilt
    genau einmal und nur zehn Minuten."""
    jetzt = int(time.time())
    with core.db() as conn:
        bekannt = conn.execute("SELECT id FROM connect_geraete WHERE schluessel = ?",
                               (schluessel_b64,)).fetchone()
        if bekannt:
            conn.execute("UPDATE connect_geraete SET zuletzt = ? WHERE id = ?", (jetzt, bekannt["id"]))
            return None
        code = str(nutzlast.get("code") or "").upper().replace("-", "").strip()
        if not code:
            return "nicht-gekoppelt"
        zeile = conn.execute("SELECT user_id, ablauf FROM connect_codes WHERE code = ?",
                             (code,)).fetchone()
        if not zeile:
            return "code-ungueltig"
        conn.execute("DELETE FROM connect_codes WHERE code = ?", (code,))
        if zeile["ablauf"] < jetzt:
            return "code-abgelaufen"
        name = str(nutzlast.get("name") or "")[:60]
        conn.execute("INSERT INTO connect_geraete (schluessel, user_id, name, gekoppelt, zuletzt) "
                     "VALUES (?, ?, ?, ?, ?)", (schluessel_b64, zeile["user_id"], name, jetzt, jetzt))
    log("neues Gerät gekoppelt:", name or "(ohne Namen)")
    return None


# ------------------------------------------------------------- Rahmen

def _rahmen(art: int, kanal: int, nutzlast: bytes = b"") -> bytes:
    return bytes([art]) + kanal.to_bytes(4, "big") + nutzlast


def _strom(nummer: int, typ: int, inhalt: bytes = b"") -> bytes:
    return nummer.to_bytes(4, "big") + bytes([typ]) + inhalt


# ------------------------------------------------------------- Kanäle

class Kanal:
    """Ein externes Gerät auf einer Leitung: erst Handschlag, dann Ströme."""

    def __init__(self, verbinder, nummer: int, ip: str):
        self.v, self.nummer, self.ip = verbinder, nummer, ip
        self.hs = noise.Handschlag(False, PROLOG, verbinder.x25519)
        self.senden_c = self.empfangen_c = None
        self.geraet = None
        self.stroeme: dict[int, dict] = {}
        self.aufgaben: set = set()
        self.zu = asyncio.Event()
        # Verschlüsseln und Abschicken in einem Zug und der Reihe nach –
        # die Nummern im Noise-Nonce müssen in Sendereihenfolge ankommen.
        self.schloss = asyncio.Lock()

    async def schicken(self, nummer: int, typ: int, inhalt: bytes = b""):
        async with self.schloss:
            if self.zu.is_set():
                return
            c = self.senden_c.verschluesseln(b"", _strom(nummer, typ, inhalt))
            await self.v.senden(_rahmen(DATEN, self.nummer, c))

    async def eingang(self, daten: bytes):
        if self.senden_c is None:
            await self._handschlag(daten)
            return
        try:
            klar = self.empfangen_c.entschluesseln(b"", daten)
        except noise.NoiseFehler:
            await self.schliessen(melden=True)
            return
        nummer, typ, inhalt = int.from_bytes(klar[:4], "big"), klar[4], klar[5:]
        if typ == KOPF:
            self.stroeme[nummer] = {"kopf": json.loads(inhalt), "koerper": bytearray()}
        elif typ == KOERPER and nummer in self.stroeme:
            self.stroeme[nummer]["koerper"] += inhalt
        elif typ == ENDE and nummer in self.stroeme:
            anfrage = self.stroeme.pop(nummer)
            t = asyncio.create_task(self.v.bearbeiten(self, nummer, anfrage["kopf"], bytes(anfrage["koerper"])))
            self.aufgaben.add(t)
            t.add_done_callback(self.aufgaben.discard)
        elif typ == ABBRUCH:
            self.stroeme.pop(nummer, None)

    async def _handschlag(self, daten: bytes):
        try:
            nutzlast = json.loads(self.hs.erste_lesen(daten) or b"{}")
            if not isinstance(nutzlast, dict):
                raise ValueError
        except (noise.NoiseFehler, ValueError):
            # Kein gültiger Handschlag: Wer das schickt, kennt den Schlüssel
            # der Instanz nicht (falscher QR-Code oder ein Fremder).
            await self.schliessen(melden=True)
            return
        grund = await asyncio.to_thread(geraet_pruefen, base64.b64encode(self.hs.rs).decode(), nutzlast)
        antwort = {"ok": True} if grund is None else {"fehler": grund}
        await self.v.senden(_rahmen(DATEN, self.nummer, self.hs.zweite_schreiben(json.dumps(antwort).encode())))
        if grund:
            await self.schliessen(melden=True)
            return
        self.geraet = base64.b64encode(self.hs.rs).decode()
        self.senden_c, self.empfangen_c = self.hs.teilen()

    async def schliessen(self, melden: bool):
        if self.zu.is_set():
            return
        self.zu.set()
        self.v.kanaele.pop(self.nummer, None)
        for t in list(self.aufgaben):
            t.cancel()
        if melden:
            await self.v.senden(_rahmen(SCHLIESSEN, self.nummer))


# ------------------------------------------------------------- Verbinder

class Verbinder:
    def __init__(self):
        self.app = None
        self.loop = None
        self.aufgabe = None
        self.ws = None
        self.kanaele: dict[int, Kanal] = {}
        self.zustand = {"verbunden": False, "seit": None, "fehler": None}
        self.ed25519 = self.x25519 = None

    # --- Steuerung (aus Threads der Endpunkte aufrufbar)

    def einrichten(self, app):
        self.app, self.loop = app, asyncio.get_running_loop()
        self.ed25519, self.x25519 = schluessel()
        if core.get_setting("connect_an") == "1":
            self._starten()

    def umschalten(self, an: bool):
        core.set_setting("connect_an", "1" if an else "0")
        if self.loop:
            self.loop.call_soon_threadsafe(self._starten if an else self._stoppen)

    def _starten(self):
        if self.aufgabe is None or self.aufgabe.done():
            self.aufgabe = self.loop.create_task(self._laufen())

    def _stoppen(self):
        if self.aufgabe:
            self.aufgabe.cancel()
        self.aufgabe = None

    @property
    def vermittler(self) -> str:
        return (os.environ.get("CONNECT_VERMITTLER") or core.get_setting("connect_vermittler")
                or VORGABE_VERMITTLER).rstrip("/")

    def entkoppelt(self, geraet: str):
        """Offene Kanäle eines gerade entfernten Geräts sofort schließen –
        sonst liefe eine bestehende Verbindung weiter, bis sie von selbst endet."""
        if not self.loop:
            return

        async def zu():
            for k in [k for k in self.kanaele.values() if k.geraet == geraet]:
                await k.schliessen(melden=True)
        asyncio.run_coroutine_threadsafe(zu(), self.loop)

    # --- Leitung

    async def senden(self, daten: bytes):
        if self.ws is not None:
            try:
                await self.ws.send(daten)
            except Exception:
                pass            # Leitung weg – das merkt `_laufen`

    async def _laufen(self):
        import websockets
        pause = 1.0
        iid = instanz_id(self.ed25519)
        while True:
            adresse = f"{self.vermittler}/v1/instanz/{iid}?{nachweis(self.ed25519)}"
            try:
                async with websockets.connect(adresse, max_size=2 * 1024 * 1024,
                                              ping_interval=None, open_timeout=20) as ws:
                    self.ws = ws
                    self.zustand = {"verbunden": True, "seit": int(time.time()), "fehler": None}
                    log("verbunden mit", self.vermittler)
                    pause = 1.0
                    puls = asyncio.create_task(self._lebenszeichen(ws))
                    try:
                        await self._lesen(ws)
                    finally:
                        puls.cancel()
                    grund = f"Leitung geschlossen ({ws.close_code} {ws.close_reason or ''})".strip()
            except asyncio.CancelledError:
                await self._aufraeumen()
                self.zustand = {"verbunden": False, "seit": None, "fehler": None}
                log("ausgeschaltet")
                raise
            except websockets.InvalidStatus as e:
                # Der Vermittler nennt den Grund („nicht-freigeschaltet“,
                # „uhrzeit“ …) – genau das soll der Admin lesen.
                grund = f"abgewiesen: {e.response.body.decode(errors='replace') or e.response.status_code}"
            except Exception as e:
                grund = f"{type(e).__name__}: {e}"
            await self._aufraeumen()
            self.zustand = {"verbunden": False, "seit": None, "fehler": grund}
            # Wachsende Pause mit Zufall: Nach einem Ausfall des Vermittlers
            # sollen nicht alle Instanzen im selben Augenblick anklopfen.
            warten = pause + random.random() * pause / 2
            log(grund, f"– neuer Versuch in {warten:.0f} s")
            await asyncio.sleep(warten)
            pause = min(pause * 2, 300)

    async def _aufraeumen(self):
        self.ws = None
        for k in list(self.kanaele.values()):
            await k.schliessen(melden=False)
        self.kanaele.clear()

    async def _lebenszeichen(self, ws):
        # „ping“ als Text beantwortet der Vermittler, ohne aufzuwachen. Hält
        # NAT-Einträge wach – und bleibt „pong“ aus, ist die Leitung tot,
        # auch wenn TCP es noch nicht gemerkt hat.
        while True:
            self._pong = False
            await ws.send("ping")
            await asyncio.sleep(LEBENSZEICHEN)
            if not self._pong:
                await ws.close(1011, "kein pong")
                return

    async def _lesen(self, ws):
        async for r in ws:
            if isinstance(r, str):
                self._pong = self._pong or r == "pong"
                continue
            if len(r) < 5:
                continue
            art, nummer, nutzlast = r[0], int.from_bytes(r[1:5], "big"), r[5:]
            if art == OEFFNEN:
                try:
                    ip = str(ipaddress.ip_address(json.loads(nutzlast or b"{}").get("ip", "")))
                except ValueError:
                    ip = ""
                self.kanaele[nummer] = Kanal(self, nummer, ip)
            elif art == SCHLIESSEN:
                k = self.kanaele.get(nummer)
                if k:
                    await k.schliessen(melden=False)
            elif art == DATEN and nummer in self.kanaele:
                await self.kanaele[nummer].eingang(nutzlast)

    # --- Anfragen an den eigenen Server, im Prozess

    async def bearbeiten(self, kanal: Kanal, nummer: int, kopf: dict, koerper: bytes):
        weg = str(kopf.get("w") or "/")
        pfad, _, abfrage = weg.partition("?")
        kopfzeilen = [(str(n).lower().encode("latin-1"), str(w).encode("latin-1"))
                      for n, w in (kopf.get("k") or {}).items()
                      if str(n).lower() not in VERBINDUNGSKOPF]
        kopfzeilen.append((b"host", b"nupplo-connect"))
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": str(kopf.get("m") or "GET").upper(), "scheme": "https",
            "path": urllib.parse.unquote(pfad), "raw_path": pfad.encode(),
            "query_string": abfrage.encode(), "root_path": "",
            "headers": kopfzeilen,
            # Die Adresse des Geräts, wie sie beim Vermittler ankam – sonst
            # bremst die Sperre gegen Passwortraten alle Geräte gemeinsam.
            "client": (kanal.ip or "0.0.0.0", 0),
            "server": ("nupplo-connect", 443),
            SCOPE_MARKE: True,
        }
        gelesen = False

        async def empfangen():
            nonlocal gelesen
            if not gelesen:
                gelesen = True
                return {"type": "http.request", "body": koerper, "more_body": False}
            await kanal.zu.wait()
            return {"type": "http.disconnect"}

        angefangen = False

        async def senden(nachricht):
            nonlocal angefangen
            if nachricht["type"] == "http.response.start":
                angefangen = True
                k = {}
                for n, w in nachricht.get("headers", []):
                    name = n.decode("latin-1")
                    k[name] = (k[name] + ", " if name in k else "") + w.decode("latin-1")
                await kanal.schicken(nummer, KOPF, json.dumps({"s": nachricht["status"], "k": k}).encode())
            elif nachricht["type"] == "http.response.body":
                inhalt = nachricht.get("body", b"")
                for i in range(0, len(inhalt), STUECK):
                    await kanal.schicken(nummer, KOERPER, inhalt[i:i + STUECK])
                if not nachricht.get("more_body"):
                    await kanal.schicken(nummer, ENDE)

        try:
            await self.app(scope, empfangen, senden)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log("Anfrage fehlgeschlagen:", type(e).__name__, e)
            if not angefangen:
                await kanal.schicken(nummer, KOPF, json.dumps({"s": 500, "k": {}}).encode())
                await kanal.schicken(nummer, ENDE)
            else:
                await kanal.schicken(nummer, ABBRUCH)


verbinder = Verbinder()


def ueber_connect(request: Request) -> bool:
    return bool(request.scope.get(SCOPE_MARKE))


# ------------------------------------------------------------- Endpunkte

def _benutzer():
    import main
    return main.current_user


def _admin():
    import main
    return main.admin_user


def _heimnetz_adresse(request: Request) -> str | None:
    """Unter welcher Adresse das Gerät die Instanz zu Hause direkt erreicht –
    geraten aus der Adresse, über die gerade die Web-App offen ist. Nur,
    wenn das eine im Heimnetz ist; eine öffentliche nützt dem Gerät nichts
    (dann ginge es ohnehin über den Vermittler)."""
    host = request.url.hostname or ""
    try:
        if ipaddress.ip_address(host).is_private:
            return str(request.base_url).rstrip("/")
    except ValueError:
        if host.endswith(".local") or ("." not in host and host not in ("", "localhost")):
            return str(request.base_url).rstrip("/")
    return None


@router.get("/api/connect")
def connect_status(user: dict = Depends(_benutzer())):
    d = {"an": core.get_setting("connect_an") == "1",
         "nur_2fa": core.get_setting("connect_nur_2fa") == "1", **verbinder.zustand}
    if user["is_admin"]:
        d["instanz_id"] = instanz_id(verbinder.ed25519) if verbinder.ed25519 else None
        d["vermittler"] = verbinder.vermittler
    return d


class ConnectBody(BaseModel):
    an: bool | None = None
    nur_2fa: bool | None = None


@router.post("/api/connect")
def connect_umschalten(body: ConnectBody, user: dict = Depends(_admin())):
    if body.nur_2fa is not None:
        core.set_setting("connect_nur_2fa", "1" if body.nur_2fa else "0")
    if body.an is not None:
        verbinder.umschalten(body.an)
    return {"an": core.get_setting("connect_an") == "1",
            "nur_2fa": core.get_setting("connect_nur_2fa") == "1"}


@router.post("/api/connect/koppeln")
def connect_koppeln(request: Request, user: dict = Depends(_benutzer())):
    """Einmalcode und QR-Inhalt zum Koppeln eines Geräts – gilt zehn Minuten."""
    if core.get_setting("connect_an") != "1":
        raise HTTPException(409, "Der externe Zugriff ohne Portfreigabe ist aus")
    code, ablauf = code_erzeugen(user["id"])
    teile = {"i": instanz_id(verbinder.ed25519), "k": _b64url(_oeffentlich(verbinder.x25519)), "c": code}
    heim = _heimnetz_adresse(request)
    if heim:
        teile["l"] = heim
    if verbinder.vermittler != VORGABE_VERMITTLER:
        teile["r"] = verbinder.vermittler
    link = "nupplo-connect://v1?" + urllib.parse.urlencode(teile)
    return {"code": f"{code[:4]}-{code[4:]}", "ablauf": ablauf, "link": link}


@router.get("/api/connect/koppeln.svg")
def connect_koppeln_qr(link: str, user: dict = Depends(_benutzer())):
    """Der QR-Code zum Link aus `/api/connect/koppeln` – als eigener Aufruf,
    damit die Oberfläche ihn wie jedes Bild einbinden kann."""
    if not link.startswith("nupplo-connect://"):
        raise HTTPException(400, "Kein Kopplungslink")
    import io

    import segno
    puffer = io.BytesIO()
    # Wie beim Zwei-Faktor-Code: viewBox statt fester Größe, Rand nach Norm,
    # weißer Grund – sonst abgeschnitten oder dunkel auf dunkel.
    segno.make(link, error="m").save(puffer, kind="svg", scale=5, border=4,
                                     omitsize=True, light="#fff")
    return Response(puffer.getvalue(), media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"})


@router.get("/api/connect/geraete")
def connect_geraete(user: dict = Depends(_benutzer())):
    with core.db() as conn:
        zeilen = conn.execute(
            "SELECT g.id, g.name, g.gekoppelt, g.zuletzt, g.user_id, u.username "
            "FROM connect_geraete g LEFT JOIN users u ON u.id = g.user_id "
            + ("" if user["is_admin"] else "WHERE g.user_id = ? ")
            + "ORDER BY g.gekoppelt DESC", () if user["is_admin"] else (user["id"],)).fetchall()
    return [{"id": z["id"], "name": z["name"], "gekoppelt": z["gekoppelt"], "zuletzt": z["zuletzt"],
             "benutzer": z["username"], "eigenes": z["user_id"] == user["id"]} for z in zeilen]


@router.delete("/api/connect/geraete/{geraet_id}")
def connect_geraet_entfernen(geraet_id: int, user: dict = Depends(_benutzer())):
    """Entkoppeln: Das Gerät kommt danach nicht mehr durch, auch nicht bis
    zur Anmeldeseite. Eigene Geräte darf jeder entfernen, fremde nur ein Admin."""
    with core.db() as conn:
        z = conn.execute("SELECT user_id, schluessel FROM connect_geraete WHERE id = ?",
                         (geraet_id,)).fetchone()
        if not z:
            raise HTTPException(404, "Gerät nicht gefunden")
        if z["user_id"] != user["id"] and not user["is_admin"]:
            raise HTTPException(403, "Nur eigene Geräte")
        conn.execute("DELETE FROM connect_geraete WHERE id = ?", (geraet_id,))
    verbinder.entkoppelt(z["schluessel"])
    return {"ok": True}
