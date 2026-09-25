"""Das Tausch-Netzwerk hat eigene Dateien – und bleibt optional.

Seit 2.88.52: Server in `backend/community.py` (Router), Oberfläche in
`frontend/community.js`. Die Tests hier halten fest, was der Umzug
versprochen hat.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend"


def test_community_js_laedt_vor_app_js():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert html.index("/static/community.js") < html.index("/static/app.js")


def test_community_js_fuehrt_beim_laden_nichts_aus():
    """Geladen vor app.js: Auf oberster Ebene darf nur stehen, was nichts
    aus app.js braucht – Funktionen und Variablen mit festem Anfangswert."""
    js = (FRONTEND / "community.js").read_text(encoding="utf-8")
    ohne_kommentare = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    erlaubt = re.compile(
        r"^(async function |function |let \w+ = (null|false|true|\d+|\[\]|"
        r"\"\w*\"|new Map\(\));|const [A-Z_]+ = \[|\];|\}|$|//)")
    oben = [z for z in ohne_kommentare.split("\n")
            if z and not z[0].isspace() and not erlaubt.match(z)]
    assert not oben, "oberste Ebene: " + "; ".join(oben[:5])


def test_service_worker_haelt_community_js_vor():
    sw = (FRONTEND / "sw.js").read_text(encoding="utf-8")
    assert '"/static/community.js"' in sw


def test_hub_endpunkte_liegen_im_community_router():
    main = (WURZEL / "backend" / "main.py").read_text(encoding="utf-8")
    community = (WURZEL / "backend" / "community.py").read_text(
        encoding="utf-8")
    assert '"/api/hub' not in main, "Hub-Endpunkte gehören nach community.py"
    # 26 beim Umzug (2.88.52), dazu Profile und Entdecken (2.88.53).
    assert community.count('@router.') >= 26
    assert "app.include_router(community.router)" in main


def test_ohne_einladung_bleibt_der_tab_verborgen():
    """Optional: Der Tab erscheint erst nach dem Beitritt per Einladung."""
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert re.search(r'id="tab-hub"[^>]*hidden', html)
    app = (FRONTEND / "app.js").read_text(encoding="utf-8")
    assert "tab.hidden = !state.hubConnected;" in app
