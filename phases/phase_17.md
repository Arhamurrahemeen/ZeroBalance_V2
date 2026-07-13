# Phase 17 — Cash Movement UI + Denomination-view EOD + Verify Chain button

## Goal

Surface the Phase 16 Cash Movement Ledger backend in the dashboard. Add the Cash Movement UI, surface the denomination-view EOD reconciliation table in the session detail side pane, and expose a single Verify Audit Chain button that checks both ledger chains.

## Project Structure

- `frontend/src/App.jsx` — add the Cash Movement tab and render the new screen.
- `frontend/src/api.js` — add `recordCashMovement`, `getCashMovements`, `verifyCashMovementChain`, and `getEodReconciliation`.
- `frontend/src/components/CashMovement.jsx` — new screen for the four event types and denomination grid.
- `frontend/src/components/Worklist.jsx` — add Verify Audit Chain button and result panel.
- `frontend/src/components/SessionDetail.jsx` — add denomination-view table for per-denomination reconciliation.
- `frontend/src/index.css` — add styling for verify panel, denom table, and Cash Movement screen.

## Steps

1. Add a new `CashMovement` component that supports `day_start`, `reissue`, `handover`, and `day_end` contexts.
2. Wire the new screen into `App.jsx` as the fifth dashboard tab.
3. Add frontend API wrappers for the new backend endpoints.
4. Surface the data in `SessionDetail` with a new per-denomination reconciliation table.
5. Add the Verify Audit Chain button in the EOD worklist and fetch both `excess-ledger` and `cash-movement` chain statuses in parallel.
6. Run the frontend build to verify the new screens compile.

## Commands

```bash
docker compose exec backend pytest -q
cd frontend && npm install
cd frontend && npm run build
```

## What to Expect

- The dashboard has a new `Cash Movement` tab.
- The `Cash Movement` screen records all four locked event types with the correct sign-off shape.
- The EOD session detail pane shows a denomination-view table with `opening_plus_reissues`, `physical`, and `variance`.
- The EOD worklist page has a `Verify Audit Chain` button that checks both `excess-ledger` and `cash-movement` chains.
- The frontend build succeeds with no component compile errors.

## Actual outcome

- Implemented `frontend/src/components/CashMovement.jsx` for the four event types and denomination grid.
- Added API wrappers in `frontend/src/api.js` for `recordCashMovement`, `verifyCashMovementChain`, and `getEodReconciliation`.
- Added the new tab in `frontend/src/App.jsx` and rendered the screen.
- Added a verify chain panel in `frontend/src/components/Worklist.jsx`.
- Added the denom-view reconciliation table in `frontend/src/components/SessionDetail.jsx`.
- Added supporting styles in `frontend/src/index.css`.
- Verified the frontend build passes successfully in `D:\ZeroBalance_v2\frontend`.

## Notes

- The EOD denom table intentionally omits invented per-denomination deposits/withdrawals because the backend only supports the real cash movement ledger fields.
- The Verify Chain button checks both ledger chains in parallel and shows both results in the worklist UI.
