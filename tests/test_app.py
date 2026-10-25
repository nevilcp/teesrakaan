import pytest

import app as app_module
import sarvam

AUDIO = b"\x1a\x45\xdf\xa3" + b"\0" * 4096
LOAN_LLM_REPLY = {
    "product_type": "loan",
    "loan": {
        "principal": 100000,
        "tenure_months": 24,
        "quoted_rate_percent": 1.5,
        "rate_period": "month",
        "rate_type": "flat",
        "processing_fee_percent": 2,
        "insurance_premium": 5000,
    },
    "insurance": {},
    "red_flags": [],
    "questions_to_ask": ["Kul kharcha kitna hai?"],
    "top_warning": "Savdhaan raho.",
    "real_cost_sentence": "Asli byaaj {REAL_RATE}% hai.",
    "summary_en": "",
}
PITCH = "Sir, one lakh for two years at one point five percent a month flat."


def upload(client, content=AUDIO, content_type="audio/webm;codecs=opus"):
    return client.post(
        "/api/transcribe", files={"file": ("chunk.webm", content, content_type)}
    )


def test_health_needs_no_key(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_index_is_served_from_any_working_directory(client, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "Teesra Kaan" in r.text
    assert client.get("/static/js/main.js").status_code == 200


def test_security_headers_on_every_response(client):
    for path in ("/", "/api/health", "/static/css/styles.css"):
        h = client.get(path).headers
        assert "default-src 'self'" in h["content-security-policy"]
        assert h["permissions-policy"].startswith("microphone=(self)")
        assert h["x-content-type-options"] == "nosniff"
    assert client.get("/api/health").headers["cache-control"] == "no-store"
    assert client.get("/").headers["cache-control"] == "no-cache"


def test_hsts_only_over_https(client):
    assert "strict-transport-security" not in client.get("/").headers
    r = client.get("/", headers={"x-forwarded-proto": "https"})
    assert "strict-transport-security" not in r.headers  # needs uvicorn proxy mode
    https = client.get("https://testserver/")
    assert "max-age=" in https.headers["strict-transport-security"]


def test_docs_and_schema_are_not_exposed(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_analyze_computes_real_cost_in_code_not_in_the_model(client, monkeypatch):
    async def fake_chat(system, user):
        return LOAN_LLM_REPLY

    monkeypatch.setattr(sarvam, "chat_json", fake_chat)
    r = client.post(
        "/api/analyze", json={"transcript": PITCH, "language_code": "hi-IN"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["calc"]["loan"]["real_annual_percent"] == pytest.approx(47.5, abs=0.5)
    assert "47." in body["whisper_text"]
    assert any("Real cost" in f["title_en"] for f in body["red_flags"])


def test_analyze_rejects_short_transcript(client):
    r = client.post("/api/analyze", json={"transcript": "hi"})
    assert r.status_code == 400


def test_analyze_rejects_oversized_transcript(client):
    big = "x" * (app_module.MAX_TRANSCRIPT_CHARS + 1)
    r = client.post("/api/analyze", json={"transcript": big})
    assert r.status_code == 422
    assert "transcript" in r.json()["error"]
    assert "xxxx" not in r.json()["error"]  # never echo the submitted value


def test_unknown_language_is_rejected(client):
    r = client.post("/api/analyze", json={"transcript": PITCH, "language_code": "xx"})
    assert r.status_code == 422
    r = client.post("/api/speak", json={"text": "hello", "language_code": "xx"})
    assert r.status_code == 422


def test_speak_validates_text_length(client):
    assert client.post("/api/speak", json={"text": ""}).status_code == 422
    too_long = "a" * (app_module.MAX_SPEAK_CHARS + 1)
    assert client.post("/api/speak", json={"text": too_long}).status_code == 422


def test_speak_returns_audio(client, monkeypatch):
    async def fake_tts(text, language_code):
        return "UklGRg=="

    monkeypatch.setattr(sarvam, "tts", fake_tts)
    r = client.post("/api/speak", json={"text": "Savdhaan", "language_code": "hi-IN"})
    assert r.json() == {"audio_b64": "UklGRg=="}


def test_transcribe_strips_codec_suffix_and_forwards_audio(client, monkeypatch):
    seen = {}

    async def fake_transcribe(audio, filename, content_type):
        seen.update(size=len(audio), content_type=content_type)
        return {"transcript": "namaste", "language_code": "hi-IN"}

    monkeypatch.setattr(sarvam, "transcribe", fake_transcribe)
    r = upload(client)
    assert r.json()["transcript"] == "namaste"
    assert seen == {"size": len(AUDIO), "content_type": "audio/webm"}


def test_transcribe_skips_silent_chunks_without_calling_sarvam(client, monkeypatch):
    def boom(*_):
        raise AssertionError("Sarvam must not be called for empty audio")

    monkeypatch.setattr(sarvam, "transcribe", boom)
    assert upload(client, content=b"\0" * 100).json()["transcript"] == ""


def test_transcribe_rejects_non_audio(client):
    assert upload(client, content_type="text/html").status_code == 415


def test_transcribe_rejects_oversized_audio(client):
    big = b"\0" * (app_module.MAX_AUDIO_BYTES + 1)
    assert upload(client, content=big).status_code == 413


def test_declared_oversized_body_is_refused_before_reading(client):
    too_big = str(app_module.MAX_BODY_BYTES + 1)
    r = client.post("/api/analyze", content=b"{}", headers={"content-length": too_big})
    assert r.status_code == 413
    assert "content-security-policy" in r.headers


def test_upstream_errors_do_not_leak_details(client, monkeypatch):
    async def fail(system, user):
        raise sarvam.SarvamError(401, "api key sk-secret-123 for account acme")

    monkeypatch.setattr(sarvam, "chat_json", fail)
    r = client.post("/api/analyze", json={"transcript": PITCH})
    assert r.status_code == 502
    assert "sk-secret" not in r.text
    assert "acme" not in r.text


def test_upstream_rate_limit_becomes_503(client, monkeypatch):
    async def busy(text, language_code):
        raise sarvam.SarvamError(429, "slow down")

    monkeypatch.setattr(sarvam, "tts", busy)
    assert client.post("/api/speak", json={"text": "hi"}).status_code == 503


def test_rate_limit_applies_to_api_but_not_health(client, monkeypatch):
    async def fake_tts(text, language_code):
        return "AAAA"

    monkeypatch.setattr(sarvam, "tts", fake_tts)
    monkeypatch.setattr(app_module.limiter, "limit", 3)
    codes = [
        client.post("/api/speak", json={"text": "hi"}).status_code for _ in range(5)
    ]
    assert codes == [200, 200, 200, 429, 429]
    blocked = client.post("/api/speak", json={"text": "hi"})
    assert int(blocked.headers["retry-after"]) >= 1
    assert "error" in blocked.json() or "detail" in blocked.json()
    assert client.get("/api/health").status_code == 200
