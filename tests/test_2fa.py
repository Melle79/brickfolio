"""Zwei-Faktor-Anmeldung: Ablauf, Notausgänge und die Fallstricke.

Der wichtigste Test ist der, dass die Zwischenmarke aus dem ersten Schritt
keine Sitzung ist – sonst wäre die ganze Prüfung wirkungslos.
"""
import json
import time

import pytest

import core
import main
import totp
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def frischer_zaehler():
    main._login_fails.clear()
    yield
    main._login_fails.clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "2fa.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin, "
                     "created_at) VALUES ('anna', ?, 1, ?)",
                     (core.hash_password("geheim12345"), now))
    return TestClient(main.app)


def anmelden(c, pw="geheim12345"):
    return c.post("/api/login", json={"username": "anna", "password": pw})


def einrichten(c):
    """Vollständige Einrichtung; gibt (Schlüssel, Rettungscodes) zurück."""
    token = anmelden(c).json()["token"]
    c.headers["Authorization"] = "Bearer " + token
    s = c.post("/api/me/2fa/start", json={"password": "geheim12345"}).json()
    r = c.post("/api/me/2fa/confirm",
               json={"code": totp.code_jetzt(s["secret"])})
    assert r.status_code == 200
    # Das Einschalten beendet alle Sitzungen; weiter geht es mit der
    # frischen, die der Server beilegt.
    c.headers["Authorization"] = "Bearer " + r.json()["token"]
    return s["secret"], r.json()["recovery_codes"]


def test_ohne_zweiten_faktor_meldet_man_sich_wie_bisher_an(client):
    d = anmelden(client).json()
    assert "token" in d and "totp_required" not in d


def test_einrichtung_verlangt_das_passwort(client):
    client.headers["Authorization"] = "Bearer " + anmelden(client).json()["token"]
    r = client.post("/api/me/2fa/start", json={"password": "falsch"})
    assert r.status_code == 401


def test_einschalten_erst_nach_gueltigem_code(client):
    client.headers["Authorization"] = "Bearer " + anmelden(client).json()["token"]
    s = client.post("/api/me/2fa/start",
                    json={"password": "geheim12345"}).json()
    assert client.post("/api/me/2fa/confirm",
                       json={"code": "000000"}).status_code == 401
    assert client.get("/api/me/2fa").json()["active"] is False
    r = client.post("/api/me/2fa/confirm",
                    json={"code": totp.code_jetzt(s["secret"])})
    client.headers["Authorization"] = "Bearer " + r.json()["token"]
    assert client.get("/api/me/2fa").json()["active"] is True


def test_anmeldung_verlangt_danach_den_zweiten_schritt(client):
    einrichten(client)
    del client.headers["Authorization"]
    d = anmelden(client).json()
    assert d.get("totp_required") is True
    assert "token" not in d and "challenge" in d


def test_zwischenmarke_ist_keine_sitzung(client):
    """Der Kern der Sache: Mit halber Anmeldung darf nichts erreichbar sein."""
    einrichten(client)
    del client.headers["Authorization"]
    challenge = anmelden(client).json()["challenge"]
    r = client.get("/api/collection",
                   headers={"Authorization": "Bearer " + challenge})
    assert r.status_code == 401


def test_richtiger_code_schliesst_die_anmeldung_ab(client):
    secret, _ = einrichten(client)
    del client.headers["Authorization"]
    ch = anmelden(client).json()["challenge"]
    # Der Code aus der Einrichtung ist verbraucht – der nächste zählt.
    naechster = totp.code_jetzt(secret, wann=time.time() + totp.SCHRITT)
    r = client.post("/api/login/2fa", json={"challenge": ch, "code": naechster})
    assert r.status_code == 200 and "token" in r.json()
    # und dieser Token taugt als Sitzung
    assert client.get("/api/collection", headers={
        "Authorization": "Bearer " + r.json()["token"]}).status_code == 200


def test_falscher_code_im_zweiten_schritt(client):
    einrichten(client)
    del client.headers["Authorization"]
    ch = anmelden(client).json()["challenge"]
    assert client.post("/api/login/2fa",
                       json={"challenge": ch, "code": "000000"}
                       ).status_code == 401


def test_derselbe_code_gilt_nur_einmal(client):
    secret, _ = einrichten(client)
    del client.headers["Authorization"]
    code = totp.code_jetzt(secret, wann=time.time() + totp.SCHRITT)
    ch1 = anmelden(client).json()["challenge"]
    assert client.post("/api/login/2fa",
                       json={"challenge": ch1, "code": code}).status_code == 200
    ch2 = anmelden(client).json()["challenge"]
    assert client.post("/api/login/2fa",
                       json={"challenge": ch2, "code": code}).status_code == 401


def test_rettungscode_funktioniert_und_verbraucht_sich(client):
    _, codes = einrichten(client)
    del client.headers["Authorization"]
    ch = anmelden(client).json()["challenge"]
    r = client.post("/api/login/2fa", json={"challenge": ch, "code": codes[0]})
    assert r.status_code == 200
    assert r.json()["recovery_used"] is True
    assert r.json()["recovery_left"] == 7
    # Ein zweites Mal geht derselbe nicht
    ch = anmelden(client).json()["challenge"]
    assert client.post("/api/login/2fa",
                       json={"challenge": ch, "code": codes[0]}
                       ).status_code == 401


def test_rettungscodes_liegen_nicht_im_klartext(client):
    _, codes = einrichten(client)
    with core.db() as conn:
        gespeichert = conn.execute(
            "SELECT totp_recovery FROM users WHERE id = 1").fetchone()[0]
    assert codes[0] not in gespeichert
    assert totp.rettungscode_hash(codes[0]) in json.loads(gespeichert)


def test_ausschalten_verlangt_passwort_und_code(client):
    secret, _ = einrichten(client)
    assert client.post("/api/me/2fa/disable",
                       json={"password": "falsch",
                             "code": totp.code_jetzt(secret)}
                       ).status_code == 401
    assert client.post("/api/me/2fa/disable",
                       json={"password": "geheim12345", "code": "000000"}
                       ).status_code == 401


def test_admin_kann_den_zweiten_faktor_abnehmen(client):
    """Notausgang bei verlorenem Telefon."""
    einrichten(client)
    r = client.post("/api/users/1/2fa/reset")
    assert r.status_code == 200
    # Beim eigenen Konto kommt eine frische Sitzung mit: Der Handgriff
    # beendet alle bisherigen, und sich dabei selbst auszusperren wäre kein
    # Sicherheitsgewinn.
    client.headers["Authorization"] = "Bearer " + r.json()["token"]
    assert client.get("/api/me/2fa").json()["active"] is False


def test_zweiter_faktor_abnehmen_beendet_fremde_sitzungen(client):
    """Genau darum geht es: Das Telefon ist weg – eine Sitzung von diesem
    Gerät darf nicht einfach weiterlaufen."""
    einrichten(client)
    fremd = TestClient(main.app)
    fremd.headers["Authorization"] = client.headers["Authorization"]
    assert fremd.get("/api/me").status_code == 200
    client.post("/api/users/1/2fa/reset")
    assert fremd.get("/api/me").status_code == 401


def test_raten_im_zweiten_schritt_wird_gebremst(client):
    einrichten(client)
    del client.headers["Authorization"]
    ch = anmelden(client).json()["challenge"]
    for _ in range(main.LOGIN_MAX):
        client.post("/api/login/2fa", json={"challenge": ch, "code": "000000"})
    r = client.post("/api/login/2fa", json={"challenge": ch, "code": "000000"})
    assert r.status_code == 429


def test_abgelaufene_zwischenmarke_wird_abgelehnt(client):
    einrichten(client)
    alt = core.create_token(1, "anna", False, minutes=-1, zweck="2fa")
    r = client.post("/api/login/2fa", json={"challenge": alt, "code": "000000"})
    assert r.status_code == 401


def test_normaler_sitzungstoken_taugt_nicht_als_zwischenmarke(client):
    """Sonst könnte man den zweiten Schritt mit einer alten Sitzung umgehen."""
    einrichten(client)
    sitzung = client.headers["Authorization"][7:]
    r = client.post("/api/login/2fa",
                    json={"challenge": sitzung, "code": "000000"})
    assert r.status_code == 401
    assert "abgelaufen" in r.json()["detail"] or "neu" in r.json()["detail"]


def test_einschalten_beendet_die_anderen_sitzungen(client):
    """Ein Gerät, das schon angemeldet war, blieb es bis zu 90 Tage – auch
    nachdem der zweite Faktor eingeschaltet war."""
    anderes_geraet = anmelden(client).json()["token"]
    einrichten(client)
    r = client.get("/api/collection",
                   headers={"Authorization": "Bearer " + anderes_geraet})
    assert r.status_code == 401, "das andere Gerät muss sich neu anmelden"
    assert client.get("/api/me/2fa").json()["active"] is True, \
        "das eigene Gerät bleibt mit der frischen Sitzung angemeldet"


def test_qr_code_laesst_sich_skalieren(client):
    """Das SVG hatte feste 265 px ohne viewBox; die Oberfläche zeigt es in
    200 px – abgeschnitten, und keine Authenticator-App konnte es lesen."""
    client.headers["Authorization"] = "Bearer " + anmelden(client).json()["token"]
    client.post("/api/me/2fa/start", json={"password": "geheim12345"})
    r = client.get("/api/me/2fa/qr")
    assert r.status_code == 200
    kopf = r.text[r.text.index("<svg"):r.text.index(">", r.text.index("<svg"))]
    assert "viewBox" in kopf
    assert 'width="' not in kopf and 'height="' not in kopf


def test_einrichtungsassistent_bietet_zwei_faktor_an():
    """Die Zwei-Faktor-Anmeldung gehört auch in die erste Einrichtung – mit
    demselben Block wie im Profil, nicht mit einem zweiten Nachbau."""
    import pathlib
    wurzel = pathlib.Path(__file__).resolve().parent.parent / "frontend"
    html = (wurzel / "index.html").read_text(encoding="utf-8")
    js = (wurzel / "app.js").read_text(encoding="utf-8")
    assert '<div class="wiz-step" data-step="7" hidden>' in html
    assert 'id="wiz-tfa-platz"' in html and 'id="tfa-heimat"' in html
    assert html.count('id="tfa-confirm"') == 1, "der Block existiert nur einmal"
    assert "const WIZ_LAST = 8;" in js
    assert "tfaBlockUmziehen(wizStep === WIZ_TFA)" in js
    # Das Passwort vom Anlegen wird beim Ende des Assistenten vergessen.
    ende = js[js.index("function endWizard"):js.index("function endWizard") + 300]
    assert 'wizPasswort = ""' in ende


def test_rettungscode_gilt_auch_ohne_bindestriche(client):
    """Auf dem Handy tippt man „3f9a0b12c7de" – das galt als falsch."""
    _, codes = einrichten(client)
    del client.headers["Authorization"]
    ohne = codes[1].replace("-", "").upper()
    ch = anmelden(client).json()["challenge"]
    r = client.post("/api/login/2fa", json={"challenge": ch, "code": ohne})
    assert r.status_code == 200 and r.json()["recovery_used"] is True
    # verbraucht ist er in jeder Schreibweise
    ch = anmelden(client).json()["challenge"]
    assert client.post("/api/login/2fa",
                       json={"challenge": ch, "code": codes[1]}
                       ).status_code == 401


def test_code_feld_holt_fuer_rettungscodes_die_volle_tastatur():
    import pathlib
    wurzel = pathlib.Path(__file__).resolve().parent.parent / "frontend"
    html = (wurzel / "index.html").read_text(encoding="utf-8")
    js = (wurzel / "app.js").read_text(encoding="utf-8")
    assert 'id="btn-totp-rettung"' in html
    teil = js[js.index("function totpFeldAls"):js.index("function totpFeldAls") + 500]
    assert 'rettung ? "text" : "numeric"' in teil


# ------------------------------------------------ Von außen genutzt?
def _anfrage(client, **kopf):
    return client.get("/api/me/2fa", headers=kopf)


def test_ohne_kopfzeilen_gilt_es_als_heimnetz(client, monkeypatch):
    monkeypatch.setattr(main, "_extern_geschrieben", {"mit": 0.0, "ohne": 0.0})
    client.headers["Authorization"] = "Bearer " + anmelden(client).json()["token"]
    e = _anfrage(client).json()["extern"]
    assert e["genutzt"] is False and e["ohne_access"] is False


def test_cloudflare_mit_access_gilt_als_geschuetzt(client, monkeypatch):
    monkeypatch.setattr(main, "_extern_geschrieben", {"mit": 0.0, "ohne": 0.0})
    client.headers["Authorization"] = "Bearer " + anmelden(client).json()["token"]
    _anfrage(client, **{"CF-Ray": "abc", "Cf-Access-Jwt-Assertion": "x.y.z"})
    e = _anfrage(client).json()["extern"]
    assert e["genutzt"] and e["mit_access"] and not e["ohne_access"]
    assert e["weg"] == "cloudflare"
    with core.db() as conn:
        assert not conn.execute("SELECT 1 FROM notifications WHERE "
                                "kind = 'sicherheit'").fetchone(), \
            "mit Access drängt nichts"


def test_ohne_access_gibt_einen_hinweis_fuer_admins(client, monkeypatch):
    monkeypatch.setattr(main, "_extern_geschrieben", {"mit": 0.0, "ohne": 0.0})
    client.headers["Authorization"] = "Bearer " + anmelden(client).json()["token"]
    _anfrage(client, **{"CF-Connecting-IP": "203.0.113.7"})
    e = _anfrage(client).json()["extern"]
    assert e["ohne_access"] is True
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM notifications WHERE "
                            "kind = 'sicherheit'").fetchone()[0] == 1
    # Ein weiterer Aufruf legt keinen zweiten an.
    main._extern_geschrieben["ohne"] = 0.0
    _anfrage(client, **{"CF-Connecting-IP": "203.0.113.7"})
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM notifications WHERE "
                            "kind = 'sicherheit'").fetchone()[0] == 1


def test_proxy_nur_mit_oeffentlicher_adresse(client, monkeypatch):
    monkeypatch.setattr(main, "_extern_geschrieben", {"mit": 0.0, "ohne": 0.0})
    client.headers["Authorization"] = "Bearer " + anmelden(client).json()["token"]
    _anfrage(client, **{"X-Forwarded-For": "192.168.0.23"})
    assert _anfrage(client).json()["extern"]["genutzt"] is False, \
        "ein Reverse Proxy im Heimnetz ist nicht „von außen“"
    _anfrage(client, **{"X-Forwarded-For": "93.184.216.34, 10.0.0.1"})
    e = _anfrage(client).json()["extern"]
    assert e["genutzt"] and e["weg"] == "proxy" and e["ohne_access"]


def test_ohne_anmeldung_wird_nichts_gemerkt(client, monkeypatch):
    monkeypatch.setattr(main, "_extern_geschrieben", {"mit": 0.0, "ohne": 0.0})
    client.get("/api/laufzeit", headers={"CF-Ray": "abc"})
    assert core.get_setting("extern_zuletzt") in (None, "")
