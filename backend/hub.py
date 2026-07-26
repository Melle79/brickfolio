"""Instanz-Seite des Tausch-Hubs.

Spricht server-zu-server mit dem Brickfolio-Hub (Cloudflare Worker). Der
Instanz-Token bleibt hier in der DB (settings) und geht nie an den Browser.
"""
import json
import os

import requests

import core

TIMEOUT = 15
USER_AGENT = "Brickfolio-Instance/1.0"

# Feste Hub-Adresse für dieses Netzwerk. Über die Umgebung überschreibbar
# (z. B. später hub.brickfolio.cc), aber kein Eingabefeld in der App.
HUB_URL = (os.environ.get("HUB_URL")
           or "https://brickfolio-hub.bfhub.workers.dev").rstrip("/")


# ------------------------------------------------------------------ Konfig

def config() -> dict:
    """Verbindungs-Info (feste Adresse, Token bleibt intern)."""
    return {
        "url": HUB_URL,
        "token": core.get_setting("hub_token") or "",
        "member_id": core.get_setting("hub_member_id") or "",
        "display_name": core.get_setting("hub_display_name") or "",
        "is_admin": core.get_setting("hub_is_admin") == "1",
    }


def enabled() -> bool:
    return bool(core.get_setting("hub_token"))


def _store(token, me):
    core.set_setting("hub_token", token)
    core.set_setting("hub_member_id", me.get("member_id", ""))
    core.set_setting("hub_display_name", me.get("display_name", ""))
    core.set_setting("hub_is_admin", "1" if me.get("is_admin") else "0")


def disconnect():
    for k in ("hub_token", "hub_member_id", "hub_display_name",
              "hub_is_admin", "hub_last_publish"):
        core.set_setting(k, "")


# ------------------------------------------------------------------ HTTP

def _request(method, url, path, token=None, body=None, timeout=TIMEOUT):
    headers = {"user-agent": USER_AGENT}
    if token:
        headers["authorization"] = "Bearer " + token
    resp = requests.request(method, url.rstrip("/") + path, headers=headers,
                            json=body, timeout=timeout)
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if not resp.ok:
        msg = data.get("error") if isinstance(data, dict) else None
        raise HubError(resp.status_code, msg or f"Hub-Fehler {resp.status_code}")
    return data


class HubError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# ------------------------------------------------------------------ Aktionen

def connect_with_token(token: str) -> dict:
    """Bestehenden Token prüfen (/v1/me) und speichern."""
    me = _request("GET", HUB_URL, "/v1/me", token=token)
    _store(token, me)
    return me


def connect_with_invite(invite_code: str, display_name: str) -> dict:
    """Per Einladungscode beitreten, Token erhalten und speichern."""
    res = _request("POST", HUB_URL, "/v1/register",
                   body={"invite_code": invite_code,
                         "display_name": display_name})
    _store(res.get("token", ""), res)
    return res


def _authed(method, path, body=None, timeout=TIMEOUT):
    token = core.get_setting("hub_token")
    if not token:
        raise HubError(400, "Kein Hub verbunden")
    return _request(method, HUB_URL, path, token=token, body=body,
                    timeout=timeout)


def refresh():
    """Aktuellen Anzeigenamen/Admin-Status vom Hub holen und Cache auffrischen.
    Kurzer Timeout, weil best-effort (Statusanzeige)."""
    me = _authed("GET", "/v1/me", timeout=6)
    core.set_setting("hub_display_name", me.get("display_name", ""))
    core.set_setting("hub_is_admin", "1" if me.get("is_admin") else "0")
    return me




def publish(offers: list) -> dict:
    res = _authed("PUT", "/v1/offers", body={"offers": offers})
    core.set_setting("hub_last_publish", json.dumps(
        {"ts": _now(), "count": res.get("count", 0)}))
    return res


def offers(params: dict | None = None) -> list:
    qs = ""
    if params:
        from urllib.parse import urlencode
        qs = "?" + urlencode({k: v for k, v in params.items() if v})
    return _authed("GET", "/v1/offers" + qs).get("offers", [])


def members() -> list:
    return _authed("GET", "/v1/members").get("members", [])


def create_invite(note: str = "", expires_in_days: int = 0) -> dict:
    body = {"note": note}
    if expires_in_days:
        body["expires_in_days"] = expires_in_days
    return _authed("POST", "/v1/invites", body=body)


def last_publish() -> dict | None:
    raw = core.get_setting("hub_last_publish")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _now():
    import time
    return int(time.time())
