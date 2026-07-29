"""Tests für Themen (Star Wars, City …) und die Sortierung danach."""
import time

import pytest

import core
import integrations
import main
import themes
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "t.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('sven', 'x', 1, 1, ?)", (now,))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "sven", True)
    c.uid = uid
    return c


# ------------------------------------------------------ Erkennung aus Nummer

@pytest.mark.parametrize("no,expected", [
    ("sw1213", "Star Wars"),
    ("sw0001a", "Star Wars"),
    ("cty0123", "City"),
    ("njo0456", "Ninjago"),
    ("hp123", "Harry Potter"),
    ("sh0111", "Super Heroes"),
    ("col123", "Sammelfiguren"),
])
def test_theme_from_number(no, expected):
    assert themes.from_minifig_number(no) == expected


def test_longest_prefix_wins():
    """njo darf nicht als „nj" oder „n" missverstanden werden."""
    assert themes.from_minifig_number("njo0001") == "Ninjago"


def test_unknown_prefix_has_no_theme():
    assert themes.from_minifig_number("zzz0001") is None
    assert themes.from_minifig_number("75300-1") is None
    assert themes.from_minifig_number("") is None


def test_only_minifigs_get_a_number_theme():
    assert themes.for_item("sw1213", "minifig") == "Star Wars"
    assert themes.for_item("sw1213", "set") is None      # Sets: über Kategorie


# ------------------------------------------------------------- beim Anlegen

def test_theme_is_set_when_adding(client):
    client.post("/api/collection", json={
        "item_id": "sw1213", "item_type": "minifig", "name": "Yoda",
        "quantity": 1, "condition": "used"})
    with core.db() as conn:
        row = conn.execute(
            "SELECT theme FROM collection WHERE item_id = 'sw1213'").fetchone()
    assert row["theme"] == "Star Wars"


# ------------------------------------------------------------- Sortierung

def _add(client, item_id, name, item_type="minifig"):
    client.post("/api/collection", json={
        "item_id": item_id, "item_type": item_type, "name": name,
        "quantity": 1, "condition": "used"})


def test_sort_by_theme_groups_and_puts_unknown_last(client):
    _add(client, "sw0002", "Vader")          # Star Wars
    _add(client, "cty0001", "Polizist")      # City
    _add(client, "zzz9999", "Rätsel")        # ohne Thema
    _add(client, "sw0001", "Luke")           # Star Wars
    items = client.get("/api/collection?sort=theme").json()["items"]
    assert [i["name"] for i in items] == [
        "Polizist",            # City
        "Luke", "Vader",       # Star Wars, darin nach Name
        "Rätsel",              # ohne Thema ans Ende
    ]


def test_unknown_sort_falls_back(client):
    _add(client, "sw0001", "Luke")
    assert client.get("/api/collection?sort=quatsch").status_code == 200


# ------------------------------------------------- Einstellung im Profil

def test_sort_pref_is_saved_and_returned(client):
    assert client.post("/api/me/sort", json={"sort": "theme"}).status_code == 200
    assert client.get("/api/me").json()["sort_pref"] == "theme"


def test_sort_pref_rejects_unknown(client):
    assert client.post("/api/me/sort",
                       json={"sort": "hack"}).status_code == 400


def test_sort_pref_is_per_user(client, tmp_path):
    client.post("/api/me/sort", json={"sort": "theme"})
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES ('paul', 'x', 0, 0, ?)", (now,))
        other = cur.lastrowid
    c2 = TestClient(main.app)
    c2.headers["Authorization"] = "Bearer " + core.create_token(other, "paul", False)
    assert c2.get("/api/me").json()["sort_pref"] is None   # unberührt


# ------------------------------------------------------------ Nachladen

def test_status_counts_missing_themes(client):
    _add(client, "75300-1", "TIE Fighter", item_type="set")   # kein Nummer-Thema
    _add(client, "sw0001", "Luke")                            # bekommt Thema
    assert client.get("/api/themes/status").json()["pending"] == 1


def test_refresh_uses_bricklink_category_for_sets(client, monkeypatch):
    _add(client, "75300-1", "TIE Fighter", item_type="set")
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(integrations, "bricklink_category_id",
                        lambda t, n: "65")
    monkeypatch.setattr(integrations, "bricklink_categories",
                        lambda: {"65": ("Episode IV", "12"),
                                 "12": ("Star Wars", "0")})
    main._category_cache.update(at=0, map={})
    res = client.post("/api/themes/refresh").json()
    assert res["updated"] == 1 and res["remaining"] == 0
    items = client.get("/api/collection?sort=theme").json()["items"]
    assert items[0]["theme"] == "Star Wars"      # oberste Kategorie zählt


def test_refresh_skips_custom_and_manual(client):
    _add(client, "custom-001", "Eigenbau")
    _add(client, "manuell-123", "Handarbeit")
    assert client.get("/api/themes/status").json()["pending"] == 0


# ------------------------------------------- Nachziehen bestehender Daten

def test_migration_fills_themes_for_existing_minifigs(tmp_path, monkeypatch):
    """Nach einem Update sollen vorhandene Figuren sofort ihr Thema haben –
    sonst steht die ganze Sammlung unter „Ohne Thema"."""
    db = tmp_path / "old.db"
    monkeypatch.setattr(core, "DB_PATH", str(db))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:                      # Zustand „vor dem Update"
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, added_at) VALUES ('sw1213', 'minifig', 'Yoda', 1, "
            "'used', ?)", (now,))
        conn.execute(
            "INSERT INTO wanted (item_id, item_type, name, added_at) "
            "VALUES ('njo0456', 'minifig', 'Kai', ?)", (now,))
        conn.execute("UPDATE collection SET theme = NULL")
        conn.execute("UPDATE wanted SET theme = NULL")

    core.init_db()                               # Update läuft erneut

    with core.db() as conn:
        c = conn.execute(
            "SELECT theme FROM collection WHERE item_id = 'sw1213'").fetchone()
        w = conn.execute(
            "SELECT theme FROM wanted WHERE item_id = 'njo0456'").fetchone()
    assert c["theme"] == "Star Wars"
    assert w["theme"] == "Ninjago"


def test_migration_leaves_sets_alone(tmp_path, monkeypatch):
    """Sets bekommen ihr Thema erst über die BrickLink-Kategorie."""
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "s.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, added_at) VALUES ('75300-1', 'set', 'TIE', 1, "
            "'used', ?)", (now,))
    core.init_db()
    with core.db() as conn:
        row = conn.execute(
            "SELECT theme FROM collection WHERE item_id = '75300-1'").fetchone()
    assert row["theme"] is None


# --------------------------------------------------------- eigene Figuren

def test_custom_items_get_custom_theme():
    assert themes.for_item("custom-001", "minifig") == "Custom"
    assert themes.for_item("custom-mein-set", "set") == "Custom"
    # manuelle Alt-Einträge bleiben ohne Thema
    assert themes.for_item("manuell-123", "minifig") is None


def test_custom_theme_when_adding(client):
    _add(client, "custom-001", "Eigenbau")
    items = client.get("/api/collection?sort=theme").json()["items"]
    assert items[0]["theme"] == "Custom"


def test_migration_fills_custom_theme(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "cm.db"))
    core.init_db()
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, added_at) VALUES ('custom-002', 'minifig', 'Drache', "
            "1, 'used', ?)", (now,))
        conn.execute("UPDATE collection SET theme = NULL")
    core.init_db()
    with core.db() as conn:
        row = conn.execute(
            "SELECT theme FROM collection WHERE item_id = 'custom-002'").fetchone()
    assert row["theme"] == "Custom"


# ---------------------------------------------- Rückfall über die Figuren

def test_set_ohne_kategorie_erbt_das_thema_seiner_figuren(tmp_path, monkeypatch):
    """Die Kategorie-ID eines Sets steht nicht immer in BrickLinks
    Kategorieliste – dann bleibt die Kette am ersten Glied stehen. Die
    Figuren im Set wissen es aber ohnehin."""
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "t.db"))
    core.init_db()
    with core.db() as conn:
        for fig in ("sw0910", "sw0552", "col123"):
            conn.execute("INSERT INTO set_contents (set_no, fig_no, qty) "
                         "VALUES ('75018-1', ?, 1)", (fig,))
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(integrations, "bricklink_category_id",
                        lambda t, i: "9999")          # unbekannte Kategorie
    monkeypatch.setattr(main, "_top_category", lambda cid: None)
    assert main._theme_from_bricklink("75018-1", "set") == "Star Wars"


def test_kategorie_hat_weiter_vorrang(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "t.db"))
    core.init_db()
    with core.db() as conn:
        conn.execute("INSERT INTO set_contents (set_no, fig_no, qty) "
                     "VALUES ('75018-1', 'sw0910', 1)")
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(integrations, "bricklink_category_id",
                        lambda t, i: "65")
    monkeypatch.setattr(main, "_top_category", lambda cid: "Ninjago")
    assert main._theme_from_bricklink("75018-1", "set") == "Ninjago"


def test_ohne_figuren_bleibt_es_ohne_thema(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "t.db"))
    core.init_db()
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(integrations, "bricklink_category_id",
                        lambda t, i: None)
    assert main._theme_from_bricklink("9999-1", "set") is None


def test_figuren_rueckfall_gilt_nicht_fuer_teile(tmp_path, monkeypatch):
    """Ein Teil steckt in vielen Sets – daraus ein Thema zu raten wäre
    geraten, nicht gewusst."""
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "t.db"))
    core.init_db()
    with core.db() as conn:
        conn.execute("INSERT INTO set_contents (set_no, fig_no, qty) "
                     "VALUES ('3001', 'sw0910', 1)")
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(integrations, "bricklink_category_id", lambda t, i: None)
    assert main._theme_from_bricklink("3001", "part") is None


def test_nachziehen_holt_das_set_wirklich_aus_ohne_thema(client, monkeypatch):
    """Der ganze Weg, wie ihn der Knopf geht – nicht nur die Hilfsfunktion.

    Genau dieser Fall stand in der App: ein Star-Wars-Set unter „Ohne Thema",
    weil BrickLink zu seiner Kategorie nichts sagt.
    """
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, theme, added_at) VALUES ('75018-1', 'set', "
            "'Jek-14''s Stealth Starfighter', 1, 'used', NULL, ?)", (now,))
        for fig in ("sw0473", "sw0474", "sw0475", "col123"):
            conn.execute("INSERT INTO set_contents (set_no, fig_no, qty) "
                         "VALUES ('75018-1', ?, 1)", (fig,))

    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    # BrickLink kennt die Kategorie-ID, die Kategorieliste sie aber nicht
    monkeypatch.setattr(integrations, "bricklink_category_id",
                        lambda t, i: "1234")
    monkeypatch.setattr(main, "_bl_category_map", lambda: {"65": ("Star Wars", "")})

    assert client.get("/api/themes/status").json()["pending"] == 1
    res = client.post("/api/themes/refresh?limit=25").json()
    assert res["updated"] == 1 and res["remaining"] == 0
    with core.db() as conn:
        row = conn.execute("SELECT theme FROM collection WHERE item_id = "
                           "'75018-1'").fetchone()
    assert row["theme"] == "Star Wars"


def test_nicht_aufloesbares_set_wird_benannt(client, monkeypatch):
    """Bleibt wirklich nichts übrig, muss wenigstens die Nummer dastehen –
    sonst sucht man ewig, welcher Eintrag gemeint ist."""
    now = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, theme, added_at) VALUES ('9999-1', 'set', 'Rätsel', "
            "1, 'used', NULL, ?)", (now,))
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: True)
    monkeypatch.setattr(integrations, "bricklink_category_id", lambda t, i: None)
    res = client.post("/api/themes/refresh?limit=25").json()
    assert res["remaining"] == 1 and res["unresolved"] == ["9999-1"]


def test_figuren_rueckfall_braucht_keine_bricklink_schluessel(tmp_path, monkeypatch):
    """Die Set-Inhalte liegen längst in der eigenen Datenbank. Ohne Schlüssel
    blieb das Set trotzdem ohne Thema – die Antwort war die ganze Zeit da."""
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "t.db"))
    core.init_db()
    with core.db() as conn:
        for fig in ("sw0473", "sw0474"):
            conn.execute("INSERT INTO set_contents (set_no, fig_no, qty) "
                         "VALUES ('75018-1', ?, 1)", (fig,))
    monkeypatch.setattr(integrations, "bricklink_enabled", lambda: False)
    assert main._theme_nachschlagen("75018-1", "set") == "Star Wars"
