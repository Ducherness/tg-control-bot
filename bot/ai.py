import os
import httpx
import json

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """
You are a command parser for a PC control system.

Return ONLY valid JSON.
No explanations. No text outside JSON.

Allowed actions:
- wake
- shutdown
- sleep
- status
- ping
- unknown

Examples:
User: turn on my computer
Response: {"action":"wake"}

User: shut it down
Response: {"action":"shutdown"}
"""

async def parse_intent(text: str) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Ducherness/tg-control-bot",
        "X-Title": "tg-control-bot"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "temperature": 0,
        "response_format": { "type": "json_object" }
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(OPENROUTER_URL, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    return json.loads(data["choices"][0]["message"]["content"])
