"""Report Fetch API Router
Handles fetching and retrieving cached AI reports from Redis.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

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

    if DEBUG:
        print(f"📥 Request for all reports: {normalized_symbol}")

    reports = get_reports_for_symbol(normalized_symbol, client)
    if not reports:
        if DEBUG:
            print(f"❌ No reports found for {normalized_symbol}")
        raise HTTPException(
            status_code=404,
            detail=f"No cached reports found for symbol {normalized_symbol}",
        )

    fundamental_report = reports.get("fundamental", {}).get("content")
    market_report = reports.get("market", {}).get("content")
    news_report = reports.get("news", {}).get("content")
    sentiment_report = reports.get("sentiment", {}).get("content")
    facilitator_report = reports.get("facilitator", {}).get("content")

    if DEBUG:
        print(f"📊 {normalized_symbol}: F={'✅' if fundamental_report else '❌'} M={'✅' if market_report else '❌'} N={'✅' if news_report else '❌'} S={'✅' if sentiment_report else '❌'} Fac={'✅' if facilitator_report else '❌'}")

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
