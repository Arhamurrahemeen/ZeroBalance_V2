import { useState } from "react";
import Ageing from "./components/Ageing.jsx";
import IngestModal from "./components/IngestModal.jsx";
import Report from "./components/Report.jsx";
import Saathi from "./components/Saathi.jsx";
import Worklist from "./components/Worklist.jsx";

const TABS = [
  ["worklist", "Exception Worklist"],
  ["ageing", "Ageing"],
  ["report", "EOD Recon Report"],
];

export default function App() {
  const [tab, setTab] = useState("worklist");
  const [showIngest, setShowIngest] = useState(false);
  const [showSaathi, setShowSaathi] = useState(false);

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
          <button className="btn primary" onClick={() => setShowIngest(true)}>
            + New EOD Session
          </button>
          <button className="btn ghost" onClick={() => setShowSaathi((s) => !s)}>
            ساتھی Saathi
          </button>
        </div>
      </header>

      <main className="content">
        {tab === "worklist" && <Worklist />}
        {tab === "ageing" && <Ageing />}
        {tab === "report" && <Report />}
      </main>

      {showIngest && <IngestModal onClose={() => setShowIngest(false)} />}
      {showSaathi && <Saathi onClose={() => setShowSaathi(false)} />}
    </div>
  );
}
