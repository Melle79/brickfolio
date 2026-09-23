"""Der Update-Kasten bricht nicht mitten durchs Verb.

`text-wrap: balance` teilt eine kurze, mittige Textstelle auf gleich lange
Zeilen auf. Das ist meistens richtig – hier war es falsch: Es entstand

    Die App startet gleich
    neu – bitte kurz warten.

„startet … neu" ist ein trennbares Verb; getrennt liest sich die zweite
Zeile wie ein neuer Satz. `balance` kennt keine Grammatik, es zählt. Wo
eine Stelle nicht brechen darf, muss es in der Vorlage stehen – als
geschütztes Leerzeichen.

Zwei Stellen sind es: vor „neu" und vor dem Gedankenstrich. Nur die erste
zu schützen ergab

    Die App startet gleich neu
    – bitte kurz warten.

und mit einem Gedankenstrich fängt keine Zeile an.

Die Übersetzung findet den Satz trotzdem: `\\s` in JavaScript deckt auch
U+00A0 ab, und die Oberfläche schlägt im zweiten Anlauf mit
`kern.replace(/\\s+/g, " ")` nach. Der englische Schlüssel bleibt also
unverändert – genau das prüft der letzte Test hier, denn ein umbenannter
Schlüssel fiele stillschweigend ins Deutsche zurück.
"""
import io
import json
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1] / "frontend"
SATZ = "Die App startet gleich neu – bitte kurz warten."


def _lies(name: str) -> str:
    return io.open(WURZEL / name, encoding="utf-8").read()


def test_gleich_und_neu_haengen_zusammen():
    html = _lies("index.html")
    assert "Die App startet gleich&nbsp;neu&nbsp;– bitte" in html
    assert "Die App startet gleich neu –" not in html, (
        "Ein gewöhnliches Leerzeichen lässt `balance` wieder dort brechen.")


def test_auch_der_spaete_hinweis_haelt_zusammen():
    """Nach 20 Sekunden schreibt app.js den Satz mit Sekundenzähler neu.

    Ohne denselben Handgriff sprang der Umbruch genau dann zurück, wenn man
    am längsten hinschaut.
    """
    js = _lies("app.js")
    assert 'replace("gleich neu – ", "gleich\\u00A0neu\\u00A0– ")' in js


def test_der_englische_schluessel_bleibt_wie_er_ist():
    woerter = json.loads(_lies("i18n/en.json"))
    assert SATZ in woerter, (
        "Der Schlüssel ist der deutsche Satz mit gewöhnlichem Leerzeichen –"
        " die Oberfläche vereinheitlicht die Leerzeichen vor dem Nachschlagen.")
