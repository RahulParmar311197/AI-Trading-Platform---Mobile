# AI Trading Platform — Project Progress

> Persistent execution tracker. **Rule: before every next implementation step, re-check this file and the repository call graph to avoid duplicate/loop work.**

Last maintained: 2026-09-01

## Working Rules

1. Target `main` unless explicitly changed.
2. Before changing code: inspect this tracker + repository tree/callers/dependencies.
3. Never recreate an existing subsystem under a second filename/class.
4. Prefer extending the canonical implementation already used by the application.
5. After every code change: verify the changed file, callers, imports, and CI/status where available.
6. Record every completed change and the next verified pending item here.
7. User requested autonomous execution: do not ask the user to run commands; inspect, change, verify, and continue through the repository tools until the blueprint is satisfied.

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
- [x] Traced canonical broker result mapping into `OrderLifecycle`.
- [x] Wired canonical AI execution to reconcile terminal and partial-fill reservation state through the existing `RiskReservationStore`.
- [x] Terminal `FILLED` / `REJECTED` / `CANCELLED` results now reconcile/release the reservation; partial fills reduce the reserved exposure to the remaining quantity.
- [x] Existing store idempotency protects repeated terminal reconciliation.
- [x] Unified API/manual `PreTradeRiskGate` reservations with the durable `RiskReservationStore` when a database-backed resource set is active.
- [x] Added durable reservation adapter binding to the authoritative broker account/route on every execution authorization.
- [x] Made active reservation replay idempotent for the same client order, account/route, and amount.
- [x] Added regression tests for durable reservation reserve/partial-fill/terminal-release behavior.
- [x] Hardened authoritative broker reconciliation so every active durable reservation must have exactly one client-order match before any reservation mutation is applied.
- [x] Added regression coverage proving missing/ambiguous broker matches and incomplete partial-fill facts fail closed without partial reservation mutation.

### Repository cleanup findings
- [x] Audited `backend/app/execution/` for duplicate execution infrastructure.
- [x] Confirmed `app/execution/orchestrator.py`, `sql_repository.py`, `reconcile.py`, and `settlement.py` form a separate legacy/parallel execution stack.
- [x] Confirmed the legacy orchestrator imports the removed `risk_gate`, so it is stale/broken as a standalone path.
- [x] Confirmed no active repository callers were found for the legacy execution orchestrator during the audit.
- [x] Confirmed no repository references to `app.execution.*` were found in the active code search.
- [x] Retired the orphaned legacy execution stack after call-graph verification.
- [x] Removed `backend/app/execution/orchestrator.py`, `sql_repository.py`, `reconcile.py`, and `settlement.py` from the active tree.
- [x] Added CI import smoke validation for canonical backend entrypoints and explicit absence of the retired `app.execution` package.

### Market-data / AI pipeline findings
- [x] Confirmed canonical `Candle` / `MarketTick` / `MarketDataProvider` contract already exists.
- [x] Confirmed AI feature and SMC/technical signal layers consume canonical `Candle[]` directly.
- [x] Confirmed AI market analyst is grounded on deterministic signal snapshots and cannot place orders.
- [x] Confirmed deterministic position sizing already exists and is used by `AITradeIntent`.
- [x] Confirmed canonical AI execution bridge already reaches the existing execution authorization/gateway stack.
- [x] Verified Upstox has quote support but previously had no historical-candle capability.
- [x] Added provider-neutral optional historical-candle capability to `BrokerAdapter` without breaking brokers that do not support it.
- [x] Added Upstox Historical Candle V3 client support using the official V3 endpoint and native OHLCV rows.
- [x] Exposed Upstox historical candles through `UpstoxAdapter` without creating a second candle model or market-data subsystem.
- [x] Verified the existing canonical `RepositoryHistoricalMarketDataProvider` / `HistoricalCandleRepository` boundary is the correct persistence contract.
- [x] Connected the existing Upstox broker historical rows to the canonical `HistoricalMarketDataProvider` contract through `UpstoxHistoricalMarketDataProvider`.
- [x] Added canonical timestamp normalization, timeframe mapping, date-range filtering, Candle validation, chronological ordering, and timestamp deduplication for Upstox historical data.
- [x] Added regression coverage for the Upstox historical-to-canonical-Candle bridge.

### Reconciliation / recovery findings
- [x] Verified `broker_reconciliation.py` remains the pure broker/local validation and invariant engine.
- [x] Verified `ReconciliationEngine` refuses a verified result while durable submission intents remain unresolved.
- [x] Verified `BrokerRouter.reconcile_unresolved_submission_intents()` resolves durable intents only from a complete broker order snapshot and never resubmits automatically.
- [x] Verified canonical `OrderLifecycle` remains the order-state transition owner; reconciliation does not introduce a competing lifecycle.
- [x] Verified submission-intent lifecycle regression coverage exists for restart/reuse of a resolved client order ID.
- [x] Hardened unresolved submission-intent creation so identical request fingerprints are idempotent while fingerprint mismatches fail closed.
- [x] Added file-store and cross-process regression coverage for same-fingerprint replay and fingerprint mismatch.
- [x] Hardened broker submission/recovery so an authoritative broker order is durably bound to the submission intent before the intent is resolved.
- [x] Added regression coverage proving both normal acceptance and timeout-after-acceptance recovery persist the broker order binding before resolution.
- [x] Hardened ambiguous submission recovery to require broker account/route/route-generation identity whenever the original request is account-bound.
- [x] Added regression coverage proving account-bound timeout-after-acceptance recovery preserves canonical broker route identity.
- [x] Hardened durable reservation reconciliation to validate all active reservation-to-broker matches before applying any reservation mutation.
- [x] Added regression coverage for orphaned reservations, ambiguous matches, and incomplete partial-fill facts.

### Broker adapter hardening
- [x] Dhan submission results now pass the canonical broker-update normalization contract with request/account/route identity preserved.
- [x] Dhan immediate `TRADED` placement results now carry authoritative filled quantity and average price when supplied by the broker.
- [x] Dhan immediate `TRADED` results fail closed when fill price is missing rather than fabricating a canonical `FILLED` event.
- [x] Added regression coverage for Dhan canonical fill normalization and fail-closed behavior.
- [x] Upstox account-bound submission results now preserve persisted broker account, route, and route-generation identity through canonical normalization.
- [x] Upstox account-bound route construction now injects the canonical persisted account/route/generation identity into `UpstoxConfig`.
- [x] Upstox cancellation results preserve configured route identity when available.
- [x] Added regression coverage for Upstox account-route identity and route mismatch rejection.

## Pending — ordered by priority

### P0 — Remove/retire duplicate execution stack safely
- [x] Re-run whole-repository import/call-graph search for every `app.execution.*` module.
- [x] Verify tests, scripts, docs, and dynamic imports do not depend on the legacy package.
- [x] Delete/retire only the orphaned legacy modules after verification.
- [x] Add backend CI import validation after cleanup.

### P0 — Canonical execution lifecycle
- [x] Trace every broker lifecycle update into `OrderLifecycle`.
- [x] Ensure terminal broker states release the canonical reservation exactly once.
- [x] Ensure partial fills retain the correct remaining reservation/exposure.
- [x] Ensure repeated lifecycle events are idempotent at the reservation layer.
- [x] Validate reconciliation/order lifecycle integration: broker reconciliation validates authoritative state, durable submission-intent recovery resolves unresolved intents from broker snapshots, and canonical `OrderLifecycle` remains the only order-state transition owner.

### P0 — Production execution integration
- [ ] Trace all API/order entrypoints to the actual broker gateway.
- [ ] Verify AI-generated orders cannot bypass risk, authorization, reservation, or reconciliation.
- [x] Verify non-AI/manual order paths now use the same durable reservation authority as the canonical AI path.
- [x] Verify all configured broker adapters conform to the same execution contract.
- [x] Replace API/manual-order-only in-memory exposure reservation with the canonical durable `RiskReservationStore` where the execution path has sufficient authoritative exposure inputs.

### P1 — Reliability / recovery
- [ ] Validate ambiguous broker submission recovery end-to-end.
- [x] Validate submission-intent uniqueness and fingerprint mismatch behavior under concurrency.
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
- [x] Connect broker historical candles to the existing canonical `MarketDataProvider` / validated `Candle[]` pipeline.
- [ ] Add live/intraday candle ingestion or stream integration using the same canonical candle contract.

### P1 — Broker coverage
- [ ] Audit broker adapters and capability declarations.
- [ ] Validate broker-specific order types, status mappings, precision, lot sizes, and rejection handling.
- [x] Validate account identity and route binding for Dhan and Upstox submission paths.

### P2 — Platform / operations
- [ ] Authentication/authorization audit.
- [ ] Secrets/configuration audit.
- [ ] Database migration consistency audit.
- [ ] Observability: structured logs, metrics, tracing, alerts.
- [ ] CI/CD and deployment readiness audit.
- [ ] Frontend/mobile integration audit.

## Current Architecture of Record

```text
AI Decision / API Manual Order
    ↓
Execution Authorization
    ↓
PreTradeRiskGate
    ↓
RiskReservationStore (durable, cross-worker)
    ↓
LiveExecutionGateway / OrderExecutionService
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
- `Candle` / `MarketTick` / `MarketDataProvider`
- existing AI/SMC/technical signal engines
- existing deterministic `position_sizing`

If an apparent gap is found, first search for an existing implementation and wire/extend it rather than creating a parallel class.

## Progress Estimate

This is a **work tracker, not a fabricated percentage**. A percentage will only be reported after a full repository/blueprint inventory has been re-run against the current `main` tree.
