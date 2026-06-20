import pyttsx3
import uuid
import os

def text_to_speech(text, lang="en"):
    """
    Fully offline text-to-speech using pyttsx3.
    No internet required.
    """
    os.makedirs("static", exist_ok=True)
    filename = f"static/voice_{uuid.uuid4()}.wav"

    try:
        engine = pyttsx3.init()

        # Set speech rate — 160 is natural, not too fast
        engine.setProperty("rate", 160)

        # Set volume to maximum
        engine.setProperty("volume", 1.0)

        # Try to pick the best available voice
        voices = engine.getProperty("voices")
        if voices:
            selected = voices[0]  # default to first voice

            for voice in voices:
                name = voice.name.lower()
                # Prefer a female voice for clarity
                if 'zira' in name or 'hazel' in name or 'susan' in name:
                    selected = voice
                    break
                # Fallback: any english voice
                elif 'english' in name or 'en' in name:
                    selected = voice

            engine.setProperty("voice", selected.id)

        # Save speech to file
        engine.save_to_file(text, filename)
        engine.runAndWait()

        # Confirm file was actually created
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            return filename
        else:
            print("TTS Warning: file was not created.")
            return ""

    except Exception as e:
        print(f"TTS Error: {e}")
        return ""