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


def blocked() -> bool:
    return core.get_setting("hub_blocked") == "1"


def _remember_instance(data: dict):
    """Kennung und Geheimnis der Installation merken.

    Beides ist nichts für die Oberfläche – es liegt still in den Einstellungen
    und geht nur beim Beitritt wieder an den Hub. Weil die Einstellungen in der
    Sicherung stecken, ist eine neu aufgesetzte und zurückgesicherte
    Installation für den Hub wieder dieselbe Instanz. Sichtbar wird die Kennung
    dort, wo man sie braucht: in der Admin-Konsole.
    """
    code = (data.get("instance_code") or "").strip()
    if code:
        core.set_setting("hub_instance_code", code)
    secret = (data.get("instance_secret") or "").strip()
    if secret:
        core.set_setting("hub_instance_secret", secret)


def _instance_claim() -> dict:
    """Womit sich diese Installation beim Hub zu erkennen gibt."""
    code = core.get_setting("hub_instance_code") or ""
    secret = core.get_setting("hub_instance_secret") or ""
    if not code or not secret:
        return {}
    return {"instance_code": code, "instance_secret": secret}


def _store(token, me):
    core.set_setting("hub_token", token)
    core.set_setting("hub_member_id", me.get("member_id", ""))
    core.set_setting("hub_display_name", me.get("display_name", ""))
    core.set_setting("hub_is_admin", "1" if me.get("is_admin") else "0")
    core.set_setting("hub_blocked", "")
    # Der Schlüssel gilt beim Hub je Mitglied. Wer sich neu anmeldet, ist dort
    # ein neues Mitglied – ohne diese Zeile hielte sich die Instanz für schon
    # gemeldet und bliebe für Nachrichten unerreichbar.
    core.set_setting("hub_key_sent", "")


def disconnect():
    for k in ("hub_token", "hub_member_id", "hub_display_name",
              "hub_is_admin", "hub_last_publish", "hub_blocked",
              "hub_key_sent"):
        core.set_setting(k, "")


# ------------------------------------------------------------------ HTTP

def _stoerung(method, path, grund):
    """Eine Störung des Hubs ins Container-Protokoll schreiben.

    Am 13.08.2026 stand im Fehlerbericht zu einem 502 nur „Fehler 502" und
    eine Cloudflare-Seite. Die App hatte ihre Erklärung dabei – „Hub: …" –,
    aber der Rumpf ihrer Antwort wurde zwischen Instanz und Browser durch
    eine Fehlerseite ersetzt. Der Hub wiederum antwortet nach außen nur mit
    „interner Fehler". Beide Seiten kannten den Grund, keine behielt ihn,
    und rückwirkend war er nicht mehr zu ermitteln.

    Nur Störungen, keine Absagen: Ein 401 bei falschem Token und ein 403 für
    einen gesperrten Zugang sind Antworten, keine Ausfälle – die gehören
    nicht ins Protokoll.
    """
    print(f"[brickfolio] Hub {method} {path} – {grund}", flush=True)


def _request(method, url, path, token=None, body=None, timeout=TIMEOUT):
    headers = {"user-agent": USER_AGENT}
    if token:
        headers["authorization"] = "Bearer " + token
    try:
        resp = requests.request(method, url.rstrip("/") + path,
                                headers=headers, json=body, timeout=timeout)
    except requests.RequestException as e:
        # Der Typ trägt hier die Aussage: `ConnectTimeout` heißt „gar nicht
        # erreicht", `ReadTimeout` heißt „angenommen und dann nichts mehr".
        _stoerung(method, path, f"keine Antwort ({type(e).__name__}, "
                                f"{timeout}s)")
        raise
    json_gelesen = True
    try:
        data = resp.json()
    except ValueError:
        data = {}
        json_gelesen = False
    if not resp.ok:
        msg = data.get("error") if isinstance(data, dict) else None
        if resp.status_code >= 500:
            # Ob der Worker selbst geantwortet hat oder eine Fehlerseite von
            # Cloudflare davor – daran hängt, wo man weitersucht. Sichtbar
            # ist der Unterschied nur am Anfang der Antwort: Der Worker
            # schickt JSON, Cloudflare eine HTML-Seite.
            _stoerung(method, path, f"{resp.status_code} – " + (
                msg if json_gelesen and msg
                else "kein JSON: " + " ".join(resp.text.split())[:200]))
        if (isinstance(data, dict) and data.get("blocked")
                and core.get_setting("hub_token")):
            # Der Zugang ist gesperrt, nicht kaputt. Das merken wir uns, damit
            # die App es sagen kann – der Token bleibt liegen, denn nach einer
            # Freischaltung geht damit alles weiter.
            core.set_setting("hub_blocked", "1")
        raise HubError(resp.status_code, msg or f"Hub-Fehler {resp.status_code}")
    if token and core.get_setting("hub_blocked"):
        core.set_setting("hub_blocked", "")     # Freischaltung bemerkt
    return data


class HubError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# ------------------------------------------------------------------ Aktionen

def connect_with_token(token: str) -> dict:
    """Bestehenden Token prüfen (/v1/me) und speichern."""
    me = _request("GET", HUB_URL, "/v1/me?instance=1", token=token)
    _store(token, me)
    _remember_instance(me)
    return me


def connect_with_invite(invite_code: str, display_name: str) -> dict:
    """Per Einladungscode beitreten, Token erhalten und speichern.

    Kennt diese Installation schon eine Instanz-Kennung, geht sie mit: der Hub
    führt die Vorgeschichte dann fort, statt eine neue Instanz anzulegen.
    """
    body = {"invite_code": invite_code, "display_name": display_name}
    body.update(_instance_claim())
    res = _request("POST", HUB_URL, "/v1/register", body=body)
    _store(res.get("token", ""), res)
    _remember_instance(res)
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
    me = _authed("GET", "/v1/me?instance=1", timeout=6)
    core.set_setting("hub_display_name", me.get("display_name", ""))
    core.set_setting("hub_is_admin", "1" if me.get("is_admin") else "0")
    _remember_instance(me)      # Instanzen von vor der Kennung holen sie hier
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


def invite_quota() -> dict:
    """Wie viele Einladungen sind noch offen?"""
    return _authed("GET", "/v1/invites/quota")


def request_invites(want: int, reason: str = "") -> dict:
    """Mehr Einladungen anfragen – ein Hub-Admin entscheidet darüber."""
    return _authed("POST", "/v1/invite_requests",
                   body={"want": want, "reason": reason})


# ------------------------------------------------- Handel & Nachrichten

def put_key(public_key: str) -> dict:
    return _authed("PUT", "/v1/key", body={"public_key": public_key})


def member_key(member_id: str) -> dict:
    return _authed("GET", f"/v1/key/{member_id}")


def create_trade(to: str, item_id: str, item_name: str, box: str) -> dict:
    return _authed("POST", "/v1/trades", body={
        "to": to, "item_id": item_id, "item_name": item_name, "box": box})


def trades() -> list:
    return _authed("GET", "/v1/trades").get("trades", [])


def send_message(trade_id: str, box: str) -> dict:
    return _authed("POST", f"/v1/trades/{trade_id}/messages", body={"box": box})


def fetch_messages(trade_id: str) -> dict:
    return _authed("GET", f"/v1/trades/{trade_id}/messages")


def set_trade_status(trade_id: str, status: str) -> dict:
    return _authed("POST", f"/v1/trades/{trade_id}/status",
                   body={"status": status})


def delete_trade(trade_id: str) -> dict:
    return _authed("DELETE", f"/v1/trades/{trade_id}")


def report(against: str, reason: str, trade_id: str = "",
           disclosed: list | None = None) -> dict:
    body = {"against": against, "reason": reason}
    if trade_id:
        body["trade_id"] = trade_id
    if disclosed:
        body["disclosed"] = disclosed
    return _authed("POST", "/v1/reports", body=body)


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


# --------------------------------------------------- Fehlerberichte

# Eigener Token, eigener Weg. Bewusst **nicht** der Tausch-Token:
#
# 1. Nicht jede Instanz ist Mitglied im Tausch-Netzwerk. Von vier Instanzen
#    im Haushalt waren es zwei – hinge der Kanal am Mitgliedskonto, bliebe
#    die Hälfte stumm, und zwar ausgerechnet die aussagekräftige Hälfte.
# 2. Wer einen Fehlerbericht schickt, gibt damit nichts über sein Tauschen
#    preis. Dieser Token kann nichts anderes als Berichte abliefern.
# 3. Er lässt sich einzeln zurückziehen, ohne jemandem das Tauschen zu nehmen.

def report_enabled() -> bool:
    return bool(core.get_setting("crash_token"))


# Wie viele Zeilen je Anfrage. Muss zum Hub passen, der bei 500 abriegelt.
KATALOG_STAPEL = 500


def katalog_hochladen(zeilen: list) -> dict:
    """Katalogzeilen an den Hub geben, in Stapeln zu 500.

    Eigener Token (`katalog_token`) wie beim Berichts-Kanal, nicht der
    Mitglieds-Token: Wer den Katalog pflegt, hat damit nichts im
    Tausch-Netzwerk zu tun – und umgekehrt.

    Gibt zurück, wie viele Zeilen angekommen sind. Ein Stapel, der scheitert,
    beendet den Vorgang: Der Rest kommt beim nächsten Lauf, und ein halb
    hochgeladener Stand ist kein Problem – der Hub führt jede Zeile für sich.
    """
    token = core.get_setting("katalog_token")
    if not token:
        raise HubError(400, "Für diese Instanz ist kein Katalog-Token "
                            "hinterlegt")
    geschrieben = 0
    for i in range(0, len(zeilen), KATALOG_STAPEL):
        antwort = _request("POST", HUB_URL, "/v1/katalog", token=token,
                           body={"zeilen": zeilen[i:i + KATALOG_STAPEL]},
                           timeout=60)
        geschrieben += int(antwort.get("geschrieben") or 0)
    return {"geschrieben": geschrieben}


def katalog_holen(seit: int = 0) -> dict:
    """Katalogänderungen seit `seit` abholen – eine Seite.

    Lesen darf jeder gültige Token; der Abzug ist Nachschlagewerk, kein
    Geheimnis. Der zurückgegebene `stand` ist der Zeitstempel der letzten
    gelieferten Zeile, nicht die Uhrzeit: Sonst übersähe der nächste Abruf
    alles, was zwischen Abfrage und Antwort geschrieben wurde.
    """
    token = core.get_setting("katalog_token") or core.get_setting("crash_token")
    if not token:
        raise HubError(400, "Kein Token für den Katalog hinterlegt")
    return _request("GET", HUB_URL, "/v1/katalog?seit=%d" % max(seit, 0),
                    token=token, timeout=60)


def send_crash_report(payload: str, app_version: str = "",
                      crashes: int = 0, views: str = "") -> dict:
    """Bericht abliefern. Wirft HubError, wenn es nicht klappt – die App
    zeigt dann den Weg zum Kopieren, statt so zu tun, als sei es raus."""
    token = core.get_setting("crash_token")
    if not token:
        raise HubError(400, "Für diese Instanz ist kein Berichts-Token "
                            "hinterlegt")
    return _request("POST", HUB_URL, "/v1/crash", token=token, body={
        "payload": payload, "app_version": app_version,
        "crashes": crashes, "views": views})
