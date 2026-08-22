"""Warum die Zahl der offenen Figuren frisch gezählt wird.

Am 22.08.2026 meldete die Oberfläche „alle Bilder angesehen", während in
Wahrheit erst 1.413 von 9.741 Figuren eine Beschreibung hatten – 8.328 waren
offen. Der Grund: `offen` stand im Laufzustand `_farb_lauf`, einem Wörterbuch
im Arbeitsspeicher, und wurde nur *während* eines laufenden Bilderlaufs
gefüllt. Nach jedem Neustart des Containers stand dort wieder 0, und an
diesem Tag wurde dreimal ausgerollt.

Eine Null, die „fertig" bedeutet, ist die unangenehmste Sorte Fehler: Sie
sieht aus wie ein Erfolg. Deshalb wird sie jetzt bei jeder Abfrage aus der
Datenbank gezählt – sie beschreibt die Daten, nicht den Lauf.
"""
import pytest

import core
import main


@pytest.fixture
def abzug(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "status.db"))
    core.init_db()
    with core.db() as conn:
        for nr, merkmale in (("sw0001", "head red"), ("sw0002", ""),
                             ("sw0003", ""), ("sw0004", "torso blue")):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such, "
                "img_url, merkmale, updated_at) VALUES (?, 'minifig', ?, ?, "
                "'https://x/y.jpg', ?, 0)", (nr, nr, nr, merkmale))
        # Ohne Bild kommt sie nie dran und zählt deshalb nicht als offen.
        conn.execute(
            "INSERT INTO katalog_index (item_no, item_type, name, such, "
            "img_url, merkmale, updated_at) VALUES ('sw0005', 'minifig', "
            "'ohne Bild', 'ohne bild', '', '', 0)")
    return True


def test_offen_kommt_aus_der_datenbank(abzug):
    """Der Vorfall: nach einem Neustart stand im Laufzustand 0."""
    main._farb_lauf.update({"aktiv": False, "getan": 0, "gefunden": 0})
    s = main.katalog_status(user={"name": "test", "is_admin": 1})
    assert s["farben"]["offen"] == 2, (
        "die offenen Figuren werden nicht frisch gezählt")
    assert s["anzahl"] == 5


def test_offen_steht_nicht_mehr_im_laufzustand():
    """Sonst schliche sich dieselbe Null über die Hintertür zurück."""
    assert "offen" not in main._farb_lauf
