async function request(path, opts) {
  const r = await fetch(path, opts);
  let body = null;
  try {
    body = await r.json();
  } catch {
    // Non-JSON error bodies fall through to the generic message below.
  }
  if (!r.ok) {
    const detail = body && (body.error || body.detail);
    throw new Error(detail ? String(detail) : `Request failed (${r.status})`);
  }
  return body;
}

const postJson = (path, payload) =>
  request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const health = () => request("/api/health");

export const analyze = (transcript, languageCode) =>
  postJson("/api/analyze", { transcript, language_code: languageCode });

export const speak = (text, languageCode) =>
  postJson("/api/speak", { text, language_code: languageCode });

export function transcribe(blob) {
  const fd = new FormData();
  fd.append("file", blob, "chunk.webm");
  return request("/api/transcribe", { method: "POST", body: fd });
}
