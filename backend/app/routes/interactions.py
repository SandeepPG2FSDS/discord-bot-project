import logging

from fastapi import APIRouter, Request, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.discord_verify import verify_discord_signature
from app.discord_client import send_followup_message, send_mirror_notification
from app.database import get_db
from app.models import InteractionLog, CommandConfig, ServerConfig
from app.ai import summarize_and_tag

router = APIRouter()
logger = logging.getLogger("interactions")

PING = 1
APPLICATION_COMMAND = 2
MESSAGE_COMPONENT = 3

PONG = 1
CHANNEL_MESSAGE_WITH_SOURCE = 4
DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
MODAL_SUBMIT = 5


def safe_dedup_and_log(db: Session, interaction_id: str, **log_fields) -> tuple[InteractionLog | None, bool]:
    """
    Checks for a duplicate delivery and inserts the log row, tolerating a
    transient DB failure (e.g. a pooled connection Neon closed for being
    idle). On a DB error this logs it and returns (None, False) rather than
    raising, so the caller can still ack Discord within the 3s window
    instead of the outage surfacing as a failed/timed-out interaction.
    """
    try:
        existing = db.query(InteractionLog).filter_by(interaction_id=interaction_id).first()
        if existing:
            return None, True
        log = InteractionLog(interaction_id=interaction_id, status="received", **log_fields)
        db.add(log)
        db.commit()
        return log, False
    except Exception:
        logger.exception("DB error while logging interaction %s — acking Discord anyway", interaction_id)
        db.rollback()
        return None, False


def mirror_for_guild(db: Session, guild_id: str | None, text: str) -> bool:
    """Routes the mirror notification to whatever the admin connected for
    this guild (a Discord channel or a Slack webhook); falls back to the
    global MIRROR_WEBHOOK_URL env var if the guild hasn't been connected."""
    server = db.query(ServerConfig).filter_by(guild_id=guild_id).first() if guild_id else None
    return send_mirror_notification(
        text,
        slack_webhook_url=server.slack_webhook_url if server else None,
        discord_channel_id=server.mirror_channel_id if server else None,
    )


DEFAULT_REPLY_TEMPLATES = {
    "status": "✅ All systems operational — bot is online and responding normally.",
    "report": '📝 Thanks, I\'ve logged your report: "{text}"',
}


def get_config(db: Session, command_name: str, guild_id: str | None = None) -> CommandConfig:
    """Get or create CommandConfig, respecting per-guild isolation. New
    commands get a sensible default reply for that command name rather than
    a generic placeholder, though the admin can always override it."""
    cfg = db.query(CommandConfig).filter_by(
        command_name=command_name, guild_id=guild_id
    ).first()
    if not cfg:
        default_template = DEFAULT_REPLY_TEMPLATES.get(command_name, "Got it: {text}")
        cfg = CommandConfig(command_name=command_name, guild_id=guild_id, reply_template=default_template)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def process_command_in_background(interaction_id: str, interaction_token: str, command_name: str,
                                    command_text: str, guild_id: str | None):
    """
    Runs after we've already ack'd Discord (within the 3s window).
    Applies the rule, calls AI if enabled, replies, mirrors, and updates the log.
    Never raises — all failures are caught and recorded so nothing is lost silently.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        log = db.query(InteractionLog).filter_by(interaction_id=interaction_id).first()
        if not log:
            return

        cfg = get_config(db, command_name, guild_id)

        ai_summary = None
        if cfg.ai_enabled:
            ai_summary = summarize_and_tag(command_text)

        reply_text = cfg.reply_template.format(text=command_text or "(no text)")
        if ai_summary:
            reply_text += f"\n_AI: {ai_summary}_"

        replied_ok = send_followup_message(interaction_token, reply_text)

        mirror_ok = False
        if cfg.mirror_enabled:
            mirror_ok = mirror_for_guild(
                db, guild_id, f"[{command_name}] from guild {guild_id}: {command_text} -> {reply_text}"
            )

        log.ai_summary = ai_summary
        log.mirror_delivered = mirror_ok
        log.action_taken = "replied" + (" + mirrored" if mirror_ok else "")
        log.status = "processed" if replied_ok else "failed"
        if not replied_ok:
            log.error_message = "Failed to deliver follow-up message to Discord"
        db.commit()
    except Exception as exc:  # noqa: BLE001 - must never crash the background task
        logger.exception("Failed processing interaction %s", interaction_id)
        try:
            log = db.query(InteractionLog).filter_by(interaction_id=interaction_id).first()
            if log:
                log.status = "failed"
                log.error_message = str(exc)
                db.commit()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


def process_modal_submit_in_background(interaction_id: str, interaction_token: str, custom_id: str,
                                       modal_data: dict, guild_id: str | None):
    """
    Processes modal submit interactions using the same pattern as commands.
    modal_data contains extracted fields from the modal form.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        log = db.query(InteractionLog).filter_by(interaction_id=interaction_id).first()
        if not log:
            return

        # Use custom_id as the "command" name for config lookup
        cfg = get_config(db, custom_id, guild_id)

        modal_text = " | ".join(f"{k}: {v}" for k, v in modal_data.items())

        ai_summary = None
        if cfg.ai_enabled:
            ai_summary = summarize_and_tag(modal_text)

        reply_text = cfg.reply_template.format(text=modal_text or "(no data)")
        if ai_summary:
            reply_text += f"\n_AI: {ai_summary}_"

        replied_ok = send_followup_message(interaction_token, reply_text)

        mirror_ok = False
        if cfg.mirror_enabled:
            mirror_ok = mirror_for_guild(
                db, guild_id, f"[MODAL {custom_id}] from guild {guild_id}: {modal_text} -> {reply_text}"
            )

        log.ai_summary = ai_summary
        log.mirror_delivered = mirror_ok
        log.action_taken = "modal_processed" + (" + mirrored" if mirror_ok else "")
        log.status = "processed" if replied_ok else "failed"
        if not replied_ok:
            log.error_message = "Failed to deliver follow-up message to Discord"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed processing modal submission %s", interaction_id)
        try:
            log = db.query(InteractionLog).filter_by(interaction_id=interaction_id).first()
            if log:
                log.status = "failed"
                log.error_message = str(exc)
                db.commit()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


@router.post("/interactions")
async def interactions(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp = request.headers.get("X-Signature-Timestamp", "")
    raw_body = await request.body()

    if not verify_discord_signature(signature, timestamp, raw_body):
        raise HTTPException(status_code=401, detail="invalid request signature")

    body = await request.json()
    interaction_type = body.get("type")

    if interaction_type == PING:
        return {"type": PONG}

    if interaction_type == APPLICATION_COMMAND:
        interaction_id = body["id"]
        interaction_token = body["token"]
        data = body.get("data", {})
        command_name = data.get("name", "unknown")
        guild_id = body.get("guild_id")
        channel_id = body.get("channel_id")
        member = body.get("member", {}).get("user", {})
        user_tag = f'{member.get("username", "unknown")}'

        options = data.get("options", [])
        command_text = options[0]["value"] if options else ""

        # Dedup: Discord may redeliver the same interaction. If we've already
        # seen this id, don't process it again — just ack again quietly.
        log, is_duplicate = safe_dedup_and_log(
            db, interaction_id,
            guild_id=guild_id, channel_id=channel_id, user_tag=user_tag,
            command_name=command_name, command_text=command_text,
        )
        if not is_duplicate and log:
            # Defer immediately (well within 3s), do the real work in the background,
            # then follow up — this is how slow work (AI calls, retries) stays safe.
            background_tasks.add_task(
                process_command_in_background,
                interaction_id, interaction_token, command_name, command_text, guild_id,
            )
        return {"type": DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE}

    if interaction_type == MESSAGE_COMPONENT:
        """Handle button clicks and modal selections (not form submissions)."""
        interaction_id = body["id"]
        interaction_token = body["token"]
        data = body.get("data", {})
        custom_id = data.get("custom_id", "unknown")
        guild_id = body.get("guild_id")
        channel_id = body.get("channel_id")
        member = body.get("member", {}).get("user", {})
        user_tag = f'{member.get("username", "unknown")}'

        # Dedup check
        log, is_duplicate = safe_dedup_and_log(
            db, interaction_id,
            guild_id=guild_id, channel_id=channel_id, user_tag=user_tag,
            command_name=f"component_{custom_id}", command_text=f"component click: {custom_id}",
        )
        if not is_duplicate and log:
            # Defer and handle in background
            background_tasks.add_task(
                process_modal_submit_in_background,
                interaction_id, interaction_token, custom_id, {}, guild_id,
            )
        return {"type": DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE}

    # Handle modal form submissions (custom_type=5 for modals)
    # Discord sends modals as MESSAGE_COMPONENT with a special structure
    # Check for modal_data in the components array
    if interaction_type == 5:  # MODAL_SUBMIT (if Discord sends it this way)
        interaction_id = body["id"]
        interaction_token = body["token"]
        data = body.get("data", {})
        custom_id = data.get("custom_id", "report")
        guild_id = body.get("guild_id")
        channel_id = body.get("channel_id")
        member = body.get("member", {}).get("user", {})
        user_tag = f'{member.get("username", "unknown")}'

        # Extract form fields from components
        modal_data = {}
        components = data.get("components", [])
        for row in components:
            for component in row.get("components", []):
                custom_id_field = component.get("custom_id", "field")
                value = component.get("value", "")
                modal_data[custom_id_field] = value

        # Dedup check
        log, is_duplicate = safe_dedup_and_log(
            db, interaction_id,
            guild_id=guild_id, channel_id=channel_id, user_tag=user_tag,
            command_name=f"modal_{custom_id}", command_text=str(modal_data),
        )
        if not is_duplicate and log:
            # Process in background
            background_tasks.add_task(
                process_modal_submit_in_background,
                interaction_id, interaction_token, custom_id, modal_data, guild_id,
            )
        return {"type": CHANNEL_MESSAGE_WITH_SOURCE, "data": {"content": "Report received and processing..."}}

    # Unhandled interaction types - ack politely for now.
    return {"type": CHANNEL_MESSAGE_WITH_SOURCE, "data": {"content": "Unsupported interaction type."}}
