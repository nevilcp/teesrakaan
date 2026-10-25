# 👂 Teesra Kaan: the third ear

A live voice advocate for the **customer's side of the counter**.

Teesra Kaan ("third ear") listens to a conversation between a borrower or policyholder and a loan or insurance agent, then warns the customer in their own language when something is off. Most voice AI works for the institution. This one works for the person across the table.

Built for the Sarvam Campus Connect session with the Sarvam API.

## How it works

```
 mic (12s rolling chunks)
        │
        ▼
 Saaras v4  ──►  Hinglish / regional transcript
        │
        ▼
 Sarvam-105B ──►  extracts terms (principal, tenure, rate, fees, bundled insurance)
        │         and spots tricks (flat rate sold as monthly, "compulsory" insurance, pressure to sign)
        ▼
 calc.py (deterministic) ──►  real annual cost / real return
        │
        ▼
 UI cards + red flags + questions to ask  ──►  Bulbul v3 whispers the top warning back
```

## Why the math is deterministic

The LLM only **extracts the numbers that were said**. It never computes rates or totals. `calc.py` turns "1.5% a month flat" plus fees and bundled insurance into the true annual cost (an IRR on the cash you actually receive), and turns a "guaranteed" maturity amount into the real yearly return. Language models make arithmetic mistakes, and a financial warning cannot afford one.

Example: ₹1 lakh for 24 months at "1.5% a month flat", with a 2% processing fee and ₹5,000 compulsory insurance, costs about **47.5% a year**, not the 18% it sounds like.

## Run it

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your SARVAM_API_KEY in .env
uvicorn app:app --reload --port 8000
```

Open http://localhost:8000 (Chrome or Edge recommended for the microphone).

- **Live:** press _Start listening_ and put the phone or laptop near the conversation. The transcript and warnings update about every 12 seconds.
- **Demo mode (no microphone, no speech credits):** open _Demo mode_, load a sample loan or insurance pitch, and press _Analyze text_.
- Pick the language you want warnings in from the top-right selector. Press _Whisper warning_ to hear it spoken, or leave auto-whisper on.

## Stack

- **Sarvam Saaras v4**: speech-to-text for code-mixed Hinglish and regional speech
- **Sarvam-105B**: term extraction and red-flag analysis
- **Sarvam Bulbul v3**: spoken warnings in the customer's language
- **FastAPI** backend, plain HTML/JS browser front end (no build step)

## Files

| File                | Role                                                                           |
| ------------------- | ------------------------------------------------------------------------------ |
| `app.py`            | FastAPI routes: `/api/transcribe`, `/api/analyze`, `/api/speak`, `/api/health` |
| `sarvam.py`         | Thin async client for the Sarvam APIs                                          |
| `analyzer.py`       | Prompt, LLM extraction, and merging of deterministic flags                     |
| `calc.py`           | Loan and insurance math                                                        |
| `static/index.html` | The whole UI                                                                   |

## Notes

This is a hackathon prototype, not financial advice. Always read the sanction letter and key fact statement before you sign.
