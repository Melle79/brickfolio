"""Jede Preiszeile im Steckbrief trägt die Fahne ihres Gebiets.

Seit 2.90.12 (gewünscht am 26.09.2026): Bisher stand sie nur, wenn der Preis
aus einem größeren Gebiet kam. Neben einer EU-Fahne stand dann eine Zeile
ohne jede Angabe, und man konnte nicht sehen, dass sie aus Deutschland kam.
Der Test führt die Funktion aus app.js in Node aus.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


def _laufen(faelle):
    q = APP.read_text(encoding="utf-8")
    teile = [re.search(r"const REGION_FLAG = .*?;\n", q, re.S).group(0),
             re.search(r"const REGION_NAME = .*?;\n", q, re.S).group(0),
             re.search(r"function scopeFlag\(scope\) \{.*?\n\}\n", q, re.S).group(0),
             re.search(r"function scopeFlagHtml\(d\) \{.*?\n\}\n", q, re.S).group(0)]
    js = ("const tr = (t, p) => t.replace(/\\{(\\w+)\\}/g, (_, k) => p[k]);"
          "const esc = (t) => String(t);" + "".join(teile)
          + f"console.log(JSON.stringify({json.dumps(faelle)}.map(scopeFlagHtml)));")
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True,
                                     text=True, check=True).stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="Node fehlt")
def test_flagge_auch_ohne_ausweichen():
    de, eu, alt = _laufen([
        {"used_scope": "DE", "fell_back": False},
        {"used_scope": "europe", "fell_back": True},
        {"avg": "1.0"},                     # ältere Daten ohne Gebiet
    ])
    assert "🇩🇪" in de and 'title="Preis aus Deutschland"' in de
    assert "🇪🇺" in eu and "im eingestellten Gebiet gab es nichts" in eu
    assert alt == ""
