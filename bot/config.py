import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_MAC = os.getenv("TARGET_MAC")
TARGET_HOST = os.getenv("TARGET_HOST", "192.168.0.102")
AGENT_PORT = int(os.getenv("AGENT_PORT", 8000))
ALLOWED_USERS = list(
    map(int, os.getenv("ALLOWED_USERS", "").split(",")) if os.getenv("ALLOWED_USERS") else []
)
