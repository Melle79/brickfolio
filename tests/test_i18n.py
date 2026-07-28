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
    """Sichtbarer Text plus die Attribute, die ebenfalls Text tragen –
    placeholder und Co. sind genauso übersetzbar wie ein Absatz."""
    roh = INDEX.read_text()
    roh = re.sub(r"<script\b.*?</script>", " ", roh, flags=re.S)
    attribute = re.findall(
        r'(?:placeholder|title|aria-label|alt)="([^"]*)"', roh)
    return nur_text(roh) + "   " + "   ".join(
        nur_text(a) for a in attribute)


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
    blind = [k for k in json.loads(pfad.read_text())
             if nur_text(k) and nur_text(k) not in seitentext]
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
