"""Die Kürzel-Tabelle muss zu BrickLinks Nummernkreisen passen.

Ein falscher Name fällt nirgends auf: Die Figur landet unter dem falschen
Thema, sieht dort aber genauso aus wie überall sonst. `mar` stand jahrelang
auf „Marvel" – tatsächlich sind `mar001` ff. Boo, Bowser und Bowser Jr.,
also Super Mario. Aufgefallen ist es erst, als die Themenauswahl der
Katalogliste die Namen nebeneinander zeigte.
"""
import themes


def test_mar_ist_super_mario():
    """Der Fall, der den Anlass gab."""
    assert themes.MINIFIG_PREFIXES["mar"] == "Super Mario"
    assert themes.from_minifig_number("mar0023") == "Super Mario"


def test_marvel_laeuft_unter_super_heroes():
    """Damit niemand den alten Namen aus Versehen wieder einträgt."""
    assert "Marvel" not in themes.MINIFIG_PREFIXES.values()
    assert themes.MINIFIG_PREFIXES["sh"] == "Super Heroes"


def test_kuerzel_sind_klein_und_ohne_ziffern():
    """`from_minifig_number` schneidet vor der ersten Ziffer ab – ein
    Kürzel mit Ziffer oder Großbuchstabe würde nie gefunden."""
    for k in themes.MINIFIG_PREFIXES:
        assert k.isalpha() and k.islower(), k


def test_keine_zwei_kuerzel_mit_demselben_zweck_verwechselt():
    """Belville-Frauen und -Männer gehören in dasselbe Thema."""
    assert (themes.MINIFIG_PREFIXES["belvfemale"]
            == themes.MINIFIG_PREFIXES["belvmale"] == "Belville")


def test_das_laengste_kuerzel_gewinnt():
    """`sh` und `shg` beginnen gleich – `shg0004` darf nicht bei den
    Super Heroes landen."""
    assert themes.from_minifig_number("shg0004") == "DC Super Hero Girls"
    assert themes.from_minifig_number("sh0004") == "Super Heroes"
    assert themes.from_minifig_number("col0004") == "Sammelfiguren"
    assert themes.from_minifig_number("colhp0004") == "Sammelfiguren: Harry Potter"


def test_unbekanntes_kuerzel_bleibt_unbenannt():
    """Lieber kein Thema als ein falsches."""
    assert themes.from_minifig_number("bdp0001") is None
