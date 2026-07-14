import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getSessions, verifyCashMovementChain, verifyExcessChain } from "../api.js";
import SessionDetail from "./SessionDetail.jsx";

export const pkr = (n) => `${n < 0 ? "−" : ""}${Math.abs(n).toLocaleString("en-PK")}`;

export function StatusBadge({ status }) {
  return <span className={`badge status-${status}`}>{status}</span>;
}

export default function Worklist({ lang = "ur" }) {
  const [selected, setSelected] = useState(null);
  const { data: sessions, isLoading, error } = useQuery({
    queryKey: ["sessions"],
    queryFn: getSessions,
  });

  const [verifyResult, setVerifyResult] = useState(null);
  const [verifyError, setVerifyError] = useState(null);

  const verify = useMutation({
    mutationFn: async () => {
      const [excess, cash] = await Promise.all([
        verifyExcessChain(),
        verifyCashMovementChain(),
      ]);
      return { excess, cash };
    },
    onSuccess: setVerifyResult,
    onError: (error) => setVerifyError(error.message),
  });

  if (isLoading) return <p className="muted">Loading worklist…</p>;
  if (error) return <p className="error">Backend unreachable: {error.message}</p>;

  const order = { flagged: 0, open: 1, resolved: 2, closed: 3 };
  const rows = [...(sessions ?? [])].sort(
    (a, b) => order[a.status] - order[b.status] || b.id - a.id,
  );

  return (
    <div className="split">
      <section className="panel">
        <div className="detail-head">
          <div>
            <h2>EOD Recon Report</h2>
            <p className="muted">
              Worklist of ingested EOD sessions, ranked engine suspects, and the
              signed reconciliation PDF for each — select a row for detail.
            </p>
          </div>
          <button className="btn primary" disabled={verify.isPending}
                  onClick={() => { setVerifyError(null); verify.mutate(); }}>
            {verify.isPending ? "Verifying…" : "Verify Audit Chain"}
          </button>
        </div>
        {verifyResult && (
          <div className="verify-panel">
            <h3>Audit Chain Status</h3>
            <div className="verify-item">
              <span>Excess Ledger</span>
              <strong className={verifyResult.excess.ok ? "status-ok" : "status-broken"}>
                {verifyResult.excess.ok ? "OK" : "Broken"}
              </strong>
            </div>
            <div className="verify-item">
              <span>Cash Movement Ledger</span>
              <strong className={verifyResult.cash.ok ? "status-ok" : "status-broken"}>
                {verifyResult.cash.ok ? "OK" : "Broken"}
              </strong>
            </div>
            <div className="verify-item">
              <span>Cash movement head</span>
              <code>{verifyResult.cash.head}</code>
            </div>
            <div className="verify-item">
              <span>Rows checked</span>
              <strong>{verifyResult.cash.rows}</strong>
            </div>
          </div>
        )}
        {verifyError && <p className="error">Audit chain verification failed: {verifyError}</p>}
        {rows.length === 0 && (
          <p className="muted">No sessions yet — ingest an EOD session to begin.</p>
        )}
        {rows.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>#</th><th>Branch</th><th>Teller</th><th>Date</th>
                <th className="num">Variance (PKR)</th><th className="num">Suspects</th>
                <th className="num">Age</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => (
                <tr
                  key={s.id}
                  className={selected === s.id ? "row selected" : "row"}
                  onClick={() => setSelected(s.id)}
                >
                  <td>{s.id}</td>
                  <td>{s.branch_code}</td>
                  <td>{s.teller_id}</td>
                  <td>{s.business_date}</td>
                  <td className={`num ${s.variance !== 0 ? "variance" : ""}`}>
                    {pkr(s.variance)}
                  </td>
                  <td className="num">{s.suspect_count}</td>
                  <td className="num">{s.age_days}d</td>
                  <td><StatusBadge status={s.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      {selected && (
        <SessionDetail sessionId={selected} onClose={() => setSelected(null)} lang={lang} />
      )}
    </div>
  );
}
