"""
Pytest configuration and fixtures for Discord bot backend tests.
"""

import os
import sys
from pathlib import Path
from nacl.signing import SigningKey

# Add the backend app directory to the path so imports work correctly
sys.path.insert(0, str(Path(__file__).parent.parent))

# Force an isolated test database BEFORE any app module (and therefore
# app.config's load_dotenv()) is imported. load_dotenv() does not override
# variables already present in os.environ, so setting this first means
# tests never touch the real DATABASE_URL from backend/.env even if it
# points at a live Neon database.
os.environ['DATABASE_URL'] = 'sqlite:///./test.db'

# Generate a test signing key for use in tests
_test_signing_key = SigningKey.generate()
_test_public_key_hex = _test_signing_key.verify_key.encode().hex()

# Configure environment for tests with a valid hex key
os.environ.setdefault('DISCORD_PUBLIC_KEY', _test_public_key_hex)
os.environ.setdefault('DISCORD_BOT_TOKEN', 'test_token_placeholder')
os.environ.setdefault('DISCORD_APPLICATION_ID', '123456789')
os.environ.setdefault('MIRROR_WEBHOOK_URL', '')
os.environ.setdefault('JWT_SECRET', 'test-jwt-secret')

TEST_SIGNING_KEY = _test_signing_key

