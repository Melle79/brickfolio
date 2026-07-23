"""Tests für Hinweise zu verschwundenen BrickLink-Nummern.

Kernfragen: Wird ein Nummernwechsel überhaupt bemerkt, bleibt der Hinweis
stehen bis jemand ihn wegklickt, und trägt „Nummer übernehmen“ die neue
Nummer wirklich überall ein?
"""
import time

import pytest
import requests

import core
import integrations
import main
from fastapi.testclient import TestClient


def _client(name="admin", admin=True):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, 'x', ?, 1, ?)", (name, int(admin), now))
        uid = cur.lastrowid
    c = TestClient(main.app)
    c.headers["Authorization"] = (
        "Bearer " + core.create_token(uid, name, admin))
    return c


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "note.db"))
    core.init_db()
    return _client()


def _entry(item_id="sw0001", item_type="minifig", priced=True, name="Vader"):
    """Sammlungseintrag anlegen; `priced` = BrickLink kannte ihn schon mal."""
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO collection (item_id, item_type, name, quantity, "
            "condition, added_at, price_updated_at) VALUES (?, ?, ?, 1, "
            "'used', ?, ?)",
            (item_id, item_type, name, now, now - 8 * 86400 if priced else None))
        eid = cur.lastrowid
    with core.db() as conn:
        return dict(conn.execute("SELECT * FROM collection WHERE id = ?",
                                 (eid,)).fetchone())


class _Resp404:
    status_code = 404


def _all_404(monkeypatch):
    """BrickLink kennt die Nummer nicht mehr."""
    def boom(*a, **k):
        raise requests.HTTPError(response=_Resp404())
    monkeypatch.setattr(integrations, "price_guide", boom)


# ------------------------------------------------------------ Erkennung

def test_gone_item_creates_notification(ctx, monkeypatch):
    entry = _entry()
    _all_404(monkeypatch)
    with pytest.raises(LookupError):
        main._fetch_and_store_prices(entry)

    items = ctx.get("/api/notifications").json()["items"]
    assert len(items) == 1
    assert items[0]["item_id"] == "sw0001"
    assert items[0]["kind"] == "item_gone"


def test_never_priced_item_is_not_reported(ctx, monkeypatch):
    """Eine von Hand falsch eingetippte Nummer ist kein BrickLink-Ereignis."""
    entry = _entry(item_id="tippfehler", priced=False)
    _all_404(monkeypatch)
    with pytest.raises(LookupError):
        main._fetch_and_store_prices(entry)
    assert ctx.get("/api/notifications").json()["items"] == []


def test_notification_is_not_duplicated(ctx, monkeypatch):
    entry = _entry()
    _all_404(monkeypatch)
    for _ in range(3):
        with pytest.raises(LookupError):
            main._fetch_and_store_prices(entry)
    assert len(ctx.get("/api/notifications").json()["items"]) == 1


# ------------------------------------------------------------ Stehenbleiben

def test_notification_stays_until_dismissed(ctx, monkeypatch):
    entry = _entry()
    _all_404(monkeypatch)
    with pytest.raises(LookupError):
        main._fetch_and_store_prices(entry)
    note = ctx.get("/api/notifications").json()["items"][0]

    # Erst das Wegklicken beendet ihn
    assert ctx.delete(f"/api/notifications/{note['id']}").status_code == 200
    assert ctx.get("/api/notifications").json()["items"] == []


def test_dismissed_notification_does_not_come_back(ctx, monkeypatch):
    """Wer entschieden hat, soll nicht bei jedem Preislauf neu gefragt werden."""
    entry = _entry()
    _all_404(monkeypatch)
    with pytest.raises(LookupError):
        main._fetch_and_store_prices(entry)
    note = ctx.get("/api/notifications").json()["items"][0]
    ctx.delete(f"/api/notifications/{note['id']}")

    with pytest.raises(LookupError):
        main._fetch_and_store_prices(entry)
    assert ctx.get("/api/notifications").json()["items"] == []


# ------------------------------------------------------------ Change Log

def test_change_log_fills_in_new_number(ctx, monkeypatch):
    entry = _entry()
    _all_404(monkeypatch)
    with pytest.raises(LookupError):
        main._fetch_and_store_prices(entry)

    monkeypatch.setattr(
        integrations, "find_number_change",
        lambda item_id, since: {"new_id": "sw0001a", "item_type": "minifig",
                                "kind": "renumbered"})
    main._resolve_gone_items()

    note = ctx.get("/api/notifications").json()["items"][0]
    assert note["new_item_id"] == "sw0001a"
    assert "sw0001a" in note["title"]


def test_change_log_silence_leaves_plain_hint(ctx, monkeypatch):
    """Findet der Log nichts, bleibt der Hinweis – nur ohne neue Nummer."""
    entry = _entry()
    _all_404(monkeypatch)
    with pytest.raises(LookupError):
        main._fetch_and_store_prices(entry)
    monkeypatch.setattr(integrations, "find_number_change",
                        lambda item_id, since: None)
    main._resolve_gone_items()

    note = ctx.get("/api/notifications").json()["items"][0]
    assert note["new_item_id"] is None
    assert "nicht mehr" in note["title"]


def test_change_log_outage_does_not_break_anything(ctx, monkeypatch):
    entry = _entry()
    _all_404(monkeypatch)
    with pytest.raises(LookupError):
        main._fetch_and_store_prices(entry)

    def boom(*a, **k):
        raise requests.ConnectionError("BrickLink nicht erreichbar")
    monkeypatch.setattr(integrations, "find_number_change", boom)
    main._resolve_gone_items()          # darf nicht durchschlagen
    assert len(ctx.get("/api/notifications").json()["items"]) == 1


# ------------------------------------------------------------ Übernehmen

def test_apply_renames_everywhere(ctx, monkeypatch):
    entry = _entry()
    now = int(time.time())
    with core.db() as conn:
        conn.execute("INSERT INTO wanted (item_id, item_type, name, added_at)"
                     " VALUES ('sw0001', 'minifig', 'Vader', ?)", (now,))
        conn.execute("INSERT INTO set_contents (set_no, fig_no, qty) "
                     "VALUES ('7965-1', 'sw0001', 1)")
        conn.execute("INSERT INTO price_history (item_id, item_type, ts, "
                     "price_new, price_used, source) VALUES "
                     "('sw0001', 'minifig', ?, 1.0, 0.5, 'auto')", (now,))

    _all_404(monkeypatch)
    with pytest.raises(LookupError):
        main._fetch_and_store_prices(entry)
    monkeypatch.setattr(
        integrations, "find_number_change",
        lambda item_id, since: {"new_id": "sw0001a", "item_type": "minifig",
                                "kind": "renumbered"})
    main._resolve_gone_items()
    note = ctx.get("/api/notifications").json()["items"][0]

    res = ctx.post(f"/api/notifications/{note['id']}/apply").json()
    assert res["new_item_id"] == "sw0001a"

    with core.db() as conn:
        one = lambda q: conn.execute(q).fetchone()[0]
        assert one("SELECT item_id FROM collection") == "sw0001a"
        assert one("SELECT item_id FROM wanted") == "sw0001a"
        assert one("SELECT fig_no FROM set_contents") == "sw0001a"
        assert one("SELECT item_id FROM price_history") == "sw0001a"
        # Preis muss neu geholt werden, der alte gehört zur alten Nummer
        assert one("SELECT price_updated_at IS NULL FROM collection") == 1

    # Der erledigte Hinweis verschwindet
    assert ctx.get("/api/notifications").json()["items"] == []


def test_apply_without_new_number_is_refused(ctx, monkeypatch):
    entry = _entry()
    _all_404(monkeypatch)
    with pytest.raises(LookupError):
        main._fetch_and_store_prices(entry)
    note = ctx.get("/api/notifications").json()["items"][0]
    assert ctx.post(f"/api/notifications/{note['id']}/apply").status_code == 400


# ------------------------------------------------------------ Change-Log-Parser

_RENAME_HTML = """
<TR><TD>Part <B><A HREF="/v2/catalog/catalogitem.page?P=4215apb18">4215apb18
&nbsp;Panel</A></B>:</TD></TR>
<TR><TD>Changed <B>Item No</B> from {<B>4215pb061</B>} to {<B>4215apb18</B>}</TD></TR>
"""

_MERGE_HTML = """
<TR><TD>Minifigure <B><A HREF="/v2/catalog/catalogitem.page?M=fort019">fort019
&nbsp;Leviathan</A></B>:</TD></TR>
<TR><TD><B>Merged</B> from <B>Minifigure&nbsp;fort028</B></TD></TR>
"""


def test_parses_number_change():
    got = integrations._parse_log(_RENAME_HTML, "renumbered")
    assert got["4215pb061"] == {"new_id": "4215apb18", "item_type": "part",
                               "kind": "renumbered"}


def test_parses_merge():
    got = integrations._parse_log(_MERGE_HTML, "merged")
    assert got["fort028"] == {"new_id": "fort019", "item_type": "minifig",
                              "kind": "merged"}


def test_parser_ignores_unrelated_markup():
    assert integrations._parse_log("<TR><TD>nichts</TD></TR>", "renumbered") == {}
