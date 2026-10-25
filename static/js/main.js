import * as api from "./api.js";
import { createRecorder, isSupported } from "./recorder.js";
import {
  renderCost,
  renderFlags,
  renderQuestions,
  renderTerms,
} from "./render.js";
import { SAMPLES } from "./samples.js";
import { $, store, toast } from "./ui.js";

const CHUNK_MS = 12000;
const MIN_NEW_CHARS = 40;
const MIN_TRANSCRIPT_CHARS = 20;
const LANG_KEY = "teesrakaan.lang";

const session = {
  transcript: "",
  analyzedLen: 0,
  analyzing: false,
  rerun: false,
  autoSpoken: false,
  spokenHigh: new Set(),
  whisperText: "",
  audio: null,
};

function resetSession() {
  session.spokenHigh.clear();
  session.autoSpoken = false;
}

function setTranscript(text) {
  session.transcript = text;
  const el = $("transcript");
  el.textContent = text;
  el.scrollTop = el.scrollHeight;
}

function setStatus(text) {
  $("status").textContent = text;
}

function setLive(live) {
  $("micBtn").classList.toggle("is-live", live);
  $("micBtn").classList.toggle("btn-danger", live);
  $("micBtn").classList.toggle("btn-primary", !live);
  $("micLabel").textContent = live ? "Stop" : "Start listening";
  $("dot").classList.toggle("live", live);
}

async function runAnalysis() {
  if (session.analyzing) {
    session.rerun = true;
    return;
  }
  if (session.transcript.trim().length < MIN_TRANSCRIPT_CHARS) return;

  session.analyzing = true;
  session.rerun = false;
  session.analyzedLen = session.transcript.length;
  $("analysisStatus").textContent = "Analyzing…";

  try {
    const result = await api.analyze(session.transcript, $("lang").value);
    const flags = result.red_flags || [];
    renderCost(result.calc);
    renderFlags(flags);
    renderQuestions(result.questions_to_ask || []);
    renderTerms(result);

    session.whisperText = result.whisper_text || "";
    $("whisperBtn").disabled = !session.whisperText;

    const newHigh = flags.filter(
      (f) => f.severity === "high" && !session.spokenHigh.has(f.title_en),
    );
    newHigh.forEach((f) => session.spokenHigh.add(f.title_en));
    if (
      newHigh.length &&
      $("auto").checked &&
      session.whisperText &&
      !session.autoSpoken
    ) {
      session.autoSpoken = true;
      whisper();
    }
  } catch (e) {
    toast("Analysis failed: " + e.message);
  } finally {
    session.analyzing = false;
    $("analysisStatus").textContent = "";
    const hasNewText =
      session.transcript.length - session.analyzedLen >= MIN_NEW_CHARS;
    if (session.rerun || (recorder.listening && hasNewText)) runAnalysis();
  }
}

function appendTranscript(text) {
  if (!text) return;
  setTranscript(session.transcript ? `${session.transcript}\n${text}` : text);
  if (session.transcript.length - session.analyzedLen >= MIN_NEW_CHARS)
    runAnalysis();
}

async function whisper() {
  if (!session.whisperText) return;
  $("whisperBtn").disabled = true;
  try {
    const { audio_b64 } = await api.speak(session.whisperText, $("lang").value);
    if (session.audio) session.audio.pause();
    session.audio = new Audio("data:audio/wav;base64," + audio_b64);
    await session.audio.play();
  } catch (e) {
    toast("Could not play warning: " + e.message);
  } finally {
    $("whisperBtn").disabled = !session.whisperText;
  }
}

const recorder = createRecorder({
  chunkMs: CHUNK_MS,
  onText: appendTranscript,
  onStatus: setStatus,
  onError: toast,
  onFinish: runAnalysis,
});

$("micBtn").onclick = async () => {
  if (recorder.listening) {
    setLive(false);
    recorder.stop();
    return;
  }
  if (!isSupported()) {
    toast("This browser does not support microphone recording.");
    return;
  }
  try {
    resetSession();
    session.analyzedLen = 0;
    setTranscript("");
    await recorder.start();
    setLive(true);
  } catch {
    toast("Microphone permission denied.");
  }
};

$("sampleLoan").onclick = () => ($("demoText").value = SAMPLES.loan);
$("sampleIns").onclick = () => ($("demoText").value = SAMPLES.insurance);
$("demoBtn").onclick = () => {
  const text = $("demoText").value.trim();
  if (text.length < MIN_TRANSCRIPT_CHARS) {
    toast("Enter a longer conversation first.");
    return;
  }
  resetSession();
  setTranscript(text);
  runAnalysis();
};

$("whisperBtn").onclick = whisper;

const savedLang = store(LANG_KEY);
if (savedLang && [...$("lang").options].some((o) => o.value === savedLang)) {
  $("lang").value = savedLang;
}
$("lang").onchange = () => store(LANG_KEY, $("lang").value);

api
  .health()
  .then((h) => {
    if (!h.key_configured) $("banner").hidden = false;
  })
  .catch(() => {});
