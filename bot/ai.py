import json

import httpx

from bot.config import OPENROUTER_API_KEY, OPENROUTER_MODEL

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """
You are a command parser for a PC control system.

Return ONLY valid JSON.
No explanations. No text outside JSON.

Allowed actions:
- wake
- wake_wait
- shutdown
- sleep
- hibernate
- status
- health
- logs
- tasks
- start_comfyui
- stop_comfyui
- ping
- screenshot
- stats
- volume
- clipboard
- clear_clipboard
- unknown

Examples:
User: turn on my computer
Response: {"action":"wake"}

User: wake the pc and wait
Response: {"action":"wake_wait"}

User: hibernate the laptop
Response: {"action":"hibernate"}

User: show agent logs
Response: {"action":"logs"}

User: list tasks
Response: {"action":"tasks"}

User: start comfyui
Response: {"action":"start_comfyui"}

User: stop comfyui
Response: {"action":"stop_comfyui"}
"""

FALLBACK_RULES = (
    ("clear_clipboard", ("clear clipboard", "clipboard clear", "очисти буфер", "очистить буфер")),
    ("start_comfyui", ("start comfyui", "run comfyui", "запусти comfyui", "включи comfyui")),
    ("stop_comfyui", ("stop comfyui", "kill comfyui", "останови comfyui", "выключи comfyui")),
    ("tasks", ("tasks", "processes", "managed tasks", "задачи", "процессы")),
    ("clipboard", ("clipboard", "буфер", "copied text")),
    ("screenshot", ("screenshot", "screen", "экран", "скрин")),
    ("hibernate", ("hibernate", "гибернация", "гибернируй")),
    ("shutdown", ("shutdown", "turn off", "power off", "выключи", "отключи")),
    ("sleep", ("sleep", "suspend", "спящий", "усыпи")),
    ("wake_wait", ("wake and wait", "wake wait", "разбуди и жди", "включи и жди")),
    ("wake", ("wake", "turn on", "start pc", "включи", "разбуди")),
    ("health", ("health", "agent info", "system info", "здоровье", "инфо")),
    ("logs", ("logs", "log", "журнал", "логи")),
    ("stats", ("stats", "cpu", "ram", "memory", "disk", "стат", "память", "процессор")),
    ("status", ("status", "online", "reachable", "статус", "доступен")),
    ("ping", ("ping", "pong", "пинг")),
    ("volume", ("volume", "mute", "sound", "тише", "громче", "звук")),
)


def fallback_parse_intent(text: str) -> dict:
    normalized = (text or "").strip().lower()
    if not normalized:
        return {"action": "unknown"}

    for action, keywords in FALLBACK_RULES:
        if any(keyword in normalized for keyword in keywords):
            return {"action": action}

    return {"action": "unknown"}


async def parse_intent(text: str) -> dict:
    if not OPENROUTER_API_KEY:
        return fallback_parse_intent(text)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Ducherness/tg-control-bot",
        "X-Title": "tg-control-bot",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(OPENROUTER_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return {"action": parsed.get("action", "unknown")}
    except Exception:
        return fallback_parse_intent(text)
