"""Der Sprung zu einem Set und das Wettrennen dahinter.

Am 08.09.2026 gemeldet: Ein Klick auf ein Set in „Fehlende Set-Figuren"
wechselt in die Sammlung und trägt die Setnummer ins Suchfeld – das Set
erscheint kurz und weicht dann wieder der **vollständigen** Sammlung.

Zwei Ursachen, beide hier geprüft:

- `showTab("collection")` stößt selbst einen Ladevorgang an. `jumpToSet`
  setzte das Suchfeld erst **danach**, also lief ein zweiter mit leerer
  Abfrage.
- `loadCollection` hatte keine Sperre gegen überholte Antworten: Es gewann
  schlicht die, die zuletzt eintraf – auch die ältere.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP_JS = Path(__file__).resolve().parents[1] / "frontend" / "app.js"

ohne_node = pytest.mark.skipif(
    not shutil.which("node"),
    reason="node fehlt – die Probe läse sonst nur Text")


def _stueck(name):
    m = re.search(r"^(async )?function %s\([^)]*\) \{.*?\n\}$" % name,
                  APP_JS.read_text(), re.S | re.M)
    assert m, name
    return m.group(0)


# Eine Werkbank: nur so viel Umgebung, dass `loadCollection` läuft. Die
# Antwortzeit je Abfrage ist einstellbar – damit lässt sich erzwingen, dass
# die **ältere** Antwort zuletzt eintrifft.
HARNISCH = """
const felder = { search: "", sort: "", "type-filter": "" };
const gezeigt = [];
let verzoegerung = {};
const $ = (id) => ({
  get value() { return felder[id] ?? ""; },
  set value(v) { felder[id] = v; },
  set textContent(v) {}, get textContent() { return ""; },
  set innerHTML(v) {}, setAttribute() {}, removeAttribute() {},
  set hidden(v) {},
});
const state = { collection: [] };
const tr = (s) => s;
const toast = () => {};
const fmtEur = (v) => String(v);
const brickLoading = () => "";
const requestAnimationFrame = (f) => setTimeout(f, 0);
async function api(pfad) {
  const q = decodeURIComponent((pfad.match(/q=([^&]*)/) || [, ""])[1]);
  await new Promise((r) => setTimeout(r, verzoegerung[q] ?? 0));
  return { items: [{ q }], stats: {} };
}
function renderCollection() { gezeigt.push(state.collection[0].q); }
"""


def _lauf(skript):
    quelle = HARNISCH + _stueck("loadCollection")
    # Die Laufnummer steht vor der Funktion und gehört dazu.
    quelle = "let sammlungLauf = 0;\n" + quelle
    return json.loads(subprocess.run(
        ["node", "-e", quelle + skript],
        capture_output=True, text=True, check=True).stdout)


@ohne_node
def test_die_aeltere_antwort_ueberschreibt_die_neuere_nicht():
    """Der gemeldete Fehler in Reinform: Ein Lauf mit leerer Abfrage startet
    zuerst, antwortet aber langsam. Ohne Sperre stünde am Ende die
    vollständige Sammlung da, obwohl längst nach dem Set gesucht wurde."""
    aus = _lauf("""
      verzoegerung = { "": 40, "75021-1": 5 };
      (async () => {
        const alt = loadCollection(true);      // leere Abfrage, langsam
        felder.search = "75021-1";
        const neu = loadCollection();          // Setnummer, schnell
        await Promise.all([alt, neu]);
        console.log(JSON.stringify({ zuletzt: gezeigt[gezeigt.length - 1],
                                     alle: gezeigt }));
      })();
    """)
    assert aus["zuletzt"] == "75021-1", (
        "die vollständige Sammlung hat den Treffer überschrieben: %s"
        % aus["alle"])


@ohne_node
def test_der_juengste_lauf_zeigt_immer_an():
    """Auch andersherum: Kommt die neuere Antwort zuerst, darf die ältere
    nicht hinterherlaufen und sie ersetzen."""
    aus = _lauf("""
      verzoegerung = { "": 5, "abc": 30 };
      (async () => {
        const alt = loadCollection(true);
        felder.search = "abc";
        const neu = loadCollection();
        await Promise.all([alt, neu]);
        console.log(JSON.stringify({ zuletzt: gezeigt[gezeigt.length - 1] }));
      })();
    """)
    assert aus["zuletzt"] == "abc"


def test_der_sprung_setzt_erst_die_felder():
    """`showTab` lädt selbst. Steht das Suchfeld dann noch leer, entsteht
    der zweite Lauf überhaupt erst – die Reihenfolge ist die eigentliche
    Behebung, die Sperre nur das Netz darunter."""
    f = _stueck("jumpToSet")
    kopf = f[:f.index("showTab(")]
    assert '$("search").value = setNo' in kopf, \
        "das Suchfeld wird erst nach dem Tabwechsel gesetzt"
    assert "await showTab(" in f, "auf den Ladevorgang wird nicht gewartet"
    assert "await loadCollection()" not in f, "es wird zweimal geladen"


def test_showtab_gibt_den_ladevorgang_heraus():
    """Sonst könnte niemand darauf warten."""
    f = _stueck("showTab")
    assert "geladen = loadCollection(true)" in f
    assert "return geladen;" in f
