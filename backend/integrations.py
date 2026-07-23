"""Brickfolio – externe Dienste: Brickognize (Erkennung) & BrickLink (Preise)."""
import io
import os
import re

import requests
from PIL import Image, ImageOps

BRICKOGNIZE_URL = "https://api.brickognize.com/predict/"
USER_AGENT = "Brickfolio/1.0 (self-hosted minifig manager)"

import core

# API-Schlüssel: in der App gespeicherte Werte (DB) haben Vorrang,
# ENV-Variablen aus docker-compose dienen als Startwerte.
SETTING_ENV = {
    "bl_consumer_key": "BL_CONSUMER_KEY",
    "bl_consumer_secret": "BL_CONSUMER_SECRET",
    "bl_token": "BL_TOKEN",
    "bl_token_secret": "BL_TOKEN_SECRET",
    "rebrickable_key": "REBRICKABLE_KEY",
}


def setting(name: str) -> str:
    return core.get_setting(name) or os.environ.get(SETTING_ENV[name], "")


def _bl_auth():
    from requests_oauthlib import OAuth1
    return OAuth1(setting("bl_consumer_key"), setting("bl_consumer_secret"),
                  setting("bl_token"), setting("bl_token_secret"))


def bricklink_enabled() -> bool:
    return all(setting(k) for k in ("bl_consumer_key", "bl_consumer_secret",
                                    "bl_token", "bl_token_secret"))


def rebrickable_enabled() -> bool:
    return bool(setting("rebrickable_key"))


_RB_PATH = {"minifig": "minifigs", "part": "parts", "set": "sets"}


def search_catalog(query: str, item_type: str = "minifig",
                   page: int = 1, page_size: int = 10) -> dict:
    """Textsuche im Rebrickable-Katalog, seitenweise, mit Bild.

    Gibt neben den Treffern die Gesamtzahl (``count``) und ``has_more``
    zurück, damit die Ergebnisliste seitenweise nachgeladen werden kann.
    """
    path = _RB_PATH.get(item_type)
    if not path:
        raise ValueError(f"Unbekannter Typ: {item_type}")
    resp = requests.get(
        f"https://rebrickable.com/api/v3/lego/{path}/",
        params={"search": query, "page": page, "page_size": page_size,
                "key": setting("rebrickable_key")},
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    items = []
    for r in data.get("results", []):
        year = 0
        if item_type == "minifig":
            item_id = r.get("set_num", "")          # z. B. fig-001234
            img = r.get("set_img_url") or ""
            sub = f'{r.get("num_parts", "?")} Teile'
            bl_url = ("https://www.bricklink.com/search.asp?q="
                      + requests.utils.quote(r.get("name", "")[:60]))
        elif item_type == "set":
            item_id = r.get("set_num", "")           # z. B. 10179-1
            img = r.get("set_img_url") or ""
            sub = str(r.get("year", ""))
            year = r.get("year") or 0
            bl_url = ("https://www.bricklink.com/v2/catalog/catalogitem.page?S="
                      + requests.utils.quote(item_id))
        else:
            item_id = r.get("part_num", "")
            img = r.get("part_img_url") or ""
            sub = ""
            bl_ids = (r.get("external_ids") or {}).get("BrickLink") or []
            bl_url = ("https://www.bricklink.com/v2/catalog/catalogitem.page?P="
                      + requests.utils.quote(bl_ids[0])) if bl_ids else ""
        items.append({
            "item_id": item_id,
            "item_type": item_type,
            "name": r.get("name", ""),
            "img_url": img,
            "sub": sub,
            "year": year,
            "bricklink_url": bl_url,
        })
    return {"items": items,
            "count": data.get("count", len(items)),
            "page": page,
            "page_size": page_size,
            "has_more": bool(data.get("next"))}


# ---------------------------------------------------------------- Brickognize

RESOLVE_HOSTS = {"cdn.rebrickable.com", "img.bricklink.com"}


def fetch_catalog_image(url: str) -> bytes:
    """Katalogbild von erlaubten CDNs laden (für die Nummern-Auflösung)."""
    from urllib.parse import urlparse
    p = urlparse(url)
    if p.scheme not in ("http", "https") or p.hostname not in RESOLVE_HOSTS:
        raise ValueError("Bild-URL nicht erlaubt")
    resp = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    if len(resp.content) > 10 * 1024 * 1024:
        raise ValueError("Bild zu groß")
    return resp.content


def prepare_image(raw: bytes, max_side: int = 1200) -> bytes:
    """EXIF-Rotation anwenden, verkleinern, als JPEG komprimieren."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue()


def recognize(raw_image: bytes) -> dict:
    """Bild an Brickognize schicken, Kandidatenliste zurückgeben."""
    jpeg = prepare_image(raw_image)
    resp = requests.post(
        BRICKOGNIZE_URL,
        files={"query_image": ("scan.jpg", jpeg, "image/jpeg")},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    items = []
    _TYPE_MAP = {"fig": "minifig", "minifig": "minifig",
                 "part": "part", "set": "set"}
    for it in data.get("items", []):
        bricklink_url = ""
        for site in it.get("external_sites") or []:
            if site.get("name", "").lower() == "bricklink":
                bricklink_url = site.get("url", "")
                break
        raw_type = (it.get("type") or "").lower()
        items.append({
            "item_id": it.get("id", ""),
            "item_type": _TYPE_MAP.get(raw_type, raw_type),
            "name": it.get("name", ""),
            "img_url": it.get("img_url", ""),
            "score": round(float(it.get("score", 0)) * 100),
            "category": it.get("category", ""),
            "bricklink_url": bricklink_url,
        })
    return {"items": items, "listing_id": data.get("listing_id", "")}


def rebrickable_minifig_image(fig_num: str) -> str:
    """Katalogbild einer Rebrickable-Minifigur (fig-…)."""
    resp = requests.get(
        f"https://rebrickable.com/api/v3/lego/minifigs/{requests.utils.quote(fig_num)}/",
        params={"key": setting("rebrickable_key")},
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("set_img_url") or ""


# ---------------------------------------------------------------- BrickLink

_BL_TYPE = {"minifig": "MINIFIG", "part": "PART", "set": "SET"}


def bricklink_item(item_type: str, item_no: str) -> dict:
    """Artikeldetails (Name, Bild) von BrickLink per Katalognummer."""
    import html as html_mod

    bl_type = _BL_TYPE.get(item_type.lower())
    if not bl_type:
        raise ValueError(f"Unbekannter Typ: {item_type}")
    if bl_type == "SET" and "-" not in item_no:
        item_no = f"{item_no}-1"

    auth = _bl_auth()
    url = f"https://api.bricklink.com/api/store/v1/items/{bl_type}/{item_no}"
    resp = requests.get(url, auth=auth, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    meta = payload.get("meta", {})
    if meta.get("code") != 200:
        raise LookupError(f"Nummer '{item_no}' nicht im BrickLink-Katalog gefunden")
    d = payload.get("data", {})
    img = d.get("image_url") or d.get("thumbnail_url") or ""
    if img.startswith("//"):
        img = "https:" + img
    no = d.get("no", item_no)
    return {
        "item_id": no,
        "item_type": item_type,
        "name": html_mod.unescape(d.get("name", "")),
        "img_url": img,
        "year": d.get("year_released") or 0,
        "sub": str(d.get("year_released", "")),
        "bricklink_url": ("https://www.bricklink.com/v2/catalog/catalogitem.page?"
                          f"{bl_type[0]}={requests.utils.quote(no)}"),
    }


def bricklink_subsets(set_no: str) -> list:
    """Enthaltene Minifiguren eines Sets (BrickLink Subsets)."""
    import html as html_mod

    if "-" not in set_no:
        set_no = f"{set_no}-1"
    auth = _bl_auth()
    safe = requests.utils.quote(set_no)
    resp = requests.get(
        f"https://api.bricklink.com/api/store/v1/items/SET/{safe}/subsets",
        auth=auth, timeout=25)
    resp.raise_for_status()
    payload = resp.json()
    meta = payload.get("meta", {})
    if meta.get("code") != 200:
        raise LookupError(f"Set '{set_no}' nicht im BrickLink-Katalog gefunden")

    figs = []
    for group in payload.get("data", []):
        for entry in group.get("entries", []):
            item = entry.get("item", {})
            if item.get("type") != "MINIFIG":
                continue
            no = item.get("no", "")
            safe_no = requests.utils.quote(no)
            figs.append({
                "item_id": no,
                "item_type": "minifig",
                "name": html_mod.unescape(item.get("name", "")),
                "qty": entry.get("quantity", 1),
                "img_url": f"https://img.bricklink.com/ItemImage/MN/0/{safe_no}.png",
                "bricklink_url": ("https://www.bricklink.com/v2/catalog/"
                                  f"catalogitem.page?M={safe_no}"),
            })
    return figs


def bricklink_supersets(fig_no: str) -> list:
    """In welchen Sets kommt diese Minifigur vor? (BrickLink Supersets)"""
    import html as html_mod

    auth = _bl_auth()
    safe = requests.utils.quote(fig_no)
    resp = requests.get(
        f"https://api.bricklink.com/api/store/v1/items/MINIFIG/{safe}/supersets",
        auth=auth, timeout=25)
    resp.raise_for_status()
    payload = resp.json()
    meta = payload.get("meta", {})
    if meta.get("code") != 200:
        raise LookupError(f"Figur '{fig_no}' nicht im BrickLink-Katalog gefunden")

    sets = []
    for group in payload.get("data", []):
        for entry in group.get("entries", []):
            item = entry.get("item", {})
            if item.get("type") != "SET":
                continue
            sets.append({
                "no": item.get("no", ""),
                "name": html_mod.unescape(item.get("name", "")),
                "qty": entry.get("quantity", 1),
            })
    return sets


# Auswählbare Preisgebiete. Zwei Großbuchstaben = Land (country_code),
# sonst eine BrickLink-Region. "" bedeutet weltweit (BrickLink-Standard).
PRICE_REGIONS = {
    "": "weltweit",
    "DE": "Deutschland",
    "AT": "Österreich",
    "CH": "Schweiz",
    "europe": "Europa",
}


def price_region() -> str:
    """Eingestelltes Preisgebiet; unbekannte Werte gelten als weltweit."""
    value = core.get_setting("price_region") or os.environ.get("PRICE_REGION", "")
    return value if value in PRICE_REGIONS else ""


def _has_avg(d: dict) -> bool:
    """Steckt ein echter Durchschnitt in der Antwort?

    Wichtig: Gibt es im gewählten Gebiet keine Verkäufe, liefert BrickLink
    `avg_price` als String „0.0000" – also gerade *nicht* leer. Ein reiner
    Wahrheitstest (`not avg_price`) hält das fälschlich für einen Preis und
    überspringt den Rückfall; deshalb wird hier numerisch geprüft.
    """
    try:
        return float(d.get("avg_price") or 0) > 0
    except (TypeError, ValueError):
        return False


def _fallback_chain(wanted: str) -> list[str]:
    """Gebiete in der Reihenfolge, in der ein Preis gesucht wird.

    Erst das eingestellte Gebiet, dann Europa als Auffangnetz, zuletzt
    weltweit – jede Stufe breiter als die vorige. Doppelte fallen raus, damit
    kein Gebiet zweimal abgefragt wird (Europa als Einstellung, oder weltweit
    als Einstellung ganz ohne Rückfall).
    """
    chain: list[str] = []
    for scope in (wanted, "europe", ""):
        if scope not in PRICE_REGIONS or scope in chain:
            continue
        chain.append(scope)
        if scope == "":      # weltweit ist am breitesten – danach kommt nichts
            break
    return chain


def _price_request(bl_type: str, item_no: str, condition: str, scope: str,
                   auth) -> dict:
    params = {"guide_type": "sold", "new_or_used": condition,
              "currency_code": "EUR"}
    if scope:
        # Länderkürzel und Region schließen sich bei BrickLink gegenseitig aus
        if len(scope) == 2 and scope.isupper():
            params["country_code"] = scope
        else:
            params["region"] = scope
    resp = requests.get(
        f"https://api.bricklink.com/api/store/v1/items/{bl_type}/{item_no}/price",
        params=params, auth=auth, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    meta = payload.get("meta", {})
    if meta.get("code") != 200:
        raise RuntimeError(meta.get("message", "BrickLink-Fehler"))
    return payload.get("data", {})


def price_guide(item_type: str, item_no: str, condition: str = "U",
                scope: str | None = None) -> dict:
    """Preisübersicht (verkaufte Artikel, letzte 6 Monate) von BrickLink.

    `scope` grenzt auf ein Land bzw. eine Region ein; ohne Angabe gilt die
    Einstellung. Gibt es dort keine Verkäufe – bei selteneren Figuren häufig –,
    wird stufenweise ausgeweitet: erst Europa, dann weltweit, damit kein
    Artikel ohne Preis dasteht. `used_scope` sagt, welches Gebiet am Ende
    gezählt hat.
    """
    bl_type = _BL_TYPE.get(item_type.lower())
    if not bl_type:
        raise ValueError(f"Unbekannter Typ: {item_type}")
    if bl_type == "SET" and "-" not in item_no:
        item_no = f"{item_no}-1"

    wanted = price_region() if scope is None else scope
    if wanted not in PRICE_REGIONS:
        wanted = ""
    auth = _bl_auth()

    used = wanted
    d = {}
    found = False
    for step in _fallback_chain(wanted):
        d = _price_request(bl_type, item_no, condition, step, auth)
        used = step
        found = _has_avg(d)
        if found:
            break      # erster Treffer mit echtem Durchschnitt gewinnt

    # Ohne echten Treffer die Preisfelder leeren, statt BrickLinks „0.0000"
    # durchzureichen – sonst hielte der Rest der App die Null für einen Preis.
    return {
        "currency": d.get("currency_code", "EUR"),
        "min": d.get("min_price") if found else None,
        "avg": d.get("avg_price") if found else None,
        "max": d.get("max_price") if found else None,
        "times_sold": d.get("unit_quantity"),
        "condition": condition,
        "scope": wanted,
        "used_scope": used,
        "fell_back": used != wanted,
    }


# ------------------------------------------------- BrickLink Catalog Change Log

CATALOG_LOG_URL = "https://www.bricklink.com/catalogReqList.asp"

# Kürzel, mit denen BrickLink im Katalog-Link die Artikelart angibt
_LOG_TYPE = {"S": "set", "M": "minifig", "P": "part", "B": "book",
             "G": "gear", "C": "catalog", "I": "instruction", "O": "box"}

# Artikel-Link, Nummernwechsel und Zusammenlegung – in einem Ausdruck, damit
# sie in Dokumentreihenfolge kommen: Der Änderungstext gehört immer zum
# zuletzt genannten Artikel.
_RE_LOG = re.compile(
    r'catalogitem\.page\?(?P<t>[A-Z])=(?P<no>[^"&]+)"'
    r'|Changed <B>Item No</B> from \{<B>(?P<old>[^<]+)</B>\}'
    r' to \{<B>(?P<new>[^<]+)</B>\}'
    r'|<B>Merged</B> from <B>[A-Za-z ]+&nbsp;(?P<merged>[A-Za-z0-9_.\-]+)</B>',
    re.I)
_RE_NEXT = re.compile(
    r'Next Page:</B>\s*<A HREF="(catalogReqList\.asp\?[^"]+)"', re.I)


def _log_page(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    return resp.text


def _parse_log(html: str, kind: str) -> dict[str, dict]:
    """Änderungen einer Log-Seite als `{alte_nummer: {...}}`."""
    found: dict[str, dict] = {}
    current: tuple[str | None, str] | None = None    # (Art, neue Nummer)
    for m in _RE_LOG.finditer(html):
        if m.group("no"):
            current = (_LOG_TYPE.get(m.group("t").upper()), m.group("no"))
            continue
        old = m.group("old") or m.group("merged")
        if not old or not current:
            continue
        # Beim Nummernwechsel steht die neue Nummer im Text selbst, bei der
        # Zusammenlegung nur in der Überschrift darüber.
        new_id = m.group("new") or current[1]
        found[old.lower()] = {"new_id": new_id, "item_type": current[0],
                              "kind": kind}
    return found


def catalog_number_changes(year: int, month: int,
                           max_pages: int = 20) -> dict[str, dict]:
    """Nummernwechsel und Zusammenlegungen eines Monats aus dem Change Log.

    BrickLink bietet dafür keine API, nur die öffentliche Log-Seite. Gelesen
    wird sie ausschließlich dann, wenn wirklich ein Artikel der Sammlung
    verschwunden ist – im Normalbetrieb also gar nicht.
    """
    changes: dict[str, dict] = {}
    for action, kind in (("I", "renumbered"), ("M", "merged")):
        url = (f"{CATALOG_LOG_URL}?viewYear={year}&viewMonth={month}"
               f"&viewAction={action}")
        for _ in range(max_pages):
            html = _log_page(url)
            changes.update(_parse_log(html, kind))
            nxt = _RE_NEXT.search(html)
            if not nxt:
                break
            url = "https://www.bricklink.com/" + nxt.group(1)
    return changes


def find_number_change(item_id: str, since: int) -> dict | None:
    """Sucht die neue Nummer zu `item_id` in den Monaten ab `since` (Epoch).

    Gibt `{"new_id", "item_type", "kind"}` oder None, wenn der Change Log
    nichts hergibt – dann bleibt es beim Hinweis „Nummer nicht mehr gültig".
    """
    import datetime
    start = datetime.date.fromtimestamp(max(since, 0))
    today = datetime.date.today()
    year, month = start.year, start.month
    needle = item_id.lower()
    for _ in range(24):
        if (year, month) > (today.year, today.month):
            return None
        try:
            hit = catalog_number_changes(year, month).get(needle)
        except Exception:
            hit = None
        if hit:
            return hit
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return None
