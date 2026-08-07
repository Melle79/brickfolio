"""Ein zweiter Tab ist kein Absturz.

Aus dem Betrieb, Verlauf vom 06.08.2026:

    23:31:13  5 MB · 975 Elemente · v2.21.3
    23:31:40  1 MB · 971 Elemente · start · OHNE ABSCHIED · nav=navigate
    23:31:43  5 MB · 975 Elemente · v2.21.3
    23:32:10  6 MB · …
    23:32:13  5 MB · …

Nach dem angeblichen Absturz liefen **zwei** Messreihen im Abstand von 30
Sekunden weiter. Da war nichts abgestürzt, da war ein Tab dazugekommen.

Der Grund: Der Abschiedszettel (`bf_weg`) liegt im localStorage, und der
gehört allen Tabs derselben Adresse gemeinsam. Ein frisch geöffneter zweiter
Tab fand darin keinen frischen Abschied – während der erste munter weiterlief
– und trug sich selbst als Absturz ein.

Das ist der schlimmste Fehler, den eine Messung haben kann: Sie erfand die
Ereignisse, die sie erklären sollte. Die Absturzzählung war damit zu hoch,
und die Suche nach der Ursache lief teils auf erfundenen Daten.

Der bisherige Notbehelf – ein Aufruf mehr als 90 Sekunden nach dem letzten
Messwert zählt nicht – griff hier nicht: Es waren 27 Sekunden.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


# ------------------------------------------------- Kennung und Lebenszeichen

def test_die_tabkennung_liegt_im_sessionstorage():
    """sessionStorage gehört genau einem Tab – localStorage allen. Läge die
    Kennung dort, hätten alle Tabs dieselbe und nichts wäre gewonnen."""
    j = js()
    anfang = j.index("function tabKennung")
    stelle = j[anfang:j.index("function tabsLesen", anfang)]
    assert "sessionStorage.getItem(DIAG_TAB_KEY)" in stelle
    assert "sessionStorage.setItem(DIAG_TAB_KEY" in stelle
    assert "localStorage" not in stelle, "die Kennung wäre für alle Tabs gleich"


def test_die_lebenszeichen_liegen_im_localstorage():
    """Umgekehrt: Die Liste der offenen Tabs muss geteilt sein, sonst sieht
    kein Tab die anderen."""
    stelle = js()[js().index("function tabsLesen"):][:300]
    assert "localStorage.getItem(DIAG_TABS_KEY)" in stelle


def test_abgelaufene_lebenszeichen_verschwinden():
    """Ohne Aufräumen gälte ein längst geschlossener Tab ewig als offen – und
    danach wäre nie wieder ein Absturz erkennbar."""
    stelle = js()[js().index("function tabsMelden"):][:600]
    assert "TAB_FRIST" in stelle and "delete alle[id]" in stelle


def test_der_abschied_nimmt_das_lebenszeichen_mit():
    stelle = js()[js().index('addEventListener("pagehide"'):][:600]
    assert "delete alle[tabKennung()]" in stelle, (
        "ein geschlossener Tab gilt noch 90 Sekunden als offen")


# --------------------------------------------------------- Die Reihenfolge

def test_erst_fragen_dann_anmelden():
    """`andererTabLebt` muss **vor** dem eigenen Lebenszeichen laufen – sonst
    findet sich der Tab selbst und hält sich für seinen eigenen Nachbarn."""
    j = js()
    frage = j.index("if (andererTabLebt(punkt.tab)) punkt.mehr = 1;")
    anmeldung = j.index("punkt.tabs = tabsMelden(punkt.tab);")
    assert frage < anmeldung, "der Tab meldet sich an, bevor er fragt"


# ------------------------------------------------------- Kein Absturz mehr

def test_ein_zweiter_tab_gilt_nicht_als_absturz():
    # Nicht die Deklaration oben treffen, sondern die Zuweisung im Startfall.
    stelle = js()[js().index("absturzZuvor = !punkt.sauber"):][:300]
    assert "!punkt.mehr" in stelle, (
        "ein zweiter Tab löst weiterhin die Absturz-Behandlung aus")


def test_die_zaehlung_ueberspringt_den_zweiten_tab():
    j = js()
    stelle = j[j.index("else if (p.sauber) sauber++"):][:900]
    assert re.search(r"else if \(p\.mehr\) continue;", stelle), (
        "der zweite Tab landet weiter in der Absturz-Zählung")
    # Reihenfolge: Die Prüfung muss vor dem `else abbruch++` stehen.
    assert stelle.index("p.mehr") < stelle.index("abbruch++")


def test_der_alte_notbehelf_gilt_nur_noch_fuer_alte_verlaeufe():
    """Verläufe von vor dieser Version haben keine Tab-Kennung. Für sie bleibt
    die 90-Sekunden-Regel – für neue wäre sie nur noch eine zweite,
    ungenauere Meinung."""
    j = js()
    stelle = j[j.index("else if (p.sauber) sauber++"):][:900]
    assert "!p.tab && p.t - vor.t >= 90000" in stelle


# ------------------------------------------------------------ Was man sieht

def test_der_verlauf_benennt_den_zweiten_tab():
    assert '"weiterer Tab"' in js(), (
        "im Verlauf stünde weiter „OHNE ABSCHIED“")


def test_der_verlauf_zeigt_wie_viele_tabs_offen_waren():
    """Teilen sich zwei Tabs den Verlauf, wechseln sich ihre Messwerte ab.
    Ohne diese Zahl sähe das nach wilden Sprüngen bei Speicher und Elementen
    aus – und genau danach hatten wir gesucht."""
    assert 'p.tabs > 1 ? p.tabs + " Tabs offen"' in js()


def test_der_allererste_start_wird_nicht_bewertet():
    """Er hat keinen Vorgänger, über dessen Ende sich etwas sagen ließe. Die
    Zählung überspringt ihn längst, die Anzeige tat es nicht."""
    j = js()
    stelle = j[j.index("ordentlich beendet"):]
    stelle = j[max(0, j.index("ordentlich beendet") - 400):j.index("ordentlich beendet") + 200]
    assert "i > 0 && p.g === \"start\"" in stelle, (
        "der erste Eintrag steht weiter als „OHNE ABSCHIED“ da")
