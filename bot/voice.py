import json
import wave
import subprocess
from vosk import Model, KaldiRecognizer

MODEL = Model("models/vosk-model-small-en-us-0.15")

def recognize(wav_path: str) -> str:
    wf = wave.open(wav_path, "rb")
    rec = KaldiRecognizer(MODEL, wf.getframerate())

    text = ""
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            text += json.loads(rec.Result()).get("text", "")

    text += json.loads(rec.FinalResult()).get("text", "")
    wf.close()
    return text.strip()

async def speech_to_text(audio_path: str) -> str:
    wav_path = audio_path.replace(".ogg", ".wav")

    subprocess.run([
        "ffmpeg", "-y",
        "-i", audio_path,
        "-ar", "16000",
        "-ac", "1",
        wav_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return recognize(wav_path)
