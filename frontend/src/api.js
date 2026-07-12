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

export function ingestSession({ file, meta }) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("meta", JSON.stringify(meta));
  return api("/sessions", { method: "POST", body: fd });
}

// --- v2: Digital Excess Ledger ---------------------------------------------

export const openExcess = (body) => api("/excess-ledger/open", json(body));
export const countersignExcess = ({ caseRef, officer }) =>
  api(`/excess-ledger/${caseRef}/countersign`, json({ officer }));
export const closeExcess = ({ caseRef, officer, resolutionNote }) =>
  api(`/excess-ledger/${caseRef}/close`, json({ officer, resolution_note: resolutionNote }));
export const getExcessRegister = ({ fromDate, toDate, branch }) =>
  api(`/excess-ledger?from_date=${fromDate}&to_date=${toDate}${branch ? `&branch=${branch}` : ""}`);
export const verifyExcessChain = () => api("/excess-ledger/verify-chain");
export const explainExcess = ({ caseRef, lang = "ur" }) =>
  api(`/excess-ledger/${caseRef}/explain`, json({ lang }));
export const excessRegisterPdfUrl = ({ fromDate, toDate, branch }) =>
  `${BASE}/excess-ledger/report.pdf?from_date=${fromDate}&to_date=${toDate}` +
  (branch ? `&branch=${branch}` : "");

// --- v2: Cheque capture -----------------------------------------------------

export const captureCheque = (body) => api("/cheque", json(body));
export const getCheques = ({ fromDate, toDate, branch }) =>
  api(`/cheque?from_date=${fromDate}&to_date=${toDate}${branch ? `&branch=${branch}` : ""}`);
export const explainChequeVariance = (body) => api("/cheque/explain", json(body));

// --- v2: Pre-post validation (demo-only surface) ----------------------------

export const runPrepostCheck = (checkName, { tellerId, input }) => {
  const path = {
    denom_sum: "/prepost/denom-sum",
    cnic_name_match: "/prepost/cnic-name-match",
    duplicate_check: "/prepost/duplicate-check",
    large_amount_confirm: "/prepost/large-amount-confirm",
    sanity: "/prepost/sanity",
  }[checkName];
  return api(path, json({ teller_id: tellerId, input }));
};
