# AI Trading Platform — Project Progress

> Persistent execution tracker. **Rule: before every next implementation step, re-check this file and the repository call graph to avoid duplicate/loop work.**

Last maintained: 2026-08-31

## Working Rules

1. Target `main` unless explicitly changed.
2. Before changing code: inspect this tracker + repository tree/callers/dependencies.
3. Never recreate an existing subsystem under a second filename/class.
4. Prefer extending the canonical implementation already used by the application.
5. After every code change: verify the changed file, callers, imports, and CI/status where available.
6. Record every completed change and the next verified pending item here.

## Completed / Verified

### Execution & risk hardening
- [x] Canonical `risk_engine` identified and retained.
- [x] Duplicate lightweight `RiskGate` implementation identified/removed from the active architecture.
- [x] Canonical `AIExecutionOrchestrator` identified.
- [x] Canonical `LiveExecutionGateway` identified.
- [x] Canonical `RiskReservationStore` identified as the real reservation implementation.
- [x] Verified `app_factory.py` constructs/wires `RiskReservationStore` into the canonical execution orchestrator.
- [x] Duplicate standalone `backend/app/risk_reservation.py` provider removed after discovering the existing `RiskReservationStore`.
- [x] Verified canonical reservation store already handles transactional reservation, concurrency locking, release, partial-fill reconciliation, terminal reconciliation, and active exposure accounting.
- [x] Verified broker ambiguity is intentionally fail-closed and reservations remain held until reconciliation.
- [x] Verified `OrderLifecycle` enforces valid order-state transitions and fill invariants.

### Repository cleanup findings
- [x] Audited `backend/app/execution/` for duplicate execution infrastructure.
- [x] Confirmed `app/execution/orchestrator.py`, `sql_repository.py`, `reconcile.py`, and `settlement.py` form a separate legacy/parallel execution stack.
- [x] Confirmed the legacy orchestrator imports the removed `risk_gate`, so it is stale/broken as a standalone path.
- [x] Confirmed no active repository callers were found for the legacy execution orchestrator during the audit.

## Pending — ordered by priority

### P0 — Remove/retire duplicate execution stack safely
- [ ] Re-run whole-repository import/call-graph search for every `app.execution.*` module.
- [ ] Verify tests, scripts, docs, and dynamic imports do not depend on the legacy package.
- [ ] Delete/retire only the orphaned legacy modules after verification.
- [ ] Run backend test/import validation after cleanup.

### P0 — Canonical execution lifecycle
- [ ] Trace every broker lifecycle update into `OrderLifecycle`.
- [ ] Ensure terminal broker states release the canonical reservation exactly once.
- [ ] Ensure partial fills retain the correct remaining reservation/exposure.
- [ ] Ensure repeated lifecycle events are idempotent.
- [ ] Validate reconciliation updates both intent and order state without bypassing canonical lifecycle rules.

### P0 — Production execution integration
- [ ] Trace all API/order entrypoints to the actual broker gateway.
- [ ] Verify AI-generated orders cannot bypass risk, authorization, reservation, or reconciliation.
- [ ] Verify non-AI/manual order paths intentionally use the correct policy boundary.
- [ ] Verify all configured broker adapters conform to the same execution contract.

### P1 — Reliability / recovery
- [ ] Validate submission-intent uniqueness and fingerprint mismatch behavior under concurrency.
- [ ] Validate ambiguous broker submission recovery end-to-end.
- [ ] Validate startup reconciliation and recovery jobs.
- [ ] Validate stale reservation recovery policy and observability.

### P1 — Trading-system completeness
- [ ] Full market-data pipeline audit.
- [ ] Technical-analysis engine audit.
- [ ] SMC/ICT signal implementation audit.
- [ ] Strategy/rule engine audit.
- [ ] AI decision/ranking layer audit.
- [ ] Backtesting engine audit.
- [ ] Portfolio/position/P&L accounting audit.
- [ ] Paper/sandbox/live mode separation audit.

### P1 — Broker coverage
- [ ] Audit broker adapters and capability declarations.
- [ ] Validate broker-specific order types, status mappings, precision, lot sizes, and rejection handling.
- [ ] Validate account identity and route binding.

### P2 — Platform / operations
- [ ] Authentication/authorization audit.
- [ ] Secrets/configuration audit.
- [ ] Database migration consistency audit.
- [ ] Observability: structured logs, metrics, tracing, alerts.
- [ ] CI/CD and deployment readiness audit.
- [ ] Frontend/mobile integration audit.

## Current Architecture of Record

```text
AI Decision
    ↓
AIExecutionOrchestrator
    ↓
risk_engine
    ↓
RiskReservationStore
    ↓
Execution Authorization
    ↓
LiveExecutionGateway
    ↓
Broker Adapter
    ↓
OrderLifecycle / Reconciliation
```

## Do Not Recreate

- `RiskEngine` / `risk_engine`
- `RiskGate`
- `RiskReservationStore`
- `AIExecutionOrchestrator`
- `LiveExecutionGateway`
- `OrderLifecycle`
- submission-intent persistence/recovery

If an apparent gap is found, first search for an existing implementation and wire/extend it rather than creating a parallel class.

## Progress Estimate

This is a **work tracker, not a fabricated percentage**. A percentage will only be reported after a full repository/blueprint inventory has been re-run against the current `main` tree.
