import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { rahbarAsk, rahbarQueries } from "../api.js";

const STRINGS = {
  ur: { ask: "پوچھیں", asking: "…جواب آ رہا ہے", placeholder: "سوال منتخب کریں…" },
  en: { ask: "Ask", asking: "Rahbar is answering…", placeholder: "Select a question…" },
};

export default function Rahbar({ onClose, lang, onLangChange }) {
  const [q, setQ] = useState("");
  const { data: queries } = useQuery({ queryKey: ["rahbar-queries"], queryFn: rahbarQueries });
  const ask = useMutation({ mutationFn: rahbarAsk });
  const t = STRINGS[lang] ?? STRINGS.ur;

  return (
    <aside className="rahbar-drawer">
      <div className="detail-head">
        <h2>رہبر — Rahbar</h2>
        <div className="lang-toggle">
          <button
            className={lang === "ur" ? "btn ghost active" : "btn ghost"}
            onClick={() => { onLangChange("ur"); ask.reset(); }}
          >
            اردو
          </button>
          <button
            className={lang === "en" ? "btn ghost active" : "btn ghost"}
            onClick={() => { onLangChange("en"); ask.reset(); }}
          >
            EN
          </button>
        </div>
        <button className="btn ghost" onClick={onClose}>✕</button>
      </div>
      <p className="muted">SOP &amp; circular Q&amp;A (demo corpus — 10 pre-tested queries).</p>

      <select
        dir={lang === "ur" ? "rtl" : "ltr"}
        value={q}
        onChange={(e) => { setQ(e.target.value); ask.reset(); }}
      >
        <option value="">{t.placeholder}</option>
        {(queries ?? []).map((pair) => (
          <option key={pair.ur} value={pair.ur}>
            {lang === "ur" ? pair.ur : pair.en}
          </option>
        ))}
      </select>
      <button
        className="btn primary"
        disabled={!q || ask.isPending}
        onClick={() => ask.mutate({ question: q, lang })}
      >
        {ask.isPending ? t.asking : t.ask}
      </button>

      {ask.error && <p className="error">{String(ask.error.message)}</p>}
      {ask.data && (
        <div className="rahbar-answer">
          <p
            className={ask.data.lang === "ur" ? "urdu" : ""}
            dir={ask.data.lang === "ur" ? "rtl" : "ltr"}
            lang={ask.data.lang}
          >
            {ask.data.answer}
          </p>
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
