import json
import wave
import subprocess
from vosk import Model, KaldiRecognizer

MODEL_PATH = "models/vosk-model-small-ru-0.22"
model = Model(MODEL_PATH)

async def speech_to_text(audio_path: str) -> str:
    wav_path = audio_path.replace(".ogg", ".wav")

    # ogg → wav (telegram voice)
    subprocess.run([
        "ffmpeg", "-y",
        "-i", audio_path,
        "-ar", "16000",
        "-ac", "1",
        wav_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    wf = wave.open(wav_path, "rb")
    rec = KaldiRecognizer(model, wf.getframerate())

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
