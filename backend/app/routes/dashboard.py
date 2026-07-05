from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InteractionLog, CommandConfig
from app.auth import authenticate, require_admin

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class ConfigUpdate(BaseModel):
    reply_template: str
    mirror_enabled: bool
    ai_enabled: bool
    guild_id: str | None = None  # None for global, or specific guild_id for per-server


@router.post("/auth/login")
def login(payload: LoginRequest):
    token = authenticate(payload.username, payload.password)
    if not token:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": token}


@router.get("/dashboard/logs")
def get_logs(db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    logs = db.query(InteractionLog).order_by(InteractionLog.created_at.desc()).limit(200).all()
    return [
        {
            "id": l.id,
            "interaction_id": l.interaction_id,
            "guild_id": l.guild_id,
            "user_tag": l.user_tag,
            "command_name": l.command_name,
            "command_text": l.command_text,
            "action_taken": l.action_taken,
            "ai_summary": l.ai_summary,
            "status": l.status,
            "error_message": l.error_message,
            "mirror_delivered": l.mirror_delivered,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


@router.get("/dashboard/configs")
def get_configs(guild_id: str | None = None, db: Session = Depends(get_db), 
                _admin: str = Depends(require_admin)):
    """
    Fetch CommandConfigs. 
    If guild_id is provided, return configs for that guild + global (guild_id=None).
    Otherwise, return all configs.
    """
    if guild_id:
        # Get guild-specific configs + global (None) configs
        configs = db.query(CommandConfig).filter(
            (CommandConfig.guild_id == guild_id) | (CommandConfig.guild_id == None)
        ).all()
    else:
        configs = db.query(CommandConfig).all()
    
    return [
        {
            "id": c.id,
            "command_name": c.command_name,
            "guild_id": c.guild_id,
            "reply_template": c.reply_template,
            "mirror_enabled": c.mirror_enabled,
            "ai_enabled": c.ai_enabled,
        }
        for c in configs
    ]


@router.put("/dashboard/configs/{command_name}")
def update_config(command_name: str, payload: ConfigUpdate, db: Session = Depends(get_db),
                   _admin: str = Depends(require_admin)):
    """Update or create a CommandConfig for a specific command and optionally a guild."""
    cfg = db.query(CommandConfig).filter_by(
        command_name=command_name, guild_id=payload.guild_id
    ).first()
    if not cfg:
        cfg = CommandConfig(command_name=command_name, guild_id=payload.guild_id)
        db.add(cfg)
    cfg.reply_template = payload.reply_template
    cfg.mirror_enabled = payload.mirror_enabled
    cfg.ai_enabled = payload.ai_enabled
    db.commit()
    return {"ok": True, "command_name": command_name, "guild_id": payload.guild_id}
