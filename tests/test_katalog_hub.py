"""Warum der Abzug einmal zentral liegt statt viermal lokal.

Jede Instanz baute ihn bisher selbst: Nummern der Reihe nach bei BrickLink
abklappern (Tage, eigenes Kontingent) und danach jedes Bild von einem
Sehmodell beschreiben lassen (rund 24 Stunden Grafikeinheit für 9.741
Figuren). Dieselbe Arbeit für dasselbe Ergebnis – der Katalog beschreibt
BrickLinks Fotos, nicht die Sammlung von irgendwem. Nerdfan, Paul und Kello
hatten deshalb null Zeilen im Abzug, und seit dem 23.08. auch kein Sehmodell
mehr, mit dem sie ihn erarbeiten könnten.

Seit 2.41.0 erzeugt ihn der **Hub**: Er klappert BrickLink ab und lässt die
Bilder beschreiben. Keine Instanz schiebt mehr hoch – sie holen nur noch.
Deshalb steht hier ausschließlich die Abholrichtung.
"""
import pytest

import core
import hub
import integrations
import main


@pytest.fixture
def abzug(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "hub.db"))
    core.init_db()
    with core.db() as conn:
        for nr, merkmale, stand in (("sw0010", "head tan smooth", 100),
                                    ("sw0021", "torso white tunic", 200),
                                    ("sw0099", "", 150)):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such, "
                "img_url, farben, art, merkmale, updated_at) VALUES "
                "(?, 'minifig', ?, ?, '', 'tan', 'droid', ?, ?)",
                (nr, nr, nr, merkmale, stand))
    return True


# ------------------------------------- Die Gegenrichtung: abholen

def _hub_antwort(monkeypatch, seiten):
    """Den Hub vortäuschen – eine Liste von Antworten, Seite für Seite."""
    gefragt: list = []

    def fake(seit=0):
        gefragt.append(seit)
        return seiten[min(len(gefragt) - 1, len(seiten) - 1)]
    monkeypatch.setattr(hub, "katalog_holen", fake)
    return gefragt


def test_wer_nicht_selbst_abklappert_holt_den_abzug(abzug, monkeypatch):
    """Nerdfan, Paul und Kello haben weder BrickLink-Kontingent noch
    Sehmodell. Dieselbe Arbeit noch einmal zu leisten hieße Tage Abrufe und
    rund einen Tag Grafikeinheit – für dasselbe Ergebnis."""
    core.set_setting("crash_token", "berichts-token")
    _hub_antwort(monkeypatch, [
        {"zeilen": [{"item_no": "cas001", "item_type": "minifig",
                     "name": "Dragon Master", "such": "dragon master",
                     "merkmale": "cape yellow green dragon",
                     "farben": "red, blue", "art": "knight",
                     "img_url": "u", "jahr": 1993, "updated_at": 500}],
         "stand": 500, "mehr": False}])

    erg = main._katalog_vom_hub()
    assert erg["geholt"] == 1
    with core.db() as conn:
        r = conn.execute("SELECT name, merkmale, updated_at FROM "
                         "katalog_index WHERE item_no='cas001'").fetchone()
    assert r["name"] == "Dragon Master"
    assert r["merkmale"] == "cape yellow green dragon"
    assert int(core.get_setting("katalog_hub_geholt")) == 500


def test_ohne_hub_token_passiert_nichts(abzug, monkeypatch):
    gefragt = _hub_antwort(monkeypatch, [{"zeilen": [], "stand": 0,
                                          "mehr": False}])
    assert main._katalog_vom_hub()["geholt"] == 0
    assert gefragt == []


def test_mehrere_seiten_werden_durchgeblaettert(abzug, monkeypatch):
    core.set_setting("crash_token", "berichts-token")
    _hub_antwort(monkeypatch, [
        {"zeilen": [{"item_no": "a001", "updated_at": 10}],
         "stand": 10, "mehr": True},
        {"zeilen": [{"item_no": "a002", "updated_at": 20}],
         "stand": 20, "mehr": True},
        {"zeilen": [], "stand": 20, "mehr": False}])

    assert main._katalog_vom_hub()["geholt"] == 2
    assert int(core.get_setting("katalog_hub_geholt")) == 20


def test_ein_hub_der_immer_mehr_meldet_dreht_nicht_ewig(abzug, monkeypatch):
    """Sonst hinge der Zwölfstundenlauf für immer in dieser Schleife."""
    core.set_setting("crash_token", "berichts-token")
    gefragt = _hub_antwort(monkeypatch, [
        {"zeilen": [{"item_no": "a001", "updated_at": 10}],
         "stand": 10, "mehr": True}])

    main._katalog_vom_hub()
    assert len(gefragt) == main.KATALOG_HUB_SEITEN
