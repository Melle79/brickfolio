"""Externer Zugriff ohne Portfreigabe (backend/connect.py).

Ein externes Gerät erreicht die Instanz über einen Vermittler, bei dem sich
beide Seiten von innen melden. Hier geprüft ohne Netz: Die Tests spielen das
Gerät (Noise-Initiator) und schieben seine Rahmen direkt in den Verbinder;
was der Verbinder dem Vermittler schicken würde, landet in einer Liste.

Worauf es ankommt:
- **Fremde kommen nicht durch** – nicht einmal bis zur Anmeldeseite.
- **Ein Code gilt einmal und zehn Minuten.**
- **Anfragen gehen unverändert durch.** Im Probelauf (30.09.2026) hängte eine
  HTTP-Bibliothek `Accept-Encoding: gzip` an, und Fotos kamen gepackt an.
- **Entkoppeln wirkt sofort.**
"""
import asyncio
import base64
import json
import os
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from fastapi.testclient import TestClient

import connect
import connect_noise as noise
import core
import main

DATEN = os.path.join(os.path.dirname(__file__), "daten")


@pytest.fixture
def instanz(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "connect.db"))
    monkeypatch.setattr(core, "SECRET_KEY_FILE", str(tmp_path / "secret.key"))
    core.init_db()
    with core.db() as conn:
        for n, (name, admin) in enumerate((("chefin", 1), ("gast", 0)), start=1):
            conn.execute("INSERT INTO users (id, username, password_hash, is_admin, is_dealer, "
                         "created_at) VALUES (?, ?, 'x', ?, 0, ?)", (n, name, admin, int(time.time())))
    core.set_setting("connect_an", "1")
    v = connect.verbinder
    v.ed25519, v.x25519 = connect.schluessel()
    v.app, v.loop, v.kanaele = main.app, None, {}
    yield v


def _client(nr, name, admin):
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(nr, name, admin)
    return c


class Leitung:
    """Was der Verbinder dem Vermittler schickt."""

    def __init__(self):
        self.raus = []

    async def send(self, daten):
        self.raus.append(daten)


class Geraet:
    """Spielt ein externes Gerät auf einem Kanal."""

    def __init__(self, v, schluessel=None, kanal=7, ip="203.0.113.9"):
        self.v, self.kanal = v, kanal
        self.s = schluessel or X25519PrivateKey.generate()
        self.hs = noise.Handschlag(True, connect.PROLOG, self.s, connect._oeffentlich(v.x25519))
        v.ws = self.leitung = Leitung()
        v.kanaele[kanal] = connect.Kanal(v, kanal, ip)

    async def koppeln(self, nutzlast):
        await self.v.kanaele[self.kanal].eingang(self.hs.erste_schreiben(json.dumps(nutzlast).encode()))
        antwort = self.leitung.raus.pop(0)
        assert antwort[0] == connect.DATEN
        ergebnis = json.loads(self.hs.zweite_lesen(antwort[5:]))
        if "ok" in ergebnis:
            self.senden, self.empfangen = self.hs.teilen()
        return ergebnis

    async def anfrage(self, methode, weg, kopfzeilen=None, koerper=b"", nummer=1):
        k = self.v.kanaele[self.kanal]
        for typ, inhalt in ((connect.KOPF, json.dumps({"m": methode, "w": weg, "k": kopfzeilen or {}}).encode()),
                            (connect.KOERPER, koerper), (connect.ENDE, b"")):
            if typ == connect.KOERPER and not koerper:
                continue
            await k.eingang(self.senden.verschluesseln(b"", connect._strom(nummer, typ, inhalt)))
        for _ in range(200):                    # die Anfrage läuft als eigene Aufgabe
            if k.aufgaben:
                await asyncio.gather(*k.aufgaben, return_exceptions=True)
            if any(r[0] == connect.DATEN for r in self.leitung.raus):
                break
            await asyncio.sleep(0.01)
        kopf, koerper = None, b""
        for r in self.leitung.raus:
            if r[0] != connect.DATEN:
                continue
            klar = self.empfangen.entschluesseln(b"", r[5:])
            typ, inhalt = klar[4], klar[5:]
            if typ == connect.KOPF:
                kopf = json.loads(inhalt)
            elif typ == connect.KOERPER:
                koerper += inhalt
        self.leitung.raus.clear()
        return kopf, koerper


def lauf(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------- Koppeln

def test_fremdes_geraet_kommt_nicht_bis_zur_anmeldung(instanz):
    """Ohne Kopplung gibt es keine Ströme – auch keine Anmeldeseite."""
    async def ablauf():
        g = Geraet(instanz)
        ergebnis = await g.koppeln({})
        assert ergebnis == {"fehler": "nicht-gekoppelt"}
        assert g.leitung.raus[-1][0] == connect.SCHLIESSEN
        assert 7 not in instanz.kanaele
    lauf(ablauf())


def test_falscher_schluessel_der_instanz_scheitert_sofort(instanz):
    """Wer einen fremden QR-Code (anderen Schlüssel) mitbringt, erreicht nichts."""
    async def ablauf():
        g = Geraet(instanz)
        g.hs = noise.Handschlag(True, connect.PROLOG, g.s, connect._oeffentlich(X25519PrivateKey.generate()))
        await instanz.kanaele[7].eingang(g.hs.erste_schreiben(b"{}"))
        assert [r[0] for r in g.leitung.raus] == [connect.SCHLIESSEN]
    lauf(ablauf())


def test_code_koppelt_genau_einmal(instanz):
    code = _client(1, "chefin", True).post("/api/connect/koppeln").json()["code"]

    async def ablauf():
        erstes = Geraet(instanz)
        assert await erstes.koppeln({"code": code, "name": "Tablet"}) == {"ok": True}
        zweites = Geraet(instanz, kanal=8)
        assert await zweites.koppeln({"code": code}) == {"fehler": "code-ungueltig"}
        # Das gekoppelte Gerät kommt beim nächsten Mal ohne Code durch.
        wieder = Geraet(instanz, schluessel=erstes.s, kanal=9)
        assert await wieder.koppeln({}) == {"ok": True}
    lauf(ablauf())
    geraete = _client(1, "chefin", True).get("/api/connect/geraete").json()
    assert [(g["name"], g["benutzer"]) for g in geraete] == [("Tablet", "chefin")]


def test_abgelaufener_code(instanz, monkeypatch):
    code = _client(2, "gast", False).post("/api/connect/koppeln").json()["code"]
    echt = time.time
    monkeypatch.setattr(connect.time, "time", lambda: echt() + connect.CODE_FRIST + 5)

    async def ablauf():
        assert await Geraet(instanz).koppeln({"code": code}) == {"fehler": "code-abgelaufen"}
    lauf(ablauf())


def test_entkoppeln_wirkt_sofort(instanz):
    chefin = _client(1, "chefin", True)
    code = chefin.post("/api/connect/koppeln").json()["code"]

    async def koppeln():
        g = Geraet(instanz)
        assert await g.koppeln({"code": code}) == {"ok": True}
        return g.s
    s = lauf(koppeln())
    gid = chefin.get("/api/connect/geraete").json()[0]["id"]
    assert _client(2, "gast", False).delete(f"/api/connect/geraete/{gid}").status_code == 403
    assert chefin.delete(f"/api/connect/geraete/{gid}").status_code == 200

    async def wieder():
        assert await Geraet(instanz, schluessel=s).koppeln({}) == {"fehler": "nicht-gekoppelt"}
    lauf(wieder())


# ------------------------------------------------------------- Anfragen

def _gekoppelt(instanz):
    code = _client(1, "chefin", True).post("/api/connect/koppeln").json()["code"]

    async def ablauf():
        g = Geraet(instanz)
        assert await g.koppeln({"code": code}) == {"ok": True}
        return g
    return code, ablauf


def test_anfrage_mit_anmeldung_geht_durch(instanz):
    _, koppeln = _gekoppelt(instanz)
    token = core.create_token(1, "chefin", True)

    async def ablauf():
        g = await koppeln()
        kopf, koerper = await g.anfrage("GET", "/api/sync/info", {"Authorization": f"Bearer {token}"})
        assert kopf["s"] == 200
        assert "protocol" in json.loads(koerper)
        kopf, _ = await g.anfrage("GET", "/api/sync/info", {"Authorization": "Bearer falsch"}, nummer=2)
        assert kopf["s"] == 401
    lauf(ablauf())


def test_kopfzeilen_gehen_unveraendert_durch(instanz):
    """Probelauf 30.09.2026: Der Verbinder fügte `Accept-Encoding: gzip` an,
    und die Instanz packte Antworten, um die niemand gebeten hatte."""
    _, koppeln = _gekoppelt(instanz)

    async def ablauf():
        g = await koppeln()
        kopf, koerper = await g.anfrage("GET", "/static/app.js")
        assert kopf["s"] == 200
        assert "content-encoding" not in kopf["k"]
        assert koerper.startswith(b"/*") or b"function" in koerper[:2000]
        kopf, gepackt = await g.anfrage("GET", "/static/app.js", {"Accept-Encoding": "gzip"}, nummer=2)
        assert kopf["k"].get("content-encoding") == "gzip"
        assert len(gepackt) < len(koerper)
        # Große Antworten kommen in Stücken unter der Noise-Grenze.
        assert len(koerper) > connect.STUECK
    lauf(ablauf())


def test_hochladen_in_stuecken(instanz):
    """Ein Körper über mehrere Stücke kommt vollständig an (eigenes Foto)."""
    _, koppeln = _gekoppelt(instanz)
    token = core.create_token(1, "chefin", True)
    import io

    from PIL import Image
    puffer = io.BytesIO()
    Image.frombytes("RGB", (600, 600), os.urandom(600 * 600 * 3)).save(puffer, "JPEG", quality=95)
    bild = puffer.getvalue()
    assert len(bild) > 2 * connect.STUECK
    grenze = "----nupplo"
    koerper = (f"--{grenze}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.jpg\"\r\n"
               f"Content-Type: image/jpeg\r\n\r\n").encode() + bild + f"\r\n--{grenze}--\r\n".encode()

    async def ablauf():
        g = await koppeln()
        k = g.v.kanaele[g.kanal]
        await k.eingang(g.senden.verschluesseln(b"", connect._strom(1, connect.KOPF, json.dumps(
            {"m": "POST", "w": "/api/upload_image",
             "k": {"Authorization": f"Bearer {token}",
                   "Content-Type": f"multipart/form-data; boundary={grenze}"}}).encode())))
        for i in range(0, len(koerper), connect.STUECK):
            await k.eingang(g.senden.verschluesseln(b"", connect._strom(1, connect.KOERPER,
                                                                        koerper[i:i + connect.STUECK])))
        await k.eingang(g.senden.verschluesseln(b"", connect._strom(1, connect.ENDE)))
        await asyncio.gather(*k.aufgaben)
        antworten = [g.empfangen.entschluesseln(b"", r[5:]) for r in g.leitung.raus if r[0] == connect.DATEN]
        kopf = json.loads(antworten[0][5:])
        assert kopf["s"] == 200
        assert json.loads(b"".join(a[5:] for a in antworten[1:]))["url"].startswith("/uploads/")
    lauf(ablauf())


def test_als_externer_weg_gemerkt(instanz):
    """Über den Vermittler zählt als „von außen genutzt“ – aber nicht als
    „ohne Zugangsschutz“: Es kommen nur gekoppelte Geräte durch."""
    _, koppeln = _gekoppelt(instanz)
    token = core.create_token(1, "chefin", True)
    main._extern_geschrieben.update({"mit": 0.0, "ohne": 0.0, "connect": 0.0})

    async def ablauf():
        g = await koppeln()
        kopf, _ = await g.anfrage("GET", "/api/sync/info", {"Authorization": f"Bearer {token}"})
        assert kopf["s"] == 200
    lauf(ablauf())
    assert core.get_setting("extern_weg") == "connect"
    assert core.get_setting("extern_connect")
    assert not core.get_setting("extern_ohne_access")


# ------------------------------------------------------------- Endpunkte

def test_nur_admins_schalten_um(instanz):
    assert _client(2, "gast", False).post("/api/connect", json={"an": False}).status_code == 403
    assert _client(1, "chefin", True).post("/api/connect", json={"an": False}).status_code == 200
    assert core.get_setting("connect_an") == "0"
    assert _client(1, "chefin", True).post("/api/connect/koppeln").status_code == 409


def test_kopplungslink_und_qr(instanz):
    c = _client(1, "chefin", True)
    d = c.post("/api/connect/koppeln", headers={"Host": "192.168.0.199:8300"}).json()
    import urllib.parse
    teile = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(d["link"]).query))
    assert teile["i"] == connect.instanz_id(instanz.ed25519)
    assert base64.urlsafe_b64decode(teile["k"] + "=") == connect._oeffentlich(instanz.x25519)
    assert teile["c"] == d["code"].replace("-", "")
    assert teile["l"] == "http://192.168.0.199:8300"
    assert "r" not in teile
    svg = c.get("/api/connect/koppeln.svg", params={"link": d["link"]})
    assert svg.headers["content-type"].startswith("image/svg+xml")
    # Von einer öffentlichen Adresse aus gibt es keine Heimnetz-Adresse.
    d = c.post("/api/connect/koppeln", headers={"Host": "sammlung.example.com"}).json()
    assert "l=" not in d["link"]


# ------------------------------------------------------------- Kryptografie

@pytest.mark.parametrize("datei", ["noise_ik_cacophony.json", "noise_ik_nupplo.json"])
def test_noise_vektoren(datei):
    """Offizielle Vektoren und ein Mitschnitt, den die Gegenseite ebenso
    nachspielt – rechnet eine Seite anders, verbindet sich nichts."""
    def privat(h):
        return X25519PrivateKey.from_private_bytes(bytes.fromhex(h))
    with open(os.path.join(DATEN, datei)) as f:
        for v in json.load(f)["vektoren"]:
            i = noise.Handschlag(True, bytes.fromhex(v["init_prologue"]), privat(v["init_static"]),
                                 bytes.fromhex(v["init_remote_static"]), privat(v["init_ephemeral"]))
            r = noise.Handschlag(False, bytes.fromhex(v["resp_prologue"]), privat(v["resp_static"]),
                                 fluechtig=privat(v["resp_ephemeral"]))
            m = v["messages"]
            c = i.erste_schreiben(bytes.fromhex(m[0]["payload"]))
            assert c.hex() == m[0]["ciphertext"]
            assert r.erste_lesen(c).hex() == m[0]["payload"]
            c = r.zweite_schreiben(bytes.fromhex(m[1]["payload"]))
            assert c.hex() == m[1]["ciphertext"]
            assert i.zweite_lesen(c).hex() == m[1]["payload"]
            assert i.h.hex() == v["handshake_hash"]
            (i_s, i_e), (r_s, r_e) = i.teilen(), r.teilen()
            for n, nachricht in enumerate(m[2:]):
                von, nach = (i_s, r_e) if n % 2 == 0 else (r_s, i_e)
                c = von.verschluesseln(b"", bytes.fromhex(nachricht["payload"]))
                assert c.hex() == nachricht["ciphertext"]
                assert nach.entschluesseln(b"", c).hex() == nachricht["payload"]


def test_nachweis_fuer_den_vermittler(instanz):
    """So, wie der Vermittler ihn prüft: frische Zeit, Zufall, Unterschrift
    über „nupplo-connect-v1\\n<id>\\n<zeit>\\n<zufall>“."""
    import urllib.parse
    teile = dict(urllib.parse.parse_qsl(connect.nachweis(instanz.ed25519)))
    pub = base64.urlsafe_b64decode(teile["pub"] + "=")
    iid = connect.instanz_id(instanz.ed25519)
    Ed25519PublicKey.from_public_bytes(pub).verify(
        base64.urlsafe_b64decode(teile["sig"] + "=="),
        f"nupplo-connect-v1\n{iid}\n{teile['zeit']}\n{teile['zufall']}".encode())
    assert abs(int(teile["zeit"]) - time.time()) < 5
    assert teile["zufall"] != dict(urllib.parse.parse_qsl(connect.nachweis(instanz.ed25519)))["zufall"]


# ------------------------------------------------------------- Nur mit 2FA

def test_nur_mit_zweitem_faktor(instanz):
    """Am 30.09.2026 gemeldet: Über den Vermittler kam keine Code-Abfrage.
    Das Konto hatte keinen zweiten Faktor, und Cloudflare Access – sonst vor
    der Web-App – liegt auf diesem Weg nicht dazwischen. Mit dem Schalter
    kommt über den Vermittler nur herein, wer einen zweiten Faktor hat; bei
    jeder Anfrage, auch mit einer Sitzung aus dem Heimnetz."""
    chefin = _client(1, "chefin", True)
    assert chefin.post("/api/connect", json={"nur_2fa": True}).json()["nur_2fa"] is True
    code = chefin.post("/api/connect/koppeln").json()["code"]
    token = core.create_token(1, "chefin", True)   # z. B. zu Hause angemeldet

    async def ablauf():
        g = Geraet(instanz)
        assert await g.koppeln({"code": code}) == {"ok": True}
        kopf, koerper = await g.anfrage("GET", "/api/sync/info", {"Authorization": f"Bearer {token}"})
        assert kopf["s"] == 403
        assert "zweitem Faktor" in json.loads(koerper)["detail"]
        # Mit eingerichtetem zweiten Faktor geht es.
        with core.db() as conn:
            conn.execute("UPDATE users SET totp_secret = 'JBSWY3DPEHPK3PXP' WHERE id = 1")
        kopf, _ = await g.anfrage("GET", "/api/sync/info", {"Authorization": f"Bearer {token}"}, nummer=2)
        assert kopf["s"] == 200
    lauf(ablauf())
    # Im Heimnetz ändert der Schalter nichts.
    assert _client(2, "gast", False).get("/api/sync/info").status_code == 200


def test_anmelden_ohne_zweiten_faktor_ueber_connect(instanz):
    with core.db() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = 2", (core.hash_password("geheim1234"),))
    core.set_setting("connect_nur_2fa", "1")
    code = _client(2, "gast", False).post("/api/connect/koppeln").json()["code"]

    async def ablauf():
        g = Geraet(instanz)
        assert await g.koppeln({"code": code}) == {"ok": True}
        kopf, koerper = await g.anfrage("POST", "/api/login", {"Content-Type": "application/json"},
                                        json.dumps({"username": "gast", "password": "geheim1234"}).encode())
        assert kopf["s"] == 403
        assert "token" not in json.loads(koerper)
    lauf(ablauf())
    assert TestClient(main.app).post("/api/login", json={"username": "gast", "password": "geheim1234"}).status_code == 200


def test_nur_admins_setzen_nur_2fa(instanz):
    assert _client(2, "gast", False).post("/api/connect", json={"nur_2fa": True}).status_code == 403
    assert core.get_setting("connect_nur_2fa") != "1"
