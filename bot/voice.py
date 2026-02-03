from openai import OpenAI

client = OpenAI()

def speech_to_text(audio_path: str) -> str:
    with open(audio_path, "rb") as audio:
        transcription = client.audio.transcriptions.create(
            file=audio,
            model="whisper-1"
        )
    return transcription.text.strip()
