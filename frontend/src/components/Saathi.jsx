import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { saathiAsk, saathiQueries } from "../api.js";

export default function Saathi({ onClose }) {
  const [q, setQ] = useState("");
  const { data: queries } = useQuery({ queryKey: ["saathi-queries"], queryFn: saathiQueries });
  const ask = useMutation({ mutationFn: saathiAsk });

  return (
    <aside className="saathi-drawer">
      <div className="detail-head">
        <h2>ساتھی — Saathi</h2>
        <button className="btn ghost" onClick={onClose}>✕</button>
      </div>
      <p className="muted">SOP &amp; circular Q&amp;A (demo corpus — 10 pre-tested queries).</p>

      <select
        dir="rtl"
        value={q}
        onChange={(e) => { setQ(e.target.value); ask.reset(); }}
      >
        <option value="">سوال منتخب کریں…</option>
        {(queries ?? []).map((query) => (
          <option key={query} value={query}>{query}</option>
        ))}
      </select>
      <button
        className="btn primary"
        disabled={!q || ask.isPending}
        onClick={() => ask.mutate(q)}
      >
        {ask.isPending ? "…جواب آ رہا ہے" : "پوچھیں"}
      </button>

      {ask.error && <p className="error">{String(ask.error.message)}</p>}
      {ask.data && (
        <div className="saathi-answer">
          <p className="urdu" dir="rtl" lang="ur">{ask.data.answer_ur}</p>
          <div className="sources">
            {ask.data.sources.map((s) => (
              <span className="badge source" key={s.title} title={s.source}>
                {s.title} · {s.score.toFixed(2)}
              </span>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}
