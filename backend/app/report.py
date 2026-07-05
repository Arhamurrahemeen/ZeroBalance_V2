"""EOD Recon Report PDF (WeasyPrint).

Every generation records the audit-ledger head hash it attests to
(recon_reports row) and is itself ledgered (REPORT_GENERATED).
"""

from __future__ import annotations

import html
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from .db import append_ledger, ledger_head
from .db_models import EodSessionRow, ReconReportRow
from .schemas import SessionDetail
from .service import to_detail

_SIGNATURES = {
    "digit_transposition": "Digit transposition",
    "duplicate_posting": "Duplicate posting",
    "missed_reversal": "Missed reversal",
    "denomination_shortfall": "Denomination shortfall",
    "cash_inout_miskey": "Cash in/out miskey",
    "wrong_adjacent_account": "Wrong adjacent account",
}

_CSS = """
@page { size: A4; margin: 22mm 18mm; }
body { font-family: sans-serif; color: #1A1A18; font-size: 10.5pt; }
h1 { font-family: serif; font-size: 17pt; margin: 0; }
h2 { font-family: serif; font-size: 12pt; margin: 14pt 0 4pt;
     border-bottom: 1.5pt solid #8B7355; padding-bottom: 2pt; }
.meta { color: #6b675e; margin: 3pt 0 0; }
header { border-bottom: 3pt double #8B7355; padding-bottom: 6pt; }
table { width: 100%; border-collapse: collapse; margin-top: 4pt; }
th, td { text-align: left; padding: 3pt 5pt; border-bottom: 0.5pt solid #E5E0D5; }
th { font-size: 8.5pt; letter-spacing: 0.4pt; text-transform: uppercase; color: #8B7355; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.variance { color: #A33B2E; font-weight: bold; }
.suspect { margin: 6pt 0; padding: 5pt 7pt; border-left: 2.5pt solid #8B7355;
           background: #FAF8F3; }
.urdu { direction: rtl; text-align: right; font-family: 'Noto Naskh Arabic', sans-serif;
        font-size: 11pt; line-height: 1.9; margin: 4pt 0 0; }
footer { margin-top: 16pt; border-top: 1pt solid #E5E0D5; padding-top: 6pt;
         font-size: 8.5pt; color: #6b675e; }
.hash { font-family: monospace; font-size: 8pt; color: #8B7355; word-break: break-all; }
"""


def _fmt(n: int) -> str:
    return f"{n:+,}" if n < 0 else f"{n:,}"


def render_html(detail: SessionDetail, head: str, generated_at: datetime) -> str:
    e = html.escape
    denom_rows = "".join(
        f"<tr><td>{d:,}</td><td class='num'>{n}</td><td class='num'>{d * n:,}</td></tr>"
        for d, n in sorted(detail.denomination_count.items(), reverse=True)
    )
    suspect_blocks = "".join(
        f"""<div class="suspect">
          <strong>#{s.rank} {_SIGNATURES[s.signature]}</strong>
          — {e(", ".join(s.txn_refs)) or "till count"} · {_fmt(s.cash_delta)} PKR
          <br/><small>{e(str({k: v for k, v in s.evidence.items()}))}</small>
          {f'<p class="urdu" lang="ur">{e(s.explanation_ur)}</p>' if s.explanation_ur else ""}
        </div>"""
        for s in detail.suspects
    )
    findings = suspect_blocks or "<p>No exceptions — till balanced.</p>"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>{_CSS}</style></head><body>
<header>
  <h1>ZeroBalance — EOD Reconciliation Report</h1>
  <p class="meta">Branch {e(detail.branch_code)} · Teller {e(detail.teller_id)} ·
     {e(detail.business_date)} · status: {e(detail.status)} ·
     generated {generated_at.strftime("%Y-%m-%d %H:%M UTC")}</p>
</header>

<h2>Cash position</h2>
<table>
  <tr><td>System cash (CBS)</td><td class="num">{detail.system_cash:,} PKR</td></tr>
  <tr><td>Counted cash (single EOD count)</td><td class="num">{detail.counted_cash:,} PKR</td></tr>
  <tr class="{'variance' if detail.variance else ''}">
      <td>Variance</td><td class="num">{_fmt(detail.variance)} PKR</td></tr>
  <tr><td>Transactions ingested</td><td class="num">{detail.txn_count}</td></tr>
</table>

<h2>Denomination count</h2>
<table>
  <tr><th>Denomination</th><th class="num">Notes</th><th class="num">Value (PKR)</th></tr>
  {denom_rows}
</table>

<h2>Engine findings (deterministic, ranked)</h2>
{findings}

<footer>
  <p>Audit ledger head at generation: <span class="hash">{e(head)}</span></p>
  <p>Engine ranking is rule-based and reproducible. Urdu explanations are post-hoc
     (Groq) and carry no decision weight. Isolation-Forest scores are secondary,
     display-only signals.</p>
</footer>
</body></html>"""


def generate_report_pdf(db: Session, row: EodSessionRow) -> bytes:
    from weasyprint import HTML  # heavy import, keep lazy

    head = ledger_head(db)
    detail = to_detail(db, row)
    pdf = HTML(string=render_html(detail, head, datetime.now(UTC))).write_pdf()
    db.add(ReconReportRow(session_id=row.id, ledger_hash=head))
    append_ledger(db, actor="system", action="REPORT_GENERATED", payload={
        "session_id": row.id, "ledger_hash": head, "pdf_bytes": len(pdf),
    })
    db.commit()
    return pdf
