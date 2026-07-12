import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  closeExcess,
  countersignExcess,
  excessRegisterPdfUrl,
  explainExcess,
  getExcessRegister,
  openExcess,
} from "../api.js";
import { pkr } from "./Worklist.jsx";

const today = () => new Date().toISOString().slice(0, 10);

function StateBadge({ state }) {
  return <span className={`badge state-${state}`}>{state}</span>;
}

function KindBadge({ kind }) {
  return <span className={`badge kind-${kind}`}>{kind}</span>;
}

function OpenCaseModal({ onClose }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    branch_code: "UBL-KHI-042",
    teller_id: "",
    business_date: today(),
    entry_kind: "short",
    amount: "",
    opener: "",
    note: "",
  });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const open = useMutation({
    mutationFn: () => openExcess({ ...form, note: form.note || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["excess-register"] });
      onClose();
    },
  });

  const valid = form.teller_id && form.opener && Number(form.amount) > 0;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Open Excess / Short Entry</h2>
        <p className="muted">
          Till doesn't balance against the CBS-declared position. This opens a
          case that requires a second officer's countersign before it can close.
        </p>
        <label className="field">
          <span>Branch code</span>
          <input value={form.branch_code} onChange={set("branch_code")} />
        </label>
        <label className="field">
          <span>Teller ID</span>
          <input value={form.teller_id} onChange={set("teller_id")} />
        </label>
        <label className="field">
          <span>Business date</span>
          <input type="date" value={form.business_date} onChange={set("business_date")} />
        </label>
        <label className="field">
          <span>Kind</span>
          <select value={form.entry_kind} onChange={set("entry_kind")}>
            <option value="short">Short (till has less than expected)</option>
            <option value="excess">Excess (till has more than expected)</option>
          </select>
        </label>
        <label className="field">
          <span>Amount (PKR)</span>
          <input type="number" min="1" value={form.amount} onChange={set("amount")} />
        </label>
        <label className="field">
          <span>Opener (your teller ID / initials)</span>
          <input value={form.opener} onChange={set("opener")} />
        </label>
        <label className="field">
          <span>Note (optional)</span>
          <input value={form.note} onChange={set("note")} placeholder="e.g. till short by 500" />
        </label>

        {open.error && <p className="error">{String(open.error.message)}</p>}
        <div className="modal-actions">
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={!valid || open.isPending}
                  onClick={() => open.mutate()}>
            {open.isPending ? "Opening…" : "Open case"}
          </button>
        </div>
      </div>
    </div>
  );
}

function CaseDetail({ view, lang, onClose }) {
  const qc = useQueryClient();
  const [officer, setOfficer] = useState("");
  const [resolutionNote, setResolutionNote] = useState("");
  const [explanation, setExplanation] = useState(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["excess-register"] });

  const countersign = useMutation({
    mutationFn: () => countersignExcess({ caseRef: view.case_ref, officer }),
    onSuccess: () => { setOfficer(""); invalidate(); },
  });
  const close = useMutation({
    mutationFn: () => closeExcess({ caseRef: view.case_ref, officer, resolutionNote }),
    onSuccess: () => { setOfficer(""); setResolutionNote(""); invalidate(); },
  });
  const explain = useMutation({
    mutationFn: () => explainExcess({ caseRef: view.case_ref, lang }),
    onSuccess: (r) => setExplanation(r.explanation),
  });

  return (
    <aside className="panel detail">
      <div className="detail-head">
        <h2>
          Case {view.case_ref.slice(0, 8)}… <StateBadge state={view.state} />
        </h2>
        <button className="btn ghost" onClick={onClose}>✕</button>
      </div>
      <div className="cash-summary">
        <div><span>Kind</span><strong><KindBadge kind={view.entry_kind} /></strong></div>
        <div><span>Amount</span><strong>{pkr(Number(view.amount))} PKR</strong></div>
        <div><span>Branch</span><strong>{view.branch_code}</strong></div>
        <div><span>Date</span><strong>{view.business_date}</strong></div>
      </div>

      <dl className="evidence">
        <div><dt>Opener</dt><dd>{view.opener}</dd></div>
        <div><dt>Countersigner</dt><dd>{view.countersigner ?? "—"}</dd></div>
        <div><dt>Closer</dt><dd>{view.closer ?? "—"}</dd></div>
        <div><dt>Reason (opener's note)</dt><dd>{view.reason ?? "—"}</dd></div>
        <div><dt>Resolution</dt><dd>{view.resolution ?? "—"}</dd></div>
      </dl>

      {(explanation ?? "") && (
        <p className={lang === "ur" ? "urdu" : ""} dir={lang === "ur" ? "rtl" : "ltr"} lang={lang}>
          {explanation}
        </p>
      )}

      <div className="detail-actions">
        <button className="btn" disabled={explain.isPending} onClick={() => explain.mutate()}>
          {explain.isPending ? "Groq is writing…" : `Explain in ${lang === "ur" ? "Urdu" : "English"}`}
        </button>

        {view.state === "opened" && (
          <span className="resolve-row">
            <input placeholder="countersigning officer…" value={officer}
                   onChange={(e) => setOfficer(e.target.value)} />
            <button className="btn primary" disabled={!officer.trim() || countersign.isPending}
                    onClick={() => countersign.mutate()}>
              Countersign
            </button>
          </span>
        )}

        {view.state === "countersigned" && (
          <span className="resolve-row">
            <input placeholder="closing officer…" value={officer}
                   onChange={(e) => setOfficer(e.target.value)} />
            <input placeholder="resolution note…" value={resolutionNote}
                   onChange={(e) => setResolutionNote(e.target.value)} />
            <button className="btn primary"
                    disabled={!officer.trim() || !resolutionNote.trim() || close.isPending}
                    onClick={() => close.mutate()}>
              Close
            </button>
          </span>
        )}
      </div>
      {(countersign.error || close.error || explain.error) && (
        <p className="error">{String(countersign.error ?? close.error ?? explain.error)}</p>
      )}
    </aside>
  );
}

export default function ExcessLedger({ lang = "ur" }) {
  const [fromDate, setFromDate] = useState(today());
  const [toDate, setToDate] = useState(today());
  const [branch, setBranch] = useState("");
  const [selected, setSelected] = useState(null);
  const [showOpen, setShowOpen] = useState(false);

  const { data: cases, isLoading, error } = useQuery({
    queryKey: ["excess-register", fromDate, toDate, branch],
    queryFn: () => getExcessRegister({ fromDate, toDate, branch: branch || undefined }),
  });

  const selectedView = cases?.find((c) => c.case_ref === selected) ?? null;

  return (
    <div className="split">
      <section className="panel">
        <div className="detail-head">
          <h2>Digital Excess Ledger</h2>
          <button className="btn primary" onClick={() => setShowOpen(true)}>
            + Open entry
          </button>
        </div>
        <p className="muted">
          Append-only, hash-chained. Every excess/short case requires a second
          officer's countersign — the countersigner can never be the opener.
        </p>

        <div className="report-toolbar no-print">
          <label className="field-label">From</label>
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          <label className="field-label">To</label>
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          <input placeholder="branch (optional)" value={branch}
                 onChange={(e) => setBranch(e.target.value)} />
          <a className="btn" target="_blank" rel="noreferrer"
             href={excessRegisterPdfUrl({ fromDate, toDate, branch: branch || undefined })}>
            Download register PDF
          </a>
        </div>

        {isLoading && <p className="muted">Loading register…</p>}
        {error && <p className="error">Backend unreachable: {error.message}</p>}

        {cases && cases.length === 0 && (
          <p className="muted">No excess/short entries in this range.</p>
        )}
        {cases && cases.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Case</th><th>Branch</th><th>Teller</th><th>Date</th>
                <th>Kind</th><th className="num">Amount</th><th>State</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr
                  key={c.case_ref}
                  className={selected === c.case_ref ? "row selected" : "row"}
                  onClick={() => setSelected(c.case_ref)}
                >
                  <td>{c.case_ref.slice(0, 8)}…</td>
                  <td>{c.branch_code}</td>
                  <td>{c.teller_id}</td>
                  <td>{c.business_date}</td>
                  <td><KindBadge kind={c.entry_kind} /></td>
                  <td className="num">{pkr(Number(c.amount))}</td>
                  <td><StateBadge state={c.state} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {selectedView && (
        <CaseDetail view={selectedView} lang={lang} onClose={() => setSelected(null)} />
      )}
      {showOpen && <OpenCaseModal onClose={() => setShowOpen(false)} />}
    </div>
  );
}
