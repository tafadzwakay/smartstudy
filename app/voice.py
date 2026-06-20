import whisper
import os
import tempfile

# Load the model once at startup for better performance
model = None

def get_whisper_model():
    """Lazy load the Whisper model"""
    global model
    if model is None:
        print("Loading Whisper model (this may take a moment)...")
        model = whisper.load_model("base")
    return model

def speech_to_text(audio_path, language=None):
    """
    Convert speech to text with support for multiple languages
    """
    try:
        model = get_whisper_model()

        # Set language hints for better accuracy
        options = {}
        if language:
            if language.lower() in ['sn', 'shona']:
                # Whisper doesn't have native Shona support, use English with African accent detection
                options = {"language": "en"}
            elif language.lower().startswith('en'):
                options = {"language": "en"}
            else:
                options = {"language": language[:2]}

        result = model.transcribe(audio_path, **options)
        text = result["text"].strip()

        # Clean up the text
        if text:
            # Remove extra whitespace and normalize
            text = ' '.join(text.split())
            return text
        else:
            return ""

    except Exception as e:
        print(f"Speech-to-text error: {e}")
        return ""

def detect_language(text):
    """
    Simple language detection for Shona vs English
    """
    # Common Shona words/phrases
    shona_indicators = [
        'ndiri', 'uri', 'ari', 'tiri', 'muri', 'vari',  # to be
        'ndakaita', 'wakaita', 'akaita',  # did
        'ndichaita', 'uchaita', 'achaita',  # will do
        'chii', 'nei', 'sei',  # what, why, how
        'pano', 'apo', 'uko',  # here, there
        'nhasi', 'mangwana', 'nezuro',  # today, tomorrow, yesterday
        'mukoma', 'mukadzi', 'mwana',  # brother, woman, child
        'chikoro', 'mudzidzi', 'mudzidzisi',  # school, student, teacher
        'zimbabwe', 'harare', 'bulawayo'  # place names
    ]

    text_lower = text.lower()
    shona_count = sum(1 for word in shona_indicators if word in text_lower)

    # If we find Shona indicators, classify as Shona
    if shona_count >= 2:
        return 'sn'
    else:
        return 'en'