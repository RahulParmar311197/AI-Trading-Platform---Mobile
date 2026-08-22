# AI Trading Platform

Android-first multi-market trading platform based on `AI_TRADING_PLATFORM_BLUEPRINT.md`.

## Implemented foundation

- FastAPI backend
- PostgreSQL + Redis local infrastructure
- Deterministic SMC swing/BOS/MSS/liquidity/FVG analysis
- Risk engine with veto authority
- Event-style backtest foundation
- Paper-order endpoint
- AI strategy DSL translation endpoint
- Android Jetpack Compose dashboard
- Docker Compose development environment

## Architecture

`Market Data -> SMC/ICT -> Strategy -> AI interpretation -> Risk -> Execution -> Broker`

AI never has direct authority to submit live orders. Live broker adapters must be configured and validated separately.

## Run backend

```bash
docker compose up --build
```

API: `http://localhost:8000/docs`

## Run Android

Open `android/` in Android Studio and run the `app` module.

## Important

The repository intentionally defaults to paper/demo behavior. Real Dhan/Upstox credentials, licensed market data, authentication hardening, broker reconciliation, production observability, and regulatory/compliance validation are required before real-money trading.
