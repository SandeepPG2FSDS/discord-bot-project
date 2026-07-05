from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import requests

from app.config import DISCORD_APPLICATION_ID
from app.database import get_db
from app.models import ServerConfig
from app.auth import require_admin
from app import discord_client

router = APIRouter(prefix="/dashboard/discord", tags=["servers"])

# View Channel + Send Messages
INVITE_PERMISSIONS = 3072


class ConnectServerRequest(BaseModel):
    guild_id: str
    guild_name: str
    mirror_channel_id: str | None = None
    mirror_channel_name: str | None = None
    slack_webhook_url: str | None = None


@router.get("/invite-url")
def get_invite_url(_admin: str = Depends(require_admin)):
    """The link the admin uses to add the bot to a server they manage.
    Discord's own consent screen is where the admin actually picks the
    server; we only need scopes for slash commands + posting messages."""
    params = {
        "client_id": DISCORD_APPLICATION_ID,
        "scope": "bot applications.commands",
        "permissions": str(INVITE_PERMISSIONS),
    }
    return {"invite_url": f"https://discord.com/oauth2/authorize?{urlencode(params)}"}


@router.get("/guilds")
def get_bot_guilds(_admin: str = Depends(require_admin)):
    """Servers the bot has already been invited into, for the admin to pick
    from after clicking the invite link."""
    try:
        return discord_client.list_bot_guilds()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Discord: {exc}") from exc


@router.get("/guilds/{guild_id}/channels")
def get_guild_channels(guild_id: str, _admin: str = Depends(require_admin)):
    """Text channels in a guild, for the "picks a channel it can post to" step."""
    try:
        return discord_client.list_guild_text_channels(guild_id)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Discord: {exc}") from exc


servers_router = APIRouter(prefix="/dashboard/servers", tags=["servers"])


@servers_router.get("")
def list_servers(db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Servers the admin has connected (persisted choice of mirror channel)."""
    servers = db.query(ServerConfig).order_by(ServerConfig.connected_at.desc()).all()
    return [
        {
            "guild_id": s.guild_id,
            "guild_name": s.guild_name,
            "mirror_channel_id": s.mirror_channel_id,
            "mirror_channel_name": s.mirror_channel_name,
            "slack_webhook_url": s.slack_webhook_url,
            "connected_at": s.connected_at.isoformat() if s.connected_at else None,
        }
        for s in servers
    ]


@servers_router.post("")
def connect_server(payload: ConnectServerRequest, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Connects a server: records which guild and which channel the bot
    should mirror notifications to (or a Slack webhook instead)."""
    server = db.query(ServerConfig).filter_by(guild_id=payload.guild_id).first()
    if not server:
        server = ServerConfig(guild_id=payload.guild_id)
        db.add(server)
    server.guild_name = payload.guild_name
    server.mirror_channel_id = payload.mirror_channel_id
    server.mirror_channel_name = payload.mirror_channel_name
    server.slack_webhook_url = payload.slack_webhook_url
    db.commit()
    return {"ok": True, "guild_id": payload.guild_id}


@servers_router.delete("/{guild_id}")
def disconnect_server(guild_id: str, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    server = db.query(ServerConfig).filter_by(guild_id=guild_id).first()
    if server:
        db.delete(server)
        db.commit()
    return {"ok": True}
