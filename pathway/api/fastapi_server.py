"""
FastAPI server to expose current reports from Pathway consumers.
This allows the trading agents to fetch the latest reports for any stock symbol.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import glob
from datetime import datetime

app = FastAPI(title="Pathway Reports API", version="1.0.0")


class ReportsResponse(BaseModel):
    """Response model for all reports of a stock"""
    symbol: str
    fundamental_report: Optional[str] = None
    market_report: Optional[str] = None
    news_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    timestamp: str
    status: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str


def read_report_file(report_path: str) -> Optional[str]:
    """Read a report file and return its content"""
    try:
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    except Exception as e:
        print(f"Error reading report from {report_path}: {e}")
        return None


@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "message": "Pathway Reports API",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/reports/{symbol}": "Get all reports for a stock symbol",
            "/reports/{symbol}/fundamental": "Get fundamental report",
            "/reports/{symbol}/market": "Get market report",
            "/reports/{symbol}/news": "Get news report",
            "/reports/{symbol}/sentiment": "Get sentiment report"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/reports/{symbol}", response_model=ReportsResponse)
async def get_all_reports(symbol: str):
    """
    Get all available reports for a given stock symbol.
    
    Args:
        symbol: Stock ticker symbol (e.g., AAPL, GOOGL, TSLA)
    
    Returns:
        ReportsResponse with all available reports
    """
    symbol = symbol.upper()
    reports_base_dir = "/app/reports"
    
    # Read each report type
    fundamental_path = os.path.join(reports_base_dir, "fundamental", symbol, "fundamental_report.md")
    market_path = os.path.join(reports_base_dir, "market", symbol, "market_report.md")
    news_path = os.path.join(reports_base_dir, "news", symbol, "news_report.md")
    sentiment_path = os.path.join(reports_base_dir, "sentiment", symbol, "sentiment_report.md")
    
    fundamental_report = read_report_file(fundamental_path)
    market_report = read_report_file(market_path)
    news_report = read_report_file(news_path)
    sentiment_report = read_report_file(sentiment_path)
    
    # Check if at least one report exists
    if not any([fundamental_report, market_report, news_report, sentiment_report]):
        raise HTTPException(
            status_code=404,
            detail=f"No reports found for symbol {symbol}. Make sure the symbol is correct and data has been processed."
        )
    
    return ReportsResponse(
        symbol=symbol,
        fundamental_report=fundamental_report,
        market_report=market_report,
        news_report=news_report,
        sentiment_report=sentiment_report,
        timestamp=datetime.utcnow().isoformat(),
        status="success"
    )


@app.get("/reports/{symbol}/fundamental")
async def get_fundamental_report(symbol: str):
    """Get fundamental analysis report for a stock"""
    symbol = symbol.upper()
    reports_base_dir = "/app/reports"
    report_path = os.path.join(reports_base_dir, "fundamental", symbol, "fundamental_report.md")
    
    report = read_report_file(report_path)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Fundamental report not found for symbol {symbol}"
        )
    
    return {
        "symbol": symbol,
        "report_type": "fundamental",
        "content": report,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/reports/{symbol}/market")
async def get_market_report(symbol: str):
    """Get market analysis report for a stock"""
    symbol = symbol.upper()
    reports_base_dir = "/app/reports"
    report_path = os.path.join(reports_base_dir, "market", symbol, "market_report.md")
    
    report = read_report_file(report_path)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Market report not found for symbol {symbol}"
        )
    
    return {
        "symbol": symbol,
        "report_type": "market",
        "content": report,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/reports/{symbol}/news")
async def get_news_report(symbol: str):
    """Get news analysis report for a stock"""
    symbol = symbol.upper()
    reports_base_dir = "/app/reports"
    report_path = os.path.join(reports_base_dir, "news", symbol, "news_report.md")
    
    report = read_report_file(report_path)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"News report not found for symbol {symbol}"
        )
    
    return {
        "symbol": symbol,
        "report_type": "news",
        "content": report,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/reports/{symbol}/sentiment")
async def get_sentiment_report(symbol: str):
    """Get sentiment analysis report for a stock"""
    symbol = symbol.upper()
    reports_base_dir = "/app/reports"
    report_path = os.path.join(reports_base_dir, "sentiment", symbol, "sentiment_report.md")
    
    report = read_report_file(report_path)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Sentiment report not found for symbol {symbol}"
        )
    
    return {
        "symbol": symbol,
        "report_type": "sentiment",
        "content": report,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/available-symbols")
async def get_available_symbols():
    """
    Get list of all stock symbols that have at least one report available.
    """
    reports_base_dir = "/app/reports"
    symbols = set()
    
    # Check all report types
    for report_type in ["fundamental", "market", "news", "sentiment"]:
        type_dir = os.path.join(reports_base_dir, report_type)
        if os.path.exists(type_dir):
            # Get all subdirectories (each represents a symbol)
            for item in os.listdir(type_dir):
                item_path = os.path.join(type_dir, item)
                if os.path.isdir(item_path) and item.isupper():
                    symbols.add(item)
    
    return {
        "symbols": sorted(list(symbols)),
        "count": len(symbols),
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
