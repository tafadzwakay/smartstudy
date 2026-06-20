import pyttsx3
import os

os.makedirs('static', exist_ok=True)
engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)
voices = engine.getProperty('voices')
print('Available voices:')
for v in voices:
    print(' -', v.name, '|', v.id)
engine.say('Hello I am SmartStudy your offline tutor.')
engine.runAndWait()
engine.save_to_file('SmartStudy is working fully offline.', 'static/test_voice.wav')
engine.runAndWait()
if os.path.exists('static/test_voice.wav'):
    size = os.path.getsize('static/test_voice.wav')
    print(f'File created successfully. Size: {size} bytes')
else:
    print('File was NOT created.')
