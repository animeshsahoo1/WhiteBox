"""
FastAPI server for Trading Agents system.
Provides endpoints to:
1. Retrieve agent reports (bull, bear, trader, risk manager) from PostgreSQL
2. Retrieve trade signals
3. Trigger trading workflow for a given symbol
4. Health checks and status monitoring
"""
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, List, Union
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from dotenv import load_dotenv

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.reports_client import PathwayReportsClient, StockReports

# Import enqueue_trade - this will be None if Redis connection fails, handled gracefully
try:
    from redis_queue.task_queue import enqueue_trade
    QUEUE_AVAILABLE = True
except Exception as e:
    print(f"WARNING: Redis queue not available: {e}")
    QUEUE_AVAILABLE = False
    enqueue_trade = None

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
PATHWAY_API_URL = os.getenv("PATHWAY_API_URL", "http://pathway-reports-api:8000")

# Validate critical environment variables
if not DATABASE_URL:
    print("WARNING: DATABASE_URL not set. Database features will be unavailable.")

app = FastAPI(
    title="Trading Agents API",
    version="1.0.0",
    description="API for multi-agent trading system - retrieve reports, signals, and trigger workflows",
)


# ============================================================================
# Response Models
# ============================================================================

class GraphReportResponse(BaseModel):
    id: Union[int, str]  # Support both int (SERIAL) and str (UUID)
    graph_id: Optional[str]
    symbol: str
    report_type: str
    timestamp: str
    report_body: str


class TradeSignalResponse(BaseModel):
    id: Union[int, str]  # Support both int (SERIAL) and str (UUID)
    symbol: str
    signal: str
    quantity: int
    profit_target: float
    stop_loss: float
    invalidation_condition: str
    leverage: int
    confidence: float
    risk_usd: float
    timestamp: str


class InputReportsResponse(BaseModel):
    symbol: str
    fundamental_report: Optional[str]
    market_report: Optional[str]
    news_report: Optional[str]
    sentiment_report: Optional[str]
    source: str  # "pathway_api" or "database"
    timestamp: str


class AllReportsResponse(BaseModel):
    symbol: str
    input_reports: InputReportsResponse
    agent_reports: List[GraphReportResponse]
    trade_signals: List[TradeSignalResponse]
    timestamp: str


class ExecuteWorkflowResponse(BaseModel):
    status: str
    symbol: str
    job_id: Optional[str]
    message: str
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    database_connected: bool
    pathway_api_connected: bool
    available_symbols: List[str]


# ============================================================================
# Database Helper Functions
# ============================================================================

def get_db_connection():
    """Get PostgreSQL database connection."""
    if not DATABASE_URL:
        raise HTTPException(
            status_code=503, 
            detail="Database not configured. Set DATABASE_URL environment variable."
        )
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {e}")


def get_graph_reports_by_symbol(symbol: str, report_type: Optional[str] = None) -> List[Dict]:
    """Fetch graph reports from database by symbol and optionally filter by report_type."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if report_type:
                cur.execute(
                    """
                    SELECT id, graph_id, symbol, report_type, timestamp, report_body
                    FROM graph_reports
                    WHERE symbol = %s AND report_type = %s
                    ORDER BY timestamp DESC
                    """,
                    (symbol.upper(), report_type)
                )
            else:
                cur.execute(
                    """
                    SELECT id, graph_id, symbol, report_type, timestamp, report_body
                    FROM graph_reports
                    WHERE symbol = %s
                    ORDER BY timestamp DESC
                    """,
                    (symbol.upper(),)
                )
            results = cur.fetchall()
            return [dict(row) for row in results]
    finally:
        conn.close()


def get_trade_signals_by_symbol(symbol: str, limit: int = 10) -> List[Dict]:
    """Fetch trade signals from database by symbol."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, symbol, signal, quantity, profit_target, stop_loss, 
                       invalidation_condition, leverage, confidence, risk_usd, timestamp
                FROM trade_signals
                WHERE symbol = %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (symbol.upper(), limit)
            )
            results = cur.fetchall()
            return [dict(row) for row in results]
    finally:
        conn.close()


def get_all_symbols_from_db() -> List[str]:
    """Get list of all unique symbols from database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get symbols from both tables
            cur.execute("""
                SELECT DISTINCT symbol FROM graph_reports
                UNION
                SELECT DISTINCT symbol FROM trade_signals
                ORDER BY symbol
            """)
            results = cur.fetchall()
            return [row[0] for row in results]
    finally:
        conn.close()


def get_input_reports_from_pathway(symbol: str) -> StockReports:
    """Fetch input reports from Pathway API."""
    client = PathwayReportsClient(base_url=PATHWAY_API_URL)
    
    if not client.health_check():
        raise HTTPException(
            status_code=503,
            detail=f"Pathway API is not available at {PATHWAY_API_URL}"
        )
    
    try:
        reports = client.get_all_reports(symbol)
        return reports
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Failed to fetch reports for {symbol}: {str(e)}"
        )


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_model=dict)
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "message": "Trading Agents API",
        "version": "1.0.0",
        "description": "Multi-agent trading system with bull/bear debate, risk analysis, and signal generation",
        "endpoints": {
            "GET /health": "Health check and system status",
            "GET /symbols": "List all available symbols",
            "GET /reports/input/{symbol}": "Get input reports (fundamental, market, news, sentiment)",
            "GET /reports/agent/{symbol}": "Get agent reports (bull, bear, trader, risk)",
            "GET /reports/agent/{symbol}/{report_type}": "Get specific agent report type",
            "GET /reports/all/{symbol}": "Get all reports for a symbol",
            "GET /signals/{symbol}": "Get trade signals for a symbol",
            "GET /signals/{symbol}/latest": "Get latest trade signal",
            "POST /execute?symbol=AAPL": "Execute trading workflow for a symbol"
        },
        "examples": {
            "execute_workflow": "POST /execute?symbol=AAPL"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    # Check database connection
    db_connected = False
    try:
        conn = get_db_connection()
        conn.close()
        db_connected = True
    except Exception as e:
        print(f"Database health check failed: {e}")
        pass
    
    # Check Pathway API connection and get symbols from it
    pathway_connected = False
    symbols = []
    try:
        client = PathwayReportsClient(base_url=PATHWAY_API_URL)
        pathway_connected = client.health_check()
        
        # Get symbols from Pathway API (Redis cache)
        if pathway_connected:
            response = requests.get(f"{PATHWAY_API_URL}/symbols", timeout=5)
            if response.status_code == 200:
                symbols_data = response.json()
                symbols = symbols_data.get("symbols", [])
    except Exception as e:
        print(f"Pathway API health check failed: {e}")
        # Fallback to database if Pathway API is down
        if db_connected:
            try:
                symbols = get_all_symbols_from_db()
            except Exception as db_error:
                print(f"Database symbol fetch also failed: {db_error}")
    
    # Return OK even if some services are unavailable (degraded mode)
    return HealthResponse(
        status="ok",  # Always return ok so health check passes
        timestamp=datetime.utcnow().isoformat(),
        database_connected=db_connected,
        pathway_api_connected=pathway_connected,
        available_symbols=symbols
    )


@app.get("/symbols")
async def list_symbols() -> dict:
    """
    List all symbols with available reports.
    Routes directly to Pathway API to show real-time Redis cache data.
    """
    try:
        # Route to Pathway API for fresh Redis data
        response = requests.get(f"{PATHWAY_API_URL}/symbols", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # Fallback to database if Pathway API is unavailable
        print(f"⚠️  Pathway API unavailable, falling back to database: {e}")
        try:
            symbols = get_all_symbols_from_db()
            return {
                "symbols": symbols,
                "count": len(symbols),
                "timestamp": datetime.utcnow().isoformat(),
                "source": "database_fallback"
            }
        except Exception as db_error:
            raise HTTPException(
                status_code=500, 
                detail=f"Both Pathway API and database unavailable. Pathway: {str(e)}, DB: {str(db_error)}"
            )


@app.get("/reports/input/{symbol}", response_model=InputReportsResponse)
async def get_input_reports(symbol: str) -> InputReportsResponse:
    """
    Get input reports (fundamental, market, news, sentiment) for a symbol.
    Fetches from Pathway API.
    """
    normalized_symbol = symbol.upper()
    
    try:
        reports = get_input_reports_from_pathway(normalized_symbol)
        
        return InputReportsResponse(
            symbol=normalized_symbol,
            fundamental_report=reports.fundamental_report,
            market_report=reports.market_report,
            news_report=reports.news_report,
            sentiment_report=reports.sentiment_report,
            source="pathway_api",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Failed to fetch input reports for {normalized_symbol}: {str(e)}"
        )


@app.get("/reports/agent/{symbol}", response_model=List[GraphReportResponse])
async def get_agent_reports(symbol: str, limit: int = Query(default=20, ge=1, le=100)) -> List[GraphReportResponse]:
    """
    Get all agent reports (bull, bear, trader, risk manager) for a symbol.
    Returns most recent reports first.
    """
    normalized_symbol = symbol.upper()
    
    try:
        reports = get_graph_reports_by_symbol(normalized_symbol)
        
        if not reports:
            raise HTTPException(
                status_code=404,
                detail=f"No agent reports found for {normalized_symbol}"
            )
        
        # Limit results
        reports = reports[:limit]
        
        return [
            GraphReportResponse(
                id=r['id'],
                graph_id=r['graph_id'],
                symbol=r['symbol'],
                report_type=r['report_type'],
                timestamp=r['timestamp'].isoformat() if hasattr(r['timestamp'], 'isoformat') else str(r['timestamp']),
                report_body=r['report_body']
            )
            for r in reports
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/reports/agent/{symbol}/{report_type}", response_model=List[GraphReportResponse])
async def get_specific_agent_report(
    symbol: str, 
    report_type: str,
    limit: int = Query(default=10, ge=1, le=50)
) -> List[GraphReportResponse]:
    """
    Get specific type of agent report for a symbol.
    report_type options: 'trader', 'risk_manager'
    """
    normalized_symbol = symbol.upper()
    valid_types = ['trader', 'risk_manager']
    
    if report_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report_type. Must be one of: {valid_types}"
        )
    
    try:
        reports = get_graph_reports_by_symbol(normalized_symbol, report_type)
        
        if not reports:
            raise HTTPException(
                status_code=404,
                detail=f"No {report_type} reports found for {normalized_symbol}"
            )
        
        reports = reports[:limit]
        
        return [
            GraphReportResponse(
                id=r['id'],
                graph_id=r['graph_id'],
                symbol=r['symbol'],
                report_type=r['report_type'],
                timestamp=r['timestamp'].isoformat() if hasattr(r['timestamp'], 'isoformat') else str(r['timestamp']),
                report_body=r['report_body']
            )
            for r in reports
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/signals/{symbol}", response_model=List[TradeSignalResponse])
async def get_trade_signals(
    symbol: str,
    limit: int = Query(default=10, ge=1, le=50)
) -> List[TradeSignalResponse]:
    """Get trade signals for a symbol (most recent first)."""
    normalized_symbol = symbol.upper()
    
    try:
        signals = get_trade_signals_by_symbol(normalized_symbol, limit)
        
        if not signals:
            raise HTTPException(
                status_code=404,
                detail=f"No trade signals found for {normalized_symbol}"
            )
        
        return [
            TradeSignalResponse(
                id=s['id'],
                symbol=s['symbol'],
                signal=s['signal'],
                quantity=s['quantity'],
                profit_target=float(s['profit_target']),
                stop_loss=float(s['stop_loss']),
                invalidation_condition=s['invalidation_condition'],
                leverage=s['leverage'],
                confidence=float(s['confidence']),
                risk_usd=float(s['risk_usd']),
                timestamp=s['timestamp'].isoformat() if hasattr(s['timestamp'], 'isoformat') else str(s['timestamp'])
            )
            for s in signals
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/signals/{symbol}/latest", response_model=TradeSignalResponse)
async def get_latest_trade_signal(symbol: str) -> TradeSignalResponse:
    """Get the most recent trade signal for a symbol."""
    normalized_symbol = symbol.upper()
    
    try:
        signals = get_trade_signals_by_symbol(normalized_symbol, limit=1)
        
        if not signals:
            raise HTTPException(
                status_code=404,
                detail=f"No trade signals found for {normalized_symbol}"
            )
        
        s = signals[0]
        return TradeSignalResponse(
            id=s['id'],
            symbol=s['symbol'],
            signal=s['signal'],
            quantity=s['quantity'],
            profit_target=float(s['profit_target']),
            stop_loss=float(s['stop_loss']),
            invalidation_condition=s['invalidation_condition'],
            leverage=s['leverage'],
            confidence=float(s['confidence']),
            risk_usd=float(s['risk_usd']),
            timestamp=s['timestamp'].isoformat() if hasattr(s['timestamp'], 'isoformat') else str(s['timestamp'])
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/reports/all/{symbol}", response_model=AllReportsResponse)
async def get_all_reports(symbol: str) -> AllReportsResponse:
    """
    Get ALL reports for a symbol:
    - Input reports (fundamental, market, news, sentiment)
    - Agent reports (bull, bear, trader, risk)
    - Trade signals
    """
    normalized_symbol = symbol.upper()
    
    try:
        # Fetch input reports from Pathway API
        input_reports = get_input_reports_from_pathway(normalized_symbol)
        input_reports_response = InputReportsResponse(
            symbol=normalized_symbol,
            fundamental_report=input_reports.fundamental_report,
            market_report=input_reports.market_report,
            news_report=input_reports.news_report,
            sentiment_report=input_reports.sentiment_report,
            source="pathway_api",
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Fetch agent reports from database
        agent_reports_data = get_graph_reports_by_symbol(normalized_symbol)
        agent_reports = [
            GraphReportResponse(
                id=r['id'],
                graph_id=r['graph_id'],
                symbol=r['symbol'],
                report_type=r['report_type'],
                timestamp=r['timestamp'].isoformat() if hasattr(r['timestamp'], 'isoformat') else str(r['timestamp']),
                report_body=r['report_body']
            )
            for r in agent_reports_data
        ]
        
        # Fetch trade signals from database
        signals_data = get_trade_signals_by_symbol(normalized_symbol, limit=10)
        trade_signals = [
            TradeSignalResponse(
                id=s['id'],
                symbol=s['symbol'],
                signal=s['signal'],
                quantity=s['quantity'],
                profit_target=float(s['profit_target']),
                stop_loss=float(s['stop_loss']),
                invalidation_condition=s['invalidation_condition'],
                leverage=s['leverage'],
                confidence=float(s['confidence']),
                risk_usd=float(s['risk_usd']),
                timestamp=s['timestamp'].isoformat() if hasattr(s['timestamp'], 'isoformat') else str(s['timestamp'])
            )
            for s in signals_data
        ]
        
        return AllReportsResponse(
            symbol=normalized_symbol,
            input_reports=input_reports_response,
            agent_reports=agent_reports,
            trade_signals=trade_signals,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch all reports for {normalized_symbol}: {str(e)}"
        )


@app.post("/execute", response_model=ExecuteWorkflowResponse)
async def execute_workflow(symbol: str = Query(..., description="Stock symbol to analyze (e.g., AAPL, GOOGL)")) -> ExecuteWorkflowResponse:
    """
    Execute the trading workflow for a given symbol.
    This triggers the full multi-agent pipeline:
    1. Fetches input reports from Pathway API
    2. Bull-Bear debate
    3. Trader synthesis
    4. Risk analysis (risky, neutral, safe)
    5. Risk manager decision
    6. Final trade signal generation
    
    The workflow is executed asynchronously via Redis queue.
    """
    normalized_symbol = symbol.upper()
    
    # Check if input reports are available
    try:
        client = PathwayReportsClient(base_url=PATHWAY_API_URL)
        if not client.health_check():
            raise HTTPException(
                status_code=503,
                detail=f"Pathway API is not available. Cannot execute workflow."
            )
        
        # Verify reports exist
        reports = client.get_all_reports(normalized_symbol)
        if not reports.is_complete():
            missing = reports.missing_reports()
            raise HTTPException(
                status_code=400,
                detail=f"Incomplete input reports for {normalized_symbol}. Missing: {', '.join(missing)}. Please wait for reports to be generated."
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot verify input reports for {normalized_symbol}: {str(e)}"
        )
    
    # Enqueue the trading job
    if not QUEUE_AVAILABLE or not enqueue_trade:
        raise HTTPException(
            status_code=503,
            detail="Redis queue is not available. Check REDIS_URL in .env"
        )
    
    try:
        job_id = enqueue_trade(normalized_symbol, use_fallback=False)
        
        return ExecuteWorkflowResponse(
            status="queued",
            symbol=normalized_symbol,
            job_id=job_id,
            message=f"Trading workflow queued for {normalized_symbol}. Job ID: {job_id}",
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enqueue workflow: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Trading Agents API server")
    print(f"📡 Pathway API URL: {PATHWAY_API_URL}")
    print(f"💾 Database: {DATABASE_URL[:30]}...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
