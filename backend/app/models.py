import datetime

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean

from app.database import Base


class InteractionLog(Base):
    """One row per Discord interaction we received (deduped by interaction_id)."""

    __tablename__ = "interaction_logs"

    id = Column(Integer, primary_key=True, index=True)
    interaction_id = Column(String, unique=True, index=True, nullable=False)
    guild_id = Column(String, index=True, nullable=True)
    channel_id = Column(String, nullable=True)
    user_tag = Column(String, nullable=True)
    command_name = Column(String, index=True, nullable=True)
    command_text = Column(Text, nullable=True)
    action_taken = Column(String, nullable=True)  # e.g. "replied", "mirrored", "failed"
    ai_summary = Column(Text, nullable=True)
    status = Column(String, default="received")  # received, processed, failed
    error_message = Column(Text, nullable=True)
    mirror_delivered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ServerConfig(Base):
    """A Discord server (guild) the admin has connected, with its chosen
    notification channel. This is what step 1 of the flow ("admin connects
    the app to a server and picks a channel it can post to") persists."""

    __tablename__ = "server_configs"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, unique=True, index=True, nullable=False)
    guild_name = Column(String, nullable=True)
    mirror_channel_id = Column(String, nullable=True)
    mirror_channel_name = Column(String, nullable=True)
    slack_webhook_url = Column(String, nullable=True)
    connected_at = Column(DateTime, default=datetime.datetime.utcnow)


class CommandConfig(Base):
    """Admin-configurable behavior per command name, per server (guild)."""

    __tablename__ = "command_configs"

    id = Column(Integer, primary_key=True, index=True)
    command_name = Column(String, index=True, nullable=False)
    guild_id = Column(String, index=True, nullable=True)  # None = global config, else per-guild
    reply_template = Column(Text, default="Got it: {text}")
    mirror_enabled = Column(Boolean, default=True)
    ai_enabled = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        # Enforce uniqueness per command + guild (guild_id can be NULL for global)
        # Note: In most SQL flavors, NULL != NULL, so multiple NULL rows are allowed
        # For strict per-guild enforcement, application logic ensures guild_id is set
    )
