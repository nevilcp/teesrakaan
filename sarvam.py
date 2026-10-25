"""Thin async client for the three Sarvam endpoints we use."""

import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = "https://api.sarvam.ai"
KEY = os.getenv("SARVAM_API_KEY")

KEYTERMS = [
    "EMI",
    "processing fee",
    "flat rate",
    "reducing balance",
    "interest",
    "tenure",
    "foreclosure",
    "prepayment",
    "insurance",
    "premium",
    "maturity",
    "sum assured",
    "bonus",
    "guaranteed return",
    "lakh",
    "hazaar",
    "mahina",
    "byaaj",
    "kisht",
]

_client = httpx.AsyncClient(timeout=httpx.Timeout(60, connect=10))


async def aclose() -> None:
    await _client.aclose()


class SarvamError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"Sarvam API error {status}: {body[:300]}")
        self.status = status
        self.body = body


def _key() -> str:
    if not KEY:
        raise SarvamError(
            500, "SARVAM_API_KEY is not set. Create a .env file (see .env.example)."
        )
    return KEY


def _check(r: httpx.Response) -> httpx.Response:
    if r.status_code >= 300:
        raise SarvamError(r.status_code, r.text)
    return r


async def transcribe(audio: bytes, filename: str, content_type: str) -> dict:
    r = await _client.post(
        f"{BASE}/speech-to-text",
        headers={"api-subscription-key": _key()},
        files={"file": (filename, audio, content_type)},
        data={
            "model": "saaras:v4",
            "language_code": "unknown",
            "keyterms": json.dumps(KEYTERMS),
        },
    )
    j = _check(r).json()
    return {
        "transcript": j.get("transcript") or "",
        "language_code": j.get("language_code"),
    }


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise SarvamError(502, f"Model did not return JSON: {text[:200]}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise SarvamError(
            502, f"Model returned invalid JSON ({e}): {text[:200]}"
        ) from e


async def chat_json(system: str, user: str) -> dict:
    key = _key()
    headers = {"Authorization": f"Bearer {key}", "api-subscription-key": key}
    body = {
        "model": "sarvam-105b",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        # extraction needs no reasoning; "low" burned the whole token budget
        "reasoning_effort": None,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    r = await _client.post(f"{BASE}/v1/chat/completions", headers=headers, json=body)
    if r.status_code in (400, 422):
        body.pop("response_format")
        r = await _client.post(
            f"{BASE}/v1/chat/completions", headers=headers, json=body
        )
    j = _check(r).json()
    return _parse_json(j["choices"][0]["message"].get("content"))


async def tts(text: str, language_code: str) -> str:
    r = await _client.post(
        f"{BASE}/text-to-speech",
        headers={"api-subscription-key": _key()},
        json={
            "text": text[:2400],
            "language_code": language_code,
            "model": "bulbul:v3",
            "pace": 1.0,
        },
    )
    return _check(r).json()["audios"][0]
