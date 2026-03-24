import os

from dotenv import load_dotenv

load_dotenv()


def _parse_int_list(raw_value: str) -> tuple[int, ...]:
    values = []
    for chunk in raw_value.split(","):
        candidate = chunk.strip()
        if not candidate:
            continue
        try:
            values.append(int(candidate))
        except ValueError:
            continue
    return tuple(values)


BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
TARGET_MAC = (os.getenv("TARGET_MAC") or "").strip()
TARGET_HOST = (os.getenv("TARGET_HOST") or "192.168.0.102").strip()
AGENT_PORT = int((os.getenv("AGENT_PORT") or "8000").strip())
AGENT_TIMEOUT = float((os.getenv("AGENT_TIMEOUT") or "5").strip())
OPENROUTER_API_KEY = (os.getenv("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_MODEL = (os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini").strip()
ALLOWED_USERS = _parse_int_list(os.getenv("ALLOWED_USERS") or "")
