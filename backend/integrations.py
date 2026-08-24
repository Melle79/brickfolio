"""Brickfolio – externe Dienste: Brickognize (Erkennung) & BrickLink (Preise)."""
import base64
import html as html_mod
import io
import json
import os
import re
import time

import requests
from PIL import Image, ImageOps

import core

BRICKOGNIZE_URL = "https://api.brickognize.com/predict/"
# Echte Version und ein Kontaktweg: Brickognize stellt seine Erkennung
# kostenlos bereit. Wenn Brickfolio dort einmal auffällt, soll man uns
# erreichen können, statt nur sperren zu müssen.
USER_AGENT = (f"Brickfolio/{core.APP_VERSION} "
              "(self-hosted LEGO collection manager; "
              "+https://github.com/Melle79/brickfolio)")

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


# Alles, was in der Datenbank steht und niemals nach außen darf. Die Liste ist
# der Bezugspunkt für `scrub()`: Was hier fehlt, kann in einer Fehlermeldung
# stehen – und die kann als GitHub-Issue **öffentlich** werden. Ein Test
# vergleicht sie mit den tatsächlich gespeicherten Einstellungen und schlägt
# an, sobald eine neue dazukommt, die niemand eingeordnet hat.
GEHEIME_SETTINGS = (
    "bl_consumer_key", "bl_consumer_secret", "bl_token", "bl_token_secret",
    "rebrickable_key",
    "github_token",
    "hub_token",              # Zugang dieser Instanz zum Tausch-Netzwerk
    "hub_privkey",            # entschlüsselt die Nachrichten anderer
    "hub_instance_secret",
    "crash_token",            # liefert Fehlerberichte ab – bewusst getrennt
                              # vom Tausch-Token: Wer berichtet, gibt damit
                              # nichts über sein Tauschen preis, und der
                              # Kanal lässt sich einzeln zurückziehen
    "vapid_private",          # signiert die Push-Meldungen dieser Instanz
    "ollama_url",             # Adresse der lokalen KI. Kein Schlüssel, aber
                              # sie kann Zugangsdaten enthalten
                              # (https://benutzer:wort@host) und verrät sonst
                              # den Aufbau des Heimnetzes – beides hat in
                              # einem öffentlichen Issue nichts zu suchen.
)


def _bl_auth():
    from requests_oauthlib import OAuth1
    return OAuth1(setting("bl_consumer_key"), setting("bl_consumer_secret"),
                  setting("bl_token"), setting("bl_token_secret"))


BL_KEYS = ("bl_consumer_key", "bl_consumer_secret",
           "bl_token", "bl_token_secret")

BL_LABELS = {"bl_consumer_key": "Consumer Key",
             "bl_consumer_secret": "Consumer Secret",
             "bl_token": "Token", "bl_token_secret": "Token Secret"}


def bricklink_enabled() -> bool:
    return all(setting(k) for k in BL_KEYS)


def bricklink_missing() -> list:
    """Welche der vier Werte fehlen noch? Alle vier gehören zusammen – wer
    zwei einträgt, soll nicht „keine Schlüssel" zu lesen bekommen."""
    return [BL_LABELS[k] for k in BL_KEYS if not setting(k)]


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

# Woher Katalogbilder überhaupt kommen dürfen. Bewusst eine feste Liste und
# nicht „alles, was nach Bild aussieht": Der Abruf läuft auf dem Server, ein
# offener Weg dorthin wäre ein Werkzeug, um von innen beliebige Adressen
# anzufragen. `storage.googleapis.com` steht drin, weil Brickognize seine
# Vorschaubilder dort ablegt – ohne den Host hätte alles Gescannte kein Bild.
BILD_HOSTS = RESOLVE_HOSTS | {"storage.googleapis.com", "m.rebrickable.com"}


def fetch_catalog_image(url: str, hosts: set | None = None) -> bytes:
    """Katalogbild von erlaubten CDNs laden."""
    from urllib.parse import urlparse
    p = urlparse(url)
    erlaubt = RESOLVE_HOSTS if hosts is None else hosts
    if p.scheme not in ("http", "https") or p.hostname not in erlaubt:
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
    # Wo im Bild die Erkennung fündig wurde. Brickognize sucht **ein**
    # Objekt je Anfrage – der Rahmen zeigt, welches. Liegen mehrere Figuren
    # auf dem Foto, sieht man daran sofort, worüber geraten wurde.
    box = data.get("bounding_box") or {}
    rahmen = None
    if all(k in box for k in ("left", "upper", "right", "lower")):
        rahmen = {"left": box["left"], "upper": box["upper"],
                  "right": box["right"], "lower": box["lower"],
                  "score": box.get("score")}
    return {"items": items, "listing_id": data.get("listing_id", ""),
            "box": rahmen}


def bricklink_nummer_fuer_teil(part_num: str) -> str:
    """BrickLink-Nummer eines Teils über Rebrickable.

    Die beiden Kataloge zählen Bedruckungen unterschiedlich: Bei Rebrickable
    heißt der Karbonitblock `87561pr0001`, bei BrickLink `87561pb01`. Wer mit
    der einen Nummer beim anderen anfragt, bekommt nichts. Rebrickable führt
    die Entsprechung selbst mit.
    """
    resp = requests.get(
        f"https://rebrickable.com/api/v3/lego/parts/{part_num}/",
        params={"key": setting("rebrickable_key")},
        headers={"User-Agent": USER_AGENT}, timeout=15)
    if resp.status_code != 200:
        return ""
    ids = (resp.json().get("external_ids") or {}).get("BrickLink") or []
    return ids[0] if ids else ""


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
        # Zweitnummer aus dem Katalog. Bedruckte Teile tragen dort oft die
        # Nummer der Figur, zu der sie gehören („sw0978") – und darin steckt
        # das Thema, das der Kategorie eines Teils fehlt.
        "alternate_no": d.get("alternate_no") or "",
        # Kommt gleich mit – spart die eigene Abfrage der Kategorie.
        "category_id": d.get("category_id"),
        "year": d.get("year_released") or 0,
        "sub": str(d.get("year_released", "")),
        "bricklink_url": ("https://www.bricklink.com/v2/catalog/catalogitem.page?"
                          f"{bl_type[0]}={requests.utils.quote(no)}"),
    }


def bricklink_subsets(set_no: str) -> list:
    """Enthaltene Minifiguren eines Sets (BrickLink Subsets)."""

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


def bricklink_colors() -> dict:
    """Alle BrickLink-Farben als {color_id (str): Farbname}."""
    auth = _bl_auth()
    resp = requests.get("https://api.bricklink.com/api/store/v1/colors",
                        auth=auth, timeout=25)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("meta", {}).get("code") != 200:
        raise LookupError("BrickLink-Farben nicht abrufbar")
    out = {}
    for c in payload.get("data", []):
        cid = c.get("color_id")
        if cid is not None:
            out[str(cid)] = c.get("color_name", "")
    return out


def bricklink_categories() -> dict:
    """Alle BrickLink-Kategorien als {id (str): (Name, Eltern-ID)}."""
    auth = _bl_auth()
    resp = requests.get("https://api.bricklink.com/api/store/v1/categories",
                        auth=auth, timeout=25)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("meta", {}).get("code") != 200:
        raise LookupError("BrickLink-Kategorien nicht abrufbar")
    out = {}
    for c in payload.get("data", []):
        cid = c.get("category_id")
        if cid is not None:
            # BrickLink liefert Namen HTML-maskiert: „LEGO Ideas &#40;CUUSOO&#41;".
            # Ungewandelt steht das genau so in der Sammlung, denn die
            # Oberfläche maskiert beim Anzeigen ein zweites Mal.
            out[str(cid)] = (html_mod.unescape(c.get("category_name", "")),
                             str(c.get("parent_id") or ""))
    return out


def bricklink_category_id(item_type: str, item_no: str) -> str | None:
    """Kategorie-ID eines Artikels (für das Thema von Sets und Teilen)."""
    bl_type = _BL_TYPE.get(item_type.lower())
    if not bl_type:
        return None
    if bl_type == "SET" and "-" not in item_no:
        item_no = f"{item_no}-1"
    resp = requests.get(
        f"https://api.bricklink.com/api/store/v1/items/{bl_type}/{item_no}",
        auth=_bl_auth(), timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("meta", {}).get("code") != 200:
        return None
    cid = payload.get("data", {}).get("category_id")
    return str(cid) if cid is not None else None


def bricklink_minifig_parts(fig_no: str) -> list:
    """Aus welchen Teilen besteht diese Minifigur? (BrickLink Subsets auf
    MINIFIG). Liefert Teil-Nr., Name, Farbe, Anzahl und ein Bild."""

    auth = _bl_auth()
    safe = requests.utils.quote(fig_no)
    resp = requests.get(
        f"https://api.bricklink.com/api/store/v1/items/MINIFIG/{safe}/subsets",
        auth=auth, timeout=25)
    resp.raise_for_status()
    payload = resp.json()
    meta = payload.get("meta", {})
    if meta.get("code") != 200:
        raise LookupError(f"Figur '{fig_no}' nicht im BrickLink-Katalog gefunden")

    parts = []
    for group in payload.get("data", []):
        for entry in group.get("entries", []):
            item = entry.get("item", {})
            if item.get("type") != "PART":
                continue
            # Gegenstücke (z. B. die andere Hälfte einer Baugruppe) sind für
            # den Überblick nur Rauschen.
            if entry.get("is_counterpart"):
                continue
            no = item.get("no", "")
            color_id = entry.get("color_id", 0)
            safe_no = requests.utils.quote(no)
            parts.append({
                "item_id": no,
                "item_type": "part",
                "name": html_mod.unescape(item.get("name", "")),
                "color_id": color_id,
                "color_name": html_mod.unescape(entry.get("color_name", "")),
                "qty": entry.get("quantity", 1),
                "img_url": (f"https://img.bricklink.com/ItemImage/PN/"
                            f"{color_id}/{safe_no}.png"),
                "bricklink_url": ("https://www.bricklink.com/v2/catalog/"
                                  f"catalogitem.page?P={safe_no}"),
            })
    return parts


def bricklink_supersets(fig_no: str) -> list:
    """In welchen Sets kommt diese Minifigur vor? (BrickLink Supersets)"""

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
# sonst eine BrickLink-Region (die Namen sind von BrickLink vorgegeben).
# "" bedeutet weltweit (BrickLink-Standard).
PRICE_REGIONS = {
    "": "weltweit",
    # Länder
    "DE": "Deutschland",
    "AT": "Österreich",
    "CH": "Schweiz",
    "GB": "Großbritannien",
    "IE": "Irland",
    "US": "USA",
    "CA": "Kanada",
    "AU": "Australien",
    "NZ": "Neuseeland",
    "NL": "Niederlande",
    "BE": "Belgien",
    "FR": "Frankreich",
    "IT": "Italien",
    "ES": "Spanien",
    "PT": "Portugal",
    "PL": "Polen",
    "CZ": "Tschechien",
    "SE": "Schweden",
    "DK": "Dänemark",
    "NO": "Norwegen",
    "FI": "Finnland",
    # Regionen
    "europe": "Europa",
    "north_america": "Nordamerika",
    "south_america": "Südamerika",
    "asia": "Asien",
    "oceania": "Ozeanien",
    "africa": "Afrika",
    "middle_east": "Naher Osten",
}

# Zu welcher Region gehört ein Land? Bestimmt die zweite Stufe des Rückfalls:
# Wer für die USA rechnet, soll bei einer seltenen Figur Nordamerika bekommen
# und nicht Europa.
LAND_REGION = {
    "DE": "europe", "AT": "europe", "CH": "europe", "GB": "europe",
    "IE": "europe", "NL": "europe", "BE": "europe", "FR": "europe",
    "IT": "europe", "ES": "europe", "PT": "europe", "PL": "europe",
    "CZ": "europe", "SE": "europe", "DK": "europe", "NO": "europe",
    "FI": "europe",
    "US": "north_america", "CA": "north_america",
    "AU": "oceania", "NZ": "oceania",
}

# Währungen, in denen BrickLink Preise liefern kann. Der Schlüssel ist der
# ISO-Code, den die API erwartet.
CURRENCIES = {
    "EUR": "Euro (€)",
    "GBP": "Britisches Pfund (£)",
    "USD": "US-Dollar ($)",
    "CHF": "Schweizer Franken (CHF)",
    "CAD": "Kanadischer Dollar (C$)",
    "AUD": "Australischer Dollar (A$)",
    "NZD": "Neuseeland-Dollar (NZ$)",
    "SEK": "Schwedische Krone (kr)",
    "DKK": "Dänische Krone (kr)",
    "NOK": "Norwegische Krone (kr)",
    "PLN": "Złoty (zł)",
    "CZK": "Tschechische Krone (Kč)",
}

# Welche Währung passt zu welchem Land? Nur als Vorschlag – umstellen lässt
# sich beides unabhängig voneinander.
LAND_WAEHRUNG = {
    "DE": "EUR", "AT": "EUR", "IE": "EUR", "NL": "EUR", "BE": "EUR",
    "FR": "EUR", "IT": "EUR", "ES": "EUR", "PT": "EUR", "FI": "EUR",
    "CH": "CHF", "GB": "GBP", "US": "USD", "CA": "CAD", "AU": "AUD",
    "NZ": "NZD", "SE": "SEK", "DK": "DKK", "NO": "NOK", "PL": "PLN",
    "CZ": "CZK",
}


def price_region() -> str:
    """Eingestelltes Preisgebiet; unbekannte Werte gelten als weltweit."""
    value = core.get_setting("price_region") or os.environ.get("PRICE_REGION", "")
    return value if value in PRICE_REGIONS else ""


def currency() -> str:
    """Eingestellte Währung. BrickLink rechnet selbst um, deshalb genügt es,
    den Code mitzuschicken – ohne eigene Kurse und ohne zweite Quelle."""
    value = core.get_setting("currency") or os.environ.get("CURRENCY", "")
    return value if value in CURRENCIES else "EUR"


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

    Erst das eingestellte Gebiet, dann die zugehörige Region als Auffangnetz,
    zuletzt weltweit – jede Stufe breiter als die vorige. Die zweite Stufe
    richtet sich nach dem Land: für die USA also Nordamerika, nicht Europa.
    Doppelte fallen raus, damit kein Gebiet zweimal abgefragt wird (Europa als
    Einstellung, oder weltweit als Einstellung ganz ohne Rückfall).
    """
    breiter = LAND_REGION.get(wanted)
    chain: list[str] = []
    for scope in (wanted, breiter, ""):
        if scope is None or scope not in PRICE_REGIONS or scope in chain:
            continue
        chain.append(scope)
        if scope == "":      # weltweit ist am breitesten – danach kommt nichts
            break
    return chain


def _price_request(bl_type: str, item_no: str, condition: str, scope: str,
                   auth, waehrung: str = "EUR") -> dict:
    params = {"guide_type": "sold", "new_or_used": condition,
              "currency_code": waehrung}
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


# Kurzlebiger Cache für Katalog-Preisabfragen (Suche/Scan/Popup). Preise
# ändern sich kaum im Minutentakt, dieselbe Figur taucht aber oft mehrfach
# auf – das spart BrickLink-Requests (und schont das Tageslimit). Für
# gespeicherte Preise (Sammlung/Wunschliste) bleibt use_cache aus, damit das
# manuelle „↻ Aktualisieren" immer frisch holt.
_PRICE_CACHE: dict = {}
PRICE_CACHE_TTL = 20 * 60


def price_guide(item_type: str, item_no: str, condition: str = "U",
                scope: str | None = None, use_cache: bool = False,
                waehrung: str | None = None) -> dict:
    """Preisübersicht (verkaufte Artikel, letzte 6 Monate) von BrickLink.

    `scope` grenzt auf ein Land bzw. eine Region ein; ohne Angabe gilt die
    Einstellung. Gibt es dort keine Verkäufe – bei selteneren Figuren häufig –,
    wird stufenweise ausgeweitet: erst die zugehörige Region, dann weltweit,
    damit kein Artikel ohne Preis dasteht. `used_scope` sagt, welches Gebiet am
    Ende gezählt hat. `waehrung` überschreibt die eingestellte Währung –
    BrickLink rechnet dann selbst um. `use_cache` beschleunigt reine
    Katalog-Abfragen (kurzer TTL).
    """
    bl_type = _BL_TYPE.get(item_type.lower())
    if not bl_type:
        raise ValueError(f"Unbekannter Typ: {item_type}")
    if bl_type == "SET" and "-" not in item_no:
        item_no = f"{item_no}-1"

    wanted = price_region() if scope is None else scope
    if wanted not in PRICE_REGIONS:
        wanted = ""

    waehrung = currency() if waehrung is None else waehrung
    if waehrung not in CURRENCIES:
        waehrung = "EUR"

    cache_key = (bl_type, item_no, condition, wanted, waehrung)
    if use_cache:
        hit = _PRICE_CACHE.get(cache_key)
        if hit and time.time() - hit[0] < PRICE_CACHE_TTL:
            return hit[1]

    auth = _bl_auth()

    used = wanted
    d = {}
    found = False
    for step in _fallback_chain(wanted):
        d = _price_request(bl_type, item_no, condition, step, auth, waehrung)
        used = step
        found = _has_avg(d)
        if found:
            break      # erster Treffer mit echtem Durchschnitt gewinnt

    # Ohne echten Treffer die Preisfelder leeren, statt BrickLinks „0.0000"
    # durchzureichen – sonst hielte der Rest der App die Null für einen Preis.
    result = {
        "currency": d.get("currency_code", waehrung),
        "min": d.get("min_price") if found else None,
        "avg": d.get("avg_price") if found else None,
        "max": d.get("max_price") if found else None,
        "times_sold": d.get("unit_quantity"),
        "condition": condition,
        "scope": wanted,
        "used_scope": used,
        "fell_back": used != wanted,
    }
    if use_cache:
        _PRICE_CACHE[cache_key] = (time.time(), result)
    return result


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


# Namensänderung: dieselbe Bauart wie oben, nur ein anderes Stichwort – und
# ein anderer Schlüssel. Beim Nummernwechsel ist die **alte Nummer** der
# Anker, hier ist es die Nummer aus dem Artikel-Link darüber: Der Name ändert
# sich, die Nummer bleibt.
# Anders als beim Nummernwechsel steht der **neue** Name nicht im
# Änderungstext – der sagt nur, wie die Figur vorher hieß. Der aktuelle Name
# steht im Artikel-Link selbst:
#
#   catalogitem.page?M=dp109">dp109&nbsp;Prince Eric - Uniform with Gold …</A>
#
# Das ist genau der Wert, den wir wollen, und er ist verlässlicher als der
# Änderungstext: Wurde derselbe Artikel im Monat zweimal umbenannt, steht im
# Link der Endstand.
_RE_NAME = re.compile(
    r'catalogitem\.page\?[A-Z]=(?P<no>[^"&]+)">(?P<text>[^<]+)</A>', re.I)


def _parse_names(html_text: str) -> dict[str, str]:
    """Namensänderungen einer Log-Seite als `{nummer: aktueller Name}`."""
    import html as _html
    found: dict[str, str] = {}
    for m in _RE_NAME.finditer(html_text):
        nummer = m.group("no")
        # Linktext ist „<Nummer>\xa0<Name>" – die Entitäten müssen weg, sonst
        # stünde `&#40;` statt einer Klammer im Suchtext.
        text = _html.unescape(m.group("text"))
        teile = text.split("\xa0", 1)
        if len(teile) != 2 or teile[0].strip().lower() != nummer.lower():
            continue
        name = teile[1].strip()
        if name:
            found[nummer] = name
    return found


def catalog_name_changes(year: int, month: int, item_type: str = "M",
                         max_pages: int = 20) -> dict[str, str]:
    """Namensänderungen eines Monats – `{nummer: neuer Name}`.

    `itemType` filtert auf eine Artikelart; für den Figurenabzug reicht `M`.
    Ohne den Filter kämen Teile, Sets und Bücher mit, die uns nichts angehen
    – im August 2026 waren es 12 Minifiguren gegenüber 50 Einträgen je Seite.
    """
    namen: dict[str, str] = {}
    url = (f"{CATALOG_LOG_URL}?viewYear={year}&viewMonth={month}"
           f"&viewAction=N&itemType={item_type}")
    for _ in range(max_pages):
        seite = _log_page(url)
        namen.update(_parse_names(seite))
        nxt = _RE_NEXT.search(seite)
        if not nxt:
            break
        url = "https://www.bricklink.com/" + nxt.group(1)
    return namen


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


# ---------------------------------------------------------------- Lokale KI (Ollama)
#
# Ein einziger Zweck: deutsche Suchbegriffe in englische uebersetzen. Die
# Sammlungsnamen kommen von BrickLink und sind **englisch** – wer „Ritter" in
# das Suchfeld tippt, findet nichts, obwohl die Figuren da sind. Der Vorfall
# war nicht exotisch, sondern die naheliegendste Suche eines deutschen
# Nutzers.
#
# Bewusst eng gefasst: Das Modell liefert **Suchbegriffe, niemals Ergebnisse**.
# Jede angezeigte Zeile kommt weiter aus der eigenen Datenbank. Ein erfundener
# Begriff findet schlicht nichts – er kann keine Figur erfinden, die es nicht
# gibt. Das ist der Grund, warum hier ein kleines lokales Modell genuegt.
#
# Vollstaendig optional: Ohne hinterlegte Adresse passiert nichts, und wenn
# der Dienst schweigt oder trödelt, verhaelt sich die Suche wie vorher.

OLLAMA_ENV = {"ollama_url": "OLLAMA_URL", "ollama_model": "OLLAMA_MODEL"}
OLLAMA_STD_MODELL = "qwen2.5:14b"
# Kurz gehalten: Die Uebersetzung ist eine Zugabe, keine Bedingung. Lieber
# ohne Vorschlag bleiben als die Suche haengen lassen.
OLLAMA_TIMEOUT = 8


def ollama_setting(name: str) -> str:
    return core.get_setting(name) or os.environ.get(OLLAMA_ENV[name], "")


def ollama_enabled() -> bool:
    return bool(ollama_setting("ollama_url").strip())


def ollama_modell() -> str:
    return ollama_setting("ollama_model").strip() or OLLAMA_STD_MODELL


_OLLAMA_SYSTEM = (
    "Du uebersetzt deutsche Suchbegriffe fuer eine LEGO-Sammlung in englische "
    "BrickLink-Begriffe. BrickLink-Namen sind englisch und meist SINGULAR "
    '(also "Pirate Captain", nicht "Pirates").\n\n'
    "Regeln:\n"
    "1. Eigennamen NIE durch einen Oberbegriff ersetzen. Wer C-3PO sucht, "
    'will nicht "Droid".\n'
    "2. Nennt die Anfrage eine Eigenschaft (Farbe, Ausruestung), gib ZUERST "
    "den reinen Eigennamen zurueck und danach Varianten mit der "
    "Eigenschaft.\n"
    "3. Sonst: 2 bis 4 Varianten, Singular zuerst, dazu passende "
    "Oberbegriffe.\n"
    "4. Nur kurze Begriffe, keine Saetze, keine Erklaerung.\n\n"
    "Setnummern und bereits englische Begriffe gibst du unveraendert zurueck."
)
# Regel 1 und 2 stammen aus einer Messung: Ohne sie beantwortete das Modell
# „C3PO" mit „Droid, Astro Droid, Robot" – der gesuchte Eigenname war weg.
# Und „roter c3 po" verlor die Farbe ersatzlos. Eine dritte Regel („Namen mit
# Bindestrich schreiben") wurde wieder verworfen: Das Modell hat sie
# uebergeneralisiert und lieferte danach „Darth-Vader" und „Knight-Hunter".
# Die Schreibweise loest stattdessen der Vergleich in main.py.

# Antwortform hart vorgeben: Damit muss niemand freien Text auseinanderpfluecken
# und ein plauderndes Modell kann die Suche nicht zerlegen.
_OLLAMA_SCHEMA = {
    "type": "object",
    "properties": {"begriffe": {"type": "array", "items": {"type": "string"}}},
    "required": ["begriffe"],
}

# Gleiche Frage, gleiche Antwort – und die Suche feuert beim Tippen alle
# 300 ms. Ohne diesen Zwischenspeicher liefe je Tastendruck ein Modellaufruf.
_begriff_cache: dict = {}
_CACHE_MAX = 500

# Fehlschläge verfallen wieder. Das ist aus einem Vorfall entstanden: Die
# erste Fassung merkte sich auch die leere Antwort **dauerhaft**. Lief ein
# einziger Aufruf in den Zeitablauf – etwa weil Ollama das Modell erst laden
# musste; gemessen 1,4 s im Normalfall, aber 48,9 s bei Speicherdruck –,
# dann blieb genau dieser Suchbegriff bis zum Neustart tot. „roter c3 po"
# fand deshalb nichts mehr, während „c3 po" daneben tadellos lief. Ein
# Treffer darf bleiben, ein Fehlschlag nicht.
_MISSERFOLG_GILT = 60


def _ollama_keep_alive() -> str:
    """Wie lange Ollama das Modell geladen lassen soll.

    Ohne das entlädt Ollama nach fünf Minuten Ruhe, und die nächste Suche
    zahlt die Ladezeit – bei einem 9-GB-Modell trifft das genau den, der
    nach längerer Pause etwas sucht.
    """
    return "30m"


def _ollama_inhalt(nachricht: dict) -> str:
    """Die Antwort – auch wenn das Modell sie ins Denken geschrieben hat.

    `qwen3-vl` ist ein Denkmodell und legt seine Antwort in `thinking` ab;
    `content` bleibt leer, und `think: false` ändert daran nichts (geprüft
    am 21.08.2026). Ohne diesen Griff sah ausgerechnet das neueste Modell
    aus, als könne es gar nichts – dabei stand die richtige Antwort da, nur
    im falschen Feld.

    Bleibt auch nach dem Umzug der Bilderkennung in den Hub gebraucht: Das
    Übersetzen der Suchbegriffe läuft weiter über ein lokales Modell, und
    Denkmodelle antworten dort genauso.
    """
    inhalt = (nachricht or {}).get("content") or ""
    if inhalt.strip():
        return inhalt
    return (nachricht or {}).get("thinking") or ""


def ollama_modelle(url: str = "") -> list:
    """Welche Modelle liegen auf dem Server?

    `url` erlaubt das Abfragen einer **noch nicht gespeicherten** Adresse.
    Ohne das müsste man erst eine ungeprüfte Einstellung sichern, um zu
    sehen, was dort überhaupt zur Wahl steht – genau die Reihenfolge, die
    man beim Einrichten nicht will.

    Im Fehlerfall eine leere Liste: Die Auswahl ist eine Bequemlichkeit,
    kein Zugangsweg. Wer den Namen kennt, muss ihn weiterhin von Hand
    eintragen können, auch wenn der Dienst gerade schweigt.
    """
    leer = {"models": [], "vision": []}
    basis = (url or ollama_setting("ollama_url")).strip().rstrip("/")
    if not basis:
        return leer
    try:
        resp = requests.get(basis + "/api/tags", timeout=OLLAMA_TIMEOUT,
                            headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        roh = resp.json().get("models", [])
    except Exception:
        return leer
    namen, sieht = [], []
    for m in roh:
        name = (m or {}).get("name") or (m or {}).get("model") or ""
        name = str(name).strip()
        # Ollama liefert dieselbe Ablage teils doppelt (`name` und `model`),
        # und bei mehreren Marken desselben Modells wiederholt sich der Name.
        if not name or name in namen:
            continue
        # Code-Modelle taugen für keine der beiden Aufgaben. Sie stehen sonst
        # mitten in einer Liste, in der man das Passende suchen soll.
        if re.search(r"cod(e|er)", name, re.I):
            continue
        namen.append(name)
        if "vision" in (m.get("capabilities") or []):
            sieht.append(name)
    namen.sort(key=str.casefold)
    return {"models": namen, "vision": sorted(sieht, key=str.casefold)}


def begriffe_gelernt(begriff: str) -> tuple:
    """Was zu diesem Begriff in der Liste steht – (Begriffe, Quelle)."""
    with core.db() as conn:
        r = conn.execute("SELECT begriffe, quelle FROM suchbegriffe "
                         "WHERE begriff = ?", (begriff.casefold(),)).fetchone()
    if not r:
        return [], ""
    return [b for b in json.loads(r["begriffe"]) if b], r["quelle"]


# Wie lange ein kürzerer Begriff als Tippzwischenstand gilt. Wer „Ritter"
# eintippt, löst nach dem dritten Zeichen bei jedem weiteren eine Suche aus –
# und jede merkte sich ihren Begriff. In der Liste standen dann „rit", „ritt",
# „ritte" neben „ritter". Zwei Minuten sind großzügig fürs Tippen und kurz
# genug, dass eine Suche von gestern nicht angetastet wird.
BEGRIFF_TIPPFENSTER = 120


def begriffe_merken(begriff: str, begriffe: list, quelle: str = "ki"):
    """Eine Zeile in die Liste schreiben.

    Eine von Hand eingetragene Zeile wird vom Modell **nicht** überschrieben –
    sonst wäre das Gelernte beim nächsten Suchlauf wieder weg. Umgekehrt darf
    von Hand jederzeit korrigiert werden.

    **Zwischenstände fliegen wieder raus.** Sie sind nicht nur Krempel: Das
    Modell reimt sich aus einem abgeschnittenen Wort etwas zusammen, das es
    gar nicht gibt. Aus „at st captain phasm" wurde am 21.08.2026 ein
    „Phantom Captain" – sechs Sekunden bevor „at st captain phasma" die
    richtige Antwort brachte. Beides stand danach nebeneinander in der Liste.
    """
    schluessel = begriff.casefold().strip()
    if not schluessel:
        return
    jetzt = int(time.time())
    with core.db() as conn:
        if quelle == "ki":
            vorher = conn.execute("SELECT quelle FROM suchbegriffe "
                                  "WHERE begriff = ?", (schluessel,)).fetchone()
            if vorher and vorher["quelle"] == "hand":
                return
        conn.execute(
            "INSERT INTO suchbegriffe (begriff, begriffe, quelle, created_at,"
            " used_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(begriff) DO UPDATE SET begriffe = excluded.begriffe,"
            " quelle = excluded.quelle, used_at = excluded.used_at",
            (schluessel, json.dumps(begriffe[:8]), quelle, jetzt, jetzt))
        if quelle == "ki":
            # Alles wegräumen, was ein Anfang des neuen Begriffs ist und
            # eben erst dazukam – das war der Weg dorthin, nicht das Ziel.
            # `substr` statt `LIKE`, weil ein `_` im Begriff sonst als
            # Platzhalter wirkte. Von Hand Eingetragenes bleibt unberührt.
            conn.execute(
                "DELETE FROM suchbegriffe WHERE quelle = 'ki' "
                "AND length(begriff) < length(?) "
                "AND substr(?, 1, length(begriff)) = begriff "
                "AND created_at >= ?",
                (schluessel, schluessel, jetzt - BEGRIFF_TIPPFENSTER))


def suchbegriffe(q: str) -> list:
    """Deutsche Suchanfrage in englische BrickLink-Begriffe uebersetzen.

    Drei Stufen, in dieser Reihenfolge: die gelernte Liste in der Datenbank,
    der Zwischenspeicher, dann das Modell. Was das Modell liefert, wandert in
    die Liste – von dort ist es einseh- und korrigierbar, überlebt einen
    Neustart und bleibt beim Wechsel des Modells erhalten.

    Gibt im Zweifel eine leere Liste zurueck – jeder Fehler ist hier
    unkritisch, weil die normale Suche bereits gelaufen ist.
    """
    q = (q or "").strip()
    if not q:
        return []
    key = q.casefold()
    # **Vor** der Frage, ob eine KI eingerichtet ist: Von Hand gepflegte
    # Begriffe sollen auch ohne Modell gelten. Sonst hinge das Gelernte an
    # einem Dienst, der damit gar nichts zu tun hat.
    gelernt, quelle = begriffe_gelernt(key)
    if gelernt and quelle == "hand":
        return gelernt
    if not ollama_enabled():
        return gelernt
    gemerkt = _begriff_cache.get(key)
    if gemerkt is not None:
        bis, treffer = gemerkt
        if bis is None or time.time() < bis:
            return treffer
    if gelernt:
        _begriff_cache[key] = (None, gelernt)
        return gelernt
    basis = ollama_setting("ollama_url").strip().rstrip("/")
    try:
        resp = requests.post(
            basis + "/api/chat",
            json={"model": ollama_modell(), "stream": False, "think": False,
                  "format": _OLLAMA_SCHEMA, "options": {"temperature": 0},
                  "keep_alive": _ollama_keep_alive(),
                  "messages": [{"role": "system", "content": _OLLAMA_SYSTEM},
                               {"role": "user", "content": q}]},
            timeout=OLLAMA_TIMEOUT, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        inhalt = _ollama_inhalt(resp.json().get("message", {}))
        roh = json.loads(inhalt).get("begriffe", [])
    except Exception:
        roh = []
    begriffe = []
    for b in roh if isinstance(roh, list) else []:
        b = str(b).strip()
        # Der eigene Begriff bringt nichts – danach wurde schon gesucht.
        if b and b.casefold() != key and b not in begriffe:
            begriffe.append(b[:60])
    begriffe = begriffe[:4]
    if len(_begriff_cache) >= _CACHE_MAX:
        _begriff_cache.clear()
    # Treffer gelten dauerhaft, ein leeres Ergebnis nur kurz: Sonst macht ein
    # einzelner Aussetzer den Suchbegriff bis zum Neustart unbrauchbar.
    _begriff_cache[key] = ((None if begriffe else time.time() + _MISSERFOLG_GILT),
                           begriffe)
    # **Hier wird nichts mehr gemerkt.** Was das Modell sagt, ist noch kein
    # Wissen – erst was damit gefunden wurde. Bis 2.37.5 landete jede
    # Modellantwort dauerhaft in der Liste, auch wenn kein einziger Treffer
    # dabei herauskam; und die Liste wird **vor** dem Modell befragt. Eine
    # erfundene Übersetzung war damit für immer festgeschrieben.
    #
    # Wer merkt, ist jetzt der Aufrufer: Er allein weiß, welche Begriffe
    # wirklich etwas getroffen haben.
    return begriffe
