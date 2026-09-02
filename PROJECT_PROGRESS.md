# AI Trading Platform — Project Progress

> Persistent execution tracker. **Rule: before every next implementation step, re-check this file and the repository call graph to avoid duplicate/loop work.**

Last maintained: 2026-09-02

## Current verified additions
- [x] Upstox V3 realtime market stream transport boundary exists and normalizes broker payloads into the canonical `Tick` contract.
- [x] Upstox stream lifecycle fails closed on disconnect/error and uses reconnect + resync before strategy readiness.
- [x] Realtime fan-out uses bounded queues and atomic fail-closed backpressure.
- [x] Reconnect attempts are now explicitly bounded; exhaustion returns failure instead of retrying indefinitely.
- [x] Regression coverage added for bounded reconnect exhaustion, invalid attempt limits, and successful reconnect before the limit.
- [x] Dhan adapter snapshot access fails closed when broker credentials are unavailable; it no longer returns empty collections that could be mistaken for an authoritative zero-exposure broker state.
- [x] Regression coverage added for unconfigured Dhan positions, orders, order lookup, trades, and order-trades access.
- [x] Upstox authoritative order/position/account/trade payloads now reject malformed non-mapping records instead of allowing reconciliation to consume ambiguous data.
- [x] Regression coverage added for malformed Upstox authoritative payloads.
- [x] Canonical broker responses now require quantity equality with the submitted request when submission identity is scoped.
- [x] Regression coverage added for broker/request quantity mismatch.
- [x] Canonical `BrokerOrderRequest` now rejects unsupported sides/order types and invalid MARKET/LIMIT/SL/SL-M price/trigger combinations before broker submission.
- [x] Regression coverage added for pre-submission order parameter semantics.
- [x] Upstox submission now rejects fractional quantities before transport; it no longer silently truncates quantity through `int(...)` conversion.
- [x] Regression coverage verifies fractional quantities are rejected before any broker HTTP call and integer quantities are transmitted exactly.
- [x] Account-bound broker routes now require the request to carry the matching broker account identity; unbound routes reject explicit account identity instead of silently discarding it.
- [x] Regression coverage added for strict broker route/account binding.
- [x] Strict instrument precision constraints reject off-grid prices/quantities and over-limit quantities instead of silently rounding or clamping live orders.
- [x] Regression coverage added for strict instrument precision constraints.
- [x] Coordinator reconciliation now recovers unambiguous durable submission intents from the same authoritative broker snapshot before producing a verified execution context.
- [x] Recovery rejects duplicate broker client-order IDs, incomplete broker identity, and symbol/side/quantity mismatches without resolving the durable intent.
- [x] Regression coverage added for coordinator submission-intent recovery, missing matches, and ambiguous duplicate matches.
- [x] Authoritative risk-reservation reconciliation now requires explicit `remaining_exposure` for partial fills; it no longer derives monetary reservation exposure from broker quantity/filled-quantity fields.
- [x] Regression coverage proves missing/invalid/increasing remaining exposure fails closed without mutating the reservation.
- [x] Risk reservations now permanently reject reuse of a previously consumed terminal `client_order_id`, preventing old broker lifecycle records from being rebound to a new order identity.
- [x] Regression coverage verifies terminal client-order identity cannot be reused.
- [x] Authoritative risk reconciliation now requires broker order account and route identity to exactly match the reconciled scope before any reservation mutation.
- [x] Regression coverage verifies missing, cross-account, and cross-route broker identity fails closed without releasing or resizing risk.
- [x] Authoritative risk reconciliation now requires a unique non-empty `broker_order_id` and rejects duplicate broker-order identities before reservation mutation.
- [x] Regression coverage covers missing and duplicate broker-order identity without releasing or resizing risk.
- [x] Reservation release and single-order reconciliation now refresh the durable reservation after acquiring the account/route scope lock, preventing a stale ORM object from overwriting a concurrent lifecycle mutation.
- [x] Regression coverage verifies both mutation paths execute the post-lock refresh boundary.
- [x] Reconciliation state persistence now uses atomic PostgreSQL/SQLite upsert semantics for account/route state, eliminating the select-then-insert race between concurrent reconciliation writers.
- [x] Regression coverage added for concurrent PostgreSQL reconciliation-state writers.
- [x] Upstox order-trade reconciliation now scopes the broker request by `order_id` and rejects any returned trade carrying a different broker order identity.
- [x] Regression coverage verifies order-scoped trade lookup and fail-closed mismatched trade identity handling.
- [x] Canonical broker normalization now preserves partial fills when an order is subsequently cancelled, while rejecting contradictory full-fill cancellation and missing fill pricing.
- [x] Regression coverage added for partial-fill cancellation semantics.
- [x] Upstox broker lifecycle statuses are now mapped explicitly from the documented status vocabulary; active statuses with partial fills become `PARTIALLY_FILLED`, active statuses claiming a full fill fail closed, and unknown statuses are rejected.
- [x] Regression coverage added for documented Upstox status mapping, partial-fill open orders, contradictory full fills, unknown statuses, and rejected orders carrying fills.

## Pending — ordered by priority

### P0/P1 — Execution & reconciliation runtime verification
- [ ] Validate ambiguous broker submission recovery end-to-end in runtime/CI.
- [ ] Validate startup reconciliation and recovery jobs in runtime/CI.
- [ ] Validate stale reservation recovery audit events in runtime/CI.

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
- [x] Validate canonical pre-submission order type/price/trigger semantics.
- [x] Validate Upstox documented lifecycle status mappings and fail-closed rejection semantics.
- [ ] Validate broker-specific order types, precision, lot sizes, and rejection handling for remaining adapters.
- [x] Validate account identity and route binding for Dhan and Upstox submission paths.
- [x] Require explicit request identity on account-bound broker routes.
- [x] Prevent unconfigured Dhan snapshot reads from masquerading as authoritative empty broker state.
- [x] Reject malformed Upstox authoritative snapshot payloads before reconciliation.
- [x] Reject fractional Upstox quantities before broker submission; no silent quantity truncation.
- [x] Recover matched durable submission intents during authoritative coordinator reconciliation.

### P2 — Platform / operations
- [ ] Authentication/authorization audit.
- [ ] Secrets/configuration audit.
- [ ] Database migration consistency audit.
- [ ] Observability: structured logs, metrics, tracing, alerts.
- [ ] CI/CD and deployment readiness audit.
- [ ] Frontend/mobile integration audit.

## Architecture of Record

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
