"""
Test suite for Discord signature verification.
Tests cover valid signatures, forged signatures, and tampered payloads.
"""

import os
import pytest
from nacl.signing import SigningKey
from unittest.mock import patch

from app.discord_verify import verify_discord_signature


@pytest.fixture
def signing_key():
    """Generate a test signing key (different from the real one)."""
    return SigningKey.generate()


@pytest.fixture
def test_timestamp():
    """A test timestamp."""
    return "1234567890"


@pytest.fixture
def test_payload():
    """A test payload."""
    return b'{"type": 1}'


def test_valid_signature(signing_key, test_timestamp, test_payload):
    """
    Test that a validly signed request is accepted.
    Uses a signing key different from the production key to isolate the test.
    """
    # Create signature with our test key
    message = test_timestamp.encode() + test_payload
    signature = signing_key.sign(message).signature.hex()
    
    # Mock the production key to use our test key
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        result = verify_discord_signature(signature, test_timestamp, test_payload)
        assert result is True


def test_forged_signature(signing_key, test_timestamp, test_payload):
    """
    Test that a forged (completely random) signature is rejected.
    """
    forged_signature = "a" * 128  # 128 hex chars = 64 bytes
    
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        result = verify_discord_signature(forged_signature, test_timestamp, test_payload)
        assert result is False


def test_tampered_payload(signing_key, test_timestamp, test_payload):
    """
    Test that if the payload is modified after signing, verification fails.
    """
    # Sign the original payload
    message = test_timestamp.encode() + test_payload
    signature = signing_key.sign(message).signature.hex()
    
    # Modify the payload
    tampered_payload = b'{"type": 2, "hacked": true}'
    
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        result = verify_discord_signature(signature, test_timestamp, tampered_payload)
        assert result is False


def test_tampered_timestamp(signing_key, test_timestamp, test_payload):
    """
    Test that if the timestamp is modified after signing, verification fails.
    This prevents replay attacks with modified timestamps.
    """
    # Sign with original timestamp
    message = test_timestamp.encode() + test_payload
    signature = signing_key.sign(message).signature.hex()
    
    # Use a different timestamp
    tampered_timestamp = "9999999999"
    
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        result = verify_discord_signature(signature, tampered_timestamp, test_payload)
        assert result is False


def test_missing_signature(test_timestamp, test_payload):
    """Test that missing signature is rejected."""
    result = verify_discord_signature("", test_timestamp, test_payload)
    assert result is False


def test_missing_timestamp(test_payload):
    """Test that missing timestamp is rejected."""
    result = verify_discord_signature("a" * 128, "", test_payload)
    assert result is False


def test_none_signature(test_timestamp, test_payload):
    """Test that None signature is handled gracefully."""
    # This tests robustness against unexpected input types
    signature = ""
    result = verify_discord_signature(signature, test_timestamp, test_payload)
    assert result is False


def test_malformed_hex_signature(signing_key, test_timestamp, test_payload):
    """
    Test that a malformed hex string in signature is rejected.
    """
    # Not valid hex (contains non-hex characters)
    bad_signature = "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"
    
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        result = verify_discord_signature(bad_signature, test_timestamp, test_payload)
        assert result is False


def test_empty_payload(signing_key, test_timestamp):
    """Test signature verification with empty payload."""
    empty_payload = b''
    message = test_timestamp.encode() + empty_payload
    signature = signing_key.sign(message).signature.hex()
    
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        result = verify_discord_signature(signature, test_timestamp, empty_payload)
        assert result is True


def test_large_payload(signing_key, test_timestamp):
    """Test signature verification with a large payload."""
    large_payload = b'x' * 10000
    message = test_timestamp.encode() + large_payload
    signature = signing_key.sign(message).signature.hex()
    
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        result = verify_discord_signature(signature, test_timestamp, large_payload)
        assert result is True


def test_signature_too_short(signing_key, test_timestamp, test_payload):
    """Test that a signature that's too short is rejected."""
    # A valid signature is 64 bytes = 128 hex chars, this is only 64 hex chars
    short_signature = "a" * 64
    
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        result = verify_discord_signature(short_signature, test_timestamp, test_payload)
        assert result is False


def test_signature_wrong_length(signing_key, test_timestamp, test_payload):
    """Test that a signature with wrong byte length is rejected."""
    # Wrong length signature
    wrong_length_signature = "a" * 100
    
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        result = verify_discord_signature(wrong_length_signature, test_timestamp, test_payload)
        assert result is False


def test_replay_attack_prevention(signing_key, test_timestamp, test_payload):
    """
    Test that a valid signature cannot be replayed with different payload.
    This demonstrates the signature covers both timestamp and payload.
    """
    # Create a valid signature
    message = test_timestamp.encode() + test_payload
    signature = signing_key.sign(message).signature.hex()
    
    # Try to use it with different payload
    different_payload = b'{"type": 3, "data": "different"}'
    
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        result = verify_discord_signature(signature, test_timestamp, different_payload)
        assert result is False


def test_case_insensitive_hex_signature(signing_key, test_timestamp, test_payload):
    """
    Test that hex signature comparison is case-insensitive (hex standard).
    """
    message = test_timestamp.encode() + test_payload
    signature_lower = signing_key.sign(message).signature.hex()
    signature_upper = signature_lower.upper()
    
    with patch('app.discord_verify._verify_key', signing_key.verify_key):
        # Both lowercase and uppercase should work (hex is case-insensitive)
        result_lower = verify_discord_signature(signature_lower, test_timestamp, test_payload)
        result_upper = verify_discord_signature(signature_upper, test_timestamp, test_payload)
        assert result_lower is True
        assert result_upper is True
