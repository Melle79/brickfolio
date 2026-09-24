"""Zoom in der Kamera – und das, was vorher unbemerkt schieflag.

**Der Sucher zeigt weniger, als die Kamera liefert.** Das Video steht auf
`object-fit: cover`. Ein 1920×1080-Bild in einem hochkanten Telefonfenster
(375×812) zeigt davon 499 Pixel Breite – **26 %**. Nachgemessen am
24.09.2026 mit einem Canvas als Ersatzkamera; die Rechnung steht in
`test_der_sichtbare_ausschnitt_ist_klein`.

Bis 2.88.22 nahm `kameraAusloesen` trotzdem das ganze Sensorbild auf, mit
der Begründung, sonst fehle der Rand, an dem die Figur oft steht. Der
Gedanke stimmt, die Größenordnung nicht: 74 % sind kein Rand. Wer im Sucher
einrahmte, bekam die Figur auf ein Viertel der Breite geschrumpft – und
Brickognize rechnet jedes Bild auf 1024 Pixel herunter, also kam dort ein
Viertel an. Genau das fühlte sich an wie „der Zoom fehlt".

Darum zwei Dinge: aufnehmen, was der Sucher zeigt (plus ein Fünftel
Sicherheitsrand), und ein Zoom darüber.
"""
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def js() -> str:
    return (FRONTEND / "app.js").read_text(encoding="utf-8")


def css() -> str:
    return (FRONTEND / "style.css").read_text(encoding="utf-8")


def html() -> str:
    return (FRONTEND / "index.html").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    m = re.search(r"(?:async )?function %s\([^)]*\) \{.*?\n\}\n" % name,
                  js(), re.S)
    assert m, "%s nicht gefunden" % name
    return m.group(0)


# ---------------------------------------------------- der Ausschnitt

def test_der_sichtbare_ausschnitt_ist_klein():
    """Die Rechnung hinter dem Befund, als ausführbare Fassung.

    `object-fit: cover` deckt den Rahmen vollständig ab und schneidet den
    Überstand weg. Bei einem hochkanten Fenster über einem querformatigen
    Sensor fällt das an der Breite an – und zwar drastisch.
    """
    vw, vh = 1920, 1080          # was die Kamera liefert
    cw, ch = 375, 812            # ein Telefonfenster
    deckung = max(cw / vw, ch / vh)
    sichtbar = cw / deckung
    assert round(sichtbar) == 499
    assert round(sichtbar / vw * 100) == 26


def test_aufgenommen_wird_der_sucher_nicht_das_ganze_bild():
    f = _fn("kameraAusloesen")
    assert "kameraAusschnitt(" in f
    assert "a.sx, a.sy, a.sw, a.sh" in f, "ohne Quellrechteck kein Ausschnitt"
    assert "drawImage(video, 0, 0)" not in f, (
        "das wäre wieder das ganze Sensorbild")


def test_der_ausschnitt_rechnet_cover_nach():
    f = _fn("kameraAusschnitt")
    assert "Math.max(cw / vw, ch / vh)" in f, (
        "`cover` skaliert auf die *größere* der beiden Achsen")
    assert "(vw - sw) / 2" in f and "(vh - sh) / 2" in f, "mittig"


def test_ein_sicherheitsrand_bleibt():
    """Der alte Einwand – die Figur steht oft am Rand – bleibt gültig,
    nur nicht mehr als Freibrief für das ganze Bild."""
    assert re.search(r"const KAMERA_RAND = 1\.2;", js())
    assert "KAMERA_RAND" in _fn("kameraAusschnitt")


def test_der_ausschnitt_bleibt_im_bild():
    """Rand mal Zoom darf nicht über den Sensor hinauslaufen."""
    f = _fn("kameraAusschnitt")
    assert "Math.min(vw," in f and "Math.min(vh," in f


def test_beim_geraetezoom_wird_nicht_zweimal_verkleinert():
    """Der Sensor hat dann schon gezoomt – ein zweiter Schnitt wäre doppelt."""
    assert "kameraNativ ? 1 : kameraZoom" in _fn("kameraAusloesen")


# ---------------------------------------------------- der Zoom selbst

def test_geraetezoom_vor_digitalzoom():
    f = _fn("kameraZoomSetzen")
    assert "applyConstraints" in f and "zoom:" in f
    assert "scale(${kameraZoom})" in f, "sonst gäbe es keinen Rückfall"


def test_die_einheit_wird_nicht_geraten():
    """**Nicht jedes Gerät zählt gleich.** Manche geben den Zoom als Faktor
    (min 1), andere in Prozent (min 100). Ein festes `zoom: 2` wäre auf dem
    zweiten Gerät ein Herauszoomen auf 2 %."""
    f = _fn("kameraZoomSetzen")
    assert "kameraNativ.basis * kameraZoom" in f
    assert "Math.min(kameraNativ.max," in f


def test_bezugspunkt_ist_die_ansicht_beim_oeffnen():
    """**Der kleinste Zoomwert ist nicht die Ausgangslage.**

    Ein iPhone bietet die Rueckseite als *eine* Kamera an, die intern
    zwischen Ultraweitwinkel, Weitwinkel und Tele umschaltet – am
    24.09.2026 im Bildschirmfoto belegt: „Rückseitige Triple-Kamera".
    Deren kleinster Zoomwert gehoert zum Ultraweitwinkel, die Ansicht beim
    Oeffnen liegt darueber. Gegen `min` gerechnet haette „1×" also
    **heraus**gezoomt – ein weiteres Bild als das, was man gerade sieht.
    """
    f = _fn("kameraZoomPruefen")
    assert "getSettings().zoom" in f
    assert "kameraNativ = { basis," in f
    assert "kameraNativ = { min:" not in f


def test_ohne_gemeldeten_wert_bleibt_der_kleinste():
    f = _fn("kameraZoomPruefen")
    assert "jetzt : f.min" in f


def test_keine_stufen_wenn_die_ausgangslage_schon_das_ende_ist():
    """Steht die Kamera beim Oeffnen bereits am Anschlag, gibt es nichts
    zu zoomen – eine Leiste, die nichts bewirkt, ist schlimmer als keine."""
    assert "if (f.max > basis)" in _fn("kameraZoomPruefen")


def test_digitalzoom_faellt_zurueck_wenn_das_stellen_scheitert():
    """Die Fähigkeit gemeldet zu bekommen heißt nicht, sie stellen zu können."""
    f = _fn("kameraZoomSetzen")
    assert "kameraNativ = null;" in f


def test_keine_leiste_mit_nur_einer_stufe():
    f = _fn("kameraZoomPruefen")
    assert "stufen.length < 2" in f


def test_die_stufen_bleiben_im_bereich_des_geraets():
    """Und zwar gemessen an der Ausgangslage, nicht am kleinsten Wert –
    sonst zaehlte die Strecke mit, die unterhalb der Ansicht liegt."""
    f = _fn("kameraZoomStufen")
    assert "kameraNativ.max / kameraNativ.basis" in f


def test_kneifen_zoomt_das_bild_nicht_die_seite():
    assert "pointerdown" in js() and "kameraZeigerAn" in js()
    assert re.search(r"\.kamera \{[^}]*touch-action: none", css(), re.S), (
        "ohne das zoomt die Geste die Seite")


def test_das_gezoomte_bild_wird_abgeschnitten():
    assert re.search(r"\.kamera \{[^}]*overflow: hidden", css(), re.S)


def test_die_leiste_steht_in_der_vorlage():
    assert 'id="kamera-zoom"' in html()


# ---------------------------------------------------- die Rückfrage

def test_der_strom_endet_nicht_sofort():
    """**iOS merkt sich die Freigabe je App-Start nicht** (WebKit 215884).
    Einmal fragen lässt sich nicht vermeiden – mehrfach schon: Solange der
    Strom läuft, gibt es kein zweites `getUserMedia`."""
    f = _fn("kameraSchliessen")
    assert "kameraStromBeenden" in f and "setTimeout" in f
    assert "getTracks().forEach" not in f, (
        "sofortiges Beenden war genau das Problem")


def test_ein_laufender_strom_wird_wiederverwendet():
    f = _fn("kameraOeffnen")
    assert "if (!kameraLebt())" in f, (
        "ohne die Prüfung fragt iOS bei jedem Foto neu")


def test_ein_toter_strom_wird_nicht_wiederverwendet():
    """`kameraStrom` kann stehen, während die Spur längst beendet ist –
    etwa wenn das Gerät die Kamera anderweitig braucht."""
    assert 'spur.readyState === "live"' in _fn("kameraLebt")


def test_im_hintergrund_geht_die_kamera_aus():
    """Sonst leuchtet die Anzeige des Geräts weiter, während niemand
    hinsieht – eine halbe Minute Nachlauf ist das eine, minutenlang im
    Hintergrund das andere."""
    assert re.search(r'visibilitychange[^}]*kameraStromBeenden', js(), re.S)


def test_der_nachlauf_ist_kurz():
    m = re.search(r"const KAMERA_NACHLAUF_MS = (\d+);", js())
    assert m and int(m.group(1)) <= 60000, (
        "je länger, desto länger leuchtet die Kameraanzeige")
