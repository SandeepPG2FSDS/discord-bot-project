"""
Run once (and any time you change command definitions):
    python register_commands.py

Registers global slash commands for your Discord application.
Global commands can take up to an hour to propagate; for instant testing
during development, register per-guild instead (see commented alternative).
"""
import requests
from app.config import DISCORD_APPLICATION_ID, DISCORD_BOT_TOKEN

COMMANDS = [
    {
        "name": "report",
        "description": "Submit a report",
        "options": [
            {
                "name": "text",
                "description": "What are you reporting?",
                "type": 3,  # STRING
                "required": True,
            }
        ],
    },
    {
        "name": "status",
        "description": "Check the bot's status",
    },
]

URL = f"https://discord.com/api/v10/applications/{DISCORD_APPLICATION_ID}/commands"
HEADERS = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}

if __name__ == "__main__":
    for cmd in COMMANDS:
        resp = requests.post(URL, headers=HEADERS, json=cmd)
        print(cmd["name"], "->", resp.status_code, resp.text[:200])
