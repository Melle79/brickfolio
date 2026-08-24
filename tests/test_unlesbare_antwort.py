"""Warum eine einzelne Figur den Bilderlauf nicht mehr aufhalten kann.

Am 24.08.2026 blieb der Lauf bei 9.740 von 9.741 Figuren stehen. Die letzte
offene war `cty0131` („Police - City Leather Jacket with Gold Badge"). Das
Modell verfiel dort im Aufdruck-Feld in „TATATATATA…", die Längengrenze
schnitt die Zeichenkette bei 100 Zeichen ab, es begann im nächsten Feld von
vorn, und `num_predict` kappte schließlich mitten im JSON:

    {"kind": "Police", "parts": [ … {"part": "arms", "color": "black",
     "print": "white text \\"TATATATATATATATATA
                                              ← hier endete die Antwort

Unlesbar. Und weil ein Fehlschlag bewusst nichts wegschreibt, stand dieselbe
Figur beim nächsten Griff wieder vorn – zwölf Anläufe, dann beendete die
Ausfallschwelle den ganzen Lauf.

Der Unterschied, auf den es ankommt: „gar nicht geantwortet" ist ein Ausfall
des Dienstes – da darf nichts abgehakt werden, sonst gilt der halbe Katalog
als angesehen, ohne dass je jemand hingesehen hat (der Grund für die Regel
in 2.37.3). „Geantwortet, aber unlesbar" ist figurenspezifisch: Der Dienst
läuft, diese eine Figur bringt ihn aus dem Tritt.
"""
import pytest

import core
import integrations
import main


@pytest.fixture
def abzug(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "lauf.db"))
    core.init_db()
    with core.db() as conn:
        for nr in ("cty0131", "cty0132"):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such, "
                "img_url, merkmale, updated_at) VALUES (?, 'minifig', ?, ?, "
                "'https://x/y.jpg', '', 0)", (nr, nr, nr))
    monkeypatch.setattr(integrations, "fetch_catalog_image",
                        lambda *a, **k: b"bild")
    monkeypatch.setattr(integrations, "prepare_image", lambda b, n=512: b)
    monkeypatch.setattr(main.time, "sleep", lambda s: None)
    return True


def test_unlesbare_figur_haelt_den_lauf_nicht_auf(abzug, monkeypatch):
    """Der Vorfall: `cty0131` blockierte 9.740 fertige Figuren."""
    versuche = {"n": 0}

    def immer_unlesbar(bild):
        versuche["n"] += 1
        return {"art": "", "farben": [], "merkmale": "", "unbrauchbar": True,
                "fehler": "JSONDecodeError: Unterminated string"}

    monkeypatch.setattr(integrations, "bild_merkmale", immer_unlesbar)
    main._katalog_farben()

    with core.db() as conn:
        offen = conn.execute("SELECT COUNT(*) AS n FROM katalog_index WHERE "
                             "merkmale = ''").fetchone()["n"]
    assert offen == 0, "die unlesbare Figur blockiert die Warteschlange"
    assert not main._farb_lauf["fehler"], "der Lauf hat abgebrochen"
    # Drei Anläufe je Figur, dann abgehakt – nicht endlos.
    assert versuche["n"] == 2 * main.KATALOG_FARB_AUFGEBEN


def test_ein_ausfall_hakt_weiterhin_nichts_ab(abzug, monkeypatch):
    """Die Regel aus 2.37.3 muss unangetastet bleiben.

    Antwortet der Dienst gar nicht, darf keine Figur als angesehen gelten –
    sonst wäre der halbe Katalog stillschweigend abgehakt.
    """
    monkeypatch.setattr(
        integrations, "bild_merkmale",
        lambda bild: {"art": "", "farben": [], "merkmale": "",
                      "fehler": "ConnectionError: keine Antwort"})
    main._katalog_farben()

    with core.db() as conn:
        offen = conn.execute("SELECT COUNT(*) AS n FROM katalog_index WHERE "
                             "merkmale = ''").fetchone()["n"]
    assert offen == 2, "ein Ausfall hat Figuren abgehakt"
    assert "antwortet nicht" in main._farb_lauf["fehler"]


def test_die_wiederholungsbremse_ist_gesetzt():
    """Sie verhindert die Entgleisung überhaupt erst."""
    assert integrations.OLLAMA_BILD_WIEDERHOLUNG > 1.0
