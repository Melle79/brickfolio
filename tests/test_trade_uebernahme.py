"""Angenommene Tausche verbuchen: /take (kommt rein) und /give (geht raus).

Bis 1.85.0 war „Annehmen" eine reine Zusage im Gespräch: Der Artikel landete
nirgends und musste von Hand nachgetragen werden. Hier steht, was seitdem
passiert – und was ausdrücklich nicht passieren darf. Beim Austragen (1.86.0)
zählt das doppelt: Dort verschwindet etwas, und ein geratener Zustand wäre ein
verlorenes Stück.
"""
import time

import pytest

import core
import main
from fastapi.testclient import TestClient


def _user(is_dealer=1, name="anna"):
    now = int(time.time())
    with core.db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_dealer,"
            " created_at) VALUES (?, 'x', 1, ?, ?)", (name, is_dealer, now))
        return cur.lastrowid


def _client(tmp_path, monkeypatch, is_dealer=1):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "take.db"))
    core.init_db()
    uid = _user(is_dealer)
    c = TestClient(main.app)
    c.headers["Authorization"] = "Bearer " + core.create_token(uid, "anna", True)
    return c


@pytest.fixture
def client(tmp_path, monkeypatch):
    return _client(tmp_path, monkeypatch)


def _trade(tid="trd_1", direction="out", status="accepted", item_id="sw1213",
           name="Yoda", item_type="minifig", img="https://x.test/y.jpg",
           condition="used", unterwegs=True):
    """Standard: angenommen, verschickt und angekommen – bereit zum Buchen.
    `unterwegs=False` lässt die Zwischenschritte (seit 2.89.3) offen."""
    now = int(time.time())
    schritt = now if unterwegs else None
    with core.db() as conn:
        conn.execute(
            "INSERT INTO trades (id, direction, other_id, other_name, item_id,"
            " item_name, status, created_at, updated_at, item_type, img_url,"
            " bricklink_url, condition, shipped_at, arrived_at) VALUES "
            "(?, ?, 'm_bruno', 'Bruno', ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?)",
            (tid, direction, item_id, name, status, now, now, item_type, img,
             condition, schritt, schritt))
    return tid


def _sammlung():
    with core.db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM collection")]


def test_take_puts_item_into_collection(client):
    _trade()
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 200, r.text
    rows = _sammlung()
    assert len(rows) == 1
    assert rows[0]["item_id"] == "sw1213"
    assert rows[0]["item_type"] == "minifig"
    assert rows[0]["name"] == "Yoda"
    assert rows[0]["quantity"] == 1
    # Woher das Stück kam, steht in der Notiz – sonst weiß man es in einem
    # halben Jahr nicht mehr.
    assert "Bruno" in rows[0]["notes"]


def test_take_records_quantity_condition_and_price(client):
    _trade()
    client.post("/api/hub/trades/trd_1/take", json={
        "ziel": "sammlung", "quantity": 3, "condition": "new",
        "paid_price": 12.5})
    row = _sammlung()[0]
    assert row["quantity"] == 3 and row["condition"] == "new"
    assert row["paid_price"] == 12.5
    with core.db() as conn:
        kauf = conn.execute("SELECT * FROM purchases").fetchall()
    assert len(kauf) == 1 and kauf[0]["quantity"] == 3


def test_take_marks_trade_as_taken(client):
    _trade()
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    t = client.get("/api/hub/trades/trd_1").json()["trade"]
    assert t["taken_at"] and t["taken_at"] > 0


def test_second_take_merges_instead_of_duplicating(client):
    _trade()
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.json()["ergebnis"]["merged"] is True
    rows = _sammlung()
    assert len(rows) == 1 and rows[0]["quantity"] == 2


def test_take_onto_shopping_list(client):
    _trade()
    lid = client.post("/api/lists", json={"name": "Abholen"}).json()["id"]
    r = client.post("/api/hub/trades/trd_1/take",
                    json={"ziel": "liste", "list_id": lid, "quantity": 2})
    assert r.status_code == 200, r.text
    items = client.get("/api/lists").json()["lists"][0]["items"]
    assert len(items) == 1 and items[0]["item_id"] == "sw1213"
    assert items[0]["qty"] == 2
    assert not _sammlung()          # nicht doppelt: Liste heißt nicht Sammlung


def test_take_needs_a_list_id_for_lists(client):
    _trade()
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "liste"})
    assert r.status_code == 400


def test_take_rejects_incoming_trades(client):
    """Eingehende Anfragen sind eigene Artikel, die weggehen."""
    _trade(direction="in")
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 400
    assert not _sammlung()


def test_take_rejects_open_trades(client):
    _trade(status="open")
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 400
    assert not _sammlung()


def test_take_unknown_trade_is_404(client):
    r = client.post("/api/hub/trades/trd_nix/take", json={"ziel": "sammlung"})
    assert r.status_code == 404


def test_lists_stay_closed_for_normal_users(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, is_dealer=0)
    _trade()
    r = c.post("/api/hub/trades/trd_1/take",
               json={"ziel": "liste", "list_id": 1})
    assert r.status_code == 403


def test_old_trade_without_type_guesses_set_from_number(client):
    """Vorgänge von vor 1.85.0 haben keine Art gespeichert."""
    _trade(item_id="21306-1", name="Yellow Submarine", item_type="")
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert _sammlung()[0]["item_type"] == "set"


def test_old_trade_without_type_guesses_minifig(client):
    _trade(item_id="sw1213", item_type="")
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert _sammlung()[0]["item_type"] == "minifig"


def test_trade_without_name_falls_back_to_number(client):
    _trade(name="")
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert _sammlung()[0]["name"] == "sw1213"


def test_foreign_image_paths_are_not_taken_over(client):
    """`/uploads/…` zeigt auf die fremde Instanz – hier wäre es ein toter Link."""
    _trade(img="/uploads/fremd.jpg")
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    # Seit 2.88.56 tritt an seine Stelle das Standardbild von BrickLink.
    assert not _sammlung()[0]["img_url"].startswith("/uploads")


# ---------------------------------------------- Gegenstück: austragen (give)

def _sammlung_anlegen(client, item_id="sw1213", name="Yoda", qty=2,
                      condition="used"):
    r = client.post("/api/collection", json={
        "item_id": item_id, "item_type": "minifig", "name": name,
        "quantity": qty, "condition": condition})
    assert r.status_code == 200, r.text


def test_give_reduces_quantity(client):
    _trade(direction="in")
    _sammlung_anlegen(client, qty=3)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 200, r.text
    assert r.json()["rest"] == 2 and r.json()["geloescht"] is False
    assert _sammlung()[0]["quantity"] == 2


def test_give_deletes_entry_when_nothing_is_left(client):
    _trade(direction="in")
    _sammlung_anlegen(client, qty=1)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.json()["geloescht"] is True
    assert not _sammlung()


def test_give_takes_the_purchase_log_along(client):
    _trade(direction="in")
    client.post("/api/collection", json={
        "item_id": "sw1213", "item_type": "minifig", "name": "Yoda",
        "quantity": 1, "condition": "used", "paid_price": 9.0})
    client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    with core.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0] == 0


def test_give_refuses_more_than_there_is(client):
    _trade(direction="in")
    _sammlung_anlegen(client, qty=1)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 2})
    assert r.status_code == 400
    assert _sammlung()[0]["quantity"] == 1


def test_give_needs_a_condition_when_the_number_exists_twice(client):
    """Neu und gebraucht nebeneinander – raten wäre hier ein verlorenes Stück."""
    _trade(direction="in")
    _sammlung_anlegen(client, qty=1, condition="used")
    _sammlung_anlegen(client, qty=1, condition="new")
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 400
    assert len(_sammlung()) == 2
    r = client.post("/api/hub/trades/trd_1/give",
                    json={"quantity": 1, "condition": "new"})
    assert r.status_code == 200
    rest = _sammlung()
    assert len(rest) == 1 and rest[0]["condition"] == "used"


def test_give_rejects_outgoing_trades(client):
    _trade(direction="out")
    _sammlung_anlegen(client)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 400
    assert _sammlung()[0]["quantity"] == 2


def _angebot(direction):
    tid = _trade(direction=direction)
    with core.db() as conn:
        conn.execute("UPDATE trades SET kind = 'angebot' WHERE id = ?", (tid,))
    return tid


def test_own_offer_goes_out_instead_of_coming_in(client):
    """Ich biete jemandem an, was er sucht: Das Gespräch geht von mir aus,
    der Artikel aber weg – austragen statt übernehmen."""
    _angebot("out")
    _sammlung_anlegen(client, qty=2)
    assert client.post("/api/hub/trades/trd_1/take",
                       json={"ziel": "sammlung"}).status_code == 400
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 200, r.text
    assert _sammlung()[0]["quantity"] == 1


def test_received_offer_comes_in(client):
    """Gegenstück: Wer das Angebot bekommt, übernimmt den Artikel."""
    _angebot("in")
    assert client.post("/api/hub/trades/trd_1/give",
                       json={"quantity": 1}).status_code == 400
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 200, r.text
    assert _sammlung()[0]["item_id"] == "sw1213"


def test_start_trade_passes_the_kind_to_the_hub(client, monkeypatch):
    import community
    import hub
    gesendet = {}
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(community, "_ensure_key_published", lambda: None)
    monkeypatch.setattr(community, "_fremder_schluessel", lambda m: "k")
    monkeypatch.setattr(community.crypto_box, "seal", lambda k, t: "box")

    def anlegen(to, item_id, item_name, box, kind="anfrage", condition=""):
        gesendet["kind"] = kind
        return {"trade_id": "trd_neu", "message_id": 1}
    monkeypatch.setattr(hub, "create_trade", anlegen)
    r = client.post("/api/hub/trades", json={
        "to": "m_bruno", "item_id": "sw1", "item_name": "A", "text": "Hallo",
        "kind": "angebot", "other_name": "Bruno"})
    assert r.status_code == 200, r.text
    assert gesendet["kind"] == "angebot"
    with core.db() as conn:
        t = conn.execute("SELECT kind, other_name FROM trades "
                         "WHERE id = 'trd_neu'").fetchone()
    assert t["kind"] == "angebot" and t["other_name"] == "Bruno"


def test_give_rejects_trades_that_are_not_accepted(client):
    _trade(direction="in", status="open")
    _sammlung_anlegen(client)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 400


def test_give_without_the_item_in_the_collection_is_404(client):
    _trade(direction="in")
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 404


def test_give_marks_the_trade(client):
    _trade(direction="in")
    _sammlung_anlegen(client)
    client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert client.get("/api/hub/trades/trd_1").json()["trade"]["taken_at"]


def test_candidates_list_both_conditions(client):
    _trade(direction="in")
    _sammlung_anlegen(client, qty=2, condition="used")
    _sammlung_anlegen(client, qty=1, condition="new")
    k = client.get("/api/hub/trades/trd_1/candidates").json()["candidates"]
    assert [(c["condition"], c["quantity"]) for c in k] \
        == [("new", 1), ("used", 2)]


def test_candidates_are_empty_when_nothing_matches(client):
    _trade(direction="in")
    assert client.get("/api/hub/trades/trd_1/candidates").json()["candidates"] \
        == []


# ------------------------------------------------- Nach dem Tausch (2.88.56)
# Beim Durchspielen mit zwei Testinstanzen am 25.09.2026 blieb nach einem
# erfolgreichen Tausch einiges stehen, das nicht mehr stimmte.

def _wunsch(client, item_id="sw1213", img="https://x.test/wunsch.png"):
    r = client.post("/api/wanted", json={
        "item_id": item_id, "item_type": "minifig", "name": "Yoda",
        "img_url": img})
    assert r.status_code == 200, r.text


def _wuensche():
    with core.db() as conn:
        return [r["item_id"] for r in conn.execute("SELECT item_id FROM wanted")]


def test_take_into_collection_clears_the_wish(client):
    _trade()
    _wunsch(client)
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.json()["wunsch_erledigt"] is True
    assert _wuensche() == []


def test_take_onto_a_list_keeps_the_wish(client):
    """Auf eine Einkaufsliste heißt: zum Weiterverkaufen – der eigene Wunsch
    ist damit nicht erfüllt."""
    _trade()
    _wunsch(client)
    lid = client.post("/api/lists", json={"name": "Flohmarkt"}).json()["id"]
    r = client.post("/api/hub/trades/trd_1/take",
                    json={"ziel": "liste", "list_id": lid})
    assert r.status_code == 200, r.text
    assert r.json()["wunsch_erledigt"] is False
    assert _wuensche() == ["sw1213"]


def test_received_offer_without_picture_takes_the_wish_picture(client):
    """Wer ein Angebot bekommt, erfährt vom Hub kein Bild."""
    _trade(direction="in", img="")
    with core.db() as conn:
        conn.execute("UPDATE trades SET kind = 'angebot'")
    _wunsch(client)
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert _sammlung()[0]["img_url"] == "https://x.test/wunsch.png"


def test_without_any_picture_the_bricklink_picture_is_used(client):
    _trade(img="")
    client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert _sammlung()[0]["img_url"].endswith("/ItemImage/MN/0/sw1213.png")


def test_give_refreshes_published_offers(client, monkeypatch):
    import community
    angestossen = []
    monkeypatch.setattr(community, "angebote_nachziehen_im_hintergrund",
                        lambda: angestossen.append(1))
    _trade(direction="in")
    _sammlung_anlegen(client, qty=2)
    client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert angestossen == [1]


def test_offers_are_only_refreshed_for_those_who_published(monkeypatch):
    import community
    import hub
    gesendet = []
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(community, "_angebote_senden",
                        lambda: gesendet.append(1))
    monkeypatch.setattr(hub, "last_publish", lambda: None)
    community.angebote_nachziehen_im_hintergrund()
    time.sleep(0.2)
    assert gesendet == []



# ------------------------------------------------- verschickt → angekommen
# Seit 2.89.3: Zwischen Annehmen und Buchen liegen zwei Schritte. Verschickt
# meldet, wer abgibt; angekommen, wer bekommt. Gebucht wird erst danach.

def _hub_an(monkeypatch):
    import community
    import hub
    gemeldet, nachrichten = [], []
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "trade_progress",
                        lambda tid, step: gemeldet.append(step) or {"ok": True})
    monkeypatch.setattr(community, "_fremder_schluessel", lambda m: "k")
    monkeypatch.setattr(community.crypto_box, "seal", lambda k, t: t)
    monkeypatch.setattr(hub, "send_message",
                        lambda tid, box: nachrichten.append(box) or {"message_id": 9})
    return gemeldet, nachrichten


def test_take_waits_for_the_arrival(client):
    _trade(unterwegs=False)
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 400 and "angekommen" in r.text
    assert not _sammlung()


def test_give_waits_until_it_was_sent(client):
    _trade(direction="in", unterwegs=False)
    _sammlung_anlegen(client, qty=2)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert r.status_code == 400 and "verschickt" in r.text
    assert _sammlung()[0]["quantity"] == 2


def test_giver_reports_sent_with_a_message(client, monkeypatch):
    gemeldet, nachrichten = _hub_an(monkeypatch)
    _trade(direction="in", unterwegs=False)       # Anfrage an mich: ich gebe
    r = client.post("/api/hub/trades/trd_1/progress",
                    json={"step": "shipped", "text": "📦 Ist verschickt!"})
    assert r.status_code == 200, r.text
    assert gemeldet == ["shipped"] and nachrichten == ["📦 Ist verschickt!"]
    t = client.get("/api/hub/trades/trd_1").json()["trade"]
    assert t["shipped_at"] and not t["arrived_at"]


def test_receiver_cannot_report_sent(client, monkeypatch):
    gemeldet, _ = _hub_an(monkeypatch)
    _trade(direction="out", unterwegs=False)      # meine Anfrage: ich bekomme
    r = client.post("/api/hub/trades/trd_1/progress", json={"step": "shipped"})
    assert r.status_code == 400 and gemeldet == []


def test_giver_cannot_report_arrival(client, monkeypatch):
    gemeldet, _ = _hub_an(monkeypatch)
    _trade(direction="in", unterwegs=False)
    r = client.post("/api/hub/trades/trd_1/progress", json={"step": "arrived"})
    assert r.status_code == 400 and gemeldet == []


def test_arrival_works_without_shipping(client, monkeypatch):
    """Von Hand zu Hand wird nichts verschickt – die Ankunft geht trotzdem."""
    gemeldet, nachrichten = _hub_an(monkeypatch)
    _trade(direction="out", unterwegs=False)
    r = client.post("/api/hub/trades/trd_1/progress", json={"step": "arrived"})
    assert r.status_code == 200 and gemeldet == ["arrived"]
    assert nachrichten == []                      # ohne Text keine Nachricht
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 200, r.text


def test_steps_need_an_accepted_trade(client, monkeypatch):
    gemeldet, _ = _hub_an(monkeypatch)
    _trade(direction="in", status="open", unterwegs=False)
    r = client.post("/api/hub/trades/trd_1/progress", json={"step": "shipped"})
    assert r.status_code == 400 and gemeldet == []


def test_offer_roles_are_the_other_way_round(client, monkeypatch):
    """Beim Angebot verschickt der Absender und der Empfänger bestätigt."""
    gemeldet, _ = _hub_an(monkeypatch)
    _trade(direction="out", unterwegs=False)
    with core.db() as conn:
        conn.execute("UPDATE trades SET kind = 'angebot'")
    assert client.post("/api/hub/trades/trd_1/progress",
                       json={"step": "arrived"}).status_code == 400
    assert client.post("/api/hub/trades/trd_1/progress",
                       json={"step": "shipped"}).status_code == 200
    assert gemeldet == ["shipped"]


# ------------------------------------------------- abgeschlossen (2.89.4)
# Beide Seiten melden ihre Buchung an den Hub; stehen beide, schließt er.

def _buchung_hub(monkeypatch, antwort="accepted"):
    import hub
    gemeldet = []
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "trade_progress", lambda tid, step:
                        gemeldet.append(step) or {"ok": True, "status": antwort})
    return gemeldet


def test_take_reports_the_booking(client, monkeypatch):
    gemeldet = _buchung_hub(monkeypatch, antwort="closed")
    _trade()
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert gemeldet == ["taken"] and r.json()["status"] == "closed"
    t = client.get("/api/hub/trades/trd_1").json()["trade"]
    assert t["status"] == "closed"


def test_give_reports_the_booking(client, monkeypatch):
    gemeldet = _buchung_hub(monkeypatch)
    _trade(direction="in")
    _sammlung_anlegen(client, qty=2)
    r = client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert gemeldet == ["given"] and r.json()["status"] == "accepted"


def test_booking_stays_when_the_hub_is_away(client, monkeypatch):
    import hub

    def weg(tid, step):
        raise hub.HubError(502, "weg")
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(hub, "trade_progress", weg)
    _trade()
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 200 and _sammlung()


def test_closed_trade_can_still_be_booked_again(client, monkeypatch):
    _buchung_hub(monkeypatch, antwort="closed")
    _trade(status="closed")
    r = client.post("/api/hub/trades/trd_1/take", json={"ziel": "sammlung"})
    assert r.status_code == 200, r.text


def test_offer_sends_the_own_condition(client, monkeypatch):
    """Bei „🤝 Anbieten“ weiß nur die abgebende Seite, ob das Stück neu ist –
    also schickt sie es mit."""
    import community
    import hub
    gesendet = {}
    monkeypatch.setattr(hub, "enabled", lambda: True)
    monkeypatch.setattr(community, "_ensure_key_published", lambda: None)
    monkeypatch.setattr(community, "_fremder_schluessel", lambda m: "k")
    monkeypatch.setattr(community.crypto_box, "seal", lambda k, t: "box")
    monkeypatch.setattr(hub, "create_trade", lambda to, i, n, b, kind="anfrage",
                        condition="": gesendet.update(condition=condition)
                        or {"trade_id": "trd_neu", "message_id": 1})
    _sammlung_anlegen(client, qty=3, condition="new")
    client.post("/api/hub/trades", json={"to": "m_bruno", "item_id": "sw1213",
                "item_name": "Yoda", "text": "Hallo", "kind": "angebot"})
    assert gesendet["condition"] == "new"


# ------------------------------------------------- Kaufbuch beim Austragen
# Bis 2.90 sank nur die Stückzahl – „10,37 € für 5 Stück“ bei 4 in der
# Sammlung. Jetzt gehen die weggegebenen Stücke im Buch mit.

def _posten():
    with core.db() as conn:
        return [(r["quantity"], r["unit_price"]) for r in conn.execute(
            "SELECT quantity, unit_price FROM purchases ORDER BY bought_at, id")]


def _bezahlt():
    with core.db() as conn:
        return conn.execute("SELECT paid_price FROM collection").fetchone()[0]


def test_give_takes_the_bought_pieces_along(client):
    _trade(direction="in")
    client.post("/api/collection", json={
        "item_id": "sw1213", "item_type": "minifig", "name": "Yoda",
        "quantity": 5, "condition": "used", "paid_price": 10.0})
    client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert _posten() == [(4, 2.0)]
    assert _bezahlt() == 8.0


def test_give_takes_the_newest_purchase_first(client):
    """Weg geht der Doppelte – meist das zuletzt gekaufte Stück."""
    _trade(direction="in")
    client.post("/api/collection", json={
        "item_id": "sw1213", "item_type": "minifig", "name": "Yoda",
        "quantity": 1, "condition": "used", "paid_price": 3.0})
    with core.db() as conn:
        conn.execute("UPDATE purchases SET bought_at = 100")
    client.post("/api/collection", json={
        "item_id": "sw1213", "item_type": "minifig", "name": "Yoda",
        "quantity": 2, "condition": "used", "paid_price": 10.0})
    client.post("/api/hub/trades/trd_1/give", json={"quantity": 2})
    assert _posten() == [(1, 3.0)]
    assert _bezahlt() == 3.0


def test_give_without_ledger_shrinks_the_sum(client):
    _trade(direction="in")
    _sammlung_anlegen(client, qty=4)
    with core.db() as conn:
        conn.execute("UPDATE collection SET paid_price = 20.0")
        conn.execute("DELETE FROM purchases")
    client.post("/api/hub/trades/trd_1/give", json={"quantity": 1})
    assert _bezahlt() == 15.0
