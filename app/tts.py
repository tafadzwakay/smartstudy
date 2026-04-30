import pyttsx3
import uuid
import os

def text_to_speech(text, lang="en"):
    os.makedirs("static", exist_ok=True)

    filename = f"static/voice_{uuid.uuid4()}.wav"

    engine = pyttsx3.init()

    # Speech speed
    engine.setProperty("rate", 170)

    # Volume
    engine.setProperty("volume", 1.0)

    # Select first available voice
    voices = engine.getProperty("voices")
    if voices:
        engine.setProperty("voice", voices[0].id)

    engine.save_to_file(text, filename)
    engine.runAndWait()

    return filename