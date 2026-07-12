import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { captureCheque, explainChequeVariance, getCheques } from "../api.js";
import { pkr } from "./Worklist.jsx";

const DENOMS = [5000, 1000, 500, 100, 50, 20, 10, 5, 2, 1];
const today = () => new Date().toISOString().slice(0, 10);

const emptyForm = () => ({
  branch_code: "UBL-KHI-042",
  teller_id: "",
  business_date: today(),
  micr: "",
  account_number: "",
  amount: "",
  counts: Object.fromEntries(DENOMS.map((d) => [d, ""])),
});

export default function ChequeCapture({ lang = "ur" }) {
  const qc = useQueryClient();
  const [form, setForm] = useState(emptyForm());
  const [explanation, setExplanation] = useState(null);
  const [fromDate, setFromDate] = useState(today());
  const [toDate, setToDate] = useState(today());
  const [branch, setBranch] = useState("");

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setDenom = (d) => (e) =>
    setForm({ ...form, counts: { ...form.counts, [d]: e.target.value } });

  const total = DENOMS.reduce((sum, d) => sum + d * (Number(form.counts[d]) || 0), 0);

  const { data: cheques } = useQuery({
    queryKey: ["cheques", fromDate, toDate, branch],
    queryFn: () => getCheques({ fromDate, toDate, branch: branch || undefined }),
  });

  const requestBody = () => ({
    branch_code: form.branch_code,
    teller_id: form.teller_id,
    business_date: form.business_date,
    micr: form.micr,
    account_number: form.account_number,
    amount: form.amount,
    denomination_out: Object.fromEntries(
      DENOMS.filter((d) => Number(form.counts[d]) > 0).map((d) => [d, Number(form.counts[d])]),
    ),
  });

  const capture = useMutation({
    mutationFn: () => captureCheque(requestBody()),
    onSuccess: () => {
      setForm(emptyForm());
      setExplanation(null);
      qc.invalidateQueries({ queryKey: ["cheques"] });
    },
  });

  const explain = useMutation({
    mutationFn: () => explainChequeVariance({ ...requestBody(), lang }),
    onSuccess: (r) => setExplanation(r),
  });

  const valid = form.teller_id && form.micr && form.account_number && Number(form.amount) > 0;

  return (
    <div className="split">
      <section className="panel">
        <h2>Cheque Capture</h2>
        <p className="muted">
          Sidecar artifact — not in the CBS write path. MICR account block must
          match the typed account number; denomination-out must sum to the
          cheque amount.
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
          <span>MICR line</span>
          <input value={form.micr} onChange={set("micr")}
                 placeholder="⑈042000123456⑈ ⑆00789012⑆" />
        </label>
        <label className="field">
          <span>Account number (typed)</span>
          <input value={form.account_number} onChange={set("account_number")} />
        </label>
        <label className="field">
          <span>Cheque amount (PKR)</span>
          <input type="number" min="1" value={form.amount} onChange={set("amount")} />
        </label>

        <span className="field-label">Denomination out</span>
        <div className="denom-grid">
          {DENOMS.map((d) => (
            <label key={d}>
              <span>{d.toLocaleString("en-PK")}</span>
              <input type="number" min="0" placeholder="0" value={form.counts[d]}
                     onChange={setDenom(d)} />
            </label>
          ))}
        </div>
        <p className="denom-total">Denomination-out total: <strong>{pkr(total)} PKR</strong></p>

        <div className="modal-actions">
          <button className="btn primary" disabled={!valid || capture.isPending}
                  onClick={() => capture.mutate()}>
            {capture.isPending ? "Capturing…" : "Capture cheque"}
          </button>
          {capture.error && (
            <button className="btn" disabled={!valid || explain.isPending}
                    onClick={() => explain.mutate()}>
              {explain.isPending ? "Groq is writing…" : "Explain rejection"}
            </button>
          )}
        </div>
        {capture.error && <p className="error">{String(capture.error.message)}</p>}
        {explanation && (
          <>
            <p className="muted">Mismatch: {explanation.mismatch_types.join(", ")}</p>
            <p className={lang === "ur" ? "urdu" : ""} dir={lang === "ur" ? "rtl" : "ltr"} lang={lang}>
              {explanation.explanation}
            </p>
          </>
        )}
      </section>

      <section className="panel detail">
        <h2>Register</h2>
        <div className="report-toolbar no-print">
          <label className="field-label">From</label>
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          <label className="field-label">To</label>
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          <input placeholder="branch (optional)" value={branch}
                 onChange={(e) => setBranch(e.target.value)} />
        </div>
        {cheques && cheques.length === 0 && (
          <p className="muted">No cheques captured in this range.</p>
        )}
        {cheques && cheques.length > 0 && (
          <table className="table">
            <thead>
              <tr><th>#</th><th>Teller</th><th>Account</th><th className="num">Amount</th></tr>
            </thead>
            <tbody>
              {cheques.map((c) => (
                <tr key={c.id}>
                  <td>{c.id}</td>
                  <td>{c.teller_id}</td>
                  <td>{c.account_number}</td>
                  <td className="num">{pkr(Number(c.amount))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
