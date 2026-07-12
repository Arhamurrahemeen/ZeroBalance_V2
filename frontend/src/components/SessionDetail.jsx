import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { BASE, explainSession, getSession, resolveSession } from "../api.js";
import { StatusBadge, pkr } from "./Worklist.jsx";

const SIGNATURE_LABELS = {
  digit_transposition: "Digit transposition",
  duplicate_posting: "Duplicate posting",
  missed_reversal: "Missed reversal",
  denomination_shortfall: "Denomination shortfall",
  cash_inout_miskey: "Cash in/out miskey",
  wrong_adjacent_account: "Wrong adjacent account",
};

function Suspect({ s, lang }) {
  return (
    <div className="suspect">
      <div className="suspect-head">
        <span className="rank">#{s.rank}</span>
        <span className="badge signature">{SIGNATURE_LABELS[s.signature]}</span>
        <span className="refs">{s.txn_refs.join(", ") || "till count"}</span>
        <span className="num delta">{pkr(s.cash_delta)} PKR</span>
      </div>
      <dl className="evidence">
        {Object.entries(s.evidence).map(([k, v]) => (
          <div key={k}>
            <dt>{k.replaceAll("_", " ")}</dt>
            <dd>{typeof v === "number" ? v.toLocaleString("en-PK") : v}</dd>
          </div>
        ))}
        {s.anomaly_score != null && (
          <div>
            <dt title="Isolation Forest — display only, never affects ranking">
              anomaly (secondary)
            </dt>
            <dd>
              <span className="anomaly-bar">
                <span style={{ width: `${Math.round(s.anomaly_score * 100)}%` }} />
              </span>
              {s.anomaly_score.toFixed(2)}
            </dd>
          </div>
        )}
      </dl>
      {s.explanation_ur && (
        <p className={lang === "ur" ? "urdu" : ""} dir={lang === "ur" ? "rtl" : "ltr"} lang={lang}>
          {s.explanation_ur}
        </p>
      )}
    </div>
  );
}

export default function SessionDetail({ sessionId, onClose, lang = "ur" }) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const { data: s, isLoading } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => getSession(sessionId),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["sessions"] });
    qc.invalidateQueries({ queryKey: ["session", sessionId] });
  };
  const hasAnyExplanation = s?.suspects.some((x) => x.explanation_ur) ?? false;
  const explain = useMutation({
    mutationFn: () => explainSession(sessionId, { lang, force: hasAnyExplanation }),
    onSuccess: invalidate,
  });
  const resolve = useMutation({
    mutationFn: () => resolveSession({ id: sessionId, note }),
    onSuccess: () => { setNote(""); invalidate(); },
  });

  if (isLoading || !s) return <aside className="panel detail"><p className="muted">Loading…</p></aside>;

  return (
    <aside className="panel detail">
      <div className="detail-head">
        <h2>Session #{s.id} <StatusBadge status={s.status} /></h2>
        <button className="btn ghost" onClick={onClose}>✕</button>
      </div>
      <div className="cash-summary">
        <div><span>System</span><strong>{pkr(s.system_cash)}</strong></div>
        <div><span>Counted</span><strong>{pkr(s.counted_cash)}</strong></div>
        <div className={s.variance !== 0 ? "variance" : ""}>
          <span>Variance</span><strong>{pkr(s.variance)}</strong>
        </div>
        <div><span>Txns</span><strong>{s.txn_count}</strong></div>
      </div>

      <h3>Ranked suspects (engine)</h3>
      {s.suspects.length === 0 && <p className="muted">No suspects — session balanced.</p>}
      {s.suspects.map((x) => <Suspect key={x.rank} s={x} lang={lang} />)}

      <div className="detail-actions">
        {s.suspects.length > 0 && (
          <button className="btn primary" disabled={explain.isPending}
                  onClick={() => explain.mutate()}>
            {explain.isPending
              ? "Groq is writing…"
              : hasAnyExplanation
                ? `Re-explain in ${lang === "ur" ? "Urdu" : "English"}`
                : `Explain in ${lang === "ur" ? "Urdu" : "English"}`}
          </button>
        )}
        <a className="btn" href={`${BASE}/sessions/${s.id}/report.pdf`}
           target="_blank" rel="noreferrer">
          Download signed PDF
        </a>
        {(s.status === "flagged" || s.status === "open") && (
          <span className="resolve-row">
            <input
              placeholder="resolution note…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            <button className="btn" disabled={!note.trim() || resolve.isPending}
                    onClick={() => resolve.mutate()}>
              Resolve
            </button>
          </span>
        )}
      </div>
      {(explain.error || resolve.error) && (
        <p className="error">{String(explain.error ?? resolve.error)}</p>
      )}
    </aside>
  );
}
