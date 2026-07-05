export const BASE = "http://localhost:8000/api/v1";

async function api(path, opts = {}) {
  const r = await fetch(`${BASE}${path}`, opts);
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      msg = (await r.json()).detail ?? msg;
    } catch { /* keep status */ }
    throw new Error(msg);
  }
  return r.json();
}

const json = (body, method = "POST") => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getSessions = () => api("/sessions");
export const getSession = (id) => api(`/sessions/${id}`);
export const resolveSession = ({ id, note }) =>
  api(`/sessions/${id}/resolve`, json({ note, actor: "teller" }));
export const explainSession = (id, { lang = "ur", force = false } = {}) =>
  api(`/sessions/${id}/explain?lang=${lang}&force=${force}`, { method: "POST" });
export const verifyLedger = () => api("/ledger/verify");
export const rahbarQueries = () => api("/rahbar/queries");
export const rahbarAsk = ({ question, lang = "ur" }) =>
  api("/rahbar/ask", json({ question, lang }));

export function ingestSession({ file, meta }) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("meta", JSON.stringify(meta));
  return api("/sessions", { method: "POST", body: fd });
}
