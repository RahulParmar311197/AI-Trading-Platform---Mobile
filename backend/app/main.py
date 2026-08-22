from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.markets import router as markets_router
from app.api.analysis import router as analysis_router
from app.api.backtest import router as backtest_router
from app.api.paper import router as paper_router
from app.api.risk import router as risk_router
from app.api.replay import router as replay_router

app = FastAPI(title="AI Trading Platform API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(health_router)
app.include_router(markets_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")
app.include_router(paper_router, prefix="/api")
app.include_router(risk_router, prefix="/api")
app.include_router(replay_router, prefix="/api")

@app.get("/")
def root():
    return {"name": "AI Trading Platform", "version": "1.0.0", "status": "ok"}
