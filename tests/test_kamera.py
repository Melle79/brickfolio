"""Die Kamera in der App – und der Weg, der ohne sie bleibt.

Ein `<input type="file" capture>` reicht nur an das Betriebssystem weiter.
Dort gibt es keinen Weg zur Mediathek; lässt man `capture` weg, kommt erst
eine Auswahlliste und die Kamera kostet einen Tipp mehr. Gewollt war beides
nicht: Antippen soll das Livebild zeigen, und die Mediathek liegt *darin*
daneben.

**Das Entscheidende ist die zweite Spur.** `getUserMedia` gibt es nur im
sicheren Kontext. Über die Cloudflare-Adresse ist das gegeben, im Heimnetz
über `http://` nicht – dort fragt der Browser nicht einmal. Fällt die
Kameraansicht dann nicht sauber auf den Dateidialog zurück, kann man an
einer solchen Instanz gar nichts mehr erfassen. Diese Datei wacht darüber.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def html() -> str:
    return (FRONTEND / "index.html").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    m = re.search(r"(?:async )?function %s\([^)]*\) \{.*?\n\}\n" % name,
                  js(), re.S)
    assert m, "%s nicht gefunden" % name
    return m.group(0)


def test_ohne_schnittstelle_bleibt_der_dateidialog():
    """Kein `getUserMedia` – etwa über `http://` im Heimnetz."""
    f = _fn("kameraOeffnen")
    assert "navigator.mediaDevices" in f
    assert 'typeof navigator.mediaDevices.getUserMedia === "function"' in f
    vor_dem_zugriff = f[:f.index("await navigator.mediaDevices.getUserMedia")]
    assert '$("file-input").click()' in vor_dem_zugriff, \
        "ohne Schnittstelle muss der Dateidialog aufgehen"


def test_auch_eine_abgelehnte_freigabe_faellt_zurueck():
    """Wer „Nicht erlauben" tippt, soll nicht mit nichts dastehen."""
    f = _fn("kameraOeffnen")
    fang = f[f.index("} catch"):]
    assert '$("file-input").click()' in fang
    assert "return" in fang


def test_das_dateifeld_erzwingt_die_kamera_nicht_mehr():
    """Mit `capture` wäre der Weg zur Mediathek wieder zu – und genau der
    ist der Grund für den ganzen Umbau."""
    zeile = re.search(r'<input id="file-input"[^>]*>', html())
    assert zeile, "Dateifeld nicht gefunden"
    assert "capture" not in zeile.group(0)


def test_das_aufgenommene_bild_geht_denselben_weg():
    """Die Kamera ist eine zweite Tür, kein zweiter Ablauf."""
    f = _fn("kameraAusloesen")
    assert "handlePhoto(" in f


def test_gerechnet_wird_in_sensorpixeln():
    """Nicht in der angezeigten Größe – die ist eine CSS-Zahl.

    Der Ausschnitt steht seit 2.88.23 in `kameraAusschnitt`: Er nimmt den
    Teil, den der Sucher zeigt (`object-fit: cover`), plus Sicherheitsrand.
    Bis dahin nahm `kameraAusloesen` das ganze Sensorbild – bei einem
    hochkanten Telefon sind das 74 % Bild, die niemand gesehen hat. Warum
    das die Erkennung kostet, steht in `test_kamera_zoom.py`.
    """
    f = _fn("kameraAusschnitt")
    assert "video.videoWidth" in f and "video.videoHeight" in f


def test_schliessen_haelt_die_kamera_wirklich_an():
    """Ohne `stop()` je Spur läuft sie weiter – die Leuchte am Gerät bleibt
    an, und der Strom geht mit.

    Seit 2.88.23 geschieht das mit Frist statt sofort: iOS fragt sonst bei
    *jedem* Foto neu nach der Freigabe. Beendet wird trotzdem – nur eben in
    `kameraStromBeenden`, und `kameraSchliessen` bestellt es.
    """
    assert "getTracks().forEach((t) => t.stop())" in _fn("kameraStromBeenden")
    f = _fn("kameraSchliessen")
    assert "srcObject = null" in f
    assert "kameraStromBeenden" in f


def test_wer_die_kamera_verlaesst_haelt_sie_sofort_an():
    """Die Frist gilt nur fuer „gleich noch eine Figur".

    Beim Tabwechsel und beim Griff in die Mediathek fotografiert niemand
    mehr – dort leuchtete die Kameraanzeige sonst eine halbe Minute ohne
    Grund weiter. Ersetzt `test_der_ansichtswechsel_schliesst_sie_mit`,
    der dieselbe Stelle prüfte, aber nur auf „überhaupt geschlossen".
    """
    assert "kameraSchliessen(true)" in js()
    m = re.search(r"function showTab\(name\) \{.*?\n\}\n", js(), re.S)
    assert m
    verlassen = m.group(0)[m.group(0).index('if (name !== "scan") {'):]
    assert "kameraSchliessen(true)" in verlassen


def test_das_livebild_laeuft_auf_ios_ueberhaupt():
    """Ohne `playsinline` schaltet iOS auf Vollbild um, ohne `muted` startet
    es gar nicht erst von selbst."""
    m = re.search(r"<video id=\"kamera-bild\"[^>]*>", html())
    assert m, "Videoelement nicht gefunden"
    for pflicht in ("playsinline", "muted", "autoplay"):
        assert pflicht in m.group(0), pflicht


def test_das_licht_erscheint_nur_wo_es_geht():
    """Ein Knopf, der nichts tut, ist schlimmer als keiner – `torch`
    beherrscht längst nicht jedes Gerät."""
    f = _fn("lichtKnopfPruefen")
    assert "getCapabilities" in f and "torch" in f
    assert "knopf.hidden = !kann" in f
