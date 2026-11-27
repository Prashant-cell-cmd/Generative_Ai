
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from fastapi import UploadFile, File, Form


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "transcriptions.db"
DB_TIMEOUT = 10

whisper_model = None

app = FastAPI(title="Speech to Text")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class TranscriptionCreate(BaseModel):
    text: str = Field(min_length=1)
    language: str = "en-US"


class TranscriptionUpdate(BaseModel):
    text: str = Field(min_length=1)
    language: str | None = None


@contextmanager
def get_db():
    connection = sqlite3.connect(
        DB_PATH,
        timeout=DB_TIMEOUT,
    )
    connection.row_factory = sqlite3.Row

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                language TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def current_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


@app.get("/")
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/transcriptions")
def list_transcriptions():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM transcriptions ORDER BY created_at DESC"
        ).fetchall()

    return [dict(row) for row in rows]


@app.post("/api/transcriptions", status_code=201)
def create_transcription(payload: TranscriptionCreate):
    text = payload.text.strip()

    if not text:
        raise HTTPException(status_code=422, detail="Text cannot be blank")

    now = current_timestamp()

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO transcriptions (text, language, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (text, payload.language, now, now),
        )

        row = db.execute(
            "SELECT * FROM transcriptions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return dict(row)


@app.put("/api/transcriptions/{transcription_id}")
def update_transcription(transcription_id: int, payload: TranscriptionUpdate):
    text = payload.text.strip()

    if not text:
        raise HTTPException(status_code=422, detail="Text cannot be blank")

    now = current_timestamp()

    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM transcriptions WHERE id = ?",
            (transcription_id,),
        ).fetchone()

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Transcription not found",
            )

        language = payload.language or existing["language"]

        db.execute(
            """
            UPDATE transcriptions
            SET text = ?, language = ?, updated_at = ?
            WHERE id = ?
            """,
            (text, language, now, transcription_id),
        )

        row = db.execute(
            "SELECT * FROM transcriptions WHERE id = ?",
            (transcription_id,),
        ).fetchone()

    return dict(row)


@app.delete("/api/transcriptions/{transcription_id}", status_code=204)
def delete_transcription(transcription_id: int):
    with get_db() as db:
        cursor = db.execute(
            "DELETE FROM transcriptions WHERE id = ?",
            (transcription_id,),
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Transcription not found",
            )

    return None


@app.post("/api/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
):
    global whisper_model

    try:
        from faster_whisper import WhisperModel
        import av

        if not getattr(av.open, "_metadata_errors_compatible", False):
            original_av_open = av.open

            def compatible_av_open(*args, **kwargs):
                kwargs.pop("metadata_errors", None)
                return original_av_open(*args, **kwargs)

            compatible_av_open._metadata_errors_compatible = True
            av.open = compatible_av_open

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Local Whisper is not installed",
        )

    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp_path = Path(temp.name)
            temp.write(await audio.read())

        if whisper_model is None:
            whisper_model = WhisperModel(
                "tiny",
                device="cpu",
                compute_type="int8",
            )

        language_code = None

        if language in {"hi-IN", "en-IN"}:
            language_code = "hi" if language == "hi-IN" else "en"

        elif language in {"en-US", "es-ES", "fr-FR"}:
            language_code = {
                "en-US": "en",
                "es-ES": "es",
                "fr-FR": "fr",
            }[language]

        segments, _ = whisper_model.transcribe(
            temp_path,
            language=language_code,
            task="transcribe",
            vad_filter=True,
            beam_size=5,
            best_of=5,
            initial_prompt="Hindi and English mixed Hinglish speech.",
        )

        text = " ".join(
            segment.text.strip() for segment in segments
        ).strip()

        if not text:
            raise HTTPException(
                status_code=422,
                detail="No speech detected",
            )

        return {"text": text}

    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
