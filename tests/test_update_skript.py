"""`update.sh` muss docker finden – und vorher abbrechen, wenn nicht.

Aus dem Betrieb, beim Aktualisieren von vier Instanzen auf der Synology:

    Datenbank-Schnappschuss angelegt (die letzten 3 werden aufbewahrt).
    Hole aktuellen Stand von GitHub …
    Baue und starte den Container …
    update.sh: line 30: docker: command not found

`sudo` bringt einen eigenen, kurzen PATH mit (secure_path); auf Synology
liegt docker unter /usr/local/bin und fällt da heraus. Das Skript lief also
bis zum letzten Schritt durch, **tauschte den Quellstand auf der Platte aus**
und scheiterte erst dann. Zurück blieb der schlechteste Zustand: auf der
Platte der neue Stand, im Betrieb der alte Container – und die Ausgabe sah
bis zur letzten Zeile nach Erfolg aus.

Über den Aufgabenplaner fiel das nie auf, weil der einen längeren PATH
mitbringt. Nur der in der App gezeigte Weg von Hand (`sudo bash update.sh`)
war betroffen.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]


def skript() -> str:
    return (WURZEL / "update.sh").read_text(encoding="utf-8")


def test_der_pfad_wird_um_die_ueblichen_orte_ergaenzt():
    t = skript()
    assert "/usr/local/bin" in t, (
        "ohne /usr/local/bin findet das Skript docker auf Synology nicht")
    assert "export PATH" in t, "der ergänzte Pfad wird nicht weitergegeben"


def test_es_bricht_ab_wenn_docker_fehlt():
    assert re.search(r"command -v docker", skript()), (
        "das Skript prüft nicht, ob docker überhaupt da ist")


def test_die_pruefung_kommt_vor_dem_ersten_schreiben():
    """Der eigentliche Schaden war die Reihenfolge. Ein Abbruch **vor** dem
    Schnappschuss und dem Austausch lässt die Instanz unverändert zurück."""
    t = skript()
    pruefung = t.index("command -v docker")
    for wo, was in ((t.index("pre-update-"), "Datenbank-Schnappschuss"),
                    (t.index("tar xz"), "Austausch des Quellstands")):
        assert pruefung < wo, (
            f"die docker-Prüfung steht hinter dem {was} – bricht sie ab, "
            f"ist die Instanz schon halb verändert")


def test_die_meldung_sagt_dass_nichts_veraendert_wurde():
    """Wer die Fehlermeldung liest, muss wissen, ob er aufräumen muss."""
    t = skript()
    stelle = t[t.index("command -v docker"):][:400]
    assert "noch nichts verändert" in stelle, (
        "die Meldung lässt offen, in welchem Zustand die Instanz ist")


def test_beide_betriebsarten_kommen_nach_der_pruefung():
    """Sowohl `docker compose pull` als auch `--build` brauchen docker."""
    t = skript()
    pruefung = t.index("command -v docker")
    for treffer in re.finditer(r"^\s*docker compose", t, re.M):
        assert treffer.start() > pruefung, (
            "ein docker-Aufruf steht vor der Prüfung")
