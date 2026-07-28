"""Zeitbasierte Einmalcodes (TOTP, RFC 6238) für die Zwei-Faktor-Anmeldung.

Bewusst ohne zusätzliche Bibliothek: Der Algorithmus ist kurz und – das ist
der eigentliche Grund – **gegen die offiziellen Testvektoren aus RFC 6238
prüfbar**. Genau das tun die Tests. Bei Krypto-Bausteinen ist eine
Eigenbau-Lösung sonst keine gute Idee; hier zählt, dass jede Zeile gegen die
Norm belegt ist statt gegen eine Vermutung.

Der geheime Schlüssel liegt Base32-kodiert, wie ihn Authenticator-Apps
erwarten.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

SCHRITT = 30            # Sekunden je Code (RFC-Standard)
STELLEN = 6             # Ziffern
TOLERANZ = 1            # ein Schritt Vor- und Nachlauf gegen Uhr-Abweichung


def neuer_schluessel(bytes_laenge: int = 20) -> str:
    """Neuer Schlüssel als Base32 – 20 Byte entspricht der RFC-Empfehlung."""
    return base64.b32encode(secrets.token_bytes(bytes_laenge)).decode().rstrip("=")


def _code(schluessel_b32: str, zaehler: int, stellen: int = STELLEN,
          algo=hashlib.sha1) -> str:
    """Ein Code für einen bestimmten Zeitschritt – der Kern aus RFC 4226."""
    pad = "=" * (-len(schluessel_b32) % 8)
    key = base64.b32decode(schluessel_b32.upper() + pad)
    mac = hmac.new(key, struct.pack(">Q", zaehler), algo).digest()
    # Dynamische Kürzung: die letzten vier Bit zeigen, wo geschnitten wird.
    versatz = mac[-1] & 0x0F
    zahl = struct.unpack(">I", mac[versatz:versatz + 4])[0] & 0x7FFFFFFF
    return str(zahl % (10 ** stellen)).zfill(stellen)


def code_jetzt(schluessel_b32: str, wann: float | None = None) -> str:
    return _code(schluessel_b32, int((wann or time.time()) // SCHRITT))


def pruefe(schluessel_b32: str, eingabe: str, zuletzt: int | None = None,
           wann: float | None = None) -> int | None:
    """Code prüfen. Ergebnis: der verwendete Zeitschritt oder None.

    `zuletzt` ist der zuletzt akzeptierte Schritt. Ein Code gilt **nur
    einmal** – sonst könnte jemand, der ihn über die Schulter abliest, ihn
    innerhalb derselben halben Minute erneut verwenden.
    """
    eingabe = "".join(ch for ch in (eingabe or "") if ch.isdigit())
    if len(eingabe) != STELLEN:
        return None
    jetzt = int((wann or time.time()) // SCHRITT)
    for versatz in range(-TOLERANZ, TOLERANZ + 1):
        schritt = jetzt + versatz
        if zuletzt is not None and schritt <= zuletzt:
            continue
        if hmac.compare_digest(_code(schluessel_b32, schritt), eingabe):
            return schritt
    return None


def otpauth_url(schluessel_b32: str, benutzer: str, herausgeber: str) -> str:
    """Adresse für den QR-Code, wie sie Authenticator-Apps lesen."""
    label = quote(f"{herausgeber}:{benutzer}", safe="")
    return (f"otpauth://totp/{label}?secret={schluessel_b32}"
            f"&issuer={quote(herausgeber, safe='')}"
            f"&algorithm=SHA1&digits={STELLEN}&period={SCHRITT}")


# ------------------------------------------------- Wiederherstellungscodes

def neue_rettungscodes(anzahl: int = 8) -> list:
    """Für den Fall, dass das Telefon weg ist. Ohne sie wäre ein verlorenes
    Gerät gleichbedeutend mit einem verlorenen Konto."""
    return ["-".join(secrets.token_hex(2) for _ in range(3))
            for _ in range(anzahl)]


def rettungscode_hash(code: str) -> str:
    """Auch diese Codes werden nicht im Klartext abgelegt."""
    norm = code.strip().lower().replace(" ", "")
    return hashlib.sha256(norm.encode()).hexdigest()
