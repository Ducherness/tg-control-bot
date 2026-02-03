from openai import OpenAI
import json

client = OpenAI()

SYSTEM_PROMPT = """
You are a command parser for a PC control system.

You MUST return ONLY valid JSON.
You MUST choose one of the allowed actions.

Allowed actions:
- wake
- shutdown
- sleep
- status
- ping
- unknown

Examples:
User: "turn on my computer"
Response: {"action":"wake"}

User: "shut it down"
Response: {"action":"shutdown"}

User: "are you alive?"
Response: {"action":"ping"}
"""

def parse_intent(text: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)
