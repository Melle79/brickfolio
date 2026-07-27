"""Tests für die Ende-zu-Ende-Verschlüsselung der Tausch-Nachrichten."""
import json

import pytest

import core
import crypto_box


@pytest.fixture
def alice(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "a.db"))
    core.init_db()
    return crypto_box


def _second_instance(tmp_path, monkeypatch, name):
    """Zweite Instanz mit eigener Datenbank – eigenes Schlüsselpaar."""
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / f"{name}.db"))
    core.init_db()
    return crypto_box.public_key()


def test_public_key_is_stable(alice):
    assert alice.public_key() == alice.public_key()


def test_roundtrip(alice):
    box = alice.seal(alice.public_key(), "Hallo Paul!")
    assert alice.open_box(box) == "Hallo Paul!"


def test_envelope_reveals_nothing(alice):
    box = alice.seal(alice.public_key(), "Geheim: Yoda für 12 Euro")
    assert "Yoda" not in box and "Geheim" not in box
    data = json.loads(box)
    assert set(data) == {"v", "epk", "n", "ct"}


def test_same_text_gives_different_envelopes(alice):
    """Wegwerf-Schlüssel je Nachricht: gleicher Text, anderes Kauderwelsch."""
    a = alice.seal(alice.public_key(), "gleich")
    b = alice.seal(alice.public_key(), "gleich")
    assert a != b
    assert alice.open_box(a) == alice.open_box(b) == "gleich"


def test_other_instance_cannot_read(tmp_path, monkeypatch):
    # Alice verschlüsselt für sich selbst …
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "a.db"))
    core.init_db()
    box = crypto_box.seal(crypto_box.public_key(), "nur für Alice")

    # … Bob (andere Datenbank, anderer Schlüssel) kommt nicht heran
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "b.db"))
    core.init_db()
    with pytest.raises(Exception):
        crypto_box.open_box(box)


def test_message_for_bob_is_readable_by_bob(tmp_path, monkeypatch):
    bob_pub = _second_instance(tmp_path, monkeypatch, "bob")

    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "alice.db"))
    core.init_db()
    box = crypto_box.seal(bob_pub, "Tauschst du den Yoda?")

    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "bob.db"))
    assert crypto_box.open_box(box) == "Tauschst du den Yoda?"


def test_tampering_is_detected(alice):
    box = json.loads(alice.seal(alice.public_key(), "unverändert"))
    raw = bytearray(crypto_box._unb64(box["ct"]))
    raw[0] ^= 0x01                       # ein Bit kippen
    box["ct"] = crypto_box._b64(bytes(raw))
    with pytest.raises(Exception):
        alice.open_box(json.dumps(box))


def test_umlauts_survive(alice):
    text = 'Grüße – Föhn, Straße & Co. \U0001F9F1'
    assert alice.open_box(alice.seal(alice.public_key(), text)) == text
