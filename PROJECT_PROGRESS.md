# AI Trading Platform — Production Progress

Last maintained: 2026-09-04

## Completed — production hardening
- [x] Regression coverage verifies Dhan order-trade identity mismatch, duplicate trade identity, invalid trade quantities/prices, account mismatch, and valid authoritative trade records.
- [x] Main Dhan HTTP adapter now exposes authoritative `/trades` and `/trades/{orderId}` reads with strict trade identity/account/quantity/price validation.
- [x] Regression coverage verifies order-scoped Dhan trade requests, wrong-order trade rejection, duplicate trade identity, account mismatch, and blank broker order IDs fail closed before transport.
- [x] Startup broker position reconciliation now rejects duplicate broker position symbols instead of aggregating ambiguous authoritative records.
- [x] Regression coverage verifies duplicate broker position identity fails closed.
- [x] Startup recovery now quarantines unexplained live broker orders instead of allowing broker-only exposure to pass the readiness gate.
- [x] Regression coverage verifies broker-only live orders, duplicate broker order identities, and missing local broker identity fail closed.
- [x] Startup broker-order reconciliation now rejects missing or unknown broker order statuses instead of silently ignoring malformed authoritative records.
- [x] Regression coverage verifies missing/unknown broker order status fails closed and known terminal status remains non-live.
- [x] Startup recovery now requires an authoritative broker order snapshot before execution can become READY; missing order state fails closed.
- [x] Regression coverage verifies missing broker order snapshot keeps execution locked.
- [x] Dedicated PostgreSQL reconciliation-safety CI gate runs ambiguous-submission, startup-recovery, risk-reservation, and stale-reservation regression suites after migrations.
- [x] Canonical broker snapshot status normalization now rejects missing/unknown statuses before Dhan snapshots enter reconciliation.
- [x] Regression coverage verifies canonical broker status normalization and fail-closed Dhan snapshot mapping.
- [x] Risk reservation authoritative reconciliation now rejects malformed/non-list broker snapshots before any risk reservation mutation.
- [x] Regression coverage verifies malformed/non-dict broker snapshot records fail closed without changing active risk.
- [x] Stale risk-reservation recovery now fails closed when a stale candidate remains ACTIVE after authoritative reconciliation; completion audit is withheld on that path.
- [x] Regression coverage verifies stale reservation release, missing matches, orphan broker orders, partial-fill resize, recovery audit events, and still-active fail-closed completion.
- [x] Submission client-order IDs are now immutable after resolution; resolved IDs cannot be recycled for a new broker submission.
- [x] Regression coverage verifies resolved submission client-order IDs cannot be reused while unresolved intents remain idempotent.
- [x] PostgreSQL-backed submission-intent regression coverage verifies resolved client-order IDs remain immutable and unresolved replays remain idempotent.
- [x] Reconciliation Safety CI executes the PostgreSQL submission-intent regression suite after migrations.
- [x] Resolved submission intents are now fully immutable: broker bindings/status cannot be mutated after resolution, and repeated resolution is idempotent.
- [x] Regression coverage verifies resolved intent broker binding/status mutation is rejected and repeated resolution is safe.
- [x] Terminal broker lifecycle states now require durable risk-reservation reconciliation before the orchestrator can release its reservation handle.
- [x] Regression coverage verifies missing reconciliation capability fails closed and keeps the reservation held.
- [x] Submission-intent broker bindings now reject unknown/empty lifecycle statuses before mutating durable intent state.
- [x] Regression coverage verifies unsupported broker status cannot bind an intent and supported statuses are canonicalized.
- [x] Live execution now checks for an existing unresolved submission intent before calling the broker, recovering by authoritative client-order identity instead of issuing a duplicate submission.
- [x] Regression coverage verifies an unresolved retry performs zero new broker submissions and unmatched recovery remains blocked.
- [x] Reconciliation Safety CI now executes duplicate-submission recovery regression coverage alongside the PostgreSQL safety suites.
- [x] Broker order lifecycle now persists broker_order_id and rejects broker identity changes within an existing lifecycle.
- [x] Regression coverage verifies lifecycle broker-order identity is immutable and blank identities fail closed.
- [x] Technical-analysis snapshot now requires a non-empty, canonical, monotonic candle sequence before indicators are computed.
- [x] Technical-analysis parameter validation now rejects invalid periods and invalid Bollinger deviation multipliers.
- [x] Technical-analysis regression coverage verifies empty, mixed-identity, non-monotonic, and non-finite candle inputs fail closed.
- [x] ICT/SMC analysis functions now require canonical, monotonic, finite OHLCV candle sequences before analysis.
- [x] ICT/SMC parameter validation now rejects invalid swing lookbacks, liquidity tolerances, and order-block displacement multipliers.
- [x] ICT/SMC regression coverage verifies malformed/mixed/non-finite candle inputs and invalid analysis parameters fail closed, plus deterministic FVG/order-block detection on valid candles.
- [x] Strategy signal generation now validates configuration, market-data identity/freshness, scoring output, MTF identity/bias/score, ATR, and final risk/reward values before returning a candidate.
- [x] Strategy regression coverage verifies invalid configuration, malformed/mismatched data, non-finite scoring/ATR, and deterministic candidate generation fail closed or produce a bounded candidate without broker execution.
- [x] AI decision layer now validates market-data sequences, ML prediction identity/timestamp/label/model metadata, finite signal outputs, configuration, and ML confidence before producing an advisory decision; malformed AI/ML state fails closed and this layer has no broker execution authority.
- [x] AI decision regression coverage verifies invalid confidence/configuration, invalid ML confidence, mismatched/future predictions, explanation integrity, and fail-closed behavior.
- [x] Backtest engine now rejects malformed/non-monotonic/mixed-identity candles, invalid/non-finite configuration, unsupported/non-finite strategy outputs, and invalid fill requests; replay remains isolated from live execution.
- [x] Backtest regression coverage verifies configuration, market-data, and fill-price safety contracts.
- [x] Paper portfolio accounting now validates position/fill/mark/bar numeric state, rejects duplicate-symbol overwrites, and fails closed on incomplete valuation or malformed OHLC ranges.
- [x] Portfolio regression coverage verifies duplicate positions, invalid fills/marks, incomplete valuation, malformed OHLC, and directional short P&L behavior.
- [x] Execution module is now a package with a SQL terminal-settlement adapter, restoring the durable reservation settlement regression contract.
- [x] Market-data broker ingestion now preserves source ordering and fails closed on non-monotonic/future batches instead of sorting malformed input into validity.

## Verified — 2026-09-04
- [x] Trading Safety CI run `33836170503` completed successfully, including the bound-broker recovery contract and live-execution-disabled-by-default checks.
- [x] Latest pre-fix CI run `33837533833`/`33837533840` identified concrete regressions: missing `execution_alert_worker_health` wiring, missing `app.execution.sql_repository`, and three market-data contract failures.
- [x] Those regressions were fixed in commits following the failed run; a new CI cycle is running on `main` commit `2e5283343ea6352b898209b6183e0bd3cdba73c1`.
- [ ] Upstox sandbox profile authentication remains unverified. The latest observed sandbox-auth run still received an empty `UPSTOX_SANDBOX_ACCESS_TOKEN` environment value; the read-only profile call was skipped. No sandbox order was submitted.
- [ ] Latest CI cycle for commit `2e5283343ea6352b898209b6183e0bd3cdba73c1` is pending completion; do not treat it as CI-verified until all required checks pass.

## Pending — ordered by priority

### P0/P1 — Execution & reconciliation runtime verification
- [ ] Validate ambiguous broker submission recovery end-to-end in runtime/CI.
- [ ] Validate startup reconciliation and recovery jobs in runtime/CI.
- [ ] Validate stale reservation recovery audit events in runtime/CI.
- [ ] Validate immutable submission client-order ID behavior in PostgreSQL-backed runtime/CI.
- [ ] Validate duplicate-submission prevention for unresolved intents in PostgreSQL-backed runtime/CI.

### P1 — Trading-system completeness
- [ ] Full market-data pipeline audit.
- [ ] Technical-analysis engine audit — implementation hardening and regression tests added; CI verification pending for the latest commit.
- [ ] SMC/ICT signal implementation audit — implementation hardening and regression tests added; CI verification pending for the latest commit.
- [ ] Strategy/rule engine audit — deterministic signal validation and regression contract added; CI verification pending.
- [x] AI decision/ranking layer audit — advisory decision contract hardened and regression coverage added; CI verification pending.
- [x] Backtesting engine audit — deterministic candle replay contract hardened and regression coverage added; CI verification pending.
- [x] Portfolio/position/P&L accounting audit — implementation hardening and regression contract added; CI verification pending.
- [ ] Paper/sandbox/live mode separation audit.

### P1 — Broker coverage
- [ ] Audit broker adapters and capability declarations.
- [x] Validate canonical pre-submission order type/price/trigger semantics.
- [x] Validate Upstox documented lifecycle status mappings and fail-closed rejection semantics.
- [x] Validate Dhan documented order lifecycle mapping for partial trades and fail-closed fill semantics.
- [ ] Validate broker-specific order types, precision, lot sizes, and rejection handling for remaining adapters.
- [x] Validate account identity and route binding for Dhan and Upstox submission paths.
- [x] Require explicit request identity on account-bound broker routes.
- [x] Prevent unconfigured Dhan snapshot reads from masquerading as authoritative empty broker state.
- [x] Reject malformed Upstox authoritative snapshot payloads before reconciliation.
- [x] Reject fractional Upstox quantities before broker submission; no silent quantity truncation.
- [x] Recover matched durable submission intents during authoritative coordinator reconciliation.
- [x] Bind configured Upstox reconciliation identity without masking contradictory broker account/route/generation fields.
- [x] Validate Dhan authoritative order identity before reconciliation.
- [x] Validate Dhan authoritative trade identity before reconciliation.
- [x] Validate main Dhan trade endpoints and reject blank order IDs before broker transport.

### P2 — Platform / operations
- [ ] Authentication/authorization audit.
- [ ] Secrets/configuration audit.
- [ ] Database migration consistency audit.
