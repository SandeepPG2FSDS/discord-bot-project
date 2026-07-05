import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_PUBLIC_KEY = os.environ["DISCORD_PUBLIC_KEY"]
DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
DISCORD_APPLICATION_ID = os.environ["DISCORD_APPLICATION_ID"]

MIRROR_WEBHOOK_URL = os.environ.get("MIRROR_WEBHOOK_URL", "")

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local.db")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
