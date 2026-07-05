import { useState } from "react";
import Ageing from "./components/Ageing.jsx";
import IngestModal from "./components/IngestModal.jsx";
import Report from "./components/Report.jsx";
import Rahbar from "./components/Rahbar.jsx";
import Worklist from "./components/Worklist.jsx";

const TABS = [
  ["worklist", "Exception Worklist"],
  ["ageing", "Ageing"],
  ["report", "EOD Recon Report"],
];

export default function App() {
  const [tab, setTab] = useState("worklist");
  const [showIngest, setShowIngest] = useState(false);
  const [showRahbar, setShowRahbar] = useState(false);
  // Shared EN/UR toggle for Rahbar chat + Groq exception explanations.
  // The EOD Recon Report stays fixed English regardless of this — separate audience.
  const [lang, setLang] = useState("ur");

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-zero">Zero</span>Balance
          <span className="brand-sub">EOD Recon Co-pilot</span>
        </div>
        <nav className="tabs">
          {TABS.map(([id, label]) => (
            <button
              key={id}
              className={tab === id ? "tab active" : "tab"}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="topbar-actions">
          <div className="lang-toggle" title="Rahbar & explanation language">
            <button
              className={lang === "ur" ? "btn ghost active" : "btn ghost"}
              onClick={() => setLang("ur")}
            >
              اردو
            </button>
            <button
              className={lang === "en" ? "btn ghost active" : "btn ghost"}
              onClick={() => setLang("en")}
            >
              EN
            </button>
          </div>
          <button className="btn primary" onClick={() => setShowIngest(true)}>
            + New EOD Session
          </button>
          <button className="btn ghost" onClick={() => setShowRahbar((s) => !s)}>
            رہبر Rahbar
          </button>
        </div>
      </header>

      <main className="content">
        {tab === "worklist" && <Worklist lang={lang} />}
        {tab === "ageing" && <Ageing />}
        {tab === "report" && <Report />}
      </main>

      {showIngest && <IngestModal onClose={() => setShowIngest(false)} />}
      {showRahbar && (
        <Rahbar onClose={() => setShowRahbar(false)} lang={lang} onLangChange={setLang} />
      )}
    </div>
  );
}
