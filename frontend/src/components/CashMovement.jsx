import { useMutation, useState } from "react";
import { recordCashMovement } from "../api.js";
import { pkr } from "./Worklist.jsx";

const DENOMS = [5000, 1000, 500, 100, 50, 20, 10];
const EVENT_TYPES = [
  { value: "day_start", label: "Opening Float" },
  { value: "reissue", label: "Vault Reissue" },
  { value: "handover", label: "Shift Handover" },
  { value: "day_end", label: "Closing Count" },
];

const defaultForm = () => ({
  event_type: "day_start",
  teller_id: "TLR-001",
  counterparty_id: "",
  om_id: "OM-001",
  session_id: "SES-001",
  signoff_teller: "",
  signoff_counterparty: "",
  signoff_om: "",
  counts: Object.fromEntries(DENOMS.map((d) => [d, ""])),
});

const eventLabel = (type) => {
  switch (type) {
    case "day_start": return "Opening float — receive from OM";
    case "reissue": return "Vault reissue — additional cash";
    case "handover": return "Shift handover — hand over cash to another teller";
    case "day_end": return "Closing count — end-of-day physical tally";
    default: return "Cash movement event";
  }
};

export default function CashMovement() {
  const [form, setForm] = useState(defaultForm());
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [created, setCreated] = useState(null);

  const setField = (key) => (e) => {
    setForm({ ...form, [key]: e.target.value });
    setMessage(null);
    setError(null);
  };

  const setCount = (denom) => (e) => {
    setForm({
      ...form,
      counts: { ...form.counts, [denom]: e.target.value },
    });
    setMessage(null);
    setError(null);
  };

  const total = DENOMS.reduce(
    (sum, denom) => sum + denom * (Number(form.counts[denom]) || 0),
    0,
  );

  const needsCounterparty = form.event_type === "handover";
  const submitValid = Boolean(
    form.teller_id.trim() && form.om_id.trim() && form.session_id.trim() &&
    form.signoff_teller.trim() && form.signoff_om.trim() &&
    Object.values(form.counts).some((value) => Number(value) > 0) &&
    (!needsCounterparty || form.counterparty_id.trim()) &&
    (!needsCounterparty || form.signoff_counterparty.trim())
  );

  const submit = useMutation({
    mutationFn: () => {
      const denominations = Object.fromEntries(
        DENOMS.filter((d) => Number(form.counts[d]) > 0).map((d) => [
          d.toString(), Number(form.counts[d]),
        ]),
      );
      return recordCashMovement({
        event_type: form.event_type,
        teller_id: form.teller_id,
        counterparty_id: form.event_type === "handover" ? form.counterparty_id || null : null,
        om_id: form.om_id,
        session_id: form.session_id,
        denominations,
        signoff_teller: form.signoff_teller,
        signoff_counterparty: form.event_type === "handover" ? form.signoff_counterparty : null,
        signoff_om: form.signoff_om,
      });
    },
    onSuccess: (data) => {
      setCreated(data);
      setMessage("Cash movement event recorded successfully.");
      setError(null);
    },
    onError: (err) => {
      setError(err.message);
      setMessage(null);
    },
  });

  const title = eventLabel(form.event_type);

  return (
    <div className="split">
      <section className="panel">
        <div className="detail-head">
          <div>
            <h2>Cash Movement</h2>
            <p className="muted">
              Record the day-start/reissue/handover/day-end cash event. Every event is
              hash-chained and denomination-broken. Handover requires three signers.
            </p>
          </div>
        </div>

        <label className="field">
          <span>Event type</span>
          <select value={form.event_type} onChange={(e) => {
            setForm({ ...form, event_type: e.target.value });
            setMessage(null);
            setError(null);
          }}>
            {EVENT_TYPES.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <p className="muted">{title}</p>

        <label className="field">
          <span>Teller ID</span>
          <input value={form.teller_id} onChange={setField("teller_id")} />
        </label>
        <label className="field">
          <span>Session ID</span>
          <input value={form.session_id} onChange={setField("session_id")} />
        </label>
        <label className="field">
          <span>OM ID</span>
          <input value={form.om_id} onChange={setField("om_id")} />
        </label>
        {needsCounterparty && (
          <label className="field">
            <span>Counterparty teller ID</span>
            <input value={form.counterparty_id} onChange={setField("counterparty_id")} />
          </label>
        )}

        <span className="field-label">Denomination counts</span>
        <div className="denom-grid">
          {DENOMS.map((d) => (
            <label key={d}>
              <span>{d.toLocaleString("en-PK")}</span>
              <input type="number" min="0" placeholder="0" value={form.counts[d]}
                     onChange={setCount(d)} />
            </label>
          ))}
        </div>
        <p className="denom-total">
          Total recorded: <strong>{pkr(total)} PKR</strong>
        </p>

        <div className="field-grid">
          <label className="field">
            <span>Teller PIN</span>
            <input value={form.signoff_teller} onChange={setField("signoff_teller")} />
          </label>
          {needsCounterparty && (
            <label className="field">
              <span>Counterparty PIN</span>
              <input value={form.signoff_counterparty} onChange={setField("signoff_counterparty")} />
            </label>
          )}
          <label className="field">
            <span>OM PIN</span>
            <input value={form.signoff_om} onChange={setField("signoff_om")} />
          </label>
        </div>

        {message && <p className="muted">{message}</p>}
        {error && <p className="error">{error}</p>}
        {created && (
          <div className="success-card">
            <p className="muted">Event recorded with ID {created.id}.</p>
            <p className="muted">Total amount: {pkr(Number(created.total_amount))} PKR</p>
          </div>
        )}

        <div className="detail-actions">
          <button className="btn primary" disabled={submit.isPending || !submitValid}
                  onClick={() => submit.mutate()}>
            {submit.isPending ? "Recording…" : "Record cash movement"}
          </button>
        </div>
      </section>

      <section className="panel detail">
        <h2>Event guide</h2>
        <p className="muted">
          Use the same screen for every cash movement type. Handover is the only
          event that requires a counterparty and three signoffs.
        </p>
        <dl className="evidence">
          <div><dt>day_start</dt><dd>Opening float from the vault/OM.</dd></div>
          <div><dt>reissue</dt><dd>Mid-day cash top-up from the vault to the teller.</dd></div>
          <div><dt>handover</dt><dd>Cash handover between two tellers, fully signed.</dd></div>
          <div><dt>day_end</dt><dd>Closing count of the physical cash on the desk.</dd></div>
        </dl>
      </section>
    </div>
  );
}
