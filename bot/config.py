import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_MAC = os.getenv("TARGET_MAC")
ALLOWED_USERS = list(
    map(int, os.getenv("ALLOWED_USERS", "").split(",")) if os.getenv("ALLOWED_USERS") else []
)
