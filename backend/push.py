"""Web-Push von der eigenen Instanz.

Damit erfährt ein Admin von einem Fehler auch dann, wenn Brickfolio gerade
zu ist. Wichtig ist, was dabei **nicht** passiert:

- Es geht kein Weg über den Tausch-Hub. Fehler sind Sache dieser Instanz;
  sie an einen Dienst zu schicken, den jemand anderes betreibt, wäre genau
  die Telemetrie, die es hier nicht geben soll.
- Der Text ist bewusst nichtssagend („Ein Fehler wurde aufgezeichnet").
  Zustellen muss der Push-Dienst des Browser-Herstellers (Apple, Google,
  Mozilla) – anders geht Web-Push nicht. Der Inhalt ist auf dem Weg dorthin
  zwar verschlüsselt (das schreibt der Standard vor), aber was gar nicht
  drinsteht, kann auch nicht auffallen.
- Die Schlüssel entstehen beim ersten Einschalten auf dem eigenen Server und
  bleiben dort.
"""
import json
import time

import core

VAPID_PRIV = "vapid_private"
VAPID_PUB = "vapid_public"

# Ohne Kontaktangabe lehnen manche Push-Dienste ab. Eine Seite tut es auch –
# eine E-Mail-Adresse wäre hier ein unnötiges Datum.
VAPID_CLAIMS_SUB = "https://github.com/Melle79/brickfolio"


def verfuegbar() -> bool:
    """Sind die Bibliotheken da? Ohne sie läuft der Rest weiter."""
    try:
        import pywebpush          # noqa: F401
        return True
    except Exception:
        return False


def _schluessel() -> tuple[str, str]:
    """Schlüsselpaar der Instanz – beim ersten Aufruf erzeugt.

    Es bleibt danach unverändert: Der öffentliche Teil steckt in jedem
    Abonnement, das ein Browser angelegt hat. Ein neues Paar würde alle
    bestehenden Abonnements ungültig machen, ohne dass jemand merkt, warum
    keine Meldungen mehr kommen.
    """
    priv = core.get_setting(VAPID_PRIV)
    pub = core.get_setting(VAPID_PUB)
    if priv and pub:
        return priv, pub
    from py_vapid import Vapid02
    v = Vapid02()
    v.generate_keys()
    priv = v.private_pem().decode()
    # Der öffentliche Schlüssel geht als **rohe** Kurvenpunkt-Darstellung in
    # base64url ohne Polster an den Browser – nur so nimmt ihn
    # `applicationServerKey` an. Die PEM-Fassung wäre dort wertlos.
    import base64
    from cryptography.hazmat.primitives import serialization
    roh = v.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint)
    pub = base64.urlsafe_b64encode(roh).rstrip(b"=").decode()
    core.set_setting(VAPID_PRIV, priv)
    core.set_setting(VAPID_PUB, pub)
    return priv, pub


def public_key() -> str:
    return _schluessel()[1]


def abonnieren(user_id: int, sub: dict, agent: str = "") -> None:
    """Ein Gerät einträgt. Dieselbe Adresse zweimal ist ein Gerät, nicht zwei."""
    keys = sub.get("keys") or {}
    with core.db() as conn:
        conn.execute(
            "INSERT INTO push_subs (user_id, endpoint, p256dh, auth, "
            "user_agent, created_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(endpoint) DO UPDATE SET p256dh = excluded.p256dh, "
            "auth = excluded.auth, user_id = excluded.user_id",
            (user_id, sub.get("endpoint", ""), keys.get("p256dh", ""),
             keys.get("auth", ""), agent[:200], int(time.time())))


def abbestellen(endpoint: str) -> None:
    with core.db() as conn:
        conn.execute("DELETE FROM push_subs WHERE endpoint = ?", (endpoint,))


def geraete(user_id: int) -> list:
    with core.db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, endpoint, user_agent, created_at FROM push_subs "
            "WHERE user_id = ? ORDER BY created_at", (user_id,))]


def _entfernen(endpoint: str, grund: str) -> None:
    """Abgelaufene Abonnements wegräumen. Browser wechseln ihre Adresse, wenn
    die App neu installiert wird – der alte Eintrag zeigt dann ins Leere."""
    abbestellen(endpoint)


def senden(titel: str, text: str, url: str = "/") -> int:
    """An alle eingetragenen Geräte schicken. Gibt zurück, wie viele erreicht
    wurden. Fehler dabei sind nie ein Grund, den Aufrufer zu stören."""
    if not verfuegbar():
        return 0
    with core.db() as conn:
        subs = [dict(r) for r in conn.execute("SELECT * FROM push_subs")]
    if not subs:
        return 0
    from pywebpush import webpush, WebPushException
    priv, _ = _schluessel()
    daten = json.dumps({"title": titel, "body": text, "url": url})
    zugestellt = 0
    for s in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": s["endpoint"],
                    "keys": {"p256dh": s["p256dh"], "auth": s["auth"]},
                },
                data=daten,
                vapid_private_key=priv,
                vapid_claims={"sub": VAPID_CLAIMS_SUB},
                timeout=10,
            )
            zugestellt += 1
        except WebPushException as e:
            # 404/410 heißt: Dieses Abonnement gibt es nicht mehr. Alles
            # andere kann ein vorübergehender Aussetzer sein – dann bleibt
            # der Eintrag stehen und wird beim nächsten Mal erneut versucht.
            code = getattr(e.response, "status_code", None)
            if code in (404, 410):
                _entfernen(s["endpoint"], f"Push {code}")
        except Exception:
            pass
    return zugestellt
