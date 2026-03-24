import json
import subprocess
import wave
from pathlib import Path

try:
    from vosk import KaldiRecognizer, Model
except ImportError:
    KaldiRecognizer = None
    Model = None

MODEL_PATH = Path("models") / "vosk-model-small-en-us-0.15"
_MODEL = None


def _get_model() -> Model:
    global _MODEL

    if Model is None or KaldiRecognizer is None:
        raise RuntimeError("vosk is not installed. Run `pip install -r requirements.txt` first.")

    if _MODEL is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Vosk model not found: {MODEL_PATH}. Download it before using voice commands."
            )
        _MODEL = Model(str(MODEL_PATH))
    return _MODEL


def recognize(wav_path: Path) -> str:
    model = _get_model()

    with wave.open(str(wav_path), "rb") as wav_file:
        recognizer = KaldiRecognizer(model, wav_file.getframerate())
        text_parts = []

        while True:
            data = wav_file.readframes(4000)
            if not data:
                break
            if recognizer.AcceptWaveform(data):
                text_parts.append(json.loads(recognizer.Result()).get("text", ""))

        text_parts.append(json.loads(recognizer.FinalResult()).get("text", ""))
    return " ".join(part for part in text_parts if part).strip()


async def speech_to_text(audio_path: str) -> str:
    source_path = Path(audio_path)
    wav_path = source_path.with_suffix(".wav")

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-ar",
                "16000",
                "-ac",
                "1",
                str(wav_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return recognize(wav_path)
    finally:
        if wav_path.exists():
            wav_path.unlink()
