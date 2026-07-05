import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ingestSession } from "../api.js";

const DENOMS = [5000, 1000, 500, 100, 50, 20, 10, 5, 2, 1];

export default function IngestModal({ onClose }) {
  const qc = useQueryClient();
  const [file, setFile] = useState(null);
  const [openingFloat, setOpeningFloat] = useState("2000000");
  const [counts, setCounts] = useState(Object.fromEntries(DENOMS.map((d) => [d, ""])));
  const [pasteJson, setPasteJson] = useState("");

  const total = DENOMS.reduce((sum, d) => sum + d * (Number(counts[d]) || 0), 0);

  const ingest = useMutation({
    mutationFn: ingestSession,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
      onClose();
    },
  });

  function applyPaste() {
    try {
      const meta = JSON.parse(pasteJson);
      if (meta.opening_float != null) setOpeningFloat(String(meta.opening_float));
      if (meta.denomination_count) {
        setCounts(Object.fromEntries(
          DENOMS.map((d) => [d, String(meta.denomination_count[d] ?? "")]),
        ));
      }
    } catch {
      alert("Invalid JSON");
    }
  }

  function submit() {
    const denomination_count = Object.fromEntries(
      DENOMS.filter((d) => Number(counts[d]) > 0).map((d) => [d, Number(counts[d])]),
    );
    ingest.mutate({
      file,
      meta: { opening_float: Number(openingFloat), denomination_count },
    });
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>New EOD Session</h2>
        <p className="muted">
          CBS export (PIBAS CSV) + the single end-of-day denomination count.
        </p>

        <label className="field">
          <span>PIBAS CSV export</span>
          <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0])} />
        </label>

        <label className="field">
          <span>Opening float (PKR)</span>
          <input value={openingFloat} onChange={(e) => setOpeningFloat(e.target.value)} />
        </label>

        <span className="field-label">Denomination count</span>
        <div className="denom-grid">
          {DENOMS.map((d) => (
            <label key={d}>
              <span>{d.toLocaleString("en-PK")}</span>
              <input
                type="number" min="0" placeholder="0" value={counts[d]}
                onChange={(e) => setCounts({ ...counts, [d]: e.target.value })}
              />
            </label>
          ))}
        </div>
        <p className="denom-total">Counted total: <strong>{total.toLocaleString("en-PK")} PKR</strong></p>

        <details>
          <summary>Paste meta JSON (demo shortcut)</summary>
          <textarea
            rows={3}
            placeholder='{"opening_float": 2000000, "denomination_count": {"5000": 123, ...}}'
            value={pasteJson}
            onChange={(e) => setPasteJson(e.target.value)}
          />
          <button className="btn ghost" onClick={applyPaste}>Fill form from JSON</button>
        </details>

        {ingest.error && <p className="error">{String(ingest.error.message)}</p>}
        <div className="modal-actions">
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn primary"
            disabled={!file || total <= 0 || ingest.isPending}
            onClick={submit}
          >
            {ingest.isPending ? "Running recon…" : "Ingest & reconcile"}
          </button>
        </div>
      </div>
    </div>
  );
}
