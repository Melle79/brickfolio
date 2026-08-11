"""Was in einer CSP-Meldung landet – und was nicht.

Aus Pauls Instanz kam am 11.08.2026 zweimal „Vom Browser blockiert:
img-src → flat-leaf-5175.cloudflareaccess.com". Kein Defekt: Die Instanz
steht hinter Cloudflare Access, und ist dessen Sitzung abgelaufen,
antwortet Access auf jede Anfrage – hier das Symbol der Web-App – mit einer
Umleitung auf seine Anmeldeseite. Die liegt auf einem anderen Host, und den
erlaubt `img-src` nicht.

Zwei Dinge waren daran unschön: In der Meldung stand die vollständige
Adresse samt einem JWT von rund 1,5 kB, das beim Absenden eines Berichts an
den Hub mitginge und wie ein Zugangsschlüssel aussieht. Und die Meldung las
sich wie ein Programmfehler, obwohl niemand etwas reparieren muss.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def handler() -> str:
    quelle = (FRONTEND / "app.js").read_text(encoding="utf-8")
    anfang = quelle.index('document.addEventListener("securitypolicyviolation"')
    return quelle[anfang:quelle.index("\n  });", anfang)]


def test_der_abfrageteil_wird_abgeschnitten():
    """Sonst steht das Access-JWT wortwörtlich im Fehlerprotokoll."""
    koerper = handler()
    assert "u.origin + u.pathname" in koerper, "Adresse wird nicht gekürzt"
    assert not re.search(r"reportError\([^)]*ev\.blockedURI", koerper), \
        "die ungekürzte Adresse geht weiterhin in die Meldung"


def test_dass_gekuerzt_wurde_bleibt_sichtbar():
    """Eine stillschweigend gekürzte Adresse führt bei der nächsten Suche in
    die Irre – man hielte sie für die vollständige."""
    assert '"?…"' in handler()


def test_die_abgelaufene_anmeldung_wird_benannt():
    """Ohne den Zusatz sucht man den Fehler in der App statt in der
    Sitzung."""
    koerper = handler()
    assert "cdn-cgi" in koerper and "access" in koerper, \
        "die Anmeldeadresse von Access wird nicht erkannt"
    assert "Access-Anmeldung abgelaufen" in koerper


def test_inline_verstoesse_ueberleben_die_kuerzung():
    """`blockedURI` ist bei einem Inline-Verstoß kein URL – `new URL()`
    wirft. Ohne den Auffang bliebe die Meldung ganz aus, und ausgerechnet
    die Inline-Verstöße sind die interessanten."""
    koerper = handler()
    assert "catch" in koerper
    i, j = koerper.index("let ziel"), koerper.index("catch")
    assert i < j, "ziel wird erst im Auffang gesetzt – dann ist es zu spät"
