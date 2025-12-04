"""
Drift Detection Agent

Pathway-based agent that:
1. Consumes market data from Kafka (market-data topic)
2. Calculates features for drift detection
3. Runs River-based drift detectors (ADWIN, PageHinkley)
4. Stores alerts in Redis for the API to read

Detectors:
- ADWIN: Adaptive Windowing for mean shift detection
- PageHinkley: Cumulative sum for distribution shift
- ZScore: Statistical outlier detection for sudden spikes
- MovingAverage: Short vs long MA for gradual drift
- VarianceMonitor: Rolling variance for volatility changes

Usage:
    python main_drift.py
    
    # Or import directly
    from agents.drift_agent import DriftDetectionAgent
    agent = DriftDetectionAgent()
    agent.run()
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
_parent_dir = Path(__file__).parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

import pathway as pw
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Event publisher for alerts
try:
    from event_publisher import publish_alert
    from redis_cache import get_redis_client as get_redis_client_cache
except ImportError:
    from .event_publisher import publish_alert
    from .redis_cache import get_redis_client as get_redis_client_cache

# River for drift detection
try:
    from river import drift
    RIVER_AVAILABLE = True
except ImportError:
    RIVER_AVAILABLE = False
    drift = None
    print("⚠️ River not installed. Run: pip install river")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# DRIFT DETECTION ENUMS & DATA CLASSES
# ============================================================================

class DriftType(Enum):
    MEAN_SHIFT = "mean_shift"           # Gradual change in average
    VARIANCE_SHIFT = "variance_shift"   # Change in volatility
    DISTRIBUTION_SHIFT = "distribution_shift"  # Overall distribution change
    CONCEPT_DRIFT = "concept_drift"     # Pattern/relationship change
    SUDDEN_SPIKE = "sudden_spike"       # Abrupt single-point anomaly
    GRADUAL_DRIFT = "gradual_drift"     # Slow incremental change
    RECURRING_DRIFT = "recurring_drift" # Periodic/seasonal patterns


class DriftSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftEvent:
    timestamp: datetime
    feature: str
    drift_type: DriftType
    severity: DriftSeverity
    old_value: Optional[float]
    new_value: Optional[float]
    detector: str
    confidence: float
    message: str
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'feature': self.feature,
            'drift_type': self.drift_type.value,
            'severity': self.severity.value,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'detector': self.detector,
            'confidence': self.confidence,
            'message': self.message,
        }


# ============================================================================
# FEATURE DRIFT MONITOR
# ============================================================================

class FeatureDriftMonitor:
    """
    Monitors a single feature for multiple types of concept drift.
    
    Detectors:
    - ZScore: Sudden spike detection (Z > 3.0)
    - MovingAverage: Gradual drift (short MA vs long MA > 5%)
    - VarianceMonitor: Volatility change (> 100% variance change)
    - ADWIN: Mean shift detection (River, delta=0.002)
    - PageHinkley: Distribution shift (River, threshold=50)
    
    Thresholds can be configured via environment variables:
    - DRIFT_SPIKE_THRESHOLD (default: 3.0)
    - DRIFT_GRADUAL_THRESHOLD (default: 0.05)
    - DRIFT_VARIANCE_THRESHOLD (default: 1.0)
    - DRIFT_ADWIN_DELTA (default: 0.002)
    - DRIFT_PH_THRESHOLD (default: 50)
    """
    
    def __init__(self, feature_name: str):
        self.feature_name = feature_name
        self.update_count = 0
        self.drift_events: List[DriftEvent] = []
        
        # Cooldown to prevent alert spam
        self.last_alert_update: Dict[str, int] = {}
        self.alert_cooldown = int(os.getenv('DRIFT_ALERT_COOLDOWN', '10'))
        
        # Load thresholds from environment (or use defaults)
        adwin_delta = float(os.getenv('DRIFT_ADWIN_DELTA', '0.002'))
        ph_threshold = float(os.getenv('DRIFT_PH_THRESHOLD', '50'))
        
        # Initialize River drift detectors
        if RIVER_AVAILABLE:
            try:
                self.adwin = drift.ADWIN(delta=adwin_delta)
            except Exception as e:
                logger.warning(f"Failed to init ADWIN: {e}")
                self.adwin = None
            
            try:
                self.page_hinkley = drift.PageHinkley(
                    min_instances=30,
                    delta=0.005,
                    threshold=ph_threshold,
                    alpha=0.9999
                )
            except Exception as e:
                logger.warning(f"Failed to init PageHinkley: {e}")
                self.page_hinkley = None
        else:
            self.adwin = None
            self.page_hinkley = None
        
        # Track running statistics
        self.values: List[float] = []
        self.window_size = 100
        
        # Thresholds from environment
        self.spike_threshold = float(os.getenv('DRIFT_SPIKE_THRESHOLD', '3.0'))
        self.short_window = 10
        self.long_window = 50
        self.gradual_threshold = float(os.getenv('DRIFT_GRADUAL_THRESHOLD', '0.05'))
        self.variance_change_threshold = float(os.getenv('DRIFT_VARIANCE_THRESHOLD', '1.0'))
    
    def _can_alert(self, drift_type: str) -> bool:
        """Check if enough time has passed since last alert of this type"""
        last = self.last_alert_update.get(drift_type, 0)
        return (self.update_count - last) >= self.alert_cooldown
    
    def _record_alert(self, drift_type: str):
        """Record that we just sent an alert"""
        self.last_alert_update[drift_type] = self.update_count
    
    def _calculate_stats(self) -> Tuple[float, float]:
        """Calculate mean and std of current window"""
        if len(self.values) < 2:
            return 0.0, 1.0
        mean = sum(self.values) / len(self.values)
        variance = sum((x - mean) ** 2 for x in self.values) / len(self.values)
        std = variance ** 0.5 if variance > 0 else 1.0
        return mean, std
    
    def _detect_sudden_spike(self, value: float) -> Optional[DriftEvent]:
        """Detect sudden spike using Z-score"""
        if len(self.values) < 10:
            return None
        
        mean, std = self._calculate_stats()
        if std == 0:
            return None
        
        z_score = abs(value - mean) / std
        
        if z_score > self.spike_threshold:
            return DriftEvent(
                timestamp=datetime.now(),
                feature=self.feature_name,
                drift_type=DriftType.SUDDEN_SPIKE,
                severity=DriftSeverity.HIGH if z_score > 4 else DriftSeverity.MEDIUM,
                old_value=mean,
                new_value=value,
                detector="ZScore",
                confidence=min(0.99, 0.7 + z_score * 0.05),
                message=f"Sudden spike detected in {self.feature_name} (Z={z_score:.2f})",
            )
        return None
    
    def _detect_gradual_drift(self) -> Optional[DriftEvent]:
        """Detect gradual drift by comparing short vs long moving averages"""
        if len(self.values) < self.long_window:
            return None
        
        short_ma = sum(self.values[-self.short_window:]) / self.short_window
        long_ma = sum(self.values[-self.long_window:]) / self.long_window
        
        if long_ma == 0:
            return None
        
        drift_pct = abs(short_ma - long_ma) / abs(long_ma)
        
        if drift_pct > self.gradual_threshold:
            direction = "upward" if short_ma > long_ma else "downward"
            return DriftEvent(
                timestamp=datetime.now(),
                feature=self.feature_name,
                drift_type=DriftType.GRADUAL_DRIFT,
                severity=DriftSeverity.LOW if drift_pct < 0.05 else DriftSeverity.MEDIUM,
                old_value=long_ma,
                new_value=short_ma,
                detector="MovingAverage",
                confidence=min(0.95, 0.6 + drift_pct * 2),
                message=f"Gradual {direction} drift in {self.feature_name} ({drift_pct*100:.1f}%)",
            )
        return None
    
    def _detect_variance_shift(self) -> Optional[DriftEvent]:
        """Detect change in variance/volatility"""
        if len(self.values) < 20:
            return None
        
        # Current variance (recent half)
        recent = self.values[-10:]
        recent_mean = sum(recent) / len(recent)
        current_var = sum((x - recent_mean) ** 2 for x in recent) / len(recent)
        
        # Historical variance (older half)
        older = self.values[-20:-10]
        older_mean = sum(older) / len(older)
        old_var = sum((x - older_mean) ** 2 for x in older) / len(older)
        
        if old_var == 0:
            return None
        
        var_change = abs(current_var - old_var) / old_var
        
        if var_change > self.variance_change_threshold:
            direction = "increased" if current_var > old_var else "decreased"
            return DriftEvent(
                timestamp=datetime.now(),
                feature=self.feature_name,
                drift_type=DriftType.VARIANCE_SHIFT,
                severity=DriftSeverity.MEDIUM if var_change < 1.0 else DriftSeverity.HIGH,
                old_value=old_var ** 0.5,  # Return std not var
                new_value=current_var ** 0.5,
                detector="VarianceMonitor",
                confidence=min(0.95, 0.5 + var_change * 0.3),
                message=f"Volatility {direction} in {self.feature_name} ({var_change*100:.1f}%)",
            )
        return None
    
    def update(self, value: float) -> List[DriftEvent]:
        """Update with new value and check for all drift types"""
        events = []
        self.update_count += 1
        
        # Check for sudden spike BEFORE adding to history (with cooldown)
        if self._can_alert('sudden_spike'):
            spike_event = self._detect_sudden_spike(value)
            if spike_event:
                self._record_alert('sudden_spike')
                events.append(spike_event)
        
        # Store value
        self.values.append(value)
        if len(self.values) > self.window_size:
            self.values.pop(0)
        
        # Check for gradual drift (with cooldown)
        if self._can_alert('gradual_drift'):
            gradual_event = self._detect_gradual_drift()
            if gradual_event:
                self._record_alert('gradual_drift')
                events.append(gradual_event)
        
        # Check for variance shift (with cooldown)
        if self._can_alert('variance_shift'):
            variance_event = self._detect_variance_shift()
            if variance_event:
                self._record_alert('variance_shift')
                events.append(variance_event)
        
        # River-based detectors
        if RIVER_AVAILABLE:
            # Check ADWIN (mean shift) - with cooldown
            if self.adwin is not None and self._can_alert('mean_shift'):
                try:
                    self.adwin.update(value)
                    if self.adwin.drift_detected:
                        self._record_alert('mean_shift')
                        events.append(DriftEvent(
                            timestamp=datetime.now(),
                            feature=self.feature_name,
                            drift_type=DriftType.MEAN_SHIFT,
                            severity=DriftSeverity.MEDIUM,
                            old_value=self.adwin.estimation if hasattr(self.adwin, 'estimation') else None,
                            new_value=value,
                            detector="ADWIN",
                            confidence=0.95,
                            message=f"ADWIN detected mean shift in {self.feature_name}",
                        ))
                except Exception as e:
                    logger.debug(f"ADWIN error: {e}")
            elif self.adwin is not None:
                # Still update ADWIN even if we can't alert
                try:
                    self.adwin.update(value)
                except:
                    pass
            
            # Check Page-Hinkley (distribution shift) - with cooldown
            if self.page_hinkley is not None and self._can_alert('distribution_shift'):
                try:
                    self.page_hinkley.update(value)
                    if self.page_hinkley.drift_detected:
                        self._record_alert('distribution_shift')
                        events.append(DriftEvent(
                            timestamp=datetime.now(),
                            feature=self.feature_name,
                            drift_type=DriftType.DISTRIBUTION_SHIFT,
                            severity=DriftSeverity.MEDIUM,
                            old_value=None,
                            new_value=value,
                            detector="PageHinkley",
                            confidence=0.85,
                            message=f"Page-Hinkley detected distribution shift in {self.feature_name}",
                        ))
                except Exception as e:
                    logger.debug(f"Page-Hinkley error: {e}")
            elif self.page_hinkley is not None:
                # Still update PageHinkley even if we can't alert
                try:
                    self.page_hinkley.update(value)
                except:
                    pass
        
        self.drift_events.extend(events)
        return events


# ============================================================================
# MARKET DRIFT DETECTOR
# ============================================================================

class MarketDriftDetector:
    """
    Main drift detector for market data.
    
    Monitors multiple features:
    - price_return: Percentage price change
    - volume_change: Percentage volume change
    - volatility: Intraday volatility (high-low)/close
    - spread: Bid-ask spread proxy
    - momentum: Price momentum
    """
    
    FEATURES = ['price_return', 'volume_change', 'volatility', 'spread', 'momentum', 'change_percent']
    
    def __init__(self):
        self.monitors = {f: FeatureDriftMonitor(f) for f in self.FEATURES}
        self.all_drift_events: List[DriftEvent] = []
        self.total_updates = 0
    
    def update(self, features: Dict[str, float]) -> List[DriftEvent]:
        """Update all monitors with new feature values"""
        all_events = []
        self.total_updates += 1
        
        for feature_name, value in features.items():
            if feature_name in self.monitors:
                events = self.monitors[feature_name].update(value)
                all_events.extend(events)
        
        self.all_drift_events.extend(all_events)
        return all_events
    
    def get_status(self) -> Dict:
        """Get current status"""
        return {
            'total_updates': self.total_updates,
            'total_drifts': len(self.all_drift_events),
            'features': self.FEATURES,
            'drifts_by_feature': {
                f: len(m.drift_events) for f, m in self.monitors.items()
            }
        }


# ============================================================================
# DRIFT ALERT SYSTEM
# ============================================================================

# Drift alert cooldowns (module-level)
_drift_alert_cooldowns: Dict[str, datetime] = {}

def trigger_drift_alert(symbol: str, drift_event: 'DriftEvent'):
    """Trigger alert for high-severity drift events (pure math, no LLM)."""
    
    alerts_enabled = os.getenv("DRIFT_ALERT_ENABLED", "true").lower() == "true"
    alert_cooldown = int(os.getenv("DRIFT_ALERT_COOLDOWN", "300"))  # 5 min default
    
    if not alerts_enabled:
        return
    
    # Only alert on HIGH or CRITICAL severity
    if drift_event.severity not in [DriftSeverity.HIGH, DriftSeverity.CRITICAL]:
        return
    
    # Check cooldown
    now = datetime.now()
    last = _drift_alert_cooldowns.get(symbol)
    if last and (now - last).total_seconds() < alert_cooldown:
        return
    
    severity_str = drift_event.severity.value
    reason = f"{drift_event.drift_type.value}: {drift_event.message}"
    
    logger.info(f"🚨 [{symbol}] DRIFT ALERT: {reason}")
    
    try:
        redis_client = get_redis_client_cache()
        publish_alert(
            symbol=symbol,
            alert_type="drift",
            reason=reason,
            severity=severity_str,
            redis_sync=redis_client,
            trigger_debate=True
        )
        _drift_alert_cooldowns[symbol] = now
        logger.info(f"✅ [{symbol}] Drift alert published at {now.isoformat()}")
    except Exception as e:
        logger.error(f"⚠️ [{symbol}] Drift alert failed: {e}")


# ============================================================================
# GLOBAL STATE FOR PATHWAY UDF
# ============================================================================

# Global detector instance (Pathway UDFs need to be stateless, so we use globals)
_detector: Optional[MarketDriftDetector] = None
_prev_values: Dict[str, Dict] = {}
_redis_client = None


def _get_detector() -> MarketDriftDetector:
    global _detector
    if _detector is None:
        _detector = MarketDriftDetector()
    return _detector


def _get_redis():
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            host = os.getenv('REDIS_HOST', 'redis')
            port = int(os.getenv('REDIS_PORT', '6379'))
            _redis_client = redis.Redis(host=host, port=port, decode_responses=True)
            _redis_client.ping()
            logger.info("✅ Connected to Redis")
        except Exception as e:
            logger.warning(f"⚠️ Redis not available: {e}")
            _redis_client = None
    return _redis_client


def _store_alert_in_redis(alert: Dict, symbol: str):
    """Store alert in Redis"""
    client = _get_redis()
    if client is None:
        return
    
    try:
        alert_json = json.dumps(alert)
        
        # Store in main list
        client.lpush('drift:alerts', alert_json)
        client.ltrim('drift:alerts', 0, 999)
        
        # Store by symbol
        client.lpush(f'drift:alerts:{symbol}', alert_json)
        client.ltrim(f'drift:alerts:{symbol}', 0, 99)
        
        # Update status
        detector = _get_detector()
        status = {
            'running': True,
            'total_updates': detector.total_updates,
            'total_drifts': len(detector.all_drift_events),
            'features_monitored': detector.FEATURES,
            'symbols_tracked': list(_prev_values.keys()),
            'last_update': datetime.now().isoformat(),
        }
        client.set('drift:status', json.dumps(status))
        
    except Exception as e:
        logger.error(f"Redis error: {e}")


# ============================================================================
# PATHWAY UDF FOR DRIFT DETECTION
# ============================================================================

@pw.udf
def detect_drift(
    symbol: str,
    current_price: float,
    high: float,
    low: float,
    open_price: float,
    change_percent: Optional[float],
) -> str:
    """
    Pathway UDF that detects drift and stores alerts.
    Returns JSON string of drift events (empty if none).
    """
    global _prev_values
    
    detector = _get_detector()
    
    # Get previous values
    prev = _prev_values.get(symbol, {})
    prev_close = prev.get('close', current_price)
    
    # Calculate features
    price_return = (current_price - prev_close) / prev_close if prev_close > 0 else 0
    volatility = (high - low) / current_price if current_price > 0 else 0
    spread = (high - low) / ((high + low) / 2) if (high + low) > 0 else 0
    momentum = (current_price - open_price) / open_price if open_price > 0 else 0
    
    # Handle None change_percent
    safe_change_percent = (change_percent / 100) if change_percent is not None else 0
    
    features = {
        'price_return': price_return,
        'volume_change': 0,  # Requires volume data from producer
        'volatility': volatility,
        'spread': spread,
        'momentum': momentum,
        'change_percent': safe_change_percent,
    }
    
    # Update state
    _prev_values[symbol] = {'close': current_price}
    
    # Detect drift
    events = detector.update(features)
    
    # Always update status in Redis (even if no drift)
    client = _get_redis()
    if client:
        try:
            status = {
                'running': True,
                'total_updates': detector.total_updates,
                'total_drifts': len(detector.all_drift_events),
                'features_monitored': detector.FEATURES,
                'symbols_tracked': list(_prev_values.keys()),
                'last_update': datetime.now().isoformat(),
            }
            client.set('drift:status', json.dumps(status))
        except Exception as e:
            pass  # Ignore Redis errors for status
    
    # Store alerts and trigger alert system for high-severity events
    for event in events:
        alert = {
            'id': f"{symbol}_{event.timestamp.isoformat()}_{event.feature}",
            'symbol': symbol,
            'price': current_price,
            **event.to_dict(),
        }
        _store_alert_in_redis(alert, symbol)
        logger.info(f"🚨 DRIFT: {symbol} | {event.feature} | {event.drift_type.value}")
        
        # Trigger WebSocket alert + Bull-Bear debate for high-severity events
        trigger_drift_alert(symbol, event)
    
    if events:
        return json.dumps([e.to_dict() for e in events])
    return ""


# ============================================================================
# DRIFT DETECTION AGENT
# ============================================================================

class DriftDetectionAgent:
    """
    Pathway agent for drift detection.
    
    Consumes market data, runs drift detection, stores in Redis.
    """
    
    def __init__(
        self,
        kafka_bootstrap: str = "kafka:29092",
        market_topic: str = "market-data",
    ):
        self.kafka_bootstrap = kafka_bootstrap
        self.market_topic = market_topic
        
        self.rdkafka_settings = {
            "bootstrap.servers": kafka_bootstrap,
            "group.id": "pathway-drift-agent",
            "auto.offset.reset": "latest",
        }
    
    def run(self):
        """Run the drift detection pipeline"""
        logger.info("=" * 60)
        logger.info("🚀 DRIFT DETECTION AGENT")
        logger.info(f"   Kafka: {self.kafka_bootstrap}")
        logger.info(f"   Topic: {self.market_topic}")
        logger.info("=" * 60)
        
        # Use DriftConsumer to get market data table
        from consumers.drift_consumer import DriftConsumer
        
        consumer = DriftConsumer()
        market_data = consumer.consume()
        
        # Apply drift detection UDF
        drift_results = market_data.select(
            symbol=pw.this.symbol,
            price=pw.this.current_price,
            drift_events=detect_drift(
                pw.this.symbol,
                pw.this.current_price,
                pw.this.high,
                pw.this.low,
                pw.this.open,
                pw.this.change_percent,
            ),
        )
        
        # Filter to only rows with drift events (for logging)
        drift_alerts = drift_results.filter(pw.this.drift_events != "")
        
        # Write to null sink (required to materialize the pipeline)
        pw.io.null.write(drift_alerts)
        
        logger.info("✅ Pipeline ready. Starting pw.run()...")
        logger.info("   Waiting for market data from Kafka...")
        logger.info("   Press Ctrl+C to stop")
        
        # Enable Pathway persistence for drift state
        persistence_path = os.path.join(os.path.dirname(__file__), "..", "pathway_state", "drift")
        os.makedirs(persistence_path, exist_ok=True)
        logger.info(f"💾 Persistence enabled at: {persistence_path}")
        
        # Run the pipeline with persistence
        pw.run(
            persistence_config=pw.persistence.Config.simple_config(
                pw.persistence.Backend.filesystem(persistence_path),
                snapshot_interval_ms=60000  # Snapshot every 60 seconds
            )
        )