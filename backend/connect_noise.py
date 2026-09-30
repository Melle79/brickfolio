"""Noise_IK_25519_ChaChaPoly_SHA256 – Ende zu Ende für den externen Zugriff
ohne Portfreigabe (connect.py).

Nach der Noise-Spezifikation (Revision 34, noiseprotocol.org), nur das eine
Muster, das Nupplo Connect braucht:

    IK:
      <- s
      ...
      -> e, es, s, ss
      <- e, ee, se

Das externe Gerät (Initiator) kennt den statischen Schlüssel der Instanz aus dem
QR-Code; die Instanz (Responder) lernt den des Geräts in der ersten Nachricht.
Danach ein Schlüssel je Richtung.

Keine eigene Erfindung: geprüft gegen die Testvektoren von cacophony
(tests/daten/noise_ik_cacophony.json) und gegen einen Mitschnitt der
Gegenseite (tests/daten/noise_ik_nupplo.json) – beide Seiten müssen Byte
für Byte gleich rechnen.
"""

import hashlib
import hmac

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import serialization

NAME = b"Noise_IK_25519_ChaChaPoly_SHA256"
MAX_NACHRICHT = 65535          # Grenze der Spezifikation, Chiffre samt Tag
TAG = 16


class NoiseFehler(Exception):
    pass


def _roh(k) -> bytes:
    if isinstance(k, X25519PrivateKey):
        k = k.public_key()
    return k.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _dh(privat: X25519PrivateKey, oeffentlich: bytes) -> bytes:
    return privat.exchange(X25519PublicKey.from_public_bytes(oeffentlich))


def _hkdf(ck: bytes, ikm: bytes, n: int):
    temp = hmac.new(ck, ikm, hashlib.sha256).digest()
    aus, vorher = [], b""
    for i in range(1, n + 1):
        vorher = hmac.new(temp, vorher + bytes([i]), hashlib.sha256).digest()
        aus.append(vorher)
    return aus


class Chiffre:
    """CipherState: ein Schlüssel, eine hochzählende Nummer."""

    def __init__(self, k: bytes | None = None):
        self.k, self.n = k, 0

    def _nonce(self) -> bytes:
        if self.n >= 2 ** 64 - 1:
            raise NoiseFehler("Nonce erschöpft")
        return b"\x00" * 4 + self.n.to_bytes(8, "little")

    def verschluesseln(self, ad: bytes, klar: bytes) -> bytes:
        if self.k is None:
            return klar
        c = ChaCha20Poly1305(self.k).encrypt(self._nonce(), klar, ad)
        self.n += 1
        return c

    def entschluesseln(self, ad: bytes, chiffre: bytes) -> bytes:
        if self.k is None:
            return chiffre
        try:
            p = ChaCha20Poly1305(self.k).decrypt(self._nonce(), chiffre, ad)
        except Exception:
            raise NoiseFehler("Entschlüsseln fehlgeschlagen")
        self.n += 1
        return p


class Handschlag:
    """SymmetricState + HandshakeState für IK."""

    def __init__(self, initiator: bool, prologue: bytes, statisch: X25519PrivateKey,
                 entfernt_statisch: bytes | None = None, fluechtig: X25519PrivateKey | None = None):
        self.initiator = initiator
        self.s, self.e = statisch, fluechtig
        self.rs, self.re = entfernt_statisch, None
        self.h = NAME if len(NAME) == 32 else hashlib.sha256(NAME).digest()
        self.ck = self.h
        self.c = Chiffre()
        self._mix_hash(prologue)
        # Vorab-Nachricht „<- s“: der statische Schlüssel der Instanz.
        self._mix_hash(entfernt_statisch if initiator else _roh(statisch))

    def _mix_hash(self, d: bytes):
        self.h = hashlib.sha256(self.h + d).digest()

    def _mix_key(self, ikm: bytes):
        self.ck, k = _hkdf(self.ck, ikm, 2)
        self.c = Chiffre(k)

    def _verschluesseln_und_hash(self, klar: bytes) -> bytes:
        c = self.c.verschluesseln(self.h, klar)
        self._mix_hash(c)
        return c

    def _entschluesseln_und_hash(self, c: bytes) -> bytes:
        p = self.c.entschluesseln(self.h, c)
        self._mix_hash(c)
        return p

    def teilen(self):
        """Split: (senden, empfangen) aus Sicht dieser Seite."""
        k1, k2 = _hkdf(self.ck, b"", 2)
        c1, c2 = Chiffre(k1), Chiffre(k2)
        return (c1, c2) if self.initiator else (c2, c1)

    # -> e, es, s, ss
    def erste_schreiben(self, nutzlast: bytes = b"") -> bytes:
        assert self.initiator
        self.e = self.e or X25519PrivateKey.generate()
        e = _roh(self.e)
        self._mix_hash(e)
        self._mix_key(_dh(self.e, self.rs))
        s = self._verschluesseln_und_hash(_roh(self.s))
        self._mix_key(_dh(self.s, self.rs))
        return e + s + self._verschluesseln_und_hash(nutzlast)

    def erste_lesen(self, nachricht: bytes) -> bytes:
        assert not self.initiator
        if len(nachricht) < 32 + 32 + TAG + TAG:
            raise NoiseFehler("erste Nachricht zu kurz")
        self.re = nachricht[:32]
        self._mix_hash(self.re)
        self._mix_key(_dh(self.s, self.re))
        self.rs = self._entschluesseln_und_hash(nachricht[32:32 + 32 + TAG])
        self._mix_key(_dh(self.s, self.rs))
        return self._entschluesseln_und_hash(nachricht[32 + 32 + TAG:])

    # <- e, ee, se
    def zweite_schreiben(self, nutzlast: bytes = b"") -> bytes:
        assert not self.initiator
        self.e = self.e or X25519PrivateKey.generate()
        e = _roh(self.e)
        self._mix_hash(e)
        self._mix_key(_dh(self.e, self.re))
        self._mix_key(_dh(self.e, self.rs))
        return e + self._verschluesseln_und_hash(nutzlast)

    def zweite_lesen(self, nachricht: bytes) -> bytes:
        assert self.initiator
        if len(nachricht) < 32 + TAG:
            raise NoiseFehler("zweite Nachricht zu kurz")
        self.re = nachricht[:32]
        self._mix_hash(self.re)
        self._mix_key(_dh(self.e, self.re))
        self._mix_key(_dh(self.s, self.re))
        return self._entschluesseln_und_hash(nachricht[32:])
