import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { runPrepostCheck } from "../api.js";

function ResultBadge({ result }) {
  if (!result) return null;
  return (
    <p className={result.passed ? "muted" : "error"}>
      <span className={`badge ${result.passed ? "status-resolved" : "status-flagged"}`}>
        {result.passed ? "PASS" : "FAIL"}
      </span>
      {result.reason ? ` — ${result.reason}` : ""}
    </p>
  );
}

function CheckCard({ title, description, tellerId, checkName, buildInput, children }) {
  const run = useMutation({
    mutationFn: () => runPrepostCheck(checkName, { tellerId, input: buildInput() }),
  });
  return (
    <div className="suspect">
      <div className="suspect-head">
        <span className="badge signature">{title}</span>
        <span className="refs">{description}</span>
      </div>
      <div className="denom-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
        {children}
      </div>
      <div className="detail-actions">
        <button className="btn primary" disabled={!tellerId.trim() || run.isPending}
                onClick={() => run.mutate()}>
          {run.isPending ? "Checking…" : "Run check"}
        </button>
      </div>
      {run.error && <p className="error">{String(run.error.message)}</p>}
      <ResultBadge result={run.data} />
    </div>
  );
}

export default function PrepostDemo() {
  const [tellerId, setTellerId] = useState("TLR-001");

  // denom_sum
  const [amount1, setAmount1] = useState("5500");
  const [denoms1, setDenoms1] = useState({ 5000: "1", 500: "1" });

  // cnic_name_match
  const [cnic, setCnic] = useState("42101-1234567-1");
  const [accountHolder, setAccountHolder] = useState("AHMED ALI KHAN");
  const [typedName, setTypedName] = useState("Ahmed Ali Khan");

  // duplicate_check
  const [cbsRef, setCbsRef] = useState("TXN20260711001");
  const [recentRefs, setRecentRefs] = useState("TXN20260711002, TXN20260711003");

  // large_amount_confirm
  const [amount4, setAmount4] = useState("250000");
  const [threshold4, setThreshold4] = useState("50000");
  const [confirmed4, setConfirmed4] = useState(false);

  // sanity
  const [amount5, setAmount5] = useState("5000");
  const [accountType5, setAccountType5] = useState("current");
  const [txnType5, setTxnType5] = useState("cash_out");

  return (
    <div className="panel">
      <h2>Pre-post Validation — Demo</h2>
      <p className="error" style={{ fontWeight: 600 }}>
        Demo / marketing surface only. These 5 checks fire live on typed input
        but are NOT wired into any CBS write-path intercept — no real teller
        posting is validated or blocked by this screen.
      </p>
      <label className="field" style={{ maxWidth: 260 }}>
        <span>Teller ID (used for all checks below)</span>
        <input value={tellerId} onChange={(e) => setTellerId(e.target.value)} />
      </label>

      <CheckCard
        title="denom_sum" description="Denomination breakdown must sum to the stated amount"
        tellerId={tellerId} checkName="denom_sum"
        buildInput={() => ({
          amount: Number(amount1),
          denominations: Object.fromEntries(
            Object.entries(denoms1).filter(([, v]) => Number(v) > 0),
          ),
        })}
      >
        <label><span>Amount</span>
          <input type="number" value={amount1} onChange={(e) => setAmount1(e.target.value)} />
        </label>
        {[5000, 500].map((d) => (
          <label key={d}><span>{d} × count</span>
            <input type="number" value={denoms1[d] ?? ""}
                   onChange={(e) => setDenoms1({ ...denoms1, [d]: e.target.value })} />
          </label>
        ))}
      </CheckCard>

      <CheckCard
        title="cnic_name_match" description="Typed name must fuzzy-match the CBS account holder"
        tellerId={tellerId} checkName="cnic_name_match"
        buildInput={() => ({ cnic, account_holder: accountHolder, typed_name: typedName })}
      >
        <label><span>CNIC</span><input value={cnic} onChange={(e) => setCnic(e.target.value)} /></label>
        <label><span>Account holder (CBS)</span>
          <input value={accountHolder} onChange={(e) => setAccountHolder(e.target.value)} />
        </label>
        <label><span>Typed name</span>
          <input value={typedName} onChange={(e) => setTypedName(e.target.value)} />
        </label>
      </CheckCard>

      <CheckCard
        title="duplicate_check" description="cbs_ref must not already appear in the recent window"
        tellerId={tellerId} checkName="duplicate_check"
        buildInput={() => ({
          cbs_ref: cbsRef,
          recent_refs: recentRefs.split(",").map((s) => s.trim()).filter(Boolean),
        })}
      >
        <label><span>cbs_ref</span><input value={cbsRef} onChange={(e) => setCbsRef(e.target.value)} /></label>
        <label style={{ gridColumn: "span 2" }}><span>Recent refs (comma-separated)</span>
          <input value={recentRefs} onChange={(e) => setRecentRefs(e.target.value)} />
        </label>
      </CheckCard>

      <CheckCard
        title="large_amount_confirm" description="Amounts above threshold require explicit confirmation"
        tellerId={tellerId} checkName="large_amount_confirm"
        buildInput={() => ({
          amount: Number(amount4), threshold: Number(threshold4), confirmed: confirmed4,
        })}
      >
        <label><span>Amount</span>
          <input type="number" value={amount4} onChange={(e) => setAmount4(e.target.value)} />
        </label>
        <label><span>Threshold</span>
          <input type="number" value={threshold4} onChange={(e) => setThreshold4(e.target.value)} />
        </label>
        <label><span>Confirmed?</span>
          <input type="checkbox" checked={confirmed4}
                 onChange={(e) => setConfirmed4(e.target.checked)} />
        </label>
      </CheckCard>

      <CheckCard
        title="sanity" description="Amount must be positive for the given account/txn type"
        tellerId={tellerId} checkName="sanity"
        buildInput={() => ({ amount: Number(amount5), account_type: accountType5, txn_type: txnType5 })}
      >
        <label><span>Amount</span>
          <input type="number" value={amount5} onChange={(e) => setAmount5(e.target.value)} />
        </label>
        <label><span>Account type</span>
          <select value={accountType5} onChange={(e) => setAccountType5(e.target.value)}>
            <option value="current">current</option>
            <option value="savings">savings</option>
          </select>
        </label>
        <label><span>Txn type</span>
          <select value={txnType5} onChange={(e) => setTxnType5(e.target.value)}>
            <option value="cash_out">cash_out</option>
            <option value="cash_in">cash_in</option>
          </select>
        </label>
      </CheckCard>
    </div>
  );
}
