import { transcribe } from "./api.js";

const MIN_CHUNK_BYTES = 2048;
const PREFERRED_MIME = "audio/webm;codecs=opus";

export const isSupported = () =>
  Boolean(navigator.mediaDevices && window.MediaRecorder);

/**
 * Records the microphone in complete, self-contained chunks and uploads each
 * one for transcription. Every chunk is a fresh MediaRecorder so each upload
 * is a valid standalone file.
 */
export function createRecorder({
  chunkMs,
  onText,
  onStatus,
  onError,
  onFinish,
}) {
  let stream = null;
  let recorder = null;
  let timer = null;
  let listening = false;
  let uploads = Promise.resolve();

  function enqueueUpload(blob) {
    uploads = uploads.then(async () => {
      if (blob.size < MIN_CHUNK_BYTES) return;
      onStatus("Transcribing…");
      try {
        const { transcript } = await transcribe(blob);
        onText((transcript || "").trim());
      } catch (e) {
        onError("Transcription failed: " + e.message);
      } finally {
        onStatus(listening ? "Listening…" : "Idle");
      }
    });
    return uploads;
  }

  async function finish() {
    stream.getTracks().forEach((t) => t.stop());
    await uploads;
    onStatus("Idle");
    onFinish();
  }

  function startChunk() {
    const options = MediaRecorder.isTypeSupported(PREFERRED_MIME)
      ? { mimeType: PREFERRED_MIME }
      : undefined;
    const rec = new MediaRecorder(stream, options);
    const parts = [];
    recorder = rec;
    rec.ondataavailable = (e) => {
      if (e.data.size) parts.push(e.data);
    };
    rec.onstop = () => {
      enqueueUpload(new Blob(parts, { type: rec.mimeType || "audio/webm" }));
      if (listening) startChunk();
      else finish();
    };
    rec.start();
    timer = setTimeout(() => {
      if (rec.state === "recording") rec.stop();
    }, chunkMs);
  }

  return {
    get listening() {
      return listening;
    },
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      listening = true;
      onStatus("Listening…");
      startChunk();
    },
    stop() {
      listening = false;
      clearTimeout(timer);
      onStatus("Finishing…");
      if (recorder && recorder.state === "recording") recorder.stop();
    },
  };
}
