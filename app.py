import logging
import math
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AfterValidator, BaseModel, Field

import analyzer
import sarvam
from ratelimit import RateLimiter

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("teesrakaan")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# A 12 s audio chunk is under 200 KB; these leave headroom.
MAX_AUDIO_BYTES = 2 * 1024 * 1024
MAX_BODY_BYTES = 3 * 1024 * 1024
MAX_TRANSCRIPT_CHARS = 30_000
MAX_SPEAK_CHARS = 2_400

limiter = RateLimiter(int(os.getenv("RATE_LIMIT_PER_MINUTE", "40")))

# Same-origin only; /api/speak audio plays from a data: URI.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; media-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await sarvam.aclose()


app = FastAPI(
    title="Teesra Kaan",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _language(code: str) -> str:
    if code not in analyzer.LANG_NAMES:
        raise ValueError("Unsupported language.")
    return code


LanguageCode = Annotated[str, AfterValidator(_language)]


class AnalyzeIn(BaseModel):
    transcript: str = Field(max_length=MAX_TRANSCRIPT_CHARS)
    language_code: LanguageCode = "hi-IN"


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SPEAK_CHARS)
    language_code: LanguageCode = "hi-IN"


def rate_limit(request: Request) -> None:
    # Real client IP when uvicorn runs behind a proxy.
    wait = limiter.check(request.client.host if request.client else "unknown")
    if wait:
        raise HTTPException(
            429,
            "Too many requests. Please wait a moment and try again.",
            headers={"Retry-After": str(math.ceil(wait))},
        )


@app.middleware("http")
async def guard(request: Request, call_next):
    try:
        too_big = int(request.headers.get("content-length") or 0) > MAX_BODY_BYTES
    except ValueError:
        too_big = True
    if too_big:
        response = JSONResponse(
            status_code=413, content={"error": "Request too large."}
        )
    else:
        response = await call_next(request)

    response.headers.update(SECURITY_HEADERS)
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    # no-cache revalidates via ETag; it does not disable caching.
    is_api = request.url.path.startswith("/api/")
    response.headers["Cache-Control"] = "no-store" if is_api else "no-cache"
    return response


@app.exception_handler(sarvam.SarvamError)
async def sarvam_error(_, exc: sarvam.SarvamError):
    # Upstream bodies can hold account details, so only log them.
    log.error("Sarvam API error %s: %s", exc.status, exc.body[:500])
    if exc.status == 429:
        return JSONResponse(
            status_code=503,
            content={"error": "The speech service is busy. Please try again shortly."},
        )
    return JSONResponse(
        status_code=502,
        content={"error": "The speech service had a problem. Please try again."},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc: RequestValidationError):
    # Never echo the submitted value.
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "body")
    return JSONResponse(
        status_code=422,
        content={"error": f"Invalid request ({field}): {first['msg']}"},
    )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
api = APIRouter(prefix="/api", dependencies=[Depends(rate_limit)])


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"ok": True, "key_configured": bool(sarvam.KEY)}


@api.post("/transcribe")
async def transcribe(file: Annotated[UploadFile, File()]):
    # Browsers send "audio/webm;codecs=opus"; Sarvam only accepts the bare type.
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if not content_type.startswith("audio/"):
        raise HTTPException(415, "Unsupported file type. Send an audio recording.")
    audio = await file.read(MAX_AUDIO_BYTES + 1)
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio chunk too large.")
    if len(audio) < 2048:  # silence / empty chunk
        return {"transcript": "", "language_code": None}
    return await sarvam.transcribe(audio, file.filename or "chunk.webm", content_type)


@api.post("/analyze")
async def analyze(body: AnalyzeIn):
    if len(body.transcript.strip()) < 20:
        raise HTTPException(400, "Transcript too short to analyze.")
    return await analyzer.analyze(body.transcript, body.language_code)


@api.post("/speak")
async def speak(body: SpeakIn):
    return {"audio_b64": await sarvam.tts(body.text, body.language_code)}


app.include_router(api)
