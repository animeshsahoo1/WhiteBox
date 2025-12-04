"""
FastAPI Router for Drift Detection API

Reads drift alerts from Redis cache and exposes REST endpoints.

Endpoints:
- GET /drift/health - Health check
- GET /drift/status - Drift detector status
- GET /drift/alerts - Get all drift alerts
- GET /drift/alerts/latest - Get latest N alerts
- GET /drift/alerts/{symbol} - Get alerts for specific symbol
- GET /drift/report - Get drift detection report
- POST /drift/reset - Reset drift state
- POST /drift/analyze - Analyze historical data for drift
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import sys

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import get_redis_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drift")


# ============================================================================
# REDIS KEYS
# ============================================================================

DRIFT_ALERTS_KEY = "drift:alerts"           # List of all alerts
DRIFT_STATUS_KEY = "drift:status"           # Current status
DRIFT_REPORT_KEY = "drift:report"           # Latest report
DRIFT_HISTORICAL_KEY = "drift:historical"   # Historical analysis results


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class DriftAlert(BaseModel):
    """Single drift alert"""
    id: Optional[str] = None
    timestamp: str
    symbol: str
    price: Optional[float] = None
    feature: str
    drift_type: str
    severity: str
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    detector: str
    confidence: float
    message: str


class DriftStatus(BaseModel):
    """Drift detector status"""
    running: bool = False
    total_updates: int = 0
    total_drifts: int = 0
    features_monitored: List[str] = []
    symbols_tracked: List[str] = []
    last_update: Optional[str] = None


class DriftReport(BaseModel):
    """Drift detection report"""
    total_drifts: int = 0
    drifts_by_feature: Dict[str, int] = {}
    drifts_by_type: Dict[str, int] = {}
    drifts_by_severity: Dict[str, int] = {}
    detection_rate: float = 0.0
    avg_confidence: float = 0.0
    time_range: Optional[Dict[str, str]] = None


class AlertsResponse(BaseModel):
    """Response for alerts endpoint"""
    count: int
    alerts: List[DriftAlert]


class SymbolAlertsResponse(BaseModel):
    """Response for symbol-specific alerts"""
    symbol: str
    count: int
    alerts: List[DriftAlert]
    message: Optional[str] = None


class ResetResponse(BaseModel):
    """Response for reset endpoint"""
    success: bool
    message: str
    timestamp: str


class HistoricalAnalysisRequest(BaseModel):
    """Request for historical drift analysis"""
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    period: str = Field(default="3mo", description="Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max")
    interval: str = Field(default="1d", description="Interval: 1m, 5m, 15m, 30m, 1h, 1d, 1wk")


class HistoricalDriftEvent(BaseModel):
    """Single drift event from historical analysis"""
    timestamp: str
    feature: str
    drift_type: str
    severity: str
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    detector: str
    confidence: float
    message: str
    price: Optional[float] = None


class HistoricalAnalysisResponse(BaseModel):
    """Response for historical drift analysis"""
    symbol: str
    period: str
    interval: str
    data_points: int
    total_drifts: int
    drifts_by_type: Dict[str, int]
    drifts_by_feature: Dict[str, int]
    drifts_by_severity: Dict[str, int]
    events: List[HistoricalDriftEvent]
    analysis_time_ms: float
    message: str


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_alerts_from_redis(limit: int = 100, symbol: Optional[str] = None) -> List[Dict]:
    """Fetch alerts from Redis"""
    try:
        client = get_redis_client()
        
        if symbol:
            key = f"drift:alerts:{symbol.upper()}"
        else:
            key = DRIFT_ALERTS_KEY
        
        # Get alerts (stored as JSON strings in a list)
        raw_alerts = client.lrange(key, 0, limit - 1)
        
        alerts = []
        for raw in raw_alerts:
            try:
                if isinstance(raw, bytes):
                    raw = raw.decode('utf-8')
                alerts.append(json.loads(raw))
            except:
                continue
        
        return alerts
    except Exception as e:
        logger.error(f"Redis error fetching alerts: {e}")
        return []


def get_status_from_redis() -> Dict:
    """Fetch status from Redis"""
    try:
        client = get_redis_client()
        raw = client.get(DRIFT_STATUS_KEY)
        
        if raw:
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            return json.loads(raw)
        
        return {}
    except Exception as e:
        logger.error(f"Redis error fetching status: {e}")
        return {}


def get_report_from_redis() -> Dict:
    """Fetch report from Redis"""
    try:
        client = get_redis_client()
        raw = client.get(DRIFT_REPORT_KEY)
        
        if raw:
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            return json.loads(raw)
        
        # Generate report from alerts if not cached
        alerts = get_alerts_from_redis(limit=1000)
        return generate_report_from_alerts(alerts)
    except Exception as e:
        logger.error(f"Redis error fetching report: {e}")
        return {}


def generate_report_from_alerts(alerts: List[Dict]) -> Dict:
    """Generate a report from alert list"""
    if not alerts:
        return {
            'total_drifts': 0,
            'drifts_by_feature': {},
            'drifts_by_type': {},
            'drifts_by_severity': {},
            'detection_rate': 0.0,
            'avg_confidence': 0.0,
        }
    
    by_feature = {}
    by_type = {}
    by_severity = {}
    total_confidence = 0.0
    
    for alert in alerts:
        feature = alert.get('feature', 'unknown')
        drift_type = alert.get('drift_type', 'unknown')
        severity = alert.get('severity', 'unknown')
        confidence = alert.get('confidence', 0.0)
        
        by_feature[feature] = by_feature.get(feature, 0) + 1
        by_type[drift_type] = by_type.get(drift_type, 0) + 1
        by_severity[severity] = by_severity.get(severity, 0) + 1
        total_confidence += confidence
    
    return {
        'total_drifts': len(alerts),
        'drifts_by_feature': by_feature,
        'drifts_by_type': by_type,
        'drifts_by_severity': by_severity,
        'detection_rate': len(alerts),  # Per 1000 messages ideally
        'avg_confidence': total_confidence / len(alerts) if alerts else 0.0,
    }


def get_tracked_symbols() -> List[str]:
    """Get list of symbols with drift alerts"""
    try:
        client = get_redis_client()
        
        # Scan for drift:alerts:* keys
        symbols = set()
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match="drift:alerts:*", count=100)
            for key in keys:
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                # Extract symbol from "drift:alerts:AAPL"
                parts = key.split(':')
                if len(parts) == 3:
                    symbols.add(parts[2])
            if cursor == 0:
                break
        
        return sorted(list(symbols))
    except Exception as e:
        logger.error(f"Redis error: {e}")
        return []


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        client = get_redis_client()
        client.ping()
        redis_status = "connected"
    except:
        redis_status = "disconnected"
    
    return {
        "status": "healthy",
        "redis": redis_status,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/status", response_model=DriftStatus)
async def get_status():
    """Get drift detector status"""
    status = get_status_from_redis()
    
    if not status:
        # Return default status if none in Redis
        return DriftStatus(
            running=False,
            total_updates=0,
            total_drifts=len(get_alerts_from_redis(limit=1000)),
            features_monitored=['price_return', 'volume_change', 'volatility', 'spread', 'momentum'],
            symbols_tracked=get_tracked_symbols(),
            last_update=None,
        )
    
    return DriftStatus(**status)


@router.get("/alerts", response_model=AlertsResponse)
async def get_alerts(
    limit: int = Query(default=100, ge=1, le=1000, description="Max alerts to return"),
):
    """Get all drift alerts (most recent first)"""
    alerts = get_alerts_from_redis(limit=limit)
    
    return AlertsResponse(
        count=len(alerts),
        alerts=[DriftAlert(**a) for a in alerts],
    )


@router.get("/alerts/latest", response_model=AlertsResponse)
async def get_latest_alerts(
    n: int = Query(default=10, ge=1, le=100, description="Number of alerts"),
):
    """Get latest N drift alerts"""
    alerts = get_alerts_from_redis(limit=n)
    
    return AlertsResponse(
        count=len(alerts),
        alerts=[DriftAlert(**a) for a in alerts],
    )


@router.get("/alerts/{symbol}", response_model=SymbolAlertsResponse)
async def get_alerts_by_symbol(
    symbol: str,
    limit: int = Query(default=50, ge=1, le=500),
):
    """Get drift alerts for specific symbol"""
    symbol = symbol.upper()
    alerts = get_alerts_from_redis(limit=limit, symbol=symbol)
    
    if not alerts:
        return SymbolAlertsResponse(
            symbol=symbol,
            count=0,
            alerts=[],
            message=f"No drift alerts for {symbol}",
        )
    
    return SymbolAlertsResponse(
        symbol=symbol,
        count=len(alerts),
        alerts=[DriftAlert(**a) for a in alerts],
    )


@router.get("/report", response_model=DriftReport)
async def get_report():
    """Get drift detection report"""
    report = get_report_from_redis()
    return DriftReport(**report)


@router.get("/symbols")
async def get_symbols():
    """Get list of tracked symbols with drift alerts"""
    symbols = get_tracked_symbols()
    return {
        "symbols": symbols,
        "count": len(symbols),
    }


@router.post("/reset", response_model=ResetResponse)
async def reset_drift_state():
    """Reset drift detection state (clear alerts)"""
    try:
        client = get_redis_client()
        
        # Delete all drift keys
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = client.scan(cursor, match="drift:*", count=100)
            if keys:
                client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        
        logger.info(f"Reset drift state, deleted {deleted} keys")
        
        return ResetResponse(
            success=True,
            message=f"Drift state reset successfully. Deleted {deleted} keys.",
            timestamp=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.error(f"Reset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get drift detection statistics"""
    alerts = get_alerts_from_redis(limit=1000)
    symbols = get_tracked_symbols()
    
    # Count by severity
    by_severity = {}
    by_symbol = {}
    for alert in alerts:
        sev = alert.get('severity', 'unknown')
        sym = alert.get('symbol', 'unknown')
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_symbol[sym] = by_symbol.get(sym, 0) + 1
    
    return {
        "total_alerts": len(alerts),
        "symbols_tracked": len(symbols),
        "by_severity": by_severity,
        "by_symbol": by_symbol,
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# HISTORICAL ANALYSIS ENDPOINT
# ============================================================================

@router.post("/analyze", response_model=HistoricalAnalysisResponse)
async def analyze_historical(request: HistoricalAnalysisRequest):
    """
    Analyze historical data for drift detection.
    
    This runs drift detection on historical OHLCV data from yfinance,
    allowing you to backtest drift detection on past market conditions.
    
    Example:
        POST /drift/analyze
        {"symbol": "AAPL", "period": "3mo", "interval": "1d"}
    """
    import time
    start_time = time.time()
    
    try:
        # Import yfinance
        try:
            import yfinance as yf
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="yfinance not installed. Run: pip install yfinance"
            )
        
        # Import drift detection
        try:
            from agents.drift_agent import MarketDriftDetector, DriftEvent
        except ImportError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to import drift detector: {e}"
            )
        
        symbol = request.symbol.upper()
        
        # Fetch historical data
        logger.info(f"Fetching historical data for {symbol} ({request.period}, {request.interval})")
        
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=request.period, interval=request.interval)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch data for {symbol}: {e}"
            )
        
        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol} with period={request.period}, interval={request.interval}"
            )
        
        # Initialize detector
        detector = MarketDriftDetector()
        all_events: List[Dict] = []
        
        # Process each row
        prev_close = None
        for idx, row in df.iterrows():
            close = float(row['Close'])
            high = float(row['High'])
            low = float(row['Low'])
            open_price = float(row['Open'])
            
            # Calculate features
            price_return = (close - prev_close) / prev_close if prev_close and prev_close > 0 else 0
            volatility = (high - low) / close if close > 0 else 0
            spread = (high - low) / ((high + low) / 2) if (high + low) > 0 else 0
            momentum = (close - open_price) / open_price if open_price > 0 else 0
            
            features = {
                'price_return': price_return,
                'volume_change': 0,
                'volatility': volatility,
                'spread': spread,
                'momentum': momentum,
                'change_percent': price_return,
            }
            
            # Detect drift
            events = detector.update(features)
            
            # Store events with timestamp and price
            for event in events:
                event_dict = event.to_dict()
                event_dict['timestamp'] = idx.isoformat() if hasattr(idx, 'isoformat') else str(idx)
                event_dict['price'] = close
                all_events.append(event_dict)
            
            prev_close = close
        
        # Aggregate results
        drifts_by_type = {}
        drifts_by_feature = {}
        drifts_by_severity = {}
        
        for event in all_events:
            dtype = event.get('drift_type', 'unknown')
            feature = event.get('feature', 'unknown')
            severity = event.get('severity', 'unknown')
            
            drifts_by_type[dtype] = drifts_by_type.get(dtype, 0) + 1
            drifts_by_feature[feature] = drifts_by_feature.get(feature, 0) + 1
            drifts_by_severity[severity] = drifts_by_severity.get(severity, 0) + 1
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Convert events to response format
        response_events = [
            HistoricalDriftEvent(**event) for event in all_events[-100:]  # Limit to last 100
        ]
        
        return HistoricalAnalysisResponse(
            symbol=symbol,
            period=request.period,
            interval=request.interval,
            data_points=len(df),
            total_drifts=len(all_events),
            drifts_by_type=drifts_by_type,
            drifts_by_feature=drifts_by_feature,
            drifts_by_severity=drifts_by_severity,
            events=response_events,
            analysis_time_ms=round(elapsed_ms, 2),
            message=f"Analyzed {len(df)} data points, found {len(all_events)} drift events"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Historical analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))