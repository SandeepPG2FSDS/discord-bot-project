import time
import requests

from app.config import DISCORD_APPLICATION_ID, DISCORD_BOT_TOKEN, MIRROR_WEBHOOK_URL

DISCORD_API = "https://discord.com/api/v10"
BOT_HEADERS = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
GUILD_TEXT_CHANNEL = 0


def list_bot_guilds() -> list[dict]:
    """Servers the bot has been invited into (Developer Portal invite link),
    so the admin can pick one to connect in the dashboard."""
    resp = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=BOT_HEADERS, timeout=5)
    resp.raise_for_status()
    return [{"id": g["id"], "name": g["name"]} for g in resp.json()]


def list_guild_text_channels(guild_id: str) -> list[dict]:
    """Text channels in a guild the bot can post to, for the channel picker."""
    resp = requests.get(f"{DISCORD_API}/guilds/{guild_id}/channels", headers=BOT_HEADERS, timeout=5)
    resp.raise_for_status()
    return [
        {"id": c["id"], "name": c["name"]}
        for c in resp.json()
        if c.get("type") == GUILD_TEXT_CHANNEL
    ]


def send_channel_message(channel_id: str, content: str) -> bool:
    """Posts as the bot directly to a channel (used for the mirror notification
    when the admin picked a Discord channel rather than a Slack webhook)."""
    try:
        resp = requests.post(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers=BOT_HEADERS,
            json={"content": content},
            timeout=5,
        )
        return resp.status_code < 300
    except requests.RequestException:
        return False


def send_followup_message(interaction_token: str, content: str, max_retries: int = 3) -> bool:
    """Sends the real reply after a deferred ack. Retries with backoff so a
    transient Discord API blip doesn't silently drop the response the user
    is waiting on. Returns True on success."""
    url = f"{DISCORD_API}/webhooks/{DISCORD_APPLICATION_ID}/{interaction_token}"
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json={"content": content}, timeout=5)
            if resp.status_code < 300:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5 * (2 ** attempt))
    return False


def send_mirror_notification(
    text: str,
    max_retries: int = 3,
    slack_webhook_url: str | None = None,
    discord_channel_id: str | None = None,
) -> bool:
    """
    Mirrors a notification to the second channel. Routing, in priority order:
    1. The per-server Slack webhook the admin configured for that guild.
    2. The per-server Discord channel the admin picked for that guild (posted
       via the bot token, not a webhook).
    3. The global MIRROR_WEBHOOK_URL env var, as a fallback for setups that
       haven't connected a server yet.
    Retries with backoff so a briefly-down endpoint doesn't silently drop it.
    """
    if discord_channel_id and not slack_webhook_url:
        for attempt in range(max_retries):
            if send_channel_message(discord_channel_id, text):
                return True
            time.sleep(0.5 * (2 ** attempt))
        return False

    webhook_url = slack_webhook_url or MIRROR_WEBHOOK_URL
    if not webhook_url:
        return False

    is_discord = "discord.com" in webhook_url
    payload = {"content": text} if is_discord else {"text": text}

    for attempt in range(max_retries):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=5)
            if resp.status_code < 300:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5 * (2 ** attempt))  # backoff: 0.5s, 1s, 2s

    return False
