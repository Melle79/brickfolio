"""Warum die geratene Art der Figur nicht in den Suchtext gehört.

Am 22.08.2026 lieferte die Katalogsuche auf „Ritter" drei Figuren, die
keine sind: Luke Skywalker (Tatooine), einen Imperial Royal Guard und den
siebenjährigen Boba Fett. Alle drei trugen `art='knight'` – ein einziges
Wort, vom Bildmodell geraten, das gleichberechtigt neben dem Namen im
Suchtext stand.

Das ist derselbe Fehler wie „Greedo unter den Rittern" in 2.28.1, nur durch
eine andere Tür: Dort war es die Sortierung, hier ist es eine Vermutung mit
dem Gewicht einer Tatsache.

Den Namen mitzugeben behebt es nicht. An denselben drei Figuren gemessen
verschwand „Knight" zwar, wurde aber durch „Pilot" bzw. „Soldier" ersetzt –
zwei von drei blieben falsch. Deshalb steht im Index nur noch, was entweder
Katalogwahrheit ist (Name) oder beobachtet (Farben, Teilbeschreibung).
"""
import pytest

import core
import main


@pytest.fixture
def abzug(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "abzug.db"))
    core.init_db()
    with core.db() as conn:
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such, "
            "img_url, farben, art, merkmale, updated_at) VALUES "
            "('sw0021', 'minifig', 'Luke Skywalker (Tatooine)', "
            "'luke skywalker tatooine', '', 'white, tan', 'knight', "
            "'head yellow simple face; torso white tunic', 0)")
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such, "
            "img_url, farben, art, merkmale, updated_at) VALUES "
            "('cas001', 'minifig', 'Knight with Blue Plumes', "
            "'knight with blue plumes', '', 'blue, silver', 'knight', "
            "'helmet silver with blue plumes; torso blue', 0)")
    return True


def test_geratene_art_zieht_keine_fremde_figur_herein(abzug):
    """Der Vorfall: „Knight" fand Luke Skywalker über `art`."""
    gefunden = {t["item_id"] for t in main._katalog_suchen("Knight")}
    assert "sw0021" not in gefunden, (
        "Luke Skywalker wird wieder über die geratene Art gefunden")


def test_der_echte_ritter_wird_weiter_gefunden(abzug):
    """Die Gegenprobe – sonst hätte man die Suche nur kaputtgemacht.

    `cas001` heißt im Katalog „Knight"; der Treffer kommt aus dem Namen und
    muss bleiben.
    """
    gefunden = {t["item_id"] for t in main._katalog_suchen("Knight")}
    assert "cas001" in gefunden


def test_beobachtetes_bleibt_durchsuchbar(abzug):
    """Farben und Teilbeschreibung sind der Beitrag der Bildanalyse.

    „R-3PO Protocol Droid" sagt nirgends „rot" – das steht nur im Bild.
    Fiele das mit heraus, wäre der ganze Bilderlauf umsonst.
    """
    assert "sw0021" in {t["item_id"] for t in main._katalog_suchen("tunic")}
    assert "cas001" in {t["item_id"] for t in main._katalog_suchen("plumes")}
