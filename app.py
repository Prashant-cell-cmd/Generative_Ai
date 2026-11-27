from textwrap import dedent
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "transcriptions.db"
whisper_model = None


app = FastAPI(
    title="Speech to Text API",
    description=dedent("""
        ## Speech to Text Application

        A REST API for managing speech transcription records.

        ### Features
        - Create transcription records.
        - Retrieve transcription history.
        - Update existing transcriptions.
        - Delete transcription records.
        - Convert uploaded audio into text.

        ### Technology
        - Python
        - FastAPI
        - SQLite
        - Faster Whisper
    """).strip(),
    version="1.0.0",
    contact={
        "name": "API Support",
    },
    docs_url="/docs",
    redoc_url="/redoc",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class TranscriptionCreate(BaseModel):
    """Request model for creating a transcription."""

    text: str = Field(
        min_length=1,
        description="Transcribed text",
        examples=["Hello world"],
    )
    language: str = Field(
        default="en-US",
        description="Language code of the transcription",
        examples=["en-US", "hi-IN"],
    )


class TranscriptionUpdate(BaseModel):
    """Request model for updating a transcription."""

    text: str = Field(
        min_length=1,
        description="Updated transcription text",
        examples=["Updated transcription"],
    )
    language: str | None = Field(
        default=None,
        description="Optional language code",
    )


@contextmanager
def get_db():
    """Create a database connection and manage transactions."""

    connection = sqlite3.connect(DB_PATH, timeout=10)
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
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


@app.get(
    "/",
    summary="Get application homepage",
    description="Returns the Speech to Text application homepage.",
    include_in_schema=False,
)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get(
    "/api/transcriptions",
    summary="List all transcriptions",
    description="Retrieve all saved transcription records.",
    response_description="List of transcription records",
    responses={
        200: {"description": "Transcriptions retrieved successfully"},
    },
)
def list_transcriptions():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM transcriptions ORDER BY created_at DESC"
        ).fetchall()

    return [dict(row) for row in rows]


@app.post(
    "/api/transcriptions",
    status_code=201,
    summary="Create a transcription",
    description="Create and save a new transcription record.",
    response_description="The newly created transcription",
    responses={
        201: {"description": "Transcription created successfully"},
        422: {"description": "Invalid transcription data"},
    },
)
def create_transcription(payload: TranscriptionCreate):
    text = payload.text.strip()

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Text cannot be blank",
        )

    now = current_timestamp()

    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO transcriptions
            (text, language, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (text, payload.language, now, now),
        )

        row = db.execute(
            "SELECT * FROM transcriptions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return dict(row)


@app.put(
    "/api/transcriptions/{transcription_id}",
    summary="Update a transcription",
    description="Update the text and optionally the language of a transcription.",
    response_description="The updated transcription",
    responses={
        200: {"description": "Transcription updated successfully"},
        404: {"description": "Transcription not found"},
        422: {"description": "Invalid transcription data"},
    },
)
def update_transcription(
    transcription_id: int,
    payload: TranscriptionUpdate,
):
    text = payload.text.strip()

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Text cannot be blank",
        )

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


@app.delete(
    "/api/transcriptions/{transcription_id}",
    status_code=204,
    summary="Delete a transcription",
    description="Permanently delete a transcription by its ID.",
    responses={
        204: {"description": "Transcription deleted successfully"},
        404: {"description": "Transcription not found"},
    },
)
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


@app.post(
    "/api/transcribe",
    summary="Convert audio into text",
    description=(
        "Upload an audio recording and convert speech into text "
        "using the Faster Whisper model."
    ),
    response_description="The transcribed text",
    responses={
        200: {"description": "Audio transcribed successfully"},
        422: {"description": "No speech detected or invalid audio"},
        503: {"description": "Local Whisper is not installed"},
    },
)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file to transcribe"),
    language: str = Form(
        default="auto",
        description="Language selection, such as en-US or hi-IN",
    ),
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
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp:
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
