"""Warum der Katalogabzug über den Change Log nachgeführt wird.

Der Abzug entsteht, indem Nummern der Reihe nach abgeklappert werden: sw0001,
sw0002, … Danach steht der Zeiger hinter der höchsten gefundenen Nummer, und
alles darunter gilt als erledigt. Neue Figuren werden so gefunden – eine
Umbenennung nie.

Naheliegend wäre, die bekannten Nummern reihum neu abzufragen. Das wären
9.741 Abrufe, gut zweieinhalb Stunden, und das BrickLink-Kontingent teilt
sich der Lauf mit den Preisen. Der Change Log leistet dasselbe für eine
Handvoll HTML-Seiten und ohne Kontingent: Im August 2026 waren es 12
umbenannte Minifiguren im ganzen Monat.

Gelöschte Figuren sind kein Fall: Die Aktion „Item Marked for Deletion"
hatte von Juni bis August 2026 keinen einzigen Eintrag. BrickLink löscht
nicht, es legt zusammen oder nummeriert um.
"""
import pytest

import core
import integrations
import main


@pytest.fixture
def abzug(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "log.db"))
    core.init_db()
    with core.db() as conn:
        for nr, name in (("sw1439", "Babu Frik"),
                         ("dp109", "Prince Eric"),
                         ("sw0002", "Boba Fett - Classic Grays"),
                         ("sw9999", "Ziel der Zusammenlegung")):
            conn.execute(
                "INSERT INTO katalog_index (item_no, item_type, name, such, "
                "img_url, merkmale, updated_at) VALUES (?, 'minifig', ?, ?, "
                "'', 'head red', 0)", (nr, name, nr))
    core.set_setting("katalog_log_stand", "2026-8")
    return True


def namen(**paare):
    return lambda j, m, **kw: paare if (j, m) == (2026, 8) else {}


def nummern(**paare):
    return lambda j, m, **kw: {
        a: {"new_id": b, "item_type": "minifig", "kind": "renumbered"}
        for a, b in paare.items()} if (j, m) == (2026, 8) else {}


def test_umbenennung_kommt_an(abzug, monkeypatch):
    """Der eigentliche Zweck: „Babu Frik" heißt jetzt anders."""
    monkeypatch.setattr(integrations, "catalog_name_changes",
                        namen(sw1439="Babu Frik (6538158)"))
    monkeypatch.setattr(integrations, "catalog_number_changes", nummern())
    erg = main._katalog_changelog()
    with core.db() as conn:
        r = conn.execute("SELECT name, such FROM katalog_index WHERE "
                         "item_no = 'sw1439'").fetchone()
    assert r["name"] == "Babu Frik (6538158)"
    assert "6538158" in r["such"], "der Suchtext wurde nicht mitgezogen"
    assert erg["umbenannt"] >= 1


def test_gleicher_name_wird_nicht_angefasst(abzug, monkeypatch):
    """Sonst zählte jeder Lauf dieselbe Änderung erneut."""
    monkeypatch.setattr(integrations, "catalog_name_changes",
                        namen(dp109="Prince Eric"))
    monkeypatch.setattr(integrations, "catalog_number_changes", nummern())
    assert main._katalog_changelog()["umbenannt"] == 0


def test_neue_nummer_wird_uebernommen(abzug, monkeypatch):
    monkeypatch.setattr(integrations, "catalog_name_changes", namen())
    monkeypatch.setattr(integrations, "catalog_number_changes",
                        nummern(sw0002="sw0002a"))
    main._katalog_changelog()
    with core.db() as conn:
        alt = conn.execute("SELECT 1 FROM katalog_index WHERE "
                           "item_no = 'sw0002'").fetchone()
        neu = conn.execute("SELECT merkmale FROM katalog_index WHERE "
                           "item_no = 'sw0002a'").fetchone()
    assert alt is None and neu is not None
    assert neu["merkmale"] == "head red", "die Bildanalyse ging verloren"


def test_zusammenlegung_erzeugt_keine_dublette(abzug, monkeypatch):
    """Gibt es die Zielnummer schon, liefe ein UPDATE in den Schlüssel."""
    monkeypatch.setattr(integrations, "catalog_name_changes", namen())
    monkeypatch.setattr(integrations, "catalog_number_changes",
                        nummern(sw0002="sw9999"))
    main._katalog_changelog()
    with core.db() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM katalog_index WHERE "
                         "item_no = 'sw9999'").fetchone()["n"]
        alt = conn.execute("SELECT 1 FROM katalog_index WHERE "
                           "item_no = 'sw0002'").fetchone()
    assert n == 1 and alt is None


def test_der_stand_wird_vermerkt(abzug, monkeypatch):
    """Sonst liefe jeder Abgleich wieder über alle Monate."""
    monkeypatch.setattr(integrations, "catalog_name_changes", namen())
    monkeypatch.setattr(integrations, "catalog_number_changes", nummern())
    main._katalog_changelog()
    assert core.get_setting("katalog_log_stand")
