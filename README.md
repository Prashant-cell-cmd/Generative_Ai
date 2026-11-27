# Speech to Text

A real-time, multilingual transcription web app built with FastAPI, SQLite, and the browser Web Speech API.

The project has been locally tested; it has not yet been deployed to a public hosting provider.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`. Microphone access requires a supported browser (primarily Chrome/Edge) on localhost or HTTPS.

The browser Web Speech API provides live transcription where available. If it is unavailable or returns no speech, the recorded audio is sent to the app server and transcribed with local `faster-whisper`; this fallback runs after recording stops. The first fallback use downloads the Whisper `tiny` model. Browser speech recognition may use the browser vendor's online service.

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

## Run tests

```powershell
python -m unittest discover -s tests -v
```
