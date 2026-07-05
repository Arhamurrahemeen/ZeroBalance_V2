import { useQuery } from "@tanstack/react-query";
import { getSessions } from "../api.js";
import { pkr } from "./Worklist.jsx";

const BUCKETS = [
  ["0–1 day", (d) => d <= 1],
  ["1–3 days", (d) => d > 1 && d <= 3],
  ["3+ days (escalate)", (d) => d > 3],
];

export default function Ageing() {
  const { data: sessions, isLoading, error } = useQuery({
    queryKey: ["sessions"],
    queryFn: getSessions,
  });
  if (isLoading) return <p className="muted">Loading…</p>;
  if (error) return <p className="error">Backend unreachable: {error.message}</p>;

  const open = (sessions ?? []).filter((s) => s.status === "flagged" || s.status === "open");

  return (
    <section className="panel">
      <h2>Ageing — unresolved exceptions</h2>
      <div className="bucket-grid">
        {BUCKETS.map(([label, match]) => {
          const rows = open.filter((s) => match(s.age_days));
          return (
            <div className="bucket" key={label}>
              <h3>{label}</h3>
              <p className="bucket-count">{rows.length}</p>
              <ul>
                {rows.map((s) => (
                  <li key={s.id}>
                    #{s.id} · {s.teller_id} · {s.business_date} ·{" "}
                    <span className="variance">{pkr(s.variance)} PKR</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
      {open.length === 0 && <p className="muted">Nothing outstanding — all tills reconciled.</p>}
    </section>
  );
}
