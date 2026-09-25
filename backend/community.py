"""Tausch-Netzwerk (Community) – die Seite der Instanz.

Alles, was diese Brickfolio-Instanz mit dem Hub bespricht: Verbindung per
Einladung, Freigaben, Angebote, Mitglieder, Tauschvorgänge mit
Ende-zu-Ende-verschlüsselten Nachrichten, Einladungen. Der Hub selbst ist
ein eigenes Projekt (Cloudflare Worker); hier liegt nur der Teil, den jede
Instanz mitbringt. Die Verbindung zum Hub steckt in `hub.py`, die
Verschlüsselung in `crypto_box.py`.

**Warum eine eigene Datei.** Bis 2.88.51 standen diese 26 Endpunkte mitten
in `main.py`, zwischen Preisen und Einkaufslisten. Das Netzwerk soll zu
einer Community wachsen (Profile, Entdecken); dafür braucht es einen eigenen
Platz. Verhalten hat sich beim Umzug nicht geändert.

**Bleibt optional.** Ohne Einladung ist nichts davon aktiv: `hub.enabled()`
ist erst nach dem Beitritt wahr, und die Oberfläche zeigt den Tab erst dann.

Eingebunden wird der Router am Ende von `main.py` – nach allem, was er von
dort braucht (Anmeldung, Sammlung, Einkaufslisten).
"""
import base64
import os
import re
import time

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import core
import crypto_box
import hub
import integrations
from main import (AddItemBody, ListItemBody, UpdateItemBody,
                  _duplicate_items, _uploads_dir, add_item, add_list_item,
                  admin_user, current_user, update_item)

router = APIRouter()


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


@router.get("/api/hub")
def hub_status(refresh: int = 0, user: dict = Depends(current_user)):
    return _hub_status(refresh=bool(refresh))




@router.post("/api/hub/connect")
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


@router.post("/api/hub/disconnect")
def hub_disconnect(user: dict = Depends(admin_user)):
    # Eine gezeigte Wunschliste nicht im Hub zurücklassen: Das Mitglied
    # bleibt dort bestehen, wer sich trennt, will aber nicht weiter zeigen,
    # was er sucht. Best-effort – ein Hub, der gerade klemmt, soll das
    # Trennen nicht verhindern.
    if core.get_setting("hub_wuensche_zeigen") == "1":
        try:
            p = hub.profile()
            hub.put_profile({"about": p.get("about", ""),
                             "region": p.get("region", ""),
                             "themes": p.get("themes") or [],
                             "wants_public": False,
                             "show_collection": bool(p.get("show_collection"))})
        except Exception:
            pass
    hub.disconnect()
    return {"connected": False}


class ShareBody(BaseModel):
    shared: bool
    qty: int | None = Field(default=None, ge=1, le=9999)


@router.post("/api/collection/{entry_id}/share")
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


@router.get("/api/share/status")
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


@router.post("/api/share/from_duplicates")
def share_from_duplicates(user: dict = Depends(current_user)):
    """Bequemlichkeit: alles aus der Abgabeliste auswählen."""
    ids = [it["id"] for it in _duplicate_items()["items"]]
    with core.db() as conn:
        for i in ids:
            conn.execute("UPDATE collection SET shared = 1 WHERE id = ?", (i,))
    return {"ok": True, "added": len(ids)}


@router.post("/api/share/clear")
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


@router.post("/api/hub/publish")
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


@router.get("/api/hub/offers")
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


@router.get("/api/hub/members")
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


@router.post("/api/hub/trades/sync")
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


@router.get("/api/hub/trades")
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


@router.get("/api/hub/trades/{trade_id}")
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


@router.get("/api/hub/key/{member_id}")
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


@router.post("/api/hub/key/accept")
def hub_key_accept(body: KeyAcceptBody, user: dict = Depends(admin_user)):
    """Einen geänderten Schlüssel annehmen – nach der Rückfrage.

    Bewusst Admin-Sache: Wer hier bestätigt, erklärt, dass er nachgefragt
    hat. Das ist keine Kleinigkeit, die nebenbei weggeklickt gehört.
    """
    crypto_box.forget_key(body.member_id)
    return {"ok": True}


@router.post("/api/hub/trades")
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


@router.post("/api/hub/trades/{trade_id}/messages")
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


@router.delete("/api/hub/trades/{trade_id}")
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


@router.post("/api/hub/trades/{trade_id}/status")
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


@router.post("/api/hub/trades/{trade_id}/take")
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


@router.get("/api/hub/trades/{trade_id}/candidates")
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


@router.post("/api/hub/trades/{trade_id}/give")
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


@router.post("/api/hub/trades/{trade_id}/report")
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


@router.get("/api/hub/invite_quota")
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


@router.post("/api/hub/invite_request")
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


@router.post("/api/hub/invite")
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


# ------------------------------------------------ Community: Profile, Entdecken
#
# **Das Entdecken rechnet diese Instanz aus, nicht der Hub.** Der Hub liefert
# nur die Listen: Angebote aller, die gezeigten Wunschlisten und die Profile.
# Welche davon zur eigenen Wunschliste und zu den eigenen Doppelten passen,
# steht nur hier fest – die eigene Wunschliste verlässt die Instanz dafür
# nicht. Gezeigt wird sie erst, wenn jemand „Wunschliste zeigen" einschaltet.
#
# Die Schalter stehen im Hub-Profil; hier liegt nur ein Merker davon
# (`hub_wuensche_zeigen`), damit nicht jede Änderung an der Wunschliste
# erst beim Hub nachfragen muss.

WUENSCHE_MAX = 1000                  # so viele nimmt der Hub je Mitglied


def _hub_fehler(e: Exception):
    """Aus einem Hub-Fehler die passende Antwort machen."""
    if isinstance(e, hub.HubError):
        if e.status == 404 and "unbekannter Endpunkt" in (e.message or ""):
            raise HTTPException(501, "Der Hub kennt Profile noch nicht – "
                                     "er muss erst aktualisiert werden.")
        raise HTTPException(502, f"Hub: {e.message}")
    raise HTTPException(502, "Hub nicht erreichbar")


def _verbunden():
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")


def _eigene_wuensche() -> list:
    with core.db() as conn:
        rows = conn.execute(
            "SELECT item_id, item_type, name, img_url FROM wanted "
            "ORDER BY name COLLATE NOCASE").fetchall()
    return [dict(r) for r in rows]


def wuensche_nachziehen(erzwingen: bool = False) -> int | None:
    """Die eigene Wunschliste zum Hub bringen – nur, wenn sie gezeigt wird.

    Gibt die Zahl der gezeigten Wünsche zurück, oder None, wenn nichts zu tun
    war. Schickt nur, wenn sich seit dem letzten Mal etwas geändert hat.
    """
    if not hub.enabled() or core.get_setting("hub_wuensche_zeigen") != "1":
        return None
    liste = [{"item_id": w["item_id"], "item_type": w["item_type"],
              "name": w["name"], "img_url": w["img_url"] or ""}
             for w in _eigene_wuensche()][:WUENSCHE_MAX]
    import hashlib
    import json as _json
    stand = hashlib.sha256(_json.dumps(liste, sort_keys=True)
                           .encode()).hexdigest()
    if not erzwingen and core.get_setting("hub_wuensche_stand") == stand:
        return None
    hub.put_wants(liste)
    core.set_setting("hub_wuensche_stand", stand)
    return len(liste)


def wuensche_nachziehen_im_hintergrund() -> None:
    """Nach einer Änderung an der Wunschliste – ohne die Antwort aufzuhalten."""
    if not hub.enabled() or core.get_setting("hub_wuensche_zeigen") != "1":
        return
    import threading

    def lauf():
        try:
            wuensche_nachziehen()
        except Exception:
            pass                  # beim nächsten Entdecken klappt es wieder
    threading.Thread(target=lauf, daemon=True).start()


def _sammlung_figuren() -> int:
    with core.db() as conn:
        r = conn.execute("SELECT COALESCE(SUM(quantity), 0) AS n FROM "
                         "collection WHERE item_type = 'minifig'").fetchone()
    return int(r["n"] or 0)


def _abgebbar() -> dict:
    """Was diese Instanz abgeben kann: Doppelte und ausdrücklich Geteiltes.
    Schlüssel (Nummer, Typ) → Menge."""
    frei = {}
    for d in _duplicate_items()["items"]:
        schluessel = (d["item_id"], d["item_type"])
        frei[schluessel] = frei.get(schluessel, 0) + (d["surplus"] or 0)
    with core.db() as conn:
        for r in _shared_rows(conn):
            schluessel = (r["item_id"], r["item_type"])
            frei.setdefault(schluessel,
                            r["share_qty"] or r["quantity"] or 1)
    return frei


class ProfilBody(BaseModel):
    about: str = Field(default="", max_length=280)
    region: str = Field(default="", max_length=60)
    themes: list[str] = Field(default_factory=list, max_length=20)
    wants_public: bool = False
    show_collection: bool = False


@router.get("/api/hub/profil")
def eigenes_profil(user: dict = Depends(current_user)):
    _verbunden()
    try:
        p = hub.profile()
    except Exception as e:
        _hub_fehler(e)
    # Den Merker nachführen – der Hub ist die Quelle.
    core.set_setting("hub_wuensche_zeigen", "1" if p.get("wants_public")
                     else "")
    p["figuren_hier"] = _sammlung_figuren()
    return p


@router.put("/api/hub/profil")
def profil_speichern(body: ProfilBody, user: dict = Depends(current_user)):
    _verbunden()
    daten = body.model_dump()
    daten["themes"] = [t.strip()[:40] for t in body.themes if t.strip()]
    if body.show_collection:
        daten["collection_count"] = _sammlung_figuren()
    try:
        p = hub.put_profile(daten)
    except Exception as e:
        _hub_fehler(e)
    core.set_setting("hub_wuensche_zeigen", "1" if body.wants_public else "")
    if body.wants_public:
        try:
            wuensche_nachziehen(erzwingen=True)
        except Exception:
            pass                  # das Profil steht; die Liste folgt später
    else:
        core.set_setting("hub_wuensche_stand", "")
    p["figuren_hier"] = _sammlung_figuren()
    return p


@router.get("/api/hub/profil/{member_id}")
def fremdes_profil(member_id: str, user: dict = Depends(current_user)):
    """Profil eines Mitglieds – dazu, was davon hier zusammenpasst."""
    _verbunden()
    try:
        p = hub.profile(member_id)
    except Exception as e:
        _hub_fehler(e)
    frei = _abgebbar()
    gesucht = {(w["item_id"], w["item_type"]) for w in _eigene_wuensche()}
    for w in p.get("wants") or []:
        w["hier_abgebbar"] = frei.get((w["item_id"],
                                       w.get("item_type") or "minifig"), 0)
    for o in p.get("offers") or []:
        o["auf_wunschliste"] = (o["item_id"], o.get("item_type") or "minifig") \
            in gesucht
    return p


@router.get("/api/hub/entdecken")
def entdecken(user: dict = Depends(current_user)):
    """Wer hat, was ich suche – wer sucht, was ich abgeben kann – wer passt."""
    _verbunden()
    try:
        wuensche_nachziehen()
    except Exception:
        pass                      # Entdecken geht auch ohne frischen Stand
    try:
        angebote = hub.offers()
        profile = hub.profiles()
        fremde_wuensche = hub.wants()
    except Exception as e:
        _hub_fehler(e)

    meine = _eigene_wuensche()
    gesucht = {(w["item_id"], w["item_type"]) for w in meine}
    hat = [{"member_id": o["member_id"], "display_name": o.get("display_name"),
            "item_id": o["item_id"], "item_type": o.get("item_type"),
            "name": o["name"], "img_url": o.get("img_url"),
            "img_data": o.get("img_data"), "condition": o.get("condition"),
            "qty": o.get("qty") or 1}
           for o in angebote
           if (o["item_id"], o.get("item_type") or "minifig") in gesucht]

    frei = _abgebbar()
    sucht = [{"member_id": w["member_id"], "display_name": w["display_name"],
              "item_id": w["item_id"], "item_type": w.get("item_type"),
              "name": w["name"], "img_url": w.get("img_url"),
              "hier_abgebbar": frei[(w["item_id"],
                                     w.get("item_type") or "minifig")]}
             for w in fremde_wuensche
             if (w["item_id"], w.get("item_type") or "minifig") in frei]

    ich = next((p for p in profile if p.get("eigen")), {})
    meine_themen = {t.lower() for t in ich.get("themes") or []}
    passt = []
    for p in profile:
        if p.get("eigen"):
            continue
        gemeinsam = [t for t in p.get("themes") or []
                     if t.lower() in meine_themen]
        if gemeinsam:
            passt.append({**p, "gemeinsam": gemeinsam})
    passt.sort(key=lambda p: (-len(p["gemeinsam"]), -(p.get("offers") or 0),
                              (p.get("display_name") or "").lower()))

    return {"hat": hat, "sucht": sucht, "passt": passt,
            "wuensche_zeigen": core.get_setting("hub_wuensche_zeigen") == "1",
            "meine_themen": ich.get("themes") or [],
            "wuensche_anzahl": len(meine),
            "profil_leer": not (ich.get("themes") or ich.get("region"))}
