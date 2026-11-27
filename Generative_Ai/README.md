# Speech to Text

A real-time, multilingual transcription web app built with FastAPI, SQLite, and the browser Web Speech API.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`. Microphone recognition works in a supported browser (primarily Chrome/Edge) on localhost or HTTPS.

## Features

- Real-time browser microphone transcription
- Local Whisper fallback when the browser speech service is unavailable
- English, Hindi/Hinglish, Spanish, and French recognition options
- SQLite persistence
- Full transcription history
- Create, edit, and delete operations
- Live waveform studio
- Search, export, copy, text-to-speech, and keyboard save shortcut
- Responsive light/dark dashboard
