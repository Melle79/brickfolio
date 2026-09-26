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
import hashlib
import json
import os
import functools
import re
import threading
import time

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import core
import crypto_box
import hub
import integrations
from main import (AddItemBody, ListItemBody, UpdateItemBody,
                  _duplicate_items, _uploads_dir,
                  _wuensche_geaendert,
                  add_item, add_list_item, admin_user, current_user,
                  update_item)

router = APIRouter()


# ---------------------------------------------------------------- Tausch-Hub

class HubConnectBody(BaseModel):
    token: str | None = Field(default=None, max_length=200)
    invite_code: str | None = Field(default=None, max_length=200)
    display_name: str | None = Field(default=None, max_length=80)


class HubInviteBody(BaseModel):
    note: str = Field(default="", max_length=120)
    expires_in_days: int = Field(default=0, ge=0, le=365)


def _hub_antwort(e: "hub.HubError") -> HTTPException:
    """Eine Absage des Hubs als passende Antwort weitergeben.

    Bis 2.90.20 wurde **jede** zu 502. Die Oberfläche zeichnet alles ab 500
    als Serverfehler auf – eine Sperre, ein aufgebrauchtes Kontingent oder
    ein schon benutzter Einladungscode landeten so als „🐞 Fehler“ im
    Bericht, bei gesperrter Instanz alle 15 Sekunden neu (Tausch-Gesamttest
    26.09.2026). Absagen sind gewöhnlicher Betrieb: Sie behalten ihren
    Status. Nur ein 401 nicht – den liest die Oberfläche als „Sitzung
    abgelaufen“ und meldet ab.
    """
    status = getattr(e, "status", 0) or 0
    if status == 401:
        if hub.verwaist():
            return HTTPException(409, "Der Hub kennt diese Instanz nicht mehr "
                                      "– vermutlich hat der Hub-Admin sie "
                                      "entfernt. Unter Mehr → Tausch-Netzwerk "
                                      "abmelden und mit einer neuen Einladung "
                                      "wieder beitreten.")
        return HTTPException(400, f"Hub: {e.message}")
    if 400 <= status < 500:
        return HTTPException(status, f"Hub: {e.message}")
    return HTTPException(502, f"Hub: {e.message}")


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
    pause = hub.pause() if hub.enabled() else None
    if pause and pause.get("bis"):
        _pause_melden(pause)
        # Nur die jüngste Pause zeigen, und nur zwei Wochen lang – danach
        # ist sie Geschichte.
        if pause["bis"] < time.time() - 14 * 86400:
            pause = None
    tage = core.get_setting("hub_inaktiv_tage")
    hinweise = hub.hinweise() if hub.enabled() else []
    _hinweise_melden(hinweise)
    return {"connected": hub.enabled(), "url": c["url"],
            "member_id": c["member_id"], "display_name": c["display_name"],
            "is_admin": c["is_admin"], "last_publish": hub.last_publish(),
            "blocked": hub.blocked(),
            "verwaist": hub.verwaist(),
            "block": hub.block_info() if hub.blocked() else None,
            "pause": pause, "hinweise": hinweise,
            "inaktiv_tage": int(tage) if tage and tage.isdigit() else None}


def _hinweise_melden(hinweise: list) -> None:
    """Jeden Hinweis des Admins einmal als Mitteilung hinterlegen."""
    gemeldet = set((core.get_setting("hub_hinweise_gemeldet") or "").split(","))
    neu = [h for h in hinweise if str(h.get("id")) not in gemeldet]
    if not neu:
        return
    core.set_setting("hub_hinweise_gemeldet", ",".join(
        sorted(gemeldet | {str(h["id"]) for h in neu} - {""})))
    try:
        from main import _notify
    except Exception:
        return
    for h in neu:
        _notify("hub_hinweis", "📣 Mitteilung vom Hub-Admin",
                "Der Hub-Admin hat dir eine Mitteilung zum Tausch-Netzwerk "
                "geschickt. Du findest sie oben im Tausch-Tab.",
                item_type="system", item_id=f"hinweis-{h['id']}")


@router.post("/api/hub/hinweise/{notice_id}/gelesen")
def hub_hinweis_gelesen(notice_id: int, user: dict = Depends(current_user)):
    """„Verstanden“ – der Hinweis verschwindet hier und beim Hub."""
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    try:
        hub.ack_notice(notice_id)
    except hub.HubError as e:
        if e.status != 404:
            raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")
    rest = [h for h in hub.hinweise() if h.get("id") != notice_id]
    core.set_setting("hub_hinweise", json.dumps(rest))
    return {"ok": True, "hinweise": rest}


def _pause_melden(pause: dict) -> None:
    """Einmal je Pause einen Hinweis hinterlegen.

    Während der Pause meldet sich die Instanz ja nicht – sonst gäbe es keine.
    Erfahren kann sie es also erst beim Zurückkommen, und genau dann soll
    es auch jemand lesen: Die Angebote sind wieder sichtbar, stammen aber
    womöglich von vor Wochen.
    """
    bis = int(pause.get("bis") or 0)
    if not bis or bis <= int(core.get_setting("hub_pause_gemeldet") or 0):
        return
    core.set_setting("hub_pause_gemeldet", str(bis))
    try:
        from main import _notify
        _notify("hub_pause", "⏸ Deine Angebote waren pausiert",
                "Du warst eine Weile nicht im Tausch-Netzwerk, deshalb hat der "
                "Hub deine Angebote und Wünsche ausgeblendet. Jetzt sind sie "
                "wieder sichtbar – schau am besten, ob noch alles stimmt.",
                item_type="system", item_id=f"pause-{bis}")
    except Exception:
        pass


@router.get("/api/hub")
def hub_status(refresh: int = 0, user: dict = Depends(current_user)):
    return _hub_status(refresh=bool(refresh))




@router.post("/api/hub/connect")
def hub_connect(body: HubConnectBody, user: dict = Depends(admin_user)):
    if hub.enabled():
        # Ein zweiter Beitritt legte ein zweites Mitglied an; das alte blieb
        # samt Angeboten aktiv, und niemand holte seine Nachrichten mehr ab
        # (Tausch-Gesamttest 26.09.2026). Nur wenn der Hub uns vergessen hat,
        # ist ein Neubeitritt der richtige Weg.
        if not hub.verwaist():
            raise HTTPException(409, "Diese Instanz ist schon mit dem Tausch-"
                                     "Netzwerk verbunden – zum Wechseln erst "
                                     "abmelden.")
        hub.disconnect()
        with core.db() as conn:
            conn.execute("DELETE FROM hub_invites")
            conn.execute("UPDATE trades SET ehemalig = 1")
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
        raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


@router.post("/api/hub/disconnect")
def hub_disconnect(user: dict = Depends(admin_user)):
    """Aus dem Netzwerk abmelden – und das dem Hub auch sagen.

    Bis 2.90 vergaß nur die Instanz ihre Verbindung: Im Hub blieben
    Angebote und gezeigte Wünsche stehen, andere fragten bei jemandem an,
    der nie antworten würde, und in der Verwaltung sah das Mitglied aus wie
    jedes andere. Jetzt meldet sich die Instanz ab; der Hub nimmt alles
    heraus und führt das Mitglied als „abgemeldet“.

    Klemmt der Hub gerade, wird trotzdem getrennt – festhalten lässt sich
    niemand. Die Antwort sagt dann, dass der Hub nichts davon weiß; die
    Angebote verschwinden dort spätestens mit der Pause wegen Inaktivität.
    """
    informiert = False
    verwaist = hub.verwaist()
    try:
        if not verwaist:
            hub.leave()
            informiert = True
    except Exception:
        # Ein Hub vor 1.17.0 kennt das Abmelden nicht – dann wenigstens die
        # gezeigte Wunschliste zurückziehen, wie bisher.
        if core.get_setting("hub_wuensche_zeigen") == "1":
            try:
                p = hub.profile()
                hub.put_profile({
                    "about": p.get("about", ""), "region": p.get("region", ""),
                    "themes": p.get("themes") or [], "wants_public": False,
                    "show_collection": bool(p.get("show_collection"))})
            except Exception:
                pass
    hub.disconnect()
    with core.db() as conn:
        conn.execute("DELETE FROM hub_invites")
        # Die Gespräche bleiben lesbar, gehören aber zur alten Mitgliedschaft.
        # Sonst hielt der Abgleich nach einem Wiederbeitritt alle für „vom
        # Gegenüber gelöscht“.
        conn.execute("UPDATE trades SET ehemalig = 1")
    # Kannte der Hub uns ohnehin nicht mehr, gibt es dort nichts abzumelden –
    # „nicht erreichbar“ wäre dann die falsche Auskunft.
    return {"connected": False, "hub_informiert": informiert or verwaist}


class ShareBody(BaseModel):
    shared: bool
    qty: int | None = Field(default=None, ge=1, le=9999)
    # Tausch, Verkauf oder beides. Ohne Angabe bleibt, was schon eingestellt
    # war (anfangs: Tausch).
    deal: str | None = Field(default=None, pattern="^(tausch|verkauf|beides)$")


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
        if body.deal and body.shared:
            conn.execute("UPDATE collection SET share_deal = ? WHERE id = ?",
                         ("" if body.deal == "tausch" else body.deal,
                          entry_id))
    return {"ok": True, "shared": body.shared, "qty": qty,
            "deal": body.deal}


def _shared_rows(conn):
    return conn.execute(
        "SELECT id, item_id, item_type, name, img_url, bricklink_url, "
        "condition, quantity, share_qty, share_deal FROM collection "
        "WHERE shared = 1 "
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
               "share_qty": r["share_qty"] or r["quantity"],
               "deal": r["share_deal"] or "tausch"} for r in rows]

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
    """Bequemlichkeit: alles aus der Abgabeliste auswählen.

    **Mit der abgebbaren Menge, nicht mit dem ganzen Bestand.** Bis 2.90.20
    wurde nur `shared` gesetzt; beim Veröffentlichen galt dann
    `share_qty or quantity` – angeboten wurden also auch das Exemplar zum
    Behalten und die Figuren, die in eigenen Sets stecken.
    """
    posten = [(it["id"], it["surplus"]) for it in _duplicate_items()["items"]
              if it.get("surplus", 0) > 0]
    with core.db() as conn:
        for i, menge in posten:
            conn.execute("UPDATE collection SET shared = 1, share_qty = ? "
                         "WHERE id = ?", (menge, i))
    return {"ok": True, "added": len(posten)}


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


def _angebote_senden() -> dict:
    """Die geteilten Zeilen als Angebote an den Hub – ersetzt die alten."""
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
            "deal": r["share_deal"] or "tausch",
        })
    return hub.publish(offers) or {"count": len(offers)}


def angebote_nachziehen_im_hintergrund() -> None:
    """Nach einem Tausch stimmen die veröffentlichten Stückzahlen nicht mehr.

    Bis 2.88.55 stand ein weggetauschtes Stück weiter im Netzwerk, bis man
    von Hand neu veröffentlichte – beim Gegenüber also als Angebot, das es
    nicht mehr gab. Nachgezogen wird nur, wer schon einmal veröffentlicht
    hat; wer das nie wollte, dem schickt auch ein Tausch nichts.
    """
    if not hub.enabled() or not hub.last_publish():
        return
    import threading

    def lauf():
        try:
            _angebote_senden()
        except Exception:
            pass                  # beim nächsten Veröffentlichen klappt es
    threading.Thread(target=lauf, daemon=True).start()


@router.post("/api/hub/publish")
def hub_publish(user: dict = Depends(admin_user)):
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    try:
        res = _angebote_senden()
        return {"ok": True, "count": res.get("count", 0)}
    except hub.HubError as e:
        raise _hub_antwort(e)
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
        raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


@router.get("/api/hub/members")
def hub_members(user: dict = Depends(current_user)):
    if not hub.enabled():
        return {"members": []}
    try:
        return {"members": hub.members()}
    except hub.HubError as e:
        raise _hub_antwort(e)
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


def _buchung_melden(trade_id: str, kommt: bool) -> str | None:
    """Dem Hub sagen, dass hier gebucht ist – ausgetragen oder übernommen.

    Haben beide Seiten gebucht, schließt der Hub den Tausch. Geht das gerade
    nicht, holt es der nächste Abgleich nach; die Buchung selbst steht.
    Gibt den neuen Status zurück, wenn der Hub ihn nennt.
    """
    try:
        res = hub.trade_progress(trade_id, "taken" if kommt else "given")
    except (hub.HubError, requests.RequestException):
        return None
    status = res.get("status")
    if status in ("accepted", "closed"):
        with core.db() as conn:
            conn.execute("UPDATE trades SET status = ? WHERE id = ?",
                         (status, trade_id))
    return status


def _buchungen_nachmelden(remote: list, me: str) -> None:
    """Hier gebucht, dem Hub aber (noch) nicht gemeldet? Dann jetzt.

    Fängt zweierlei auf: eine Meldung, die beim Buchen nicht durchkam, und
    Tausche, die vor 2.89.4 gebucht wurden – die schließen sich so beim
    ersten Abgleich von selbst. Ein Hub vor 1.16.0 schickt die Felder gar
    nicht mit; dann wird auch nichts gemeldet.
    """
    with core.db() as conn:
        lokal = {r["id"]: r for r in conn.execute(
            "SELECT id, direction, kind, taken_at FROM trades "
            "WHERE taken_at IS NOT NULL").fetchall()}
    for t in remote:
        r = lokal.get(t["id"])
        if not r or "given_at" not in t or t["status"] not in (
                "accepted", "closed"):
            continue
        kommt = _kommt_zu_mir(r)
        if not t.get("taken_at" if kommt else "given_at"):
            _buchung_melden(t["id"], kommt)


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
                kind = "angebot" if t.get("kind") == "angebot" else "anfrage"
                conn.execute(
                    "INSERT INTO trades (id, direction, other_id, other_name, "
                    "item_id, item_name, status, created_at, updated_at, kind, "
                    "shipped_at, arrived_at, condition) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(id) DO UPDATE SET status = excluded.status, "
                    "updated_at = excluded.updated_at, "
                    "other_name = excluded.other_name, kind = excluded.kind, "
                    # Ein älterer Hub kennt die Schritte nicht – dann bleibt,
                    # was hier schon stand.
                    "shipped_at = COALESCE(excluded.shipped_at, shipped_at), "
                    "arrived_at = COALESCE(excluded.arrived_at, arrived_at), "
                    # Den Zustand kennt die Seite, die angefragt hat, schon
                    # vom Angebot; nur wo er fehlt, kommt er vom Hub.
                    "condition = CASE WHEN trades.condition = '' "
                    "THEN excluded.condition ELSE trades.condition END",
                    (t["id"], "out" if mine else "in", other_id, other_name,
                     t["item_id"], t["item_name"], t["status"],
                     t["created_at"], t["updated_at"], kind,
                     t.get("shipped_at"), t.get("arrived_at"),
                     t.get("condition") if t.get("condition") in
                     ("new", "used") else ""))
                # Nur bei eigenen Anfragen sagt der Hub etwas darüber, ob das
                # Angebot noch steht – bei eingehenden ist es mein eigenes,
                # und bei einem Angebot biete ja ich selbst an.
                # Ein älterer Hub schickt den Status nicht – dann bleibt er.
                status_gegen = t.get("to_status" if mine else "from_status")
                if status_gegen:
                    conn.execute("UPDATE trades SET other_status = ? "
                                 "WHERE id = ?", (status_gegen, t["id"]))
                if mine and "item_available" in t:
                    weg = kind == "anfrage" and not t["item_available"]
                    conn.execute("UPDATE trades SET item_gone = ? WHERE id = ?",
                                 (1 if weg else 0, t["id"]))
            # Was der Hub nicht mehr kennt, hat das Gegenüber gelöscht. Der
            # Verlauf bleibt hier lesbar, aber antworten geht nicht mehr –
            # bis 2.88.55 stand so ein Gespräch ewig als „offen“ da.
            # Nur wenn die Liste vollständig ist (der Hub schickt höchstens
            # 200), sonst hielte man ältere für gelöscht.
            #
            # **Zwei Ausnahmen** (Tausch-Gesamttest 26.09.2026): Gespräche aus
            # einer früheren eigenen Mitgliedschaft kennt der Hub natürlich
            # nicht mehr – gelöscht hat da niemand etwas. Und war ein Tausch
            # schon zugesagt, bleibt die Zusage: Die Ware kann unterwegs
            # sein, verbuchen muss weiter gehen.
            if len(remote) < 200:
                da = {t["id"] for t in remote}
                for r in conn.execute(
                        "SELECT id, status FROM trades WHERE status != "
                        "'removed' AND ehemalig = 0 AND entfernt = 0"
                        ).fetchall():
                    if r["id"] in da:
                        continue
                    if r["status"] in ("accepted", "closed"):
                        conn.execute("UPDATE trades SET entfernt = 1 "
                                     "WHERE id = ?", (r["id"],))
                    else:
                        conn.execute("UPDATE trades SET status = 'removed' "
                                     "WHERE id = ?", (r["id"],))
        _buchungen_nachmelden(remote, me)
        _meldungen_abgleichen()
        for t in remote:
            if t.get("unread") or t["id"] == focus:
                new_msgs += _sync_trade(t["id"])
        return {"trades": len(remote), "new_messages": new_msgs}
    except hub.HubError as e:
        raise _hub_antwort(e)
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
            " ORDER BY m.created_at DESC, m.id DESC LIMIT 1) AS last_body, "
            "(SELECT r.status FROM hub_reports r WHERE r.trade_id = t.id "
            " ORDER BY r.created_at DESC, r.id DESC LIMIT 1) AS report_status, "
            # Wartet eine Rückfrage des Admins auf Antwort?
            "(SELECT m.from_admin FROM hub_report_messages m JOIN hub_reports r "
            " ON r.id = m.report_id WHERE r.trade_id = t.id "
            " ORDER BY m.created_at DESC, m.id DESC LIMIT 1) AS report_frage "
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
    return {"trade": dict(t), "messages": [dict(m) for m in msgs],
            "report": _meldung_zum_gespraech(trade_id)}


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
    # „anfrage“: ich möchte den Artikel des Gegenübers. „angebot“: das
    # Gegenüber sucht ihn, und ich gebe meinen ab.
    kind: str = Field(default="anfrage", pattern="^(anfrage|angebot)$")
    # Name des Gegenübers, wie er am Angebot stand. Sonst stand bis zum
    # ersten Abgleich „an ?“ da – und für immer, wenn das Gegenüber das
    # Gespräch vorher löschte.
    other_name: str = Field(default="", max_length=80)


def _kommt_zu_mir(t) -> bool:
    """Wandert der Artikel dieses Vorgangs zu mir – oder geht er weg?

    Bei einer Anfrage kommt er zum Anfragenden, bei einem Angebot zum
    Empfänger. Die Richtung des Gesprächs allein sagt es also nicht.
    """
    return (t["direction"] == "out") != ((t["kind"] or "anfrage") == "angebot")


def _eigener_zustand(item_id: str) -> str:
    """Welches eigene Stück geht bei einem Angebot weg – neu oder gebraucht?

    Steht die Nummer in beiden Zuständen da, das mit mehr Stück: Abgegeben
    wird aus dem Überschuss.
    """
    with core.db() as conn:
        r = conn.execute("SELECT condition FROM collection WHERE item_id = ? "
                         "ORDER BY quantity DESC LIMIT 1", (item_id,)).fetchone()
    return r["condition"] if r and r["condition"] in ("new", "used") else ""


def _fremder_schluessel(member_id: str, name: str = "") -> str:
    """Öffentlichen Schlüssel eines Gegenübers holen – und wiedererkennen.

    Der Hub verteilt diese Schlüssel. Nähme man sie jedes Mal ungeprüft
    hin, stünde er in der Lage, einen eigenen unterzuschieben und
    mitzulesen. Deshalb zählt der zuerst gesehene.
    """
    try:
        daten = hub.member_key(member_id)
    except hub.HubError as e:
        # **Gesperrt heißt nicht verschwunden.** Der Hub gibt Schlüssel nur
        # für aktive Mitglieder heraus; für ein gesperrtes Gegenüber kam
        # „Mitglied nicht gefunden“, obwohl der Hinweis im Gespräch
        # verspricht, dass die Nachricht nach der Freischaltung ankommt
        # (Tausch-Gesamttest 26.09.2026). Den schon gemerkten Schlüssel zu
        # nehmen ist sicher – er ist ja genau der, dem wir vertrauen.
        if e.status == 404:
            with core.db() as conn:
                row = conn.execute("SELECT public_key FROM hub_keys WHERE "
                                   "member_id = ?", (member_id,)).fetchone()
            if row:
                return row["public_key"]
        raise
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
        zustand = body.condition if body.condition in ("new", "used") \
            else ""
        if body.kind == "angebot" and not zustand:
            zustand = _eigener_zustand(body.item_id)
        res = hub.create_trade(body.to, body.item_id, body.item_name, box,
                               body.kind, zustand)
        tid = res["trade_id"]
        now_ts = int(time.time())
        with core.db() as conn:
            conn.execute(
                "INSERT INTO trades (id, direction, other_id, other_name, "
                "item_id, item_name, status, created_at, updated_at, read_at, "
                "item_type, img_url, bricklink_url, condition, kind) "
                "VALUES (?, 'out', ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?)",
                (tid, body.to, body.other_name.strip(), body.item_id,
                 body.item_name,
                 now_ts, now_ts, now_ts,
                 body.item_type if body.item_type in
                 ("minifig", "set", "part") else "",
                 body.img_url if body.img_url.startswith(
                     ("http://", "https://")) else "",
                 body.bricklink_url if body.bricklink_url.startswith("http")
                 else "",
                 zustand, body.kind))
            conn.execute(
                "INSERT INTO trade_messages (trade_id, hub_id, mine, body, "
                "created_at) VALUES (?, ?, 1, ?, ?)",
                (tid, res.get("message_id"), body.text, now_ts))
        return {"ok": True, "trade_id": tid}
    except hub.HubError as e:
        raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


class TradeMessageBody(BaseModel):
    # Nur Leerzeichen ist keine Nachricht – die Oberfläche kürzt, die
    # Schnittstelle nahm es bisher an und schickte eine leere Blase.
    text: str = Field(min_length=1, max_length=2000, pattern=r"\S")


@router.post("/api/hub/trades/{trade_id}/messages")
def hub_send_message(trade_id: str, body: TradeMessageBody,
                     user: dict = Depends(current_user)):
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    with core.db() as conn:
        t = conn.execute("SELECT other_id, other_status FROM trades "
                         "WHERE id = ?", (trade_id,)).fetchone()
    if not t:
        raise HTTPException(404, "Vorgang nicht gefunden")
    # Abgemeldet oder gelöscht: gar nicht erst versuchen. Sonst scheiterte
    # es schon am Schlüssel des Gegenübers, und heraus kam ein unklarer
    # „502 – Mitglied nicht gefunden“ statt des eigentlichen Grunds.
    if t["other_status"] in ("left", "gone"):
        raise HTTPException(410, "Das Gegenüber hat das Tausch-Netzwerk "
                                 "verlassen")
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
        if e.status == 410:
            # Gegenüber abgemeldet – gleich merken, damit das Gespräch es
            # zeigt, auch bevor der nächste Abgleich kommt.
            with core.db() as conn:
                conn.execute("UPDATE trades SET other_status = 'left' "
                             "WHERE id = ?", (trade_id,))
            raise HTTPException(410, e.message)
        raise _hub_antwort(e)
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
                raise _hub_antwort(e)
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
    with core.db() as conn:
        t = conn.execute("SELECT direction, status FROM trades WHERE id = ?",
                         (trade_id,)).fetchone()
    # **Wer darf was?** Annehmen und Ablehnen nur, wer gefragt wurde, und nur
    # solange offen; Abschließen nur nach einer Zusage; Wiederöffnen nie.
    # Bisher blendete nur die Oberfläche die Knöpfe aus – über die
    # Schnittstelle nahm man die eigene Anfrage an (Tausch-Gesamttest).
    if t:
        erlaubt = {
            "accepted": t["direction"] == "in" and t["status"] == "open",
            "declined": t["direction"] == "in" and t["status"] == "open",
            "closed": t["status"] == "accepted",
            "open": False,
        }[body.status]
        if not erlaubt:
            raise HTTPException(409, "Dieser Schritt passt nicht zum Stand "
                                     "des Gesprächs.")
    try:
        hub.set_trade_status(trade_id, body.status)
        with core.db() as conn:
            conn.execute("UPDATE trades SET status = ? WHERE id = ?",
                         (body.status, trade_id))
        return {"ok": True, "status": body.status}
    except hub.HubError as e:
        raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


class TradeProgressBody(BaseModel):
    step: str = Field(pattern="^(shipped|arrived)$")
    # Geht als ganz normale Nachricht ins Gespräch – so erfährt das
    # Gegenüber davon wie von jeder anderen Nachricht, samt Hinweis.
    text: str = Field(default="", max_length=2000)


@router.post("/api/hub/trades/{trade_id}/progress")
def hub_trade_progress(trade_id: str, body: TradeProgressBody,
                       user: dict = Depends(current_user)):
    """Zwischen Zusage und Sammlung: verschickt, dann angekommen.

    Bis 2.89 ging es von „angenommen“ direkt ans Übernehmen und Austragen –
    ob das Päckchen unterwegs oder schon da war, stand nirgends. Verschickt
    meldet, wer abgibt; angekommen, wer bekommt. Erst danach wird gebucht.
    """
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    with core.db() as conn:
        t = conn.execute("SELECT * FROM trades WHERE id = ?",
                         (trade_id,)).fetchone()
    if not t:
        raise HTTPException(404, "Vorgang nicht gefunden")
    if t["status"] != "accepted":
        raise HTTPException(400, "Der Tausch ist noch nicht angenommen.")
    kommt = _kommt_zu_mir(t)
    if body.step == "shipped" and kommt:
        raise HTTPException(400, "Verschicken kann nur, wer abgibt.")
    if body.step == "arrived" and not kommt:
        raise HTTPException(400, "Die Ankunft bestätigt, wer den Artikel "
                                 "bekommt.")
    try:
        hub.trade_progress(trade_id, body.step)
    except hub.HubError as e:
        raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")
    spalte = "shipped_at" if body.step == "shipped" else "arrived_at"
    jetzt = int(time.time())
    with core.db() as conn:
        conn.execute(f"UPDATE trades SET {spalte} = COALESCE({spalte}, ?) "
                     "WHERE id = ?", (jetzt, trade_id))
    if body.text.strip():
        try:
            hub_send_message(trade_id, TradeMessageBody(text=body.text.strip()),
                             user)
        except HTTPException:
            pass        # der Schritt steht; die Nachricht ist nur Beiwerk
    return {"ok": True, "step": body.step}


# **Buchungen nacheinander.** Zwei gleichzeitige „Austragen“ lasen beide
# dieselbe Menge, setzten beide „3 → 2“ – und das Kaufbuch zog zweimal ab
# (Tausch-Gesamttest 26.09.2026). Die App läuft in einem Prozess; eine
# Sperre um Übernehmen und Austragen reicht.
_buchen_sperre = threading.Lock()


def _nacheinander(f):
    @functools.wraps(f)
    def innen(*args, **kwargs):
        with _buchen_sperre:
            return f(*args, **kwargs)
    return innen


class TradeTakeBody(BaseModel):
    ziel: str = Field(default="sammlung", pattern="^(sammlung|liste)$")
    list_id: int | None = Field(default=None, ge=1)
    quantity: int = Field(default=1, ge=1, le=999)
    condition: str = Field(default="used", pattern="^(new|used)$")
    paid_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)


def _art_raten(item_id: str) -> str:
    """Set oder Figur? Für Vorgänge, die noch ohne Art gespeichert wurden.

    Setnummern sind reine Ziffern, gern mit Variante dahinter (`21306-1`).
    Alles andere (`sw0001`, `TX-20`) ist im Zweifel eine Minifigur – das ist
    die häufigere Sorte und im Zweifelsfall in zwei Handgriffen korrigiert.
    """
    return "set" if re.fullmatch(r"\d{2,7}(-\d{1,2})?", item_id) else "minifig"


@router.post("/api/hub/trades/{trade_id}/take")
@_nacheinander
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
    if not _kommt_zu_mir(t):
        raise HTTPException(400, "Das ist ein eigener Artikel, der weggeht.")
    if t["status"] not in ("accepted", "closed"):
        raise HTTPException(400, "Der Tausch ist noch nicht angenommen.")
    if not t["arrived_at"]:
        raise HTTPException(400, "Erst bestätigen, dass der Artikel "
                                 "angekommen ist.")

    art = t["item_type"] or _art_raten(t["item_id"])
    with core.db() as conn:
        wunsch = conn.execute(
            "SELECT id, name, img_url, bricklink_url FROM wanted "
            "WHERE item_id = ? AND item_type = ?",
            (t["item_id"], art)).fetchone()
    name = t["item_name"] or (wunsch["name"] if wunsch else "") or t["item_id"]
    bild = t["img_url"] if t["img_url"].startswith(("http://", "https://")) \
        else ""
    # Wer ein Angebot bekommt, erfährt vom Hub nur Nummer und Name – ohne
    # Bild stünde das Stück dann nackt in der Sammlung. Die Wunschliste hat
    # meist eins, sonst das Standardbild von BrickLink.
    if not bild and wunsch and wunsch["img_url"].startswith(
            ("http://", "https://")):
        bild = wunsch["img_url"]
    if not bild and art == "minifig":
        bild = integrations.minifig_bild(t["item_id"])
    bl_url = t["bricklink_url"] or (wunsch["bricklink_url"] if wunsch else "")
    if body.ziel == "liste":
        if not user["is_dealer"]:
            raise HTTPException(403, "Listen gibt es nur für Sammlerprofis")
        if not body.list_id:
            raise HTTPException(400, "Keine Liste ausgewählt")
        ergebnis = add_list_item(body.list_id, ListItemBody(
            item_id=t["item_id"], item_type=art, name=name, img_url=bild,
            bricklink_url=bl_url, qty=min(99, body.quantity),
            condition=body.condition, paid_price=body.paid_price), user)
    else:
        ergebnis = add_item(AddItemBody(
            item_id=t["item_id"], item_type=art, name=name, img_url=bild,
            bricklink_url=bl_url, quantity=body.quantity,
            condition=body.condition, paid_price=body.paid_price,
            paid_source="manual" if body.paid_price is not None else None,
            notes=f"Tausch mit {t['other_name'] or t['other_id']}"), user)
    # Ertauscht heißt: gefunden. Der Wunsch bleibt sonst stehen, und das
    # Netzwerk zeigt weiter an, wer das Stück hätte.
    wunsch_weg = bool(wunsch) and body.ziel == "sammlung"
    with core.db() as conn:
        conn.execute("UPDATE trades SET taken_at = ? WHERE id = ?",
                     (int(time.time()), trade_id))
        if wunsch_weg:
            conn.execute("DELETE FROM wanted WHERE id = ?", (wunsch["id"],))
    if wunsch_weg:
        _wuensche_geaendert()
    status = _buchung_melden(trade_id, True) if hub.enabled() else None
    return {"ok": True, "ziel": body.ziel, "item_type": art,
            "ergebnis": ergebnis, "wunsch_erledigt": wunsch_weg,
            "status": status or t["status"]}


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
@_nacheinander
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
        if _kommt_zu_mir(t):
            raise HTTPException(400, "Dieser Artikel kommt zu dir.")
        if t["status"] not in ("accepted", "closed"):
            raise HTTPException(400, "Der Tausch ist noch nicht angenommen.")
        if not t["shipped_at"]:
            raise HTTPException(400, "Erst als verschickt markieren.")
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
    # Das Kaufbuch geht dabei mit: Seit 2.90.21 bucht `update_item` selbst
    # ab, wenn die Menge sinkt – hier noch einmal abzuziehen, zählte doppelt.
    ergebnis = update_item(row["id"], UpdateItemBody(quantity=rest), user)
    with core.db() as conn:
        conn.execute("UPDATE trades SET taken_at = ? WHERE id = ?",
                     (int(time.time()), trade_id))
    angebote_nachziehen_im_hintergrund()
    status = _buchung_melden(trade_id, False) if hub.enabled() else None
    return {"ok": True, "rest": rest, "geloescht": rest == 0,
            "status": status or t["status"],
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
        res = hub.report(t["other_id"], body.reason, trade_id, disclosed) or {}
    except hub.HubError as e:
        raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")
    # Festhalten, dass gemeldet wurde. Bis 2.90.9 kam nur eine kurze
    # Bestätigung, danach fand man die Meldung nirgends wieder.
    jetzt = int(time.time())
    with core.db() as conn:
        conn.execute(
            "INSERT INTO hub_reports (hub_id, trade_id, against, other_name, "
            "reason, with_history, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res.get("id"), trade_id, t["other_id"], t["other_name"] or "",
             body.reason, 1 if disclosed else 0, jetzt))
    return {"ok": True, "report": _meldung_zum_gespraech(trade_id)}


def _meldung_zum_gespraech(trade_id: str) -> dict | None:
    with core.db() as conn:
        r = conn.execute(
            "SELECT id, status, created_at, handled_at, with_history, ergebnis "
            "FROM hub_reports WHERE trade_id = ? ORDER BY created_at DESC, "
            "id DESC LIMIT 1", (trade_id,)).fetchone()
        if not r:
            return None
        msgs = conn.execute(
            "SELECT from_admin, text, created_at FROM hub_report_messages "
            "WHERE report_id = ? ORDER BY created_at, id", (r["id"],)).fetchall()
    d = dict(r)
    d["messages"] = [{"from_admin": bool(m["from_admin"]), "text": m["text"],
                      "created_at": m["created_at"]} for m in msgs]
    return d


# Der Stand der Meldungen wird beim Nachrichten-Abgleich mitgeholt – der
# läuft alle 8–20 Sekunden. Für Meldungen genügt einmal die Minute.
MELDUNG_ABGLEICH_ALLE = 60
_meldung_zuletzt = {"ts": 0.0}


def _meldungen_abgleichen(sofort: bool = False) -> None:
    """Stand und Rückfragen eigener Meldungen beim Hub nachfragen.

    Nur wenn es Meldungen aus den letzten 90 Tagen gibt: Auch zu einer
    erledigten Meldung kann der Hub-Admin noch nachfragen. Erledigt der
    Admin eine, oder fragt er nach, steht das am Gespräch, und es kommt ein
    Hinweis. Seine interne Notiz bleibt beim Hub.
    """
    if not sofort and time.time() - _meldung_zuletzt["ts"] < MELDUNG_ABGLEICH_ALLE:
        return
    _meldung_zuletzt["ts"] = time.time()
    with core.db() as conn:
        lokal = {r["hub_id"]: r for r in conn.execute(
            "SELECT id, hub_id, status FROM hub_reports WHERE hub_id IS NOT "
            "NULL AND created_at > ?", (int(time.time()) - 90 * 86400,))}
    if not lokal:
        return
    try:
        stand = hub.own_reports()
    except Exception:
        return                      # beim nächsten Abgleich wieder
    try:
        from main import _notify
    except Exception:
        _notify = None
    for h in stand:
        r = lokal.get(h.get("id"))
        if not r:
            continue
        neu_status = "handled" if h.get("status") == "handled" else "open"
        with core.db() as conn:
            conn.execute("UPDATE hub_reports SET status = ?, handled_at = ?, "
                         "ergebnis = ? WHERE id = ?",
                         (neu_status, h.get("handled_at"), h.get("massnahme"),
                          r["id"]))
            neue_fragen = []
            for m in h.get("messages") or []:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO hub_report_messages (report_id, "
                    "hub_msg_id, from_admin, text, created_at) VALUES "
                    "(?, ?, ?, ?, ?)", (r["id"], m["id"],
                                        1 if m.get("from_admin") else 0,
                                        m.get("text") or "", m.get("created_at") or 0))
                if cur.rowcount and m.get("from_admin"):
                    neue_fragen.append(m["id"])
        if not _notify:
            continue
        if neu_status == "handled" and r["status"] != "handled":
            _notify("meldung", "✔ Deine Meldung wurde bearbeitet",
                    "Ein Hub-Admin hat sich deine Meldung angesehen und sie "
                    "als erledigt markiert. Den Stand siehst du im Gespräch.",
                    item_type="system", item_id=f"meldung-{h['id']}-{h.get('handled_at')}")
        for mid in neue_fragen:
            _notify("meldung", "💬 Rückfrage vom Hub-Admin",
                    "Zu deiner Meldung gibt es eine Rückfrage. Du findest sie "
                    "im Gespräch und kannst dort antworten.",
                    item_type="system", item_id=f"frage-{mid}")


class MeldungAntwortBody(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/api/hub/trades/{trade_id}/report/reply")
def hub_report_reply(trade_id: str, body: MeldungAntwortBody,
                     user: dict = Depends(current_user)):
    """Dem Hub-Admin zur eigenen Meldung antworten – oder etwas nachtragen."""
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    with core.db() as conn:
        r = conn.execute(
            "SELECT id, hub_id FROM hub_reports WHERE trade_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT 1", (trade_id,)).fetchone()
    if not r or not r["hub_id"]:
        raise HTTPException(404, "Zu diesem Gespräch gibt es keine Meldung")
    try:
        res = hub.report_reply(r["hub_id"], body.text.strip()) or {}
    except hub.HubError as e:
        raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")
    with core.db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO hub_report_messages (report_id, hub_msg_id, "
            "from_admin, text, created_at) VALUES (?, ?, 0, ?, ?)",
            (r["id"], res.get("id"), body.text.strip(), int(time.time())))
        # Die Antwort öffnet eine erledigte Meldung beim Hub wieder.
        conn.execute("UPDATE hub_reports SET status = 'open', handled_at = NULL "
                     "WHERE id = ?", (r["id"],))
    return {"ok": True, "report": _meldung_zum_gespraech(trade_id)}


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
        raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")


@router.post("/api/hub/invite")
def hub_invite(body: HubInviteBody, user: dict = Depends(current_user)):
    # Einladen darf jeder angemeldete Nutzer der verbundenen Instanz.
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    try:
        res = hub.create_invite(body.note, body.expires_in_days)
    except hub.HubError as e:
        raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")
    code = res.get("invite_code") or ""
    if code:
        # Merken, damit der Code nach dem Schließen des Fensters nicht weg
        # ist – bis 2.90.13 war er es, obwohl die Einladung verbraucht war.
        with core.db() as conn:
            conn.execute("INSERT OR IGNORE INTO hub_invites (code, code_hash, "
                         "created_at) VALUES (?, ?, ?)",
                         (code, hashlib.sha256(code.encode()).hexdigest(),
                          int(time.time())))
    return res


# Eingelöste Einladungen verschwinden nach vier Wochen aus der Liste – sie
# sind erledigt, und die Liste soll kurz bleiben.
EINLADUNG_EINGELOEST_ZEIGEN = 28 * 86400


@router.get("/api/hub/invites")
def hub_own_invites(user: dict = Depends(current_user)):
    """Meine Einladungen: offen (samt Code, wenn er hier erzeugt wurde),
    eingelöst (von wem, wann) oder abgelaufen."""
    if not hub.enabled():
        return {"invites": []}
    try:
        stand = hub.own_invites()
    except hub.HubError as e:
        raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")
    with core.db() as conn:
        codes = {r["code_hash"]: r["code"] for r in conn.execute(
            "SELECT code, code_hash FROM hub_invites")}
    jetzt = int(time.time())
    liste = []
    for i in stand:
        if i.get("redeemed_at"):
            if jetzt - i["redeemed_at"] > EINLADUNG_EINGELOEST_ZEIGEN:
                continue
            art = "eingeloest"
        elif i.get("expires_at") and i["expires_at"] < jetzt:
            art = "abgelaufen"
        else:
            art = "offen"
        liste.append({"id": i["id"], "status": art,
                      "code": codes.get(i["id"]) if art == "offen" else None,
                      "created_at": i.get("created_at"),
                      "redeemed_at": i.get("redeemed_at"),
                      "redeemed_by": i.get("redeemed_by_name")})
    # Eingelöste Codes braucht niemand mehr im Klartext.
    erledigt = [i["id"] for i in stand if i.get("redeemed_at")]
    if erledigt:
        with core.db() as conn:
            conn.executemany("DELETE FROM hub_invites WHERE code_hash = ?",
                             [(h,) for h in erledigt])
    return {"invites": liste}


@router.delete("/api/hub/invites/{code_hash}")
def hub_withdraw_invite(code_hash: str, user: dict = Depends(current_user)):
    """Offene Einladung zurückziehen – danach ist sie wieder frei."""
    if not re.fullmatch(r"[0-9a-f]{64}", code_hash):
        raise HTTPException(400, "Ungültige Kennung")
    if not hub.enabled():
        raise HTTPException(400, "Kein Hub verbunden")
    try:
        hub.withdraw_invite(code_hash)
    except hub.HubError as e:
        if e.status != 404:
            raise _hub_antwort(e)
    except requests.RequestException:
        raise HTTPException(502, "Hub nicht erreichbar")
    with core.db() as conn:
        conn.execute("DELETE FROM hub_invites WHERE code_hash = ?", (code_hash,))
    return {"ok": True}


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
        raise _hub_antwort(e)
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
            "qty": o.get("qty") or 1, "deal": o.get("deal") or "tausch"}
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
