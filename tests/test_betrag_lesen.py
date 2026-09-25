"""`betragLesen`: Ein leeres Feld ist keine Angabe, nicht 0 €.

Am 25.09.2026 gefunden: `Number("")` ergibt 0, und ein leer gelassenes
„Bezahlt (optional)“ landete beim Übernehmen eines Tauschs als 0 € im
Kaufbuch. Der Test führt die Funktion aus app.js in Node aus.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "frontend" / "app.js"


@pytest.mark.skipif(not shutil.which("node"), reason="Node fehlt")
def test_betrag_lesen():
    q = APP.read_text(encoding="utf-8")
    fn = re.search(r"function betragLesen\(text\) \{.*?\n\}\n", q, re.S).group(0)
    fälle = ["", "   ", None, "0", "12", "12,5", "3.99", "-1", "abc"]
    js = fn + f"console.log(JSON.stringify({json.dumps(fälle)}.map(betragLesen)));"
    aus = subprocess.run(["node", "-e", js], capture_output=True, text=True,
                         check=True).stdout
    assert json.loads(aus) == [None, None, None, 0, 12, 12.5, 3.99, None, None]
