from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from app.config import DISCORD_PUBLIC_KEY

_verify_key = None


def _get_verify_key() -> VerifyKey | None:
    """Lazily initialize the verify key. Returns None if key is invalid."""
    global _verify_key
    if _verify_key is None:
        try:
            _verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        except (ValueError, TypeError):
            # Key is not valid hex (e.g., placeholder in tests)
            return None
    return _verify_key


def verify_discord_signature(signature: str, timestamp: str, body: bytes) -> bool:
    """
    Verifies that a request really came from Discord.
    Discord signs every request with Ed25519: signature covers (timestamp + raw body).
    Returns False on any malformed/missing/forged signature — never raises.
    """
    if not signature or not timestamp:
        return False
    try:
        verify_key = _get_verify_key()
        if verify_key is None:
            return False
        verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError, Exception):
        return False
