from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.mtf_aggregator import Candle, MultiTimeframeAggregator


router = APIRouter(
    prefix="/api/mtf",
    tags=["mtf-aggregator"],
)

aggregator = MultiTimeframeAggregator()


class CandleIn(BaseModel):
    timestamp: datetime
    symbol: str | None = None
    timeframe: str | None = None
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)


class AggregateRequest(BaseModel):
    candles: list[CandleIn]
    target_timeframe: str

    # Compatibility with the integration/main API
    symbol: str | None = None
    source_timeframe: str | None = None


class AlignmentRequest(BaseModel):
    candles: list[CandleIn]
    timeframe: str
    symbol: str | None = None


def _to_candles(
    candles: list[CandleIn],
    symbol: str | None = None,
    timeframe: str | None = None,
) -> list[Candle]:
    result: list[Candle] = []

    for item in candles:
        item_symbol = item.symbol or symbol
        item_timeframe = item.timeframe or timeframe

        if not item_symbol:
            raise ValueError("symbol is required for every candle")

        if not item_timeframe:
            raise ValueError("timeframe is required for every candle")

        result.append(
            Candle(
                timestamp=item.timestamp,
                open=float(item.open),
                high=float(item.high),
                low=float(item.low),
                close=float(item.close),
                volume=float(item.volume),
                symbol=item_symbol.upper(),
                timeframe=item_timeframe,
            )
        )

    return result


@router.post("/aggregate")
def aggregate_candles(payload: AggregateRequest):
    if not payload.candles:
        return {
            "candles": [],
            "count": 0,
        }

    try:
        source = _to_candles(
            payload.candles,
            symbol=payload.symbol,
            timeframe=payload.source_timeframe,
        )

        result = aggregator.aggregate(
            source,
            payload.target_timeframe,
        )

        return {
            "candles": [c.__dict__ for c in result],
            "count": len(result),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.post("/validate")
def validate_alignment(payload: AggregateRequest):
    try:
        source = _to_candles(
            payload.candles,
            symbol=payload.symbol,
            timeframe=payload.source_timeframe,
        )

        issues = aggregator.validate_alignment(
            source,
            payload.target_timeframe,
        )

        return {
            "valid": not issues,
            "issues": issues,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.post("/alignment")
def alignment(payload: AlignmentRequest):
    try:
        source = _to_candles(
            payload.candles,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
        )

        issues = aggregator.validate_alignment(
            source,
            payload.timeframe,
        )

        return {
            "valid": not issues,
            "issues": issues,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc