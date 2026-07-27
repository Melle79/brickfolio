"""Ende-zu-Ende-Verschlüsselung für Tausch-Nachrichten.

Jede Instanz hat ein Schlüsselpaar. Der öffentliche Teil liegt beim Hub,
der private bleibt hier. Verschlüsselt wird für den Empfänger, entschlüsseln
kann nur er – der Hub speichert reines Kauderwelsch.

Verfahren: X25519 (Schlüsselaustausch mit einem Wegwerf-Schlüssel je
Nachricht) → HKDF-SHA256 → AES-256-GCM. Jede Nachricht hat damit ihren
eigenen Schlüssel; ein späterer Diebstahl des privaten Schlüssels gibt
mitgeschnittene Nachrichten nicht mehr her (Forward Secrecy je Nachricht).
"""
import base64
import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey, X25519PublicKey)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

import core

INFO = b"brickfolio-hub-message-v1"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def _unb64(text: str) -> bytes:
    return base64.b64decode(text)


# ------------------------------------------------------------- Schlüssel

def _private_key() -> X25519PrivateKey:
    """Privater Schlüssel dieser Instanz – wird beim ersten Mal erzeugt."""
    stored = core.get_setting("hub_privkey")
    if stored:
        return X25519PrivateKey.from_private_bytes(_unb64(stored))
    key = X25519PrivateKey.generate()
    core.set_setting("hub_privkey", _b64(key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption())))
    return key


def public_key() -> str:
    """Öffentlicher Schlüssel dieser Instanz (Base64) – der darf zum Hub."""
    return _b64(_private_key().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw))


def reset_keys():
    """Schlüsselpaar verwerfen (z. B. beim Trennen vom Netzwerk)."""
    core.set_setting("hub_privkey", "")


# ------------------------------------------------------- Ver-/Entschlüsseln

def _derive(shared: bytes, eph_pub: bytes, recipient_pub: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=INFO + eph_pub + recipient_pub).derive(shared)


def seal(recipient_public_key: str, plaintext: str) -> str:
    """Nachricht für einen Empfänger verschlüsseln. Ergebnis ist ein
    JSON-Umschlag (Base64-Felder), den der Hub nur weiterreicht."""
    recipient_raw = _unb64(recipient_public_key)
    recipient = X25519PublicKey.from_public_bytes(recipient_raw)
    eph = X25519PrivateKey.generate()
    eph_pub_raw = eph.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    key = _derive(eph.exchange(recipient), eph_pub_raw, recipient_raw)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return json.dumps({"v": 1, "epk": _b64(eph_pub_raw),
                       "n": _b64(nonce), "ct": _b64(ct)})


def open_box(envelope: str) -> str:
    """Für uns bestimmte Nachricht entschlüsseln."""
    data = json.loads(envelope)
    if data.get("v") != 1:
        raise ValueError("Unbekanntes Nachrichtenformat")
    priv = _private_key()
    my_pub_raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    eph_pub_raw = _unb64(data["epk"])
    eph_pub = X25519PublicKey.from_public_bytes(eph_pub_raw)
    key = _derive(priv.exchange(eph_pub), eph_pub_raw, my_pub_raw)
    return AESGCM(key).decrypt(_unb64(data["n"]), _unb64(data["ct"]),
                               None).decode()
