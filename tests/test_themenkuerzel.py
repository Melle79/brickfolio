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


def test_fort_ist_fortnite():
    """Der Anlass für den zweiten Durchgang.

    Beim ersten Mal waren nur die 45 größten Gruppen angesehen worden;
    `fort` mit 26 Figuren fiel durch und stand als „FORT" in der Auswahl.
    """
    assert themes.MINIFIG_PREFIXES["fort"] == "Fortnite"
    assert themes.from_minifig_number("fort001") == "Fortnite"


def test_gleichnamige_themen_bleiben_unterscheidbar():
    """Mehrere Kürzel dürfen dasselbe Thema tragen (Belville, Scala,
    Duplo kommen in Varianten vor) – aber die Fernsehserie „Friends"
    und LEGO Friends sind zweierlei."""
    assert themes.MINIFIG_PREFIXES["frnd"] == "Friends"
    assert themes.MINIFIG_PREFIXES["ftv"] == "Friends (Fernsehserie)"
    assert themes.MINIFIG_PREFIXES["avt"] != themes.MINIFIG_PREFIXES["ava"]


def test_die_tabelle_ist_deutlich_gewachsen():
    """Untergrenze, damit ein Rückbau auffällt."""
    assert len(themes.MINIFIG_PREFIXES) >= 200
