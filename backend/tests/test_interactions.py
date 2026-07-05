"""
Integration tests for the /interactions endpoint, covering the quality-bar
scenarios from the brief: PING/PONG, forged/unsigned request rejection,
dedup on interaction_id, and tolerance of a transient DB outage.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import InteractionLog
from app.routes.interactions import safe_dedup_and_log
from tests.conftest import TEST_SIGNING_KEY

client = TestClient(app)

TIMESTAMP = "1700000000"


def signed_headers(body: bytes, timestamp: str = TIMESTAMP) -> dict:
    message = timestamp.encode() + body
    signature = TEST_SIGNING_KEY.sign(message).signature.hex()
    return {"X-Signature-Ed25519": signature, "X-Signature-Timestamp": timestamp}


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_ping_answered_with_pong():
    body = json.dumps({"type": 1}).encode()
    resp = client.post("/interactions", data=body, headers=signed_headers(body))
    assert resp.status_code == 200
    assert resp.json() == {"type": 1}


def test_unsigned_request_rejected():
    body = json.dumps({"type": 1}).encode()
    resp = client.post("/interactions", data=body)
    assert resp.status_code == 401


def test_forged_signature_rejected():
    body = json.dumps({"type": 1}).encode()
    headers = {"X-Signature-Ed25519": "a" * 128, "X-Signature-Timestamp": TIMESTAMP}
    resp = client.post("/interactions", data=body, headers=headers)
    assert resp.status_code == 401


def test_tampered_body_rejected():
    body = json.dumps({"type": 1}).encode()
    headers = signed_headers(body)
    tampered = json.dumps({"type": 1, "extra": "hacked"}).encode()
    resp = client.post("/interactions", data=tampered, headers=headers)
    assert resp.status_code == 401


def _command_payload(interaction_id: str):
    return {
        "id": interaction_id,
        "token": "interaction-token",
        "type": 2,
        "guild_id": "guild-1",
        "channel_id": "chan-1",
        "member": {"user": {"username": "tester"}},
        "data": {"name": "status", "options": []},
    }


@patch("app.routes.interactions.mirror_for_guild", return_value=True)
@patch("app.routes.interactions.send_followup_message", return_value=True)
def test_command_is_acked_recorded_and_replied(mock_followup, mock_mirror):
    body = json.dumps(_command_payload("interaction-abc")).encode()
    resp = client.post("/interactions", data=body, headers=signed_headers(body))

    assert resp.status_code == 200
    assert resp.json() == {"type": 5}  # deferred ack within the 3s window

    db = SessionLocal()
    row = db.query(InteractionLog).filter_by(interaction_id="interaction-abc").first()
    db.close()
    assert row is not None
    assert row.status == "processed"
    assert mock_followup.called
    assert mock_mirror.called


@patch("app.routes.interactions.mirror_for_guild", return_value=True)
@patch("app.routes.interactions.send_followup_message", return_value=True)
def test_redelivered_interaction_is_not_processed_twice(mock_followup, mock_mirror):
    body = json.dumps(_command_payload("interaction-dup")).encode()
    headers = signed_headers(body)

    resp1 = client.post("/interactions", data=body, headers=headers)
    resp2 = client.post("/interactions", data=body, headers=headers)  # Discord redelivery

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    db = SessionLocal()
    rows = db.query(InteractionLog).filter_by(interaction_id="interaction-dup").all()
    db.close()
    assert len(rows) == 1  # only recorded once despite two deliveries
    assert mock_followup.call_count == 1  # only replied once
    assert mock_mirror.call_count == 1  # only mirrored once


def test_safe_dedup_and_log_tolerates_db_outage():
    """Simulates the exact failure we hit against Neon: the very first query
    (the dedup check) raises because the pooled connection was dropped. The
    request must still be able to ack Discord instead of raising and timing
    out — this is the fix for that incident."""
    db = MagicMock()
    db.query.side_effect = Exception("SSL connection has been closed unexpectedly")

    log, is_duplicate = safe_dedup_and_log(
        db, "interaction-during-outage",
        guild_id="guild-1", channel_id="chan-1", user_tag="tester",
        command_name="status", command_text="",
    )

    assert log is None
    assert is_duplicate is False  # caller acks Discord but skips background processing
    db.rollback.assert_called_once()
