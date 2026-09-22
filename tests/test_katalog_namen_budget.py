"""Der Namenslauf nimmt sich, was die Preise übriglassen – nicht mehr.

BrickLink lässt 5.000 Abrufe am Tag zu, und daran hängen **beide**: die
Preise, die man täglich braucht, und die Namen des Katalogabzugs, die man
einmal braucht. Bis zum 22.09.2026 stand dort eine feste Zahl (1.500 je
Lauf). Sie stammte aus einer Zeit mit 9.700 Namen; bei inzwischen 19.267
wären das sechseinhalb Tage, in denen eine frische Instanz nur über die
Bildbeschreibungen sucht.

Einfach hochsetzen ging nicht: Am Preis-Deckel ist das Kontingent schon
ausgeschöpft. Nur trifft dieser Deckel genau die Instanzen, die den
Namenslauf längst hinter sich haben – wer gerade installiert hat, hat eine
leere Sammlung. Also wird gerechnet statt gesetzt.
"""
import pytest

import core
import main


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "budget.db"))
    core.init_db()
    return core


def fuellen(anzahl: int):
    with core.db() as conn:
        conn.executemany(
            "INSERT INTO collection (item_type, item_id, name, quantity,"
            " condition, added_at) VALUES (?, ?, ?, ?, ?, ?)",
            [("minifig", "sw%05d" % i, "x", 1, "used", 0)
             for i in range(anzahl)])


def tagesbedarf(namen_je_lauf: int, artikel: int) -> int:
    """Was ein Tag insgesamt an BrickLink-Abrufen kostet."""
    preise = 0
    with core.db() as conn:
        for table in main.PRICE_TABLES:
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            preise += main.preis_stapel(n) * 2 * main.PRICE_LAEUFE_JE_TAG
    return preise + namen_je_lauf * main.PRICE_LAEUFE_JE_TAG


@pytest.mark.parametrize("artikel", [0, 900, 3000, 9000])
def test_das_tagesbudget_wird_nie_ueberschritten(db, artikel):
    """Der eine Fall, der wehtut: ein gesperrter BrickLink-Zugang."""
    fuellen(artikel)
    je_lauf = main.katalog_namen_je_lauf()
    assert tagesbedarf(je_lauf, artikel) <= main.BRICKLINK_TAGESBUDGET, \
        f"bei {artikel} Artikeln reißt der Lauf das Kontingent"


def test_die_leere_sammlung_bekommt_am_meisten(db):
    """Genau dann läuft der Namens-Nachtrag, und genau dann ist Platz."""
    leer = main.katalog_namen_je_lauf()
    fuellen(9000)
    voll = main.katalog_namen_je_lauf()
    assert leer > voll, "eine große Sammlung muss die Namen ausbremsen"
    assert leer >= 1500, "eine neue Instanz darf nicht langsamer sein als vorher"


def test_nie_ganz_verhungern(db):
    """Auch bei riesiger Sammlung müssen Namen weiterlaufen – sonst bliebe
    die Suche auf einer solchen Instanz für immer ohne Namen."""
    fuellen(20000)
    assert main.katalog_namen_je_lauf() >= main.KATALOG_NAMEN_MIN


def test_ohne_datenbank_bescheiden(db, monkeypatch):
    """Wer nicht zählen kann, greift nicht zu."""
    def kaputt():
        raise RuntimeError("keine Datenbank")
    monkeypatch.setattr(core, "db", kaputt)
    assert main.katalog_namen_je_lauf() == main.KATALOG_NAMEN_MIN
