"""Wunschliste und Einkaufsliste in derselben Sprache wie der Scan.

Am 24.09.2026 von Sven nachgezeigt: „Wunschliste und Einkaufsliste
ebenso" – dort standen noch vier gleich große Knöpfe im Raster, zwei
umrandete Zustandsknöpfe (einer gelb), ein grüner ✓-Balken über die volle
Breite und „Liste löschen" über die volle Breite.

Das Muster ist überall dasselbe: eine breite Hauptsache, Löschen und
Abbrechen als rotes Zeichen, die Wege nach draußen als Verweise, eine Wahl
als Pille.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def css() -> str:
    return (FRONTEND / "style.css").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    m = re.search(r"(?:async )?function %s\([^)]*\) \{.*?\n\}\n" % name, js(), re.S)
    assert m, name
    return m.group(0)


# ---------------------------------------------------- Wunschliste

def test_wunschkarte_hat_eine_hauptsache():
    q = js()
    assert '<button class="mini-btn add" data-buy>${esc(tr("✔ Gekauft!"))}</button>' in q
    assert 'class="mini-btn zeichen loesch" data-del' in q
    assert '<button class="mini-btn danger" data-del>Löschen</button>' not in q


def test_wunschkarte_verweise_sind_text():
    q = js()
    start = q.index("data-buy>")
    teil = q[start:start + 1600]
    assert 'class="mini-btn link"' not in teil, "Preisverlauf/BrickLink waren Knöpfe"
    assert "karte-weiter" in teil


def test_gekauft_als_ist_die_zustandszeile():
    q = js()
    assert 'actions.className = "zust-reihe";' in q
    assert 'class="mini-btn zust-abbruch" data-buy-cancel' in q
    assert "`In die Sammlung übernommen ✔ (" not in q, "Zuruf ohne Übersetzung"


# ---------------------------------------------------- Einkaufsliste

def test_einkaufsartikel_zustand_ist_eine_pille():
    f = _fn("listItemRow")
    assert 'class="erf-wahl" role="radiogroup"' in f
    assert "cond-mini" not in f
    assert 'data-ic="used" data-icid=' in f, "der Lauscher hängt an data-ic"


def test_einkaufsartikel_speichern_ist_klein():
    """Der ✓ zum Speichern des Einkaufspreises war ein grüner Balken über die
    volle Breite."""
    f = _fn("listItemRow")
    assert 'class="mini-btn add liste-speichern" data-ip-save=' in f
    assert 'style="flex:1;min-height:38px"' not in f


def test_einkaufsartikel_entfernen_ist_ein_rotes_quadrat():
    f = _fn("listItemRow")
    assert 'class="mini-btn zust-abbruch" data-i-del=' in f


def test_liste_loeschen_ist_ein_rotes_zeichen():
    q = js()
    assert 'class="mini-btn zust-abbruch loesch" data-l-del' in q
    assert '<button class="mini-btn danger" data-l-del>Liste löschen</button>' not in q
    assert ".liste-fuss .zust-abbruch {" in css()


# ---------------------------------------------------- fehlende Set-Figuren

def test_fehlende_figuren_ohne_knopfzeile():
    """Zwei gleich große Knöpfe je Figur und bei gemerkten ein gelbes Schild –
    bei 40 fehlenden Figuren viel Höhe für wenig."""
    q = js()
    i = q.index("data-mf-row=")
    teil = q[i:i + 2600]
    assert "fig-actions" not in teil
    assert 'class="mini-btn link"' not in teil
    assert "badge-wanted" not in teil
    assert 'class="mini-btn mf-stern" data-mf-want=' in teil
    assert 'class="mf-stern an"' in teil
    assert 'class="mf-verweis"' in teil


def test_fehlende_figuren_der_fuss_hat_eine_hauptsache():
    assert 'class="mf-fuss"' in js()
    assert ".mf-fuss .add { flex: 1 1 220px; }" in css()


def test_der_sternknopf_schlaegt_die_grundregel():
    """Der Block steht vor `.mini-btn { flex: 1 }`; einstufig verlor er und
    der Knopf wurde 209 px breit."""
    assert ".mf-zeile .mf-stern {" in css()
    i_stern = css().index(".mf-zeile .mf-stern {")
    assert "flex: none" in css()[i_stern:i_stern + 120]


def test_da_ab_in_die_sammlung_fragt_nicht_doppelt():
    """„warum doppelt?" (24.09.2026) – der Knopf öffnete für Profis eine
    eigene Zeile mit Preisfeld und „✔ Gebraucht übernehmen", obwohl Preis
    und Zustand direkt darüber stehen."""
    q = js()
    assert "data-recv-paid" not in q, "das zweite Preisfeld"
    assert "data-rc-go" not in q, "„… übernehmen\""
    n = q.index('card.querySelectorAll("[data-i-recv]")')
    teil = q[n:q.index('card.querySelectorAll("[data-i-undo]")', n)]
    assert 'row.querySelector("[data-ip]")' in teil, (
        "der Preis kommt aus dem Einkaufsfeld der Zeile")


def test_da_ab_in_die_sammlung_bestaetigt_in_der_zeile():
    """„Bisher verschwindet es einfach ohne Rückmeldung" (25.09.2026): Die
    Zeile bleibt kurz stehen, grün markiert und mit dem Schild aus der
    Wunschliste – erst danach räumt die Liste auf."""
    q = js()
    n = q.index('card.querySelectorAll("[data-i-recv]")')
    teil = q[n:q.index('card.querySelectorAll("[data-i-undo]")', n)]
    assert 'row.classList.add("angekommen")' in teil
    assert 'class="badge badge-owned"' in teil
    # Aufgeräumt wird erst nach der Anzeige, nicht sofort.
    assert teil.index("ANGEKOMMEN_MS") < teil.index("loadLists()")
    assert "Einkaufspreis gemittelt" not in q, "seit 2.88.40 wird addiert"
    assert ".fig-row.angekommen {" in css()


def test_die_echte_rueckfrage_bleibt():
    """Ist der Artikel schon in der Sammlung, muss gefragt werden:
    zusätzlich oder überschreiben. Das ist keine Doppelung."""
    q = js()
    assert 'data-rm="add"' in q and 'data-rm="replace"' in q
    assert 'class="mini-btn zust-abbruch" data-rm-cancel' in q


def test_das_jahr_steht_nur_einmal_im_vorschlag():
    """„sw0815 · 2017 · 2017 · Ø neu …" (25.09.2026): Der eigene Katalog
    gibt das Jahr als `sub` mit, die Nachreichung hängte es noch einmal an."""
    q = js()
    n = q.index("function applySuggestInfo")
    teil = q[n:q.index("let gallery", n)]
    assert "schonDa.includes(String(d.year))" in teil


def test_suchvorschlaege_wie_die_trefferkarte():
    """Die Vorschläge beim manuellen Erfassen hatten vier gleich große
    Knöpfe – jetzt derselbe Aufbau wie die Trefferkarte im Scan."""
    q = js()
    n = q.index("function renderSuggestions")
    teil = q[n:q.index("function erfWahlZeichnen", n)]
    assert 'class="card-actions scan-tasten"' in teil
    assert 'class="mini-btn zeichen" data-want=' in teil
    assert 'class="mini-btn zeichen" data-cart=' in teil
    assert 'class="karte-weiter"' in teil
    assert "BrickLink ↗</a>" not in teil, "BrickLink als Knopf"


def test_gemerkter_artikel_hat_von_vornherein_einen_vollen_stern():
    q = js()
    n = q.index("function applySuggestInfo")
    teil = q[n:q.index("let gallery", n)]
    assert 'card.querySelector(".zeichen[data-want]")' in teil
    assert 'stern.classList.add("an")' in teil
