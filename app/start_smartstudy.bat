@echo off
echo Starting SmartStudy...

echo Starting Ollama...
start "" "C:\Users\HOMEPC\AppData\Local\Programs\Ollama\ollama.exe" serve

echo Waiting for Ollama to load...
timeout /t 5 /nobreak > nul

echo Starting SmartStudy server...
cd C:\Users\HOMEPC\smartstudy
call venv\Scripts\activate
python web_app.py

pause