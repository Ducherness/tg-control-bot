import os
import httpx

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

async def speech_to_text(audio_path: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com/Ducherness/tg-control-bot",
        "X-Title": "tg-control-bot"
    }

    files = {
        "file": open(audio_path, "rb"),
        "model": (None, "openai/whisper-1")
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/audio/transcriptions",
            headers=headers,
            files=files
        )
        r.raise_for_status()
        return r.json()["text"]
