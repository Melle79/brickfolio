"""Die automatische Sicherung muss verlässlich sein.

Am 30.08.2026 hat Sven eine Sicherung zurückgespielt und dabei einen Tag
Arbeit verloren geglaubt. Drei Fehler kamen zusammen:

1. Die Tagessicherung hing an der Preisschleife, und die schläft zwölf
   Stunden. Der Stand des 30. wäre um 11:35 entstanden – zurückgespielt
   wurde um 10:55.
2. Die Aufräumlogik zählte die Sicherheitskopien mit und löschte
   stattdessen die ältesten Tagesstände.
3. Das Zurückspielen überschrieb den Datenbankaufbau, ohne die
   Migrationen nachzuziehen – danach fehlte eine tags zuvor
   hinzugekommene Tabelle, und ein Endpunkt antwortete mit 500.
"""
import os
import re
import time
from pathlib import Path

import pytest

import core
import main

QUELLE = (Path(__file__).resolve().parents[1] / "backend" / "main.py").read_text()


# ── 1. Der Takt ────────────────────────────────────────────────────────

def test_die_sicherung_haengt_nicht_mehr_an_den_preisen():
    """Sonst entsteht der Tagesstand irgendwann zwischen Mitternacht und
    Mittag – je nachdem, wann der Container zuletzt startete."""
    m = re.search(r"def _price_refresher\(\):.*?\n\ndef ", QUELLE, re.S)
    assert m, "_price_refresher nicht gefunden"
    assert "_auto_backup()" not in m.group(0)


def test_ein_eigener_waechter_sieht_oft_genug_nach():
    assert "def _sicherungs_waechter():" in QUELLE
    assert "_sicherungs_waechter, daemon=True" in QUELLE
    # Höchstens stündlich – sonst bleibt wieder ein halber Tag ungeschützt.
    assert main.SICHERUNG_TAKT <= 3600, main.SICHERUNG_TAKT


# ── 2. Die Aufräumlogik ────────────────────────────────────────────────

def _dateien_anlegen(ordner, namen):
    for n in namen:
        (ordner / n).write_bytes(b"x")


def test_eine_sicherheitskopie_kostet_keinen_tagesstand(tmp_path, monkeypatch):
    """Der Fehler, der Svens Historie von 14 auf 12 Tage schrumpfen ließ.

    Alphabetisch steht `brickfolio-manuell-…` hinter `brickfolio-2026-…`
    und galt damit als neueste Datei.
    """
    monkeypatch.setattr(main, "BACKUP_KEEP", 5)
    tage = ["brickfolio-2026-08-%02d.db" % t for t in range(20, 26)]  # 6 Tage
    kopien = ["brickfolio-manuell-20260830-105508.db",
              "brickfolio-manuell-20260830-113000.db"]
    _dateien_anlegen(tmp_path, tage + kopien)

    main._sicherungen_aufraeumen(str(tmp_path))
    da = {p.name for p in tmp_path.iterdir()}

    # Sechs Tage, behalten werden fünf – der älteste fällt weg.
    assert "brickfolio-2026-08-20.db" not in da
    assert set(tage[1:]) <= da, "es darf nur genau einer fehlen"
    # Und die Kopien bleiben unangetastet.
    assert set(kopien) <= da


def test_auch_die_kopien_wachsen_nicht_unbegrenzt(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "BACKUP_KEEP", 2)
    kopien = ["brickfolio-manuell-2026083%d-105508.db" % i for i in range(4)]
    _dateien_anlegen(tmp_path, kopien)
    main._sicherungen_aufraeumen(str(tmp_path))
    da = {p.name for p in tmp_path.iterdir()}
    assert len(da) == 2 and set(kopien[2:]) == da


def test_fremde_dateien_werden_nicht_angefasst(tmp_path, monkeypatch):
    """Wer selbst etwas dort ablegt, soll es wiederfinden."""
    monkeypatch.setattr(main, "BACKUP_KEEP", 1)
    _dateien_anlegen(tmp_path, ["brickfolio-2026-08-20.db",
                                "brickfolio-2026-08-21.db",
                                "vor-dem-umzug.db"])
    main._sicherungen_aufraeumen(str(tmp_path))
    assert (tmp_path / "vor-dem-umzug.db").exists()


def test_abgeschaltet_heisst_nichts_loeschen(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "BACKUP_KEEP", 0)
    namen = ["brickfolio-2026-08-%02d.db" % t for t in range(20, 26)]
    _dateien_anlegen(tmp_path, namen)
    main._sicherungen_aufraeumen(str(tmp_path))
    assert {p.name for p in tmp_path.iterdir()} == set(namen)


# ── 3. Migrationen nach dem Zurückspielen ──────────────────────────────

def test_zurueckspielen_zieht_die_migrationen_nach():
    """`backup()` überschreibt den Aufbau mit – ein alter Stand bringt den
    alten Aufbau mit, und eine neue Tabelle fehlt danach."""
    m = re.search(r"def backup_restore_file\(.*?\n    return \{\"ok\": True",
                  QUELLE, re.S)
    assert m, "backup_restore_file nicht gefunden"
    rumpf = m.group(0)
    assert "core.init_db()" in rumpf
    # **Nach** dem Einspielen, nicht davor.
    assert rumpf.index("snap.backup(live)") < rumpf.index("core.init_db()")
