from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.ai_openai_provider import OpenAIStrategyProvider
from app.ai_provider import AIProviderError, AIStrategyService
from app.ai_rate_limit import ai_rate_limiter
from app.strategy_dsl import strategy_to_dict

router = APIRouter(prefix="/api/ai", tags=["ai"])


class StrategyRequest(BaseModel):
    request: str = Field(min_length=3, max_length=4000)
    use_llm: bool = False


@router.post("/strategy")
def build_strategy(payload: StrategyRequest, request: Request):
    # Until shared Redis throttling is wired, bound each client address locally.
    client_key = request.client.host if request.client else "unknown"
    if not ai_rate_limiter.allow(client_key):
        raise HTTPException(status_code=429, detail="AI request rate limit exceeded")
    try:
        service = AIStrategyService(
            OpenAIStrategyProvider(), "openai"
        ) if payload.use_llm else AIStrategyService()
        result = service.build(payload.request)
        return {"provider": result.provider, "strategy": strategy_to_dict(result.strategy)}
    except AIProviderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI strategy service unavailable") from exc
