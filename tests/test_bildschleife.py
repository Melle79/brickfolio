"""Warum die Zeichenketten im Bildschema eine Längengrenze haben.

Am 22.08.2026 blieb der Bilderlauf bei `sw0326` stehen – bei jedem Anlauf,
immer nach exakt 120 s. Das Modell hatte weder Ladeprobleme noch zu wenig
Speicher: Es lud in 3,8 s, verarbeitete das Bild in 2,8 s und schrieb dann
15.190 Token am Stück, 436 Sekunden lang. Der Inhalt war eine Endlosschleife
innerhalb einer **einzigen Zeichenkette** – „…and a dark blue stripe on the
upper part of the legs, and a dark blue stripe on the lower part of the
legs, …" – bis die Zeitgrenze zuschlug und die Antwort verworfen wurde.

`maxItems` hielt die Teileliste dabei sauber bei sechs. Arrays begrenzt das
Schema also, die Länge einer Zeichenkette begrenzte es nicht. Bei
`temperature: 0` und `repeat_penalty` 1.0 gibt es aus so einer Schleife
keinen Ausweg – die Grammatik muss sie verhindern.

Nach fünf solchen Figuren gab der ganze Lauf auf; 9.000 blieben liegen.
"""
import json

import pytest

import integrations as ig


def _zeichenketten(knoten, pfad="wurzel"):
    """Jeden string-Knoten des Schemas mit seinem Pfad."""
    if not isinstance(knoten, dict):
        return
    if knoten.get("type") == "string":
        yield pfad, knoten
    for name, unter in (knoten.get("properties") or {}).items():
        yield from _zeichenketten(unter, f"{pfad}.{name}")
    if "items" in knoten:
        yield from _zeichenketten(knoten["items"], f"{pfad}[]")


def test_jede_zeichenkette_ist_begrenzt():
    """Eine einzige unbegrenzte genügt, damit es wieder hängt."""
    offen = [p for p, k in _zeichenketten(ig._BILD_SCHEMA)
             if "maxLength" not in k]
    assert not offen, "ohne Längengrenze: " + ", ".join(offen)


def test_die_bremse_schneidet_keine_gueltige_antwort_ab():
    """`num_predict` ist die Notbremse, nicht die Grenze.

    Sie muss über dem liegen, was eine vollständige Antwort nach diesem
    Schema höchstens braucht – sonst zerschnitte sie gute Ergebnisse, und
    die Figur bliebe als Fehlschlag liegen.
    """
    laengste = sum(k["maxLength"] for _, k in _zeichenketten(ig._BILD_SCHEMA))
    # Sechs Teile und drei Zubehörteile, dazu die JSON-Gerüstzeichen.
    grob = 24 + 6 * (40 + 40 + 100 + 40) + 3 * 40 + 40
    assert laengste > 0
    # Ein Token trägt im Mittel gut drei Zeichen; großzügig mit zwei rechnen.
    assert ig.OLLAMA_BILD_MAX_TOKEN * 2 > grob, (
        "die Notbremse greift schon bei einer regulären Antwort")


def test_die_anfrage_traegt_beides(monkeypatch):
    """Schema und Notbremse müssen auch wirklich mitgeschickt werden."""
    gesehen = {}

    class _Antwort:
        ok = True
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": json.dumps(
                {"kind": "Droid", "parts": []})}}

    def _post(url, json=None, **kw):
        gesehen.update(json or {})
        return _Antwort()

    monkeypatch.setattr(ig.requests, "post", _post)
    monkeypatch.setattr(ig, "ollama_enabled", lambda: True)
    monkeypatch.setattr(ig, "ollama_setting",
                        lambda name: "http://kein-hub" if name == "ollama_url"
                        else "modell")
    monkeypatch.setattr(ig, "ollama_bild_modell", lambda: "modell")

    ig.bild_merkmale(b"nicht-wirklich-ein-bild")
    assert gesehen["format"] is ig._BILD_SCHEMA
    assert gesehen["options"]["num_predict"] == ig.OLLAMA_BILD_MAX_TOKEN
