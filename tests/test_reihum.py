"""Warum die Treffer reihum aus den Begriffen genommen werden.

Am 22.08.2026 lieferte „goldener Droide" vier Begriffe – `Gold Droid`,
`C-3PO`, `Droid`, `Gold` – und die Suche arbeitete sie nacheinander ab. Der
erste, `Gold Droid`, traf fünf Astromechs mit zufälligen Goldanteilen: einen
goldenen Helmstreifen bei R5-D4, einen goldenen Torso beim ASP Droid. Der
Droide, den jeder meint, stand danach – `C-3PO` auf Platz 6.

Die Sortierung nach Wortzahl bleibt richtig; ohne sie liefe `Minifigure` vor
`Knight` (2.28.1). Sie sagt nur, wer anfängt, nicht, dass er alles bekommt.
"""
import main


def kennung(e):
    return e["id"]


def test_begriffe_kommen_abwechselnd_dran():
    """Der zweite Begriff wartet nicht, bis der erste leer ist."""
    je_begriff = [("A", [{"id": f"a{i}"} for i in range(5)]),
                  ("B", [{"id": f"b{i}"} for i in range(5)])]
    items, treffer = main._reihum(je_begriff, kennung, set())
    assert [e["id"] for e in items[:4]] == ["a0", "a1", "b0", "b1"]
    assert treffer == ["A", "B"]


def test_der_vorfall_c3po_steht_vorn():
    """`C-3PO` darf nicht hinter fünf Astromechs verschwinden."""
    je_begriff = [
        ("Gold Droid", [{"id": n} for n in
                        ("sw0142", "sw0145", "sw0313", "sw0825", "sw0908")]),
        ("C-3PO", [{"id": n} for n in ("sw0010", "sw0158", "sw0161")]),
        ("Droid", [{"id": "sw0028"}]),
    ]
    items, _ = main._reihum(je_begriff, kennung, set())
    platz = [e["id"] for e in items].index("sw0010") + 1
    assert platz <= 3, f"C-3PO steht auf Platz {platz}"


def test_dubletten_zaehlen_nicht_gegen_die_portion():
    """Sonst bekäme ein Begriff mit vielen Dubletten weniger Plätze."""
    je_begriff = [("A", [{"id": "x"}, {"id": "a1"}, {"id": "a2"}]),
                  ("B", [{"id": "b1"}])]
    items, _ = main._reihum(je_begriff, kennung, {"x"})
    assert [e["id"] for e in items] == ["a1", "a2", "b1"]


def test_gesehen_wird_mitgefuehrt():
    """Der Katalogzweig befragt danach Rebrickable und darf nichts doppeln."""
    gesehen = set()
    main._reihum([("A", [{"id": "a1"}])], kennung, gesehen)
    assert "a1" in gesehen


def test_hoechstens_wird_eingehalten():
    je_begriff = [("A", [{"id": f"a{i}"} for i in range(50)]),
                  ("B", [{"id": f"b{i}"} for i in range(50)])]
    items, _ = main._reihum(je_begriff, kennung, set(), hoechstens=7)
    assert len(items) == 7


def test_leere_begriffe_stoeren_nicht():
    items, treffer = main._reihum(
        [("A", []), ("B", [{"id": "b1"}]), ("C", [])], kennung, set())
    assert [e["id"] for e in items] == ["b1"]
    assert treffer == ["B"]
