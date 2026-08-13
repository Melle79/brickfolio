"""Warum eine Störung des Hubs im Protokoll der Instanz landen muss.

Am 13.08.2026 meldete Finns Instanz um 10:03 einen 502 bei
`POST /api/hub/trades/sync`. Im Fehlerbericht stand davon nur „Fehler 502"
und der Anfang einer Cloudflare-Fehlerseite. Die App hatte ihre Erklärung
dabei – „Hub: …" –, aber der Rumpf ihrer Antwort wurde zwischen Instanz und
Browser durch diese Seite ersetzt. Der Hub wiederum antwortet nach außen
grundsätzlich nur mit „interner Fehler", und seine Protokolle wurden damals
nicht aufbewahrt.

Beide Seiten kannten den Grund, keine behielt ihn. Rückwirkend war nicht
einmal mehr zu klären, ob der Worker überhaupt zu Wort gekommen war oder
etwas davor geantwortet hatte – und genau daran hängt, wo man weitersucht.
"""
import pytest
import requests

import hub

# So fing die Antwort im Bericht vom 13.08. an: die Fehlerseite von
# Cloudflare, nicht der Worker.
CLOUDFLARE = ('<!DOCTYPE html> <!--[if lt IE 7]> <html class="no-js ie6 '
              'oldie" lang="en-US"> <![endif]--> <!--[if IE 7]> <html '
              'class="no-js ie7 oldie" lang="en-US"> <![endif]-->')


class _Antwort:
    """Nur so viel, wie `_request` anfasst."""

    def __init__(self, status, text, daten=None):
        self.status_code = status
        self.ok = status < 400
        self.text = text
        self._daten = daten

    def json(self):
        if self._daten is None:
            raise ValueError("keine JSON-Antwort")
        return self._daten


def _antwortet(monkeypatch, antwort):
    monkeypatch.setattr(hub.requests, "request", lambda *a, **k: antwort)


def test_fehlerseite_vor_dem_worker_steht_im_protokoll(monkeypatch, capsys):
    """HTML statt JSON heißt: Der Worker kam gar nicht zu Wort.

    Das ist der Unterschied, der am 13.08. fehlte. Ohne ihn sucht man den
    Fehler im Hub, obwohl er davor sitzt – oder umgekehrt.
    """
    _antwortet(monkeypatch, _Antwort(502, CLOUDFLARE))
    with pytest.raises(hub.HubError):
        hub._request("POST", hub.HUB_URL, "/v1/trades")
    aus = capsys.readouterr().out
    assert "[brickfolio] Hub POST /v1/trades" in aus
    assert "502" in aus
    assert "kein JSON" in aus
    assert "DOCTYPE html" in aus, "der Anfang der Antwort fehlt"


def test_grund_des_workers_steht_im_protokoll(monkeypatch, capsys):
    """Antwortet der Worker selbst, ist sein Text das Ergebnis – und nicht
    der Hinweis, dass kein JSON kam."""
    _antwortet(monkeypatch, _Antwort(500, '{"error": "interner Fehler"}',
                                     {"error": "interner Fehler"}))
    with pytest.raises(hub.HubError):
        hub._request("GET", hub.HUB_URL, "/v1/me")
    aus = capsys.readouterr().out
    assert "500" in aus and "interner Fehler" in aus
    assert "kein JSON" not in aus


def test_keine_antwort_wird_vermerkt(monkeypatch, capsys):
    """Läuft die Anfrage in die Zeitgrenze, gibt es gar keinen Status.

    Der Typ trägt dann die Aussage: `ConnectTimeout` heißt „nie erreicht",
    `ReadTimeout` heißt „angenommen und dann nichts mehr".
    """
    def platzt(*a, **k):
        raise requests.ReadTimeout("zu lang")

    monkeypatch.setattr(hub.requests, "request", platzt)
    with pytest.raises(requests.RequestException):
        hub._request("POST", hub.HUB_URL, "/v1/trades")
    aus = capsys.readouterr().out
    assert "keine Antwort" in aus and "ReadTimeout" in aus
    assert str(hub.TIMEOUT) in aus, "die Zeitgrenze gehört dazu"


def test_absage_bleibt_still(monkeypatch, capsys):
    """Ein abgelehnter Token ist eine Antwort, kein Ausfall.

    Stünde jede 4xx im Protokoll, würde es von gewöhnlichem Betrieb volllaufen
    und die eine Zeile, die zählt, ginge darin unter.
    """
    _antwortet(monkeypatch, _Antwort(401, '{"error": "Token ungültig"}',
                                     {"error": "Token ungültig"}))
    with pytest.raises(hub.HubError):
        hub._request("GET", hub.HUB_URL, "/v1/me", token="egal")
    assert capsys.readouterr().out == ""


def test_kein_token_im_protokoll(monkeypatch, capsys):
    """Das Protokoll geht an den, der `docker logs` liest – der Instanz-Token
    hat dort nichts verloren. Er bleibt sonst ausschließlich in der DB."""
    _antwortet(monkeypatch, _Antwort(503, CLOUDFLARE))
    with pytest.raises(hub.HubError):
        hub._request("POST", hub.HUB_URL, "/v1/trades", token="geheim-123")
    assert "geheim-123" not in capsys.readouterr().out
