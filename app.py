from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import analyzer
import sarvam

app = FastAPI(title="Teesra Kaan")
app.mount("/static", StaticFiles(directory="static"), name="static")


class AnalyzeIn(BaseModel):
    transcript: str
    language_code: str = "hi-IN"


class SpeakIn(BaseModel):
    text: str
    language_code: str = "hi-IN"


@app.exception_handler(sarvam.SarvamError)
async def sarvam_error(_, exc: sarvam.SarvamError):
    return JSONResponse(status_code=502, content={"error": exc.body})


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/health")
async def health():
    return {"ok": True, "key_configured": bool(sarvam.KEY)}


@app.post("/api/transcribe")
async def transcribe(file: Annotated[UploadFile, File()]):
    audio = await file.read()
    if len(audio) < 2048:  # silence / empty chunk
        return {"transcript": "", "language_code": None}
    # Browsers send "audio/webm;codecs=opus"; Sarvam only accepts the bare type.
    content_type = (file.content_type or "audio/webm").split(";")[0].strip()
    return await sarvam.transcribe(audio, file.filename or "chunk.webm", content_type)


@app.post("/api/analyze")
async def analyze(body: AnalyzeIn):
    if len(body.transcript.strip()) < 20:
        raise HTTPException(400, "Transcript too short to analyze.")
    return await analyzer.analyze(body.transcript, body.language_code)


@app.post("/api/speak")
async def speak(body: SpeakIn):
    return {"audio_b64": await sarvam.tts(body.text, body.language_code)}
