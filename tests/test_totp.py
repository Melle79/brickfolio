"""TOTP gegen die offiziellen Testvektoren aus RFC 6238.

Selbst gebaute Krypto-Bausteine sind nur so viel wert wie ihr Nachweis.
Die Vektoren stammen aus Anhang B der Norm; stimmen sie, rechnet die
Umsetzung nachweislich so wie jede Authenticator-App.
"""
import base64
import hashlib

import pytest

import totp

# RFC 6238, Anhang B: Schlüssel ist die ASCII-Folge "12345678901234567890"
SEED = base64.b32encode(b"12345678901234567890").decode()

# (Zeitpunkt in Sekunden, erwarteter achtstelliger Code) – SHA-1-Zeile
VEKTOREN = [
    (59,          "94287082"),
    (1111111109,  "07081804"),
    (1111111111,  "14050471"),
    (1234567890,  "89005924"),
    (2000000000,  "69279037"),
    (20000000000, "65353130"),
]


@pytest.mark.parametrize("zeit,erwartet", VEKTOREN)
def test_rfc6238_testvektoren(zeit, erwartet):
    schritt = zeit // totp.SCHRITT
    assert totp._code(SEED, schritt, stellen=8, algo=hashlib.sha1) == erwartet


def test_sechsstellig_ist_der_achtstellige_ohne_vordere_ziffern():
    """Unsere App nutzt sechs Stellen – das sind die hinteren sechs."""
    schritt = 59 // totp.SCHRITT
    assert totp._code(SEED, schritt) == "94287082"[-6:]


# ------------------------------------------------- Verhalten in der App

def test_eigener_code_wird_angenommen():
    s = totp.neuer_schluessel()
    assert totp.pruefe(s, totp.code_jetzt(s)) is not None


def test_falscher_code_wird_abgelehnt():
    s = totp.neuer_schluessel()
    falsch = "000000" if totp.code_jetzt(s) != "000000" else "111111"
    assert totp.pruefe(s, falsch) is None


def test_uhr_darf_leicht_abweichen():
    """Eine halbe Minute Versatz kommt bei Handys vor."""
    s = totp.neuer_schluessel()
    jetzt = 1_700_000_000
    frueher = totp.code_jetzt(s, wann=jetzt - totp.SCHRITT)
    assert totp.pruefe(s, frueher, wann=jetzt) is not None


def test_zu_grosse_abweichung_wird_abgelehnt():
    s = totp.neuer_schluessel()
    jetzt = 1_700_000_000
    alt = totp.code_jetzt(s, wann=jetzt - 5 * totp.SCHRITT)
    assert totp.pruefe(s, alt, wann=jetzt) is None


def test_ein_code_gilt_nur_einmal():
    """Sonst könnte ihn jemand, der ihn abliest, gleich noch mal benutzen."""
    s = totp.neuer_schluessel()
    jetzt = 1_700_000_000
    code = totp.code_jetzt(s, wann=jetzt)
    schritt = totp.pruefe(s, code, wann=jetzt)
    assert schritt is not None
    assert totp.pruefe(s, code, zuletzt=schritt, wann=jetzt) is None


def test_eingabe_mit_leerzeichen_wird_verstanden():
    s = totp.neuer_schluessel()
    code = totp.code_jetzt(s)
    assert totp.pruefe(s, f"{code[:3]} {code[3:]}") is not None


def test_otpauth_url_enthaelt_alles_noetige():
    url = totp.otpauth_url("ABCDEF", "sven", "Finn's Brickfolio")
    assert url.startswith("otpauth://totp/")
    assert "secret=ABCDEF" in url and "issuer=" in url
    assert "period=30" in url and "digits=6" in url


def test_rettungscodes_sind_verschieden_und_gehasht():
    codes = totp.neue_rettungscodes()
    assert len(set(codes)) == len(codes) == 8
    h = totp.rettungscode_hash(codes[0])
    assert len(h) == 64 and codes[0] not in h
    # Schreibweise soll egal sein
    assert totp.rettungscode_hash(codes[0].upper()) == h
