"""Grundabsicherung: Passwortraten bremsen, Schutz-Header setzen.

Wichtig, sobald jemand die App über eine Portfreigabe erreichbar macht –
im Heimnetz fällt beides nicht auf, draußen sehr wohl.
"""
import time

import pytest

import core
import integrations
import main
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def frischer_zaehler():
    main._login_fails.clear()
    yield
    main._login_fails.clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "sec.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO users (username, password_hash, is_admin, "
                     "created_at) VALUES ('sven', ?, 1, ?)",
                     (core.hash_password("richtig123"), now))
    return TestClient(main.app)


def test_falsches_passwort_wird_abgelehnt(client):
    r = client.post("/api/login", json={"username": "sven", "password": "x"})
    assert r.status_code == 401


def test_raten_wird_nach_zehn_versuchen_gebremst(client):
    for _ in range(main.LOGIN_MAX):
        client.post("/api/login", json={"username": "sven", "password": "x"})
    r = client.post("/api/login", json={"username": "sven", "password": "x"})
    assert r.status_code == 429
    assert "Fehlversuche" in r.json()["detail"]


def test_bremse_gilt_auch_bei_richtigem_passwort(client):
    """Sonst könnte man die Sperre mit dem erratenen Passwort sofort umgehen."""
    for _ in range(main.LOGIN_MAX):
        client.post("/api/login", json={"username": "sven", "password": "x"})
    r = client.post("/api/login",
                    json={"username": "sven", "password": "richtig123"})
    assert r.status_code == 429


def test_erfolgreiche_anmeldung_setzt_den_zaehler_zurueck(client):
    for _ in range(main.LOGIN_MAX - 1):
        client.post("/api/login", json={"username": "sven", "password": "x"})
    assert client.post("/api/login",
                       json={"username": "sven", "password": "richtig123"}
                       ).status_code == 200
    # Danach wieder volle Anzahl Versuche
    for _ in range(main.LOGIN_MAX - 1):
        assert client.post("/api/login",
                           json={"username": "sven", "password": "x"}
                           ).status_code == 401


def test_zaehlung_je_konto_traegt_ueber_adressen_hinweg(client):
    """Ein Wechsel der Herkunft darf die Kontosperre nicht aushebeln."""
    for i in range(main.LOGIN_MAX):
        client.post("/api/login", json={"username": "sven", "password": "x"},
                    headers={"x-forwarded-for": f"10.0.0.{i}"})
    r = client.post("/api/login", json={"username": "sven", "password": "x"},
                    headers={"x-forwarded-for": "10.0.0.99"})
    assert r.status_code == 429


def test_schutz_header_auf_der_startseite(client):
    h = client.get("/").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "SAMEORIGIN"
    assert "default-src 'self'" in h["content-security-policy"]


def test_katalogbilder_bleiben_erlaubt(client):
    """Ohne diese Ausnahme bliebe der halbe Katalog leer."""
    csp = client.get("/").headers["content-security-policy"]
    assert "img.bricklink.com" in csp and "cdn.rebrickable.com" in csp


def _csp_teil(client, name):
    csp = client.get("/").headers["content-security-policy"]
    return [t for t in csp.split(";") if t.strip().startswith(name)][0]


def test_benutzte_schemata_sind_erlaubt(client):
    """Die Regeln müssen zu dem passen, was die Oberfläche tatsächlich tut.

    Das ist inzwischen viermal schiefgegangen: blockierte Katalogbilder, der
    Ersatz für kaputte Bilder, das Setzen des Designs – und zuletzt die
    Vorschau des eigenen Fotos. Sie zeigt das Bild als `blob:` aus dem
    Arbeitsspeicher, noch bevor es hochgeladen ist; ohne Erlaubnis blockierte
    der Browser ausgerechnet das Bild, das man selbst ausgewählt hatte, und
    es blieb bei einem Platzhalter.

    Deshalb wird hier nicht eine feste Liste geprüft, sondern **aus dem
    Quelltext abgeleitet**, welche Schemata vorkommen."""
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text()
    img = _csp_teil(client, "img-src")
    if "createObjectURL" in js:
        assert " blob:" in img, "createObjectURL benutzt, aber blob: fehlt"
    if "data:image" in js:
        assert " data:" in img, "Daten-URLs benutzt, aber data: fehlt"


def test_scan_bilder_bleiben_erlaubt(client):
    """Brickognize legt seine Vorschaubilder in einem Google-Storage-Bucket
    ab. Fehlt der Host, verlieren genau die Artikel ihr Bild, die per Foto
    erfasst wurden – und zwar still, nur die Browser-Konsole sagt es."""
    csp = client.get("/").headers["content-security-policy"]
    assert "storage.googleapis.com" in csp


def test_kein_inline_skript():
    """`script-src 'self'` verbietet auch `<script>…</script>` im Dokument.

    Genau daran hing das Setzen des Designs: Der Browser blockierte es still,
    und wer ein dunkles Design nutzte, sah bei jedem Laden kurz das helle
    aufblitzen. Skript gehört in eine eigene Datei."""
    import re
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1]
            / "frontend" / "index.html").read_text()
    inline = [m.group(0)[:60] for m in
              re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>", html)]
    assert not inline, f"Skript im Dokument statt in einer Datei: {inline}"


def test_kein_skript_in_attributen():
    """`script-src 'self'` verbietet `onerror="…"` & Co. Steht so etwas doch
    im Frontend, führt der Browser es nie aus – der Fehlerfall fällt dann
    einfach aus, ohne dass es jemandem auffällt. Deshalb: gar nicht erst
    schreiben. Erklärende Kommentare dürfen den Namen nennen, sie werden
    vorher entfernt."""
    import re
    from pathlib import Path
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    ohne_kommentar = lambda t: re.sub(r"/\*.*?\*/|<!--.*?-->", " ", t, flags=re.S)
    treffer = []
    for datei in ("app.js", "index.html", "sw.js", "theme-boot.js"):
        text = ohne_kommentar((frontend / datei).read_text())
        for m in re.finditer(r'\bon[a-z]{3,}\s*=\s*["\']', text):
            treffer.append(f"{datei}: …{text[max(0, m.start() - 30):m.end()]}")
    assert not treffer, "Skript in Attributen: " + "; ".join(treffer[:3])


# ------------------------------------ Sitzungen enden mit dem Passwort

def _neuer_client(name="sven", passwort="alt12345", admin=True):
    import time as _t
    with core.db() as conn:
        uid = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, ?, ?, 1, ?)",
            (name, core.hash_password(passwort), int(admin),
             int(_t.time()))).lastrowid
    c = TestClient(main.app)
    tok = c.post("/api/login", json={"username": name,
                                     "password": passwort}).json()["token"]
    c.headers["Authorization"] = "Bearer " + tok
    return c, uid


def test_passwortwechsel_beendet_alte_sitzungen(client):
    """Ohne das liefe ein abhandengekommenes Token bis zu 90 Tage weiter,
    obwohl das Passwort längst ein anderes ist."""
    handy, uid = _neuer_client("wechsler")
    rechner = TestClient(main.app)
    rechner.headers["Authorization"] = handy.headers["Authorization"]
    assert rechner.get("/api/me").status_code == 200

    r = handy.post("/api/me/password", json={"current_password": "alt12345",
                                             "new_password": "ganzneu123"})
    assert r.status_code == 200
    assert rechner.get("/api/me").status_code == 401


def test_wer_das_passwort_aendert_bleibt_selbst_drin(client):
    """Sonst fliegt man beim eigenen Passwortwechsel aus der App."""
    c, _ = _neuer_client("bleibt")
    r = c.post("/api/me/password", json={"current_password": "alt12345",
                                         "new_password": "ganzneu123"})
    neu = r.json().get("token")
    assert neu
    c.headers["Authorization"] = "Bearer " + neu
    assert c.get("/api/me").status_code == 200


def test_admin_zuruecksetzen_wirft_das_geraet_raus(client):
    """Wird ein Passwort zurückgesetzt, weil ein Gerät weg ist, muss die
    Sitzung von genau diesem Gerät enden."""
    admin, _ = _neuer_client("chef", "chef12345", admin=True)
    kind, kid = _neuer_client("kind2", "kind1234", admin=False)
    assert kind.get("/api/me").status_code == 200
    assert admin.post(f"/api/users/{kid}/password",
                      json={"password": "vomAdmin123"}).status_code == 200
    assert kind.get("/api/me").status_code == 401


def test_alte_token_ohne_zaehler_bleiben_gueltig(client):
    """Beim Update darf niemand ausgeloggt werden – Bestand hat keinen Stand
    im Token und muss als 0 durchgehen."""
    import jwt as _jwt
    _, uid = _neuer_client("bestand")
    alt = _jwt.encode({"sub": str(uid), "name": "bestand", "adm": True,
                       "exp": int(time.time()) + 3600},
                      core.SECRET_KEY, algorithm="HS256")
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + alt
    assert c.get("/api/me").status_code == 200


# ------------------------------------ Geheimnisse gehen nie nach draußen

def test_scrub_entfernt_alle_geheimnisse(client):
    """Eine Fehlermeldung kann als GitHub-Issue **öffentlich** werden."""
    werte = {
        "bl_token": "blt_geheim_1234567890",
        "github_token": "github_pat_geheim_abcdef",
        "hub_token": "bft_hub_geheim_9876543210",
        "hub_privkey": "PRIVKEY-geheim-aaaaaaaaaaaa",
        "vapid_private": "-----BEGIN PRIVATE KEY----- geheimgeheim",
    }
    for name, wert in werte.items():
        core.set_setting(name, wert)
    text = "Fehler bei " + " und ".join(werte.values())
    sauber = main.scrub(text, limit=2000)
    for name, wert in werte.items():
        assert wert not in sauber, f"{name} steht noch drin"


def test_jede_gespeicherte_einstellung_ist_eingeordnet():
    """Der eigentliche Schutz: Kommt eine neue Einstellung dazu, muss jemand
    entscheiden, ob sie geheim ist. Sonst rutscht das nächste Geheimnis
    unbemerkt an `scrub()` vorbei."""
    import re
    from pathlib import Path
    backend = Path(__file__).resolve().parents[1] / "backend"
    namen = set()
    for datei in backend.glob("*.py"):
        namen |= set(re.findall(r'set_setting\(\s*"([a-z_]+)"',
                                datei.read_text()))
        namen |= set(re.findall(r'set_setting\(\s*([A-Z_]+)\s*,',
                                datei.read_text()))
    # Konstanten auflösen (z. B. VAPID_PRIV = "vapid_private")
    import push
    aufgeloest = {getattr(push, n, n) if n.isupper() else n for n in namen}
    OFFEN = {                       # bewusst nicht geheim
        "bl_categories", "bl_colors", "currency", "default_theme",
        "hub_blocked", "hub_display_name", "hub_instance_code", "hub_is_admin",
        "hub_key_sent", "hub_last_publish", "hub_member_id", "offer_percent",
        "owner_name", "price_region", "vapid_public",
    }
    unbekannt = aufgeloest - set(integrations.GEHEIME_SETTINGS) - OFFEN
    assert not unbekannt, (
        "Neue Einstellung(en) ohne Einordnung: " + ", ".join(sorted(unbekannt))
        + " – entweder in GEHEIME_SETTINGS aufnehmen oder hier als offen "
          "eintragen.")


def test_jede_erzeugte_objektadresse_wird_wieder_freigegeben():
    """`createObjectURL` hält die Datei bis zum Neuladen der Seite im
    Speicher. Bei der Scan-Vorschau fehlte die Freigabe: Wer nacheinander
    Bildschirmfotos hineinzog, sammelte sie alle an – jedes 2560×1440-Bild
    entpackt rund 14 MB. Irgendwann beendet der Browser den Tab.

    Geprüft wird die Zahl, nicht die Stelle: Jede erzeugte Adresse braucht
    ihr Gegenstück, sonst ist der nächste Speicherfresser schon gebaut."""
    import re
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text()
    erzeugt = len(re.findall(r"URL\.createObjectURL\(", js))
    freigegeben = len(re.findall(r"URL\.revokeObjectURL\(", js))
    assert freigegeben >= erzeugt, (
        f"{erzeugt}× createObjectURL, aber nur {freigegeben}× revokeObjectURL")
