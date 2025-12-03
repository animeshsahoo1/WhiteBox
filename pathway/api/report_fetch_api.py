"""
Report Fetch API Router
Handles fetching and retrieving cached AI reports from Redis.
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import get_redis_client, get_reports_for_symbol

REPORT_TYPES = ["fundamental", "market", "news", "sentiment", "facilitator"]


class ReportsResponse(BaseModel):
    symbol: str
    fundamental_report: Optional[str] = None
    market_report: Optional[str] = None
    news_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    facilitator_report: Optional[str] = None
    timestamp: str
    status: str


router = APIRouter(prefix="/reports")


@router.get("/{symbol}", response_model=ReportsResponse)
async def get_all_reports(symbol: str) -> ReportsResponse:
    """Get all cached reports for a symbol"""
    client = get_redis_client()
    normalized_symbol = symbol.upper()

    print(f"\n{'=' * 60}")
    print(f"📥 Request for all reports: {normalized_symbol}")
    print(f"{'=' * 60}")

    reports = get_reports_for_symbol(normalized_symbol, client)
    if not reports:
        print(f"❌ No reports found for {normalized_symbol}\n")
        raise HTTPException(
            status_code=404,
            detail=f"No cached reports found for symbol {normalized_symbol}",
        )

    fundamental_report = reports.get("fundamental", {}).get("content")
    market_report = reports.get("market", {}).get("content")
    news_report = reports.get("news", {}).get("content")
    sentiment_report = reports.get("sentiment", {}).get("content")
    facilitator_report = reports.get("facilitator", {}).get("content")

    print(f"\n📊 Cached results for {normalized_symbol}:")
    print(f"  Fundamental: {'✅' if fundamental_report else '❌'}")
    print(f"  Market: {'✅' if market_report else '❌'}")
    print(f"  News: {'✅' if news_report else '❌'}")
    print(f"  Sentiment: {'✅' if sentiment_report else '❌'}")
    print(f"  Facilitator: {'✅' if facilitator_report else '❌'}")
    print(f"✅ Returning cached response for {normalized_symbol}\n")

    return ReportsResponse(
        symbol=normalized_symbol,
        fundamental_report=fundamental_report,
        market_report=market_report,
        news_report=news_report,
        sentiment_report=sentiment_report,
        facilitator_report=facilitator_report,
        timestamp=datetime.utcnow().isoformat(),
        status="success",
    )


@router.get("/{symbol}/{report_type}")
async def get_specific_report(symbol: str, report_type: str) -> dict:
    """Get a specific report type for a symbol"""
    normalized_symbol = symbol.upper()
    normalized_report_type = report_type.lower()

    if normalized_report_type not in REPORT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report type '{report_type}'. Must be one of {REPORT_TYPES}",
        )

    client = get_redis_client()
    reports = get_reports_for_symbol(normalized_symbol, client)

    if normalized_report_type not in reports:
        raise HTTPException(
            status_code=404,
            detail=f"No cached {normalized_report_type} report found for {normalized_symbol}",
        )

    entry = reports[normalized_report_type]

    return {
        "symbol": normalized_symbol,
        "report_type": normalized_report_type,
        "content": entry.get("content"),
        "last_updated": entry.get("last_updated"),
        "received_at": entry.get("received_at"),
        "processing_time": entry.get("processing_time"),
        "timestamp": datetime.utcnow().isoformat(),
    }
