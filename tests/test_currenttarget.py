"""`currentTarget` überlebt kein `await`.

Am 21.08.2026 kam aus dem Betrieb: „Cannot set properties of null (setting
'disabled')" – aus dem Abbrechen-Knopf der Update-Leiste. Der Handler
schaltet den Knopf ab, wartet auf die Antwort und schaltet ihn wieder ein.
Nur ist `ev.currentTarget` dann **null**: Der Browser räumt es auf, sobald
der Handler das erste Mal zurückkehrt – und das ist beim ersten `await`.

Der Fehler ist tückisch, weil er nur im Fehlerfall auffällt und die Aktion
selbst gelingt. Wer nicht in die Fehlerliste sieht, merkt nichts.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def test_kein_currenttarget_nach_einem_await():
    """Jede Verwendung nach einem `await` im selben Handler ist ein Fehler
    in Wartestellung. Festhalten vor dem ersten `await` kostet eine Zeile."""
    zeilen = js().splitlines()
    schlecht = []
    # Grob, aber wirksam: Innerhalb eines Handlers gilt jedes
    # `ev.currentTarget` nach dem ersten `await` als verdächtig.
    tiefe_await = None
    for i, z in enumerate(zeilen):
        if re.search(r"addEventListener\(.*async", z):
            tiefe_await = None
        if "await " in z:
            tiefe_await = i
        if "ev.currentTarget" in z and tiefe_await is not None:
            # Nur wenn dazwischen kein neuer Handler beginnt
            zwischen = "\n".join(zeilen[tiefe_await:i])
            if "addEventListener" not in zwischen and i - tiefe_await < 30:
                schlecht.append("%d: %s" % (i + 1, z.strip()[:70]))
    assert not schlecht, ("`ev.currentTarget` nach einem `await`:\n"
                          + "\n".join(schlecht))
