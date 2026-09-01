# AI Trading Platform — Project Progress

> Persistent execution tracker. **Rule: before every next implementation step, re-check this file and the repository call graph to avoid duplicate/loop work.**

Last maintained: 2026-09-01

## Current verified additions
- [x] Upstox V3 realtime market stream transport boundary exists and normalizes broker payloads into the canonical `Tick` contract.
- [x] Upstox stream lifecycle fails closed on disconnect/error and uses reconnect + resync before strategy readiness.
- [x] Realtime fan-out uses bounded queues and atomic fail-closed backpressure.
- [x] Reconnect attempts are now explicitly bounded; exhaustion returns failure instead of retrying indefinitely.
- [x] Regression coverage added for bounded reconnect exhaustion, invalid attempt limits, and successful reconnect before the limit.

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
- [ ] Validate broker-specific order types, status mappings, precision, lot sizes, and rejection handling.
- [x] Validate account identity and route binding for Dhan and Upstox submission paths.

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
