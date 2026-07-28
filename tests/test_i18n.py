"""Der Übersetzungskatalog muss zur Oberfläche passen.

Der deutsche Text ist der Schlüssel. Ein Schlüssel, den es im Dokument nicht
(mehr) gibt, tut still gar nichts – die Stelle bliebe für immer deutsch, ohne
dass es jemandem auffällt. Genau das prüfen diese Tests.
"""
import html as html_mod
import json
import re
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
INDEX = FRONTEND / "index.html"
KATALOGE = sorted((FRONTEND / "i18n").glob("*.json"))


def nur_text(s: str) -> str:
    """Auszeichnungen und Entities weg, Leerraum vereinheitlichen."""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s).replace(" ", " ")
    return " ".join(s.split())


@pytest.fixture(scope="module")
def seitentext():
    """Alles, worin ein deutscher Satz stehen kann.

    Zwei Quellen: das Dokument (fester Aufbau, samt Attributen wie
    placeholder) und app.js – dort stecken die Texte der Karten und
    Meldungen, die erst zur Laufzeit entstehen.
    """
    roh = INDEX.read_text()
    roh = re.sub(r"<script\b.*?</script>", " ", roh, flags=re.S)
    attribute = re.findall(
        r'(?:placeholder|title|aria-label|alt)="([^"]*)"', roh)
    js = (FRONTEND / "app.js").read_text()
    # Über mehrere Zeilen zusammengesetzte Zeichenketten wieder zusammenfügen
    # ("Teil eins " + "Teil zwei"), sonst fände man den fertigen Satz nie.
    js = re.sub(r'["`]\s*\+\s*["`]', "", js)
    # Maskierte Anführungszeichen entmaskieren: im Quelltext steht \" , im
    # Katalog das nackte " .
    js = js.replace('\\"', '"')
    # JavaScript bleibt roh: Ein Vergleich wie `min < 120` sähe für den
    # Tag-Entferner wie ein angefangenes Element aus und fräße den Text
    # dahinter weg. Zusätzlich eine Fassung mit vereinheitlichtem Leerraum –
    # im Quelltext umbrechen Sätze mitten drin, gerendert stehen sie in einer
    # Zeile.
    # Auch das Backend: Seine Fehlermeldungen erreichen die Oberfläche als
    # deutscher Satz und werden dort über denselben Katalog übersetzt.
    py = "\n".join(p.read_text() for p in
                   sorted((FRONTEND.parent / "backend").glob("*.py")))
    py = re.sub(r'"\s*\n\s*"', "", py)          # umbrochene Zeichenketten
    return "   ".join([nur_text(roh)] + [nur_text(a) for a in attribute]
                      + [js, " ".join(js.split()), py, " ".join(py.split())])


def test_kataloge_vorhanden():
    assert KATALOGE, "Kein Sprachkatalog unter frontend/i18n/"


@pytest.mark.parametrize("pfad", KATALOGE, ids=lambda p: p.stem)
def test_katalog_ist_gueltiges_json(pfad):
    daten = json.loads(pfad.read_text())
    assert isinstance(daten, dict) and daten


@pytest.mark.parametrize("pfad", KATALOGE, ids=lambda p: p.stem)
def test_keine_leeren_uebersetzungen(pfad):
    leer = [k for k, v in json.loads(pfad.read_text()).items() if not str(v).strip()]
    assert not leer, f"Leere Übersetzung für: {leer[:3]}"


@pytest.mark.parametrize("pfad", KATALOGE, ids=lambda p: p.stem)
def test_jeder_schluessel_kommt_in_der_oberflaeche_vor(pfad, seitentext):
    """Sonst zeigt der Eintrag ins Leere und bleibt wirkungslos."""
    # Zwei Schreibweisen sind erlaubt: ohne Auszeichnungen (so steht es im
    # Dokument) oder wortwörtlich (so steht es in app.js).
    blind = [k for k in json.loads(pfad.read_text())
             if nur_text(k)
             and nur_text(k) not in seitentext and k not in seitentext]
    assert not blind, ("Schlüssel ohne Entsprechung in index.html: "
                       + "; ".join(repr(k[:60]) for k in blind[:5]))


@pytest.mark.parametrize("pfad", KATALOGE, ids=lambda p: p.stem)
def test_platzhalter_bleiben_erhalten(pfad):
    """{name} in der Vorlage muss auch in der Übersetzung stehen – sonst
    fehlt im fertigen Satz die eingesetzte Zahl."""
    fehler = []
    for k, v in json.loads(pfad.read_text()).items():
        if set(re.findall(r"\{(\w+)\}", k)) != set(re.findall(r"\{(\w+)\}", v)):
            fehler.append(k)
    assert not fehler, f"Platzhalter stimmen nicht überein: {fehler[:3]}"


@pytest.mark.parametrize("pfad", KATALOGE, ids=lambda p: p.stem)
def test_markup_bleibt_erhalten(pfad):
    """Enthält die Vorlage Auszeichnungen, muss die Übersetzung dieselben
    Element-Namen tragen – sonst zerbricht das Layout."""
    fehler = []
    for k, v in json.loads(pfad.read_text()).items():
        tags = lambda s: sorted(re.findall(r"<(\w+)", s))
        if tags(k) != tags(v):
            fehler.append(k)
    assert not fehler, f"Auszeichnungen weichen ab: {[f[:60] for f in fehler[:3]]}"
