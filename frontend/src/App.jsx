import { useState } from "react";
import ChequeCapture from "./components/ChequeCapture.jsx";
import ExcessLedger from "./components/ExcessLedger.jsx";
import IngestModal from "./components/IngestModal.jsx";
import PrepostDemo from "./components/PrepostDemo.jsx";
import Worklist from "./components/Worklist.jsx";

const TABS = [
  ["excess", "Excess Ledger"],
  ["eod", "EOD Recon Report"],
  ["cheque", "Cheque Capture"],
  ["prepost", "Pre-post Demo"],
];

export default function App() {
  const [tab, setTab] = useState("excess");
  const [showIngest, setShowIngest] = useState(false);
  // Shared EN/UR toggle for every Groq explanation surface (EOD suspects,
  // Excess Ledger case explain, cheque variance explain).
  const [lang, setLang] = useState("ur");

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-zero">Zero</span>Balance
          <span className="brand-sub">Bank-teller back-office overlay</span>
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
          <div className="lang-toggle" title="Groq explanation language">
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
          {tab === "eod" && (
            <button className="btn primary" onClick={() => setShowIngest(true)}>
              + New EOD Session
            </button>
          )}
        </div>
      </header>

      <main className="content">
        {tab === "excess" && <ExcessLedger lang={lang} />}
        {tab === "eod" && <Worklist lang={lang} />}
        {tab === "cheque" && <ChequeCapture lang={lang} />}
        {tab === "prepost" && <PrepostDemo />}
      </main>

      {showIngest && <IngestModal onClose={() => setShowIngest(false)} />}
    </div>
  );
}
