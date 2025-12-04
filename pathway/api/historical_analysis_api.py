"""
FastAPI server for historical market data analysis using Pathway + market_agent2.
Downloads data from yfinance, converts to Pathway table, runs pipeline ONCE.
"""
import sys
import os
import json
import uuid
import base64
import asyncio
import concurrent.futures
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from fastapi import FastAPI, HTTPException, BackgroundTasks, APIRouter
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator
import uvicorn

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.utils.tool_creation import (
    download_ohlcv,
    compute_indicators_talib,
    yfinance_available,
    talib_available
)
from agents.utils.batch_analysis import (
    run_historical_analysis_with_pathway,
    load_report_content,
    load_images_as_base64
)

# =====================================================================
# CONFIGURATION
# =====================================================================

# market_agent2 saves directly to reports/market/{ticker}/
REPORTS_BASE_DIR = Path("./reports/market")


router = APIRouter()


# =====================================================================
# ENUMS AND MODELS
# =====================================================================

class IntervalType(str, Enum):
    """Valid yfinance data intervals"""
    ONE_MINUTE = "1m"
    TWO_MINUTES = "2m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    NINETY_MINUTES = "90m"
    ONE_DAY = "1d"
    FIVE_DAYS = "5d"
    ONE_WEEK = "1wk"
    ONE_MONTH = "1mo"
    THREE_MONTHS = "3mo"


class AnalysisRequest(BaseModel):
    """Request model for historical analysis"""
    ticker: str = Field(..., description="Stock symbol (e.g., AAPL, TSLA, GOOGL)")
    start_time: Optional[str] = Field(None, description="Start time (YYYY-MM-DD HH:MM:SS)")
    end_time: Optional[str] = Field(None, description="End time (YYYY-MM-DD HH:MM:SS)")
    period: str = Field("7d", description="Download period (e.g., 1d, 5d, 1mo, 1y)")
    interval: IntervalType = Field(IntervalType.ONE_MINUTE, description="Candle size")
    indicators: Optional[List[str]] = Field(
        None, 
        description="List of indicators to focus on (e.g., ['RSI', 'MACD', 'BB', 'STOCH']). Note: Pipeline computes all indicators for comprehensive analysis."
    )
    
    @validator('ticker')
    def validate_ticker(cls, v):
        if not v or not v.strip():
            raise ValueError('Ticker symbol cannot be empty')
        return v.strip().upper()
    
    @validator('indicators')
    def validate_indicators(cls, v):
        if v is None:
            return None
        valid_indicators = {'RSI', 'MACD', 'BB', 'BBANDS', 'STOCH', 'ATR', 'ADX', 'CCI', 'MFI', 'OBV', 'EMA', 'SMA'}
        invalid = set(v) - valid_indicators
        if invalid:
            raise ValueError(f'Invalid indicators: {invalid}. Valid: {valid_indicators}')
        return [ind.upper() for ind in v]


class AnalysisResponse(BaseModel):
    """Response model for analysis"""
    status: str
    report_id: str
    ticker: str
    report: str
    images: Dict[str, str]


# =====================================================================
# MAIN GENERATION FUNCTION
# =====================================================================

def generate_historical_report(request: AnalysisRequest, report_id: str) -> Dict[str, Any]:
    """
    Generate report using Pathway + market_agent2 pipeline.
    
    Process:
    1. Download data from yfinance
    2. Convert to Pathway table (static CSV)
    3. Run market_agent2 pipeline ONCE
    4. Collect generated reports from reports/market/{ticker}/
    """
    try:
        if not yfinance_available or not talib_available:
            raise RuntimeError("Required dependencies not available")
        
        print(f"📊 Downloading {request.ticker} data...")
        
        # Download data
        df = download_ohlcv(ticker=request.ticker, period=request.period, interval=request.interval.value)
        
        if df.empty:
            raise RuntimeError(f"No data downloaded for {request.ticker}")
        
        # Filter by time if specified
        if request.start_time or request.end_time:
            import pandas as pd
            if request.start_time:
                df = df[df.index >= pd.to_datetime(request.start_time)]
            if request.end_time:
                df = df[df.index <= pd.to_datetime(request.end_time)]
            if df.empty:
                raise RuntimeError(f"No data in specified time range")
        
        print(f"✅ Downloaded {len(df)} data points")
        
        # Run Pathway pipeline (saves to reports/market/{ticker}/)
        print(f"🚀 Running Pathway + market_agent2 pipeline...")
        indicators = request.indicators if request.indicators else None
        if indicators:
            print(f"📊 User-requested indicators: {', '.join(indicators)}")
            print(f"💡 Note: Pipeline computes all indicators for comprehensive analysis")
        
        # market_agent2 will save to reports/market/{ticker}/
        pathway_result = run_historical_analysis_with_pathway(
            ticker=request.ticker,
            df=df,
            report_id=report_id,
            output_dir=Path("./reports"),  # market_agent2 creates market/{ticker} subdirs
            indicators=indicators
        )
        
        # Get comprehensive report from captured results (real-time)
        captured_results = pathway_result.get("captured_results", [])
        
        if captured_results:
            # Use the captured result (already has comprehensive report)
            result = captured_results[0]
            comprehensive = result.get("comprehensive_report", "No report generated")
            print(f"✅ Using captured result ({len(comprehensive)} chars)")
        else:
            # Fallback to loading from files in reports/market/{ticker}/
            print(f"⚠️ No captured results, falling back to file loading")
            report_files = pathway_result["report_files"]
            report_content = load_report_content(report_files)
            comprehensive = report_content.get("comprehensive_report", "No report generated")
        
        # Load images from reports/market/{ticker}/images/
        report_files = pathway_result["report_files"]
        images_b64 = load_images_as_base64(report_files)
        
        print(f"📊 Report: {len(comprehensive)} chars")
        print(f"📊 Images: {len(images_b64)} files")
        print(f"📂 Images location: reports/market/{request.ticker}/images/")
        
        return {
            "summary": comprehensive,
            "plots": images_b64
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise


# =====================================================================
# API ENDPOINTS
# =====================================================================

@router.get("/")
async def root():
    return {
        "service": "Historical Market Analysis API (Pathway)",
        "version": "3.0.0",
        "description": "Uses Pathway + market_agent2 pipeline for AI-powered analysis",
        "endpoints": {
            "POST /analyze": "Generate complete analysis with report and all images",
            "GET /health": "Health check"
        }
    }


@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "yfinance": yfinance_available,
        "talib": talib_available
    }


# Thread pool executor for running Pathway in isolation from async event loop
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    """
    Generate complete historical analysis with comprehensive report and all images.
    
    Returns:
    - report_id: Unique identifier
    - ticker: Stock symbol
    - report: Complete comprehensive markdown report
    - images: Dictionary of all images as base64 (key: image_name, value: base64_string)
    """
    try:
        report_id = f"{request.ticker}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Run the synchronous Pathway function in a separate thread pool
        # This prevents event loop conflicts with Pathway's async components
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            generate_historical_report,
            request,
            report_id
        )
        
        response = AnalysisResponse(
            status="success",
            report_id=report_id,
            ticker=request.ticker,
            report=result['summary'],
            images=result['plots']
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


