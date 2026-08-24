from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.ai_provider import AIProviderError, AIStrategyService
from app.ai_openai_provider import OpenAIStrategyProvider
from app.strategy_dsl import strategy_to_dict

router = APIRouter(prefix="/api/ai", tags=["ai"])


class StrategyRequest(BaseModel):
    request: str = Field(min_length=3, max_length=4000)
    use_llm: bool = False


@router.post("/strategy")
def build_strategy(payload: StrategyRequest):
    try:
        if payload.use_llm:
            service = AIStrategyService(OpenAIStrategyProvider(), "openai")
        else:
            service = AIStrategyService()
        result = service.build(payload.request)
        return {
            "provider": result.provider,
            "strategy": strategy_to_dict(result.strategy),
        }
    except AIProviderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI strategy service unavailable") from exc
