"""
LangGraph + Pathway implementation for streaming market analysis.
Uses custom reducers for technical indicators and multi-agent workflow.
"""

import json
import time
import os
from pathlib import Path
from typing import Annotated, List, TypedDict, Dict, Any
from datetime import datetime, timedelta

import numpy as np
import talib
import pathway as pw
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain.globals import set_llm_cache
from langchain.cache import InMemoryCache
from openai import RateLimitError
from dotenv import load_dotenv

# Enable LLM caching to reduce redundant API calls
# This caches identical prompts, saving money on repeated analysis
set_llm_cache(InMemoryCache())

# Import Redis and PostgreSQL save functions
try:
    from redis_cache import save_report_to_postgres, save_report_to_redis
    from event_publisher import publish_agent_status, publish_report
except ImportError:
    try:
        from .redis_cache import save_report_to_postgres, save_report_to_redis
        from .event_publisher import publish_agent_status, publish_report
    except ImportError:
        save_report_to_postgres = None
        save_report_to_redis = None
        publish_agent_status = None
        publish_report = None

try:
    from Pathway_InterIIT.pathway.agents.utils.tool_creation import TechnicalTools
except ImportError:
    try:
        from agents.utils.tool_creation import TechnicalTools
    except ImportError:
        from .utils.tool_creation import TechnicalTools

load_dotenv()


# =====================================================================
# MODULE-LEVEL LLM INITIALIZATION (avoids recreating on every UDF call)
# =====================================================================

def _get_llm_clients():
    """Initialize LLM clients once at module level.
    
    Returns tuple of (tool_llm, graph_llm) configured for OpenRouter or OpenAI.
    Cached at module level to avoid recreation on every UDF call.
    """
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if openrouter_key:
        tool_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1"
        )
        graph_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1"
        )
        return tool_llm, graph_llm
    elif openai_key:
        tool_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=openai_key)
        graph_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=openai_key)
        return tool_llm, graph_llm
    else:
        return None, None

# Initialize LLMs at module load time (lazy - only when first used)
_llm_cache = {}

def get_cached_llms():
    """Get cached LLM instances, initializing once if needed."""
    if 'tool_llm' not in _llm_cache:
        tool_llm, graph_llm = _get_llm_clients()
        _llm_cache['tool_llm'] = tool_llm
        _llm_cache['graph_llm'] = graph_llm
    return _llm_cache['tool_llm'], _llm_cache['graph_llm']


# =====================================================================
# STATE DEFINITION
# =====================================================================

class AgentState(TypedDict):
    """State with precomputed data - no tool calls needed."""
    
    # Input metadata
    stock_name: Annotated[str, "Stock symbol"]
    time_frame: Annotated[str, "Time period (e.g., '5m', '15m', '1h')"]
    timestamp: Annotated[str, "Analysis timestamp"]
    
    # Raw OHLCV data (for context)
    kline_data: Annotated[Dict[str, List], "Raw OHLCV data"]
    
    # PRECOMPUTED Indicator values (no need to compute)
    rsi: Annotated[List[float], "Precomputed RSI values"]
    macd: Annotated[List[float], "Precomputed MACD line values"]
    macd_signal: Annotated[List[float], "Precomputed MACD signal line values"]
    macd_hist: Annotated[List[float], "Precomputed MACD histogram values"]
    stoch_k: Annotated[List[float], "Precomputed Stochastic %K values"]
    stoch_d: Annotated[List[float], "Precomputed Stochastic %D values"]
    roc: Annotated[List[float], "Precomputed Rate of Change values"]
    willr: Annotated[List[float], "Precomputed Williams %R values"]
    
    # PRECOMPUTED Images (base64 encoded) - provided to LLM prompts, NOT embedded in reports
    pattern_image: Annotated[str, "Precomputed base64 K-line chart"]
    trend_image: Annotated[str, "Precomputed base64 trend chart with support/resistance"]
    rsi_plot: Annotated[str, "Precomputed base64 RSI plot"]
    macd_plot: Annotated[str, "Precomputed base64 MACD plot"]
    stochastic_plot: Annotated[str, "Precomputed base64 Stochastic plot"]
    roc_plot: Annotated[str, "Precomputed base64 ROC plot"]
    willr_plot: Annotated[str, "Precomputed base64 Williams %R plot"]
    price_plot: Annotated[str, "Precomputed base64 Price plot"]
    
    # Agent Analysis Results
    indicator_report: Annotated[str, "Indicator agent interpretation"]
    pattern_report: Annotated[str, "Pattern agent analysis"]
    trend_report: Annotated[str, "Trend agent analysis"]
    
    # Final outputs
    messages: Annotated[List[BaseMessage], "Conversation history"]
    final_trade_decision: Annotated[str, "Final BUY/SELL/HOLD decision"]
    confidence_score: Annotated[float, "Confidence in decision (0-1)"]


# =====================================================================
# RETRY UTILITY
# =====================================================================

def invoke_with_retry(call_fn, *args, retries=3, initial_wait_sec=2):
    """Retry LLM calls with exponential backoff.
    
    Uses exponential backoff: 2s, 4s, 8s (doubles each retry).
    This is more efficient than fixed wait times.
    """
    wait_sec = initial_wait_sec
    for attempt in range(retries):
        try:
            return call_fn(*args)
        except RateLimitError:
            print(f"⚠️ Rate limit hit, retrying in {wait_sec}s (attempt {attempt + 1}/{retries})...")
            time.sleep(wait_sec)
            wait_sec *= 2  # Exponential backoff
        except Exception as e:
            print(f"⚠️ Error: {e}, retrying in {wait_sec}s (attempt {attempt + 1}/{retries})...")
            if attempt < retries - 1:
                time.sleep(wait_sec)
                wait_sec *= 2  # Exponential backoff
    raise RuntimeError("Max retries exceeded")


# =====================================================================
# AGENT 1: INDICATOR AGENT (Interpretation Only)
# =====================================================================

def create_indicator_agent(llm):
    """
    Indicator agent that INTERPRETS precomputed technical indicators.
    Now receives indicator PLOT IMAGES in addition to values.
    """
    
    def indicator_agent_node(state: AgentState) -> Dict[str, Any]:
        """Interpret precomputed indicator values with visual plots."""
        
        stock_name = state["stock_name"]
        time_frame = state["time_frame"]
        
        # Get precomputed values (latest values for quick analysis)
        latest_rsi = state["rsi"][-5:] if state.get("rsi") else []
        latest_macd = state["macd"][-5:] if state.get("macd") else []
        latest_macd_signal = state["macd_signal"][-5:] if state.get("macd_signal") else []
        latest_macd_hist = state["macd_hist"][-5:] if state.get("macd_hist") else []
        latest_stoch_k = state["stoch_k"][-5:] if state.get("stoch_k") else []
        latest_stoch_d = state["stoch_d"][-5:] if state.get("stoch_d") else []
        latest_roc = state["roc"][-5:] if state.get("roc") else []
        latest_willr = state["willr"][-5:] if state.get("willr") else []
        
        # Get indicator plot images (base64)
        rsi_plot = state.get("rsi_plot", "")
        macd_plot = state.get("macd_plot", "")
        stoch_plot = state.get("stochastic_plot", "")
        roc_plot = state.get("roc_plot", "")
        willr_plot = state.get("willr_plot", "")
        
        # Create analysis prompt with images
        prompt_content = [
            {
                "type": "text",
                "text": f"""TECHNICAL MOMENTUM SCAN: {stock_name} ({time_frame})

LIVE READINGS (last 5 periods):
• RSI(14): {latest_rsi}
• MACD Line/Signal/Hist: {latest_macd} | {latest_macd_signal} | {latest_macd_hist}
• Stochastic %K/%D: {latest_stoch_k} | {latest_stoch_d}
• ROC(10): {latest_roc}
• Williams %R(14): {latest_willr}

[Indicator plots attached below]

ANALYSIS FRAMEWORK:

1. MOMENTUM REGIME
   • Current state: OVERBOUGHT (RSI>70, %K>80) | OVERSOLD (RSI<30, %K<20) | NEUTRAL
   • Exhaustion signals: RSI divergence, MACD histogram contraction, %K/%D crossover
   • Momentum velocity: ROC acceleration/deceleration, Williams %R thrust

2. INDICATOR CONFLUENCE
   • Alignment score: How many indicators agree on direction? (0-5 scale)
   • Divergence alert: Price vs RSI/MACD divergence = potential reversal
   • Lead indicators: Which is signaling first? (Stochastic leads, MACD confirms)

3. TRADE SIGNAL
   • Entry trigger: Specific condition (e.g., "RSI bouncing off 30 + MACD crossover")
   • Invalidation: What reading kills the setup?
   • Confidence: HIGH (4-5 align) | MEDIUM (2-3 align) | LOW (conflicting)

Output format: Direct, numbers-based, skip fluff."""
            }
        ]
        
        # Add available indicator plot images to prompt
        if rsi_plot:
            prompt_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{rsi_plot}"}
            })
        if macd_plot:
            prompt_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{macd_plot}"}
            })
        if stoch_plot:
            prompt_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{stoch_plot}"}
            })
        if roc_plot:
            prompt_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{roc_plot}"}
            })
        if willr_plot:
            prompt_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{willr_plot}"}
            })
        
        system_msg = SystemMessage(content="Quantitative momentum analyst. Parse indicator arrays, detect regime shifts, identify confluence. Output: actionable signals with specific trigger levels. No hedging language.")
        user_msg = HumanMessage(content=prompt_content)
        
        messages = state.get("messages", [])
        messages.extend([system_msg, user_msg])
        
        # Get LLM interpretation
        print(f"🔍 Indicator Agent analyzing {stock_name} with visual plots...")
        ai_response = invoke_with_retry(llm.invoke, messages)
        messages.append(ai_response)
        
        return {
            "messages": messages,
            "indicator_report": ai_response.content,
        }
    
    return indicator_agent_node


# =====================================================================
# AGENT 2: PATTERN AGENT (Visual Analysis)
# =====================================================================

def create_pattern_agent(llm):
    """
    Pattern agent that analyzes PRECOMPUTED candlestick chart images.
    Uses vision model to identify patterns.
    """
    
    def pattern_agent_node(state: AgentState) -> Dict[str, Any]:
        """Analyze precomputed pattern image."""
        
        stock_name = state["stock_name"]
        time_frame = state["time_frame"]
        pattern_image_b64 = state.get("pattern_image")
        
        if not pattern_image_b64:
            print("⚠️ Warning: No pattern image provided")
            return {
                "pattern_report": "No pattern image available for analysis.",
            }
        
        pattern_definitions = """
KEY PATTERNS TO IDENTIFY:
Bullish: Inverse H&S, Double Bottom, Falling Wedge, Ascending Triangle, Bullish Flag
Bearish: Rising Wedge, Descending Triangle, Bearish Flag, Head & Shoulders
Neutral: Rectangle, Symmetrical Triangle, Expanding Triangle
"""
        
        # Create vision prompt
        image_prompt = [
            {
                "type": "text",
                "text": f"""Analyze this candlestick chart for {stock_name} ({time_frame}).
{pattern_definitions}
PROVIDE:
1. PATTERN IDENTIFIED: Name + completion status (%)
2. STRUCTURE: Key levels forming the pattern
3. RELIABILITY: Historical accuracy of this pattern (high/medium/low)
4. PRICE TARGET: Expected move based on pattern measurement
5. INVALIDATION: Level where pattern fails

Focus on the most actionable pattern visible."""
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{pattern_image_b64}"},
            },
        ]
        
        messages = state.get("messages", [])
        
        print(f"Pattern Agent analyzing {stock_name} chart...")
        final_response = invoke_with_retry(
            llm.invoke,
            [
                SystemMessage(content="Chart pattern specialist. Identify formations using classical TA rules, calculate measured-move targets, assess completion probability. Quote specific price levels."),
                HumanMessage(content=image_prompt),
            ],
        )
        
        messages.append(final_response)
        
        return {
            "messages": messages,
            "pattern_report": final_response.content,
        }
    
    return pattern_agent_node


# =====================================================================
# AGENT 3: TREND AGENT (Trendline Analysis)
# =====================================================================

def create_trend_agent(llm):
    """
    Trend agent that analyzes PRECOMPUTED trend chart with support/resistance lines.
    Uses vision model to assess trend direction.
    """
    
    def trend_agent_node(state: AgentState) -> Dict[str, Any]:
        """Analyze precomputed trend image."""
        
        stock_name = state["stock_name"]
        time_frame = state["time_frame"]
        trend_image_b64 = state.get("trend_image")
        
        if not trend_image_b64:
            print("⚠️ Warning: No trend image provided")
            return {
                "trend_report": "No trend image available for analysis.",
            }
        
        # Create vision prompt
        image_prompt = [
            {
                "type": "text",
                "text": f"""TREND STRUCTURE ANALYSIS: {stock_name} ({time_frame})

[Trend chart with support/resistance attached]

TREND FRAMEWORK:

1. MARKET STRUCTURE
   • Primary trend: UPTREND (higher highs + higher lows) | DOWNTREND (lower highs + lower lows) | RANGE-BOUND
   • Trend strength: STRONG (steep angle, no violations) | MODERATE (some noise) | WEAK (flat, choppy)
   • Recent structure: Has the last swing violated the trend? (Higher low held? Lower high defended?)

2. CRITICAL LEVELS
   • Immediate resistance: [Price] — What's stopping upside NOW?
   • Immediate support: [Price] — What's protecting downside NOW?
   • Major levels: Swing highs/lows from this timeframe that matter
   • Level quality: Tested multiple times? Clean rejection? Volume spike at level?

3. TRENDLINE STATUS
   • Primary trendline: INTACT (price respecting) | TESTING (currently at line) | BROKEN (decisive close through)
   • Slope dynamics: Steepening (momentum increasing) | Flattening (momentum fading) | Curving (potential exhaustion)
4. BREAKOUT RISK: Distance to nearest breakout/breakdown zone
5. BIAS: Bullish/Bearish/Neutral for next 1-3 periods with confidence %

Be precise with price levels."""
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{trend_image_b64}"},
            },
        ]
        
        messages = state.get("messages", [])
        
        print(f"Trend Agent analyzing {stock_name} trends...")
        final_response = invoke_with_retry(
            llm.invoke,
            [
                SystemMessage(content="Trend structure analyst. Map support/resistance, assess trendline integrity, identify breakout/breakdown zones. Quote specific price levels with context."),
                HumanMessage(content=image_prompt),
            ],
        )
        
        messages.append(final_response)
        
        return {
            "messages": messages,
            "trend_report": final_response.content,
        }
    
    return trend_agent_node



# =====================================================================
# GRAPH CONSTRUCTION
# =====================================================================

def create_trading_graph(tool_llm, graph_llm):
    """
    Create the LangGraph workflow with three agents in sequence.
    """
    
    # Create agent nodes
    indicator_node = create_indicator_agent(tool_llm)
    pattern_node = create_pattern_agent(graph_llm)
    trend_node = create_trend_agent(graph_llm)
    
    # Build graph
    workflow = StateGraph(AgentState)
    workflow.add_node("indicator_agent", indicator_node)
    workflow.add_node("pattern_agent", pattern_node)
    workflow.add_node("trend_agent", trend_node)
    
    # Sequential execution
    workflow.set_entry_point("indicator_agent")
    workflow.add_edge("indicator_agent", "pattern_agent")
    workflow.add_edge("pattern_agent", "trend_agent")
    workflow.add_edge("trend_agent", END)
    
    return workflow.compile()


# =====================================================================
# PATHWAY INTEGRATION - WINDOWING AND STREAMING
# =====================================================================
def process_market_stream_with_agents(
    market_table: pw.Table,
    lookback_minutes: int = 10,
    hop_minutes: int = 5,
    min_data_points: int = 5,
    reports_directory: str = "./reports/market",
    indicators: list = None
) -> pw.Table:
    """
    Process market data stream with sliding windows and LangGraph agents.
    
    This function:
    1. Applies sliding window: analyzes past Y minutes every X minutes per stock
    2. Aggregates OHLCV data for each window
    3. Precomputes technical indicators and charts
    4. Runs LangGraph agent analysis
    5. Generates comprehensive trading reports
    
    Args:
        market_table: Pathway table from MarketDataConsumer
        lookback_minutes: How far back to look (window duration, default: 10)
        hop_minutes: How often to generate reports (hop/step, default: 5)
        min_data_points: Minimum data points required per window (default: 30)
                        Calculate based on: (lookback_minutes * 60) / data_interval_seconds
                        Example: 5min window with 10sec intervals = (5*60)/10 = 30 points
                        For 1min data over 10min window = (10*60)/60 = 10 points
        reports_directory: Base directory for reports (default: ./reports/market)
        indicators: List of specific indicators to compute (None = all)
                   e.g., ['RSI', 'MACD', 'STOCH', 'BB']
        
    Returns:
        Pathway table with agent analysis results
    
    Structure:
        ./reports/market/{SYMBOL}/reports/  - Markdown reports and JSON data
        ./reports/market/{SYMBOL}/images/   - Chart images
    
    Example:
        lookback_minutes=10, hop_minutes=5, min_data_points=30
        → Every 5 minutes, analyze the past 10 minutes of data
        → Only process windows with at least 30 data points
        → Reports at: 14:05 (data 13:55-14:05), 14:10 (data 14:00-14:10), etc.
        
    Data Quality Notes:
        - Windows with insufficient data are automatically skipped
        - Prevents unreliable technical indicators from sparse data
        - Adjust min_data_points based on your data frequency
        - For HFT (1-second data), use higher values (e.g., 300 for 5min)
        - For slower data (1-minute), use lower values (e.g., 5-10 for 5min)
    """
    
    print(f"=" * 70)
    print(f"🚀 Pathway + LangGraph Market Agent System (Sliding Window)")
    print(f"=" * 70)
    print(f"📊 Lookback Window: {lookback_minutes} minutes (how far back to analyze)")
    print(f"⏱️  Report Frequency: Every {hop_minutes} minutes (hop)")
    print(f"📊 Minimum Data Points: {min_data_points} (quality threshold)")
    print(f"📁 Reports Directory: {reports_directory}/{{SYMBOL}}/")
    print(f"")
    print(f"💡 Each report analyzes the past {lookback_minutes} minutes")
    print(f"💡 New reports generated every {hop_minutes} minutes per stock")
    print(f"💡 Windows with < {min_data_points} data points are skipped")
    
    # Create reports directory
    reports_dir = Path(reports_directory)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse timestamp for windowing
    enriched_table = market_table.select(
        pw.this.symbol,
        pw.this.timestamp,
        pw.this.open,
        pw.this.high,
        pw.this.low,
        pw.this.current_price,
        pw.this.previous_close,
        pw.this.change,
        pw.this.change_percent,
        sent_at=pw.this.sent_at.dt.strptime("%Y-%m-%dT%H:%M:%S.%f")
    )
    
    # Apply sliding window per stock
    print(f"🔄 Applying sliding window per stock...")
    print(f"   Duration: {lookback_minutes}min, Hop: {hop_minutes}min")
    
    # Window reduce using module-level custom reducers
    windowed_table = enriched_table.windowby(
        enriched_table.sent_at,
        window=pw.temporal.sliding(
            duration=timedelta(minutes=lookback_minutes),
            hop=timedelta(minutes=hop_minutes)
        ),
        instance=enriched_table.symbol
    ).reduce(
        symbol=pw.this._pw_instance,
        window_start=pw.this._pw_window_start,
        window_end=pw.this._pw_window_end,
        # Collect all data points in window as tuples
        timestamps=pw.reducers.sorted_tuple(pw.this.timestamp),
        opens=pw.reducers.sorted_tuple(pw.coalesce(pw.this.open, 0.0)),
        highs=pw.reducers.sorted_tuple(pw.coalesce(pw.this.high, 0.0)),
        lows=pw.reducers.sorted_tuple(pw.coalesce(pw.this.low, 0.0)),
        closes=pw.reducers.sorted_tuple(pw.coalesce(pw.this.current_price, 0.0)),
        # Aggregated metrics
        data_points=pw.reducers.count(),
        latest_price=pw.reducers.argmax(pw.this.sent_at, pw.coalesce(pw.this.current_price, 0.0)),
        latest_change=pw.reducers.argmax(pw.this.sent_at, pw.coalesce(pw.this.change, 0.0)),
        latest_change_percent=pw.reducers.argmax(pw.this.sent_at, pw.coalesce(pw.this.change_percent, 0.0))
    )
    
    # Debug: Log window contents
    @pw.udf
    def log_window_info(symbol: str, data_points: int, timestamps: tuple, window_start, window_end) -> str:
        """Debug logging for window contents."""
        window_duration_min = (window_end - window_start).total_seconds() / 60
        print(f"🔍 Window for {symbol}: {data_points} data points over {window_duration_min:.1f} minutes")
        if len(timestamps) > 0:
            print(f"   First: {timestamps[0]}, Last: {timestamps[-1]}")
        else:
            print(f"   ⚠️ No data in this window!")
        return symbol
    
    @pw.udf
    def check_data_quality(symbol: str, data_points: int, min_required: int) -> bool:
        """Check if window has sufficient data and log warnings."""
        if data_points < min_required:
            print(f"⚠️ SKIPPED: {symbol} window has only {data_points} points (need {min_required})")
            return False
        return True
    
    windowed_table = windowed_table.select(
        *pw.this,
        _debug=log_window_info(
            pw.this.symbol, 
            pw.this.data_points, 
            pw.this.timestamps,
            pw.this.window_start,
            pw.this.window_end
        ),
        _has_sufficient_data=check_data_quality(
            pw.this.symbol,
            pw.this.data_points,
            min_data_points
        )
    )
    
    # Filter windows with insufficient data
    # Ensures reliable indicator calculation (e.g., 5min window with 10sec intervals = 30 points)
    print(f"⚡ Filtering windows with at least {min_data_points} data points...")
    print(f"   Windows below this threshold will be logged and skipped")
    
    windowed_table = windowed_table.filter(pw.this.data_points >= min_data_points)
    
    # Precompute indicators and run agent analysis
    print("🤖 Setting up agent analysis pipeline...")
    analyzed_table = _precompute_and_analyze(windowed_table, indicators)
    
    # Setup report saving
    _setup_agent_report_saving(analyzed_table, reports_dir)
    
    return analyzed_table


def _precompute_and_analyze(windowed_table: pw.Table, indicators: list = None) -> pw.Table:
    """
    Precompute indicators, generate images, and run LangGraph analysis.
    
    Args:
        windowed_table: Pathway table with windowed market data
        indicators: List of specific indicators to compute (None = all)
    """
    
    # Initialize tool helper
    tech_tools = TechnicalTools()
    
    # Helper function to save reports
    def save_reports_immediately(symbol, window_start, window_end, kline_dict, indicators_dict, images_dict, agent_results):
        """
        Save all reports and image files including comprehensive indicator plots.
        Handles any data frequency: z second OHLCV data over y minute windows.
        """
        import base64
        
        try:
            reports_dir = Path("./reports/market") / symbol
            reports_subdir = reports_dir / "reports"
            images_dir = reports_dir / "images"
            
            reports_subdir.mkdir(parents=True, exist_ok=True)
            images_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            
            # Save candlestick pattern image
            if images_dict.get('pattern_image'):
                img_path = images_dir / f"candlestick_{timestamp}.png"
                try:
                    with open(img_path, 'wb') as f:
                        f.write(base64.b64decode(images_dict['pattern_image']))
                    print(f"✅ Saved candlestick chart: {img_path}")
                except Exception as e:
                    print(f"❌ Failed to save candlestick image: {e}")
            else:
                print(f"⚠️ No candlestick image data available")
            
            # Save trend chart with support/resistance
            if images_dict.get('trend_image'):
                img_path = images_dir / f"trend_{timestamp}.png"
                try:
                    with open(img_path, 'wb') as f:
                        f.write(base64.b64decode(images_dict['trend_image']))
                    print(f"✅ Saved trend chart: {img_path}")
                except Exception as e:
                    print(f"❌ Failed to save trend image: {e}")
            else:
                print(f"⚠️ No trend image data available")
            
            # Save all indicator plots
            indicator_plot_mapping = {
                'rsi_plot': f"rsi_{timestamp}.png",
                'macd_plot': f"macd_{timestamp}.png",
                'stochastic_plot': f"stochastic_{timestamp}.png",
                'roc_plot': f"roc_{timestamp}.png",
                'willr_plot': f"willr_{timestamp}.png",
                'price_plot': f"price_{timestamp}.png"
            }
            
            saved_plots = []
            for plot_key, filename in indicator_plot_mapping.items():
                if images_dict.get(plot_key):
                    img_path = images_dir / filename
                    try:
                        with open(img_path, 'wb') as f:
                            f.write(base64.b64decode(images_dict[plot_key]))
                        print(f"✅ Saved {plot_key}: {img_path}")
                        saved_plots.append((plot_key, filename))
                    except Exception as e:
                        print(f"❌ Failed to save {plot_key}: {e}")
            
            # Save indicators JSON
            json_path = reports_subdir / f"indicators_{timestamp}.json"
            data = {
                "timestamp": timestamp,
                "window_start": str(window_start),
                "window_end": str(window_end),
                "indicators": indicators_dict
            }
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Generate comprehensive markdown report WITHOUT embedded images
            comprehensive_report_path = reports_subdir / f"comprehensive_analysis_{timestamp}.md"
            comprehensive_content = f"""# 📊 Comprehensive Market Analysis: {symbol}

**Generated:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}  
**Period:** {window_start} to {window_end}  
**Data Points:** {len(kline_dict.get('Datetime', []))}

---

## 📈 Price Action & Patterns

**Pattern Agent Analysis:**
{agent_results.get('pattern_report', 'No analysis available')}

**Trend Agent Analysis:**
{agent_results.get('trend_report', 'No analysis available')}

---

## 📊 Technical Indicators

### Indicator Agent Analysis
{agent_results.get('indicator_report', 'No analysis available')}

---

## 🎯 Trading Decision

**Decision:** {agent_results.get('final_trade_decision', 'HOLD')}  
**Confidence:** {agent_results.get('confidence_score', 0.5):.2%}

---

## 📋 Indicator Values Summary

```json
{json.dumps(indicators_dict, indent=2)}
```

---

## 📊 Available Chart Images

The following chart images have been saved separately:
- Candlestick Chart: `candlestick_{timestamp}.png`
- Trend Analysis: `trend_{timestamp}.png`
- RSI Indicator: `rsi_{timestamp}.png`
- MACD Indicator: `macd_{timestamp}.png`
- Stochastic Oscillator: `stochastic_{timestamp}.png`
- Rate of Change: `roc_{timestamp}.png`
- Williams %R: `willr_{timestamp}.png`
- Price Chart: `price_{timestamp}.png`

**Images Location:** `./images/`  
**Redis Endpoint:** `/api/market/images/{symbol}/{timestamp}`

---

*Report generated by Pathway + LangGraph Multi-Agent System*
"""
            
            with open(comprehensive_report_path, 'w', encoding='utf-8') as f:
                f.write(comprehensive_content)
            
            print(f"✅ Comprehensive report saved: {comprehensive_report_path}")
            
            # Save to Redis for API caching
            if save_report_to_redis:
                try:
                    save_report_to_redis(symbol, "market", comprehensive_content)
                except Exception as e:
                    print(f"⚠️ [{symbol}] Failed to cache market report to Redis: {e}")
            
            # Save to PostgreSQL for historical storage
            if save_report_to_postgres:
                try:
                    entry = {
                        "symbol": symbol,
                        "report_type": "market",
                        "content": comprehensive_content,
                        "last_updated": datetime.utcnow().isoformat(),
                    }
                    save_report_to_postgres(symbol, "market", entry)
                except Exception as e:
                    print(f"⚠️ [{symbol}] Failed to save market to PostgreSQL: {e}")
            
            # Save individual agent reports (for backward compatibility) - NO IMAGE EMBEDS
            agent_reports = [
                {
                    "filename": f"indicator_analysis_{timestamp}.md",
                    "emoji": "📊",
                    "title": "Indicator Agent Analysis",
                    "key": "indicator_report",
                    "note": "Chart images saved separately in `../images/` directory"
                },
                {
                    "filename": f"pattern_analysis_{timestamp}.md",
                    "emoji": "📉",
                    "title": "Pattern Agent Analysis",
                    "key": "pattern_report",
                    "note": f"Candlestick chart saved as `../images/candlestick_{timestamp}.png`"
                },
                {
                    "filename": f"trend_analysis_{timestamp}.md",
                    "emoji": "📈",
                    "title": "Trend Agent Analysis",
                    "key": "trend_report",
                    "note": f"Trend chart saved as `../images/trend_{timestamp}.png`"
                }
            ]
            
            for report_info in agent_reports:
                report_path = reports_subdir / report_info["filename"]
                content = f"""# {report_info['emoji']} {report_info['title']}: {symbol}

**Generated:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}
**Period:** {window_start} to {window_end}

## Analysis

{agent_results.get(report_info['key'], 'No analysis')}

---
**Note:** {report_info['note']}
"""
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            print(f"✅ All reports saved for {symbol} ({len(saved_plots)} indicator plots)")
            
            # Publish report and COMPLETED status
            try:
                if publish_report and publish_agent_status:
                    room_id = f"symbol:{symbol}"
                    publish_report(room_id, "Market Agent", {
                        "symbol": symbol,
                        "report_type": "market",
                        "decision": agent_results.get('final_trade_decision', 'HOLD'),
                        "confidence": agent_results.get('confidence_score', 0.5),
                        "window_start": str(window_start),
                        "window_end": str(window_end)
                    })
                    publish_agent_status(room_id, "Market Agent", "COMPLETED")
            except Exception as e:
                print(f"⚠️ [{symbol}] Failed to publish Market Agent events: {e}")
                
        except Exception as e:
            print(f"❌ Error saving reports: {e}")
            import traceback
            traceback.print_exc()
            
            # Publish FAILED status
            try:
                if publish_agent_status:
                    room_id = f"symbol:{symbol}"
                    publish_agent_status(room_id, "Market Agent", "FAILED")
            except:
                pass
    
    # UDF to prepare kline data dictionary
    @pw.udf
    def prepare_kline_data(
        timestamps: tuple,
        opens: tuple,
        highs: tuple,
        lows: tuple,
        closes: tuple
    ) -> pw.Json:
        """
        Convert tuples to dictionary format for chart generation tools.
        Ensures proper datetime formatting regardless of input frequency (z seconds, y minutes window).
        """
        from datetime import datetime
        
        # Convert timestamp strings to ISO format (YYYY-MM-DDTHH:MM:SS)
        datetime_list = []
        for ts in timestamps:
            try:
                ts_str = str(ts)
                # Handle various timestamp formats
                if 'T' in ts_str:
                    # Already ISO format, clean up
                    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00').split('+')[0])
                elif ' ' in ts_str:
                    # Space-separated format
                    dt = datetime.strptime(ts_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
                else:
                    # Try parsing as-is
                    dt = datetime.fromisoformat(ts_str)
                
                # Return in clean ISO format without timezone/microseconds
                datetime_list.append(dt.strftime("%Y-%m-%dT%H:%M:%S"))
            except Exception as e:
                print(f"⚠️ Warning: Failed to parse timestamp '{ts}': {e}")
                # Fallback: use as-is
                datetime_list.append(str(ts))
        
        # Ensure all data arrays have the same length
        min_len = min(len(datetime_list), len(opens), len(highs), len(lows), len(closes))
        
        result = {
            "Datetime": datetime_list[:min_len],
            "Open": list(opens[:min_len]),
            "High": list(highs[:min_len]),
            "Low": list(lows[:min_len]),
            "Close": list(closes[:min_len])
        }
        
        # Validate and log data quality
        if min_len < 2:
            print(f"⚠️ Warning: Only {min_len} data points available for chart generation")
        else:
            print(f"✅ Collected {min_len} data points for chart generation")
            if min_len > 0:
                # Calculate and log the interval
                try:
                    first_dt = datetime.fromisoformat(datetime_list[0])
                    last_dt = datetime.fromisoformat(datetime_list[-1])
                    time_span = (last_dt - first_dt).total_seconds()
                    avg_interval = time_span / (min_len - 1) if min_len > 1 else 0
                    print(f"📊 Time span: {time_span:.0f}s ({time_span/60:.1f}min), Avg interval: {avg_interval:.1f}s")
                except Exception as e:
                    print(f"⚠️ Could not calculate interval: {e}")
        
        return pw.Json(result)
    
    # Helper for empty image dict fallback
    def _empty_images_dict():
        return {
            "pattern_image": "", 
            "trend_image": "",
            "rsi_plot": "",
            "macd_plot": "",
            "stochastic_plot": "",
            "roc_plot": "",
            "willr_plot": "",
            "price_plot": ""
        }
    
    # UDF to generate images
    @pw.udf
    def generate_images(kline_data: pw.Json, indicators: pw.Json) -> pw.Json:
        """
        Generate pattern, trend, and all indicator plots from OHLCV data.
        Handles any data frequency: z second intervals over y minute windows.
        Now generates comprehensive plots for all technical indicators.
        """
        try:
            kline_dict = kline_data.as_dict()
            indicators_dict = indicators.as_dict()
            
            # Validate data structure
            if not kline_dict or not all(k in kline_dict for k in ['Datetime', 'Open', 'High', 'Low', 'Close']):
                print("⚠️ Warning: Invalid kline_data structure, missing required fields")
                return pw.Json(_empty_images_dict())
            
            # Check data points
            data_points = len(kline_dict.get('Datetime', []))
            if data_points < 2:
                print(f"⚠️ Warning: Insufficient data points ({data_points}) for chart generation")
                return pw.Json(_empty_images_dict())
            
            print(f"📊 Generating comprehensive charts with {data_points} data points...")
            
            # Generate candlestick pattern chart
            pattern_result = tech_tools.generate_kline_image.invoke({"kline_data": kline_dict})
            
            # Generate trend chart with support/resistance
            trend_result = tech_tools.generate_trend_image.invoke({"kline_data": kline_dict})
            
            # Generate all indicator plots
            indicator_plots = tech_tools.generate_all_indicator_plots(
                datetimes=kline_dict.get('Datetime', []),
                closes=kline_dict.get('Close', []),
                rsi=indicators_dict.get('rsi', []),
                macd=indicators_dict.get('macd', []),
                macd_signal=indicators_dict.get('macd_signal', []),
                macd_hist=indicators_dict.get('macd_hist', []),
                stoch_k=indicators_dict.get('stoch_k', []),
                stoch_d=indicators_dict.get('stoch_d', []),
                roc=indicators_dict.get('roc', []),
                willr=indicators_dict.get('willr', []),
                save_dir=None  # Don't save to disk here, will be saved in report generation
            )
            
            print(f"✅ All charts generated successfully ({len(indicator_plots)} indicator plots)")
            
            return pw.Json({
                "pattern_image": pattern_result.get("pattern_image", ""),
                "trend_image": trend_result.get("trend_image", ""),
                "rsi_plot": indicator_plots.get("rsi_plot", ""),
                "macd_plot": indicator_plots.get("macd_plot", ""),
                "stochastic_plot": indicator_plots.get("stochastic_plot", ""),
                "roc_plot": indicator_plots.get("roc_plot", ""),
                "willr_plot": indicator_plots.get("willr_plot", ""),
                "price_plot": indicator_plots.get("price_plot", "")
            })
        except Exception as e:
            print(f"❌ Error generating images: {e}")
            import traceback
            traceback.print_exc()
            return pw.Json(_empty_images_dict())
    
    # UDF to run LangGraph analysis
    @pw.udf
    def run_agent_analysis(
        symbol: str,
        kline_data: pw.Json,
        indicators: pw.Json,
        images: pw.Json,
        window_start: pw.DateTimeNaive,
        window_end: pw.DateTimeNaive
    ) -> pw.Json:
        """Run complete LangGraph agent analysis"""
        try:
            # Publish RUNNING status at START of analysis (before LLM calls)
            try:
                room_id = f"symbol:{symbol}"
                publish_agent_status(room_id, "Market Agent", "RUNNING")
            except Exception as e:
                print(f"⚠️ [{symbol}] Failed to publish Market Agent status: {e}")
            
            kline_dict = kline_data.as_dict()
            indicators_dict = indicators.as_dict()
            images_dict = images.as_dict()
            
            # Build precomputed state with ALL images for LLM prompts
            precomputed_state = {
                "stock_name": symbol,
                "time_frame": f"{window_end - window_start}",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "kline_data": kline_dict,
                "rsi": indicators_dict.get("rsi", []),
                "macd": indicators_dict.get("macd", []),
                "macd_signal": indicators_dict.get("macd_signal", []),
                "macd_hist": indicators_dict.get("macd_hist", []),
                "stoch_k": indicators_dict.get("stoch_k", []),
                "stoch_d": indicators_dict.get("stoch_d", []),
                "roc": indicators_dict.get("roc", []),
                "willr": indicators_dict.get("willr", []),
                # Pattern and trend images
                "pattern_image": images_dict.get("pattern_image", ""),
                "trend_image": images_dict.get("trend_image", ""),
                # Indicator plot images (for LLM vision analysis)
                "rsi_plot": images_dict.get("rsi_plot", ""),
                "macd_plot": images_dict.get("macd_plot", ""),
                "stochastic_plot": images_dict.get("stochastic_plot", ""),
                "roc_plot": images_dict.get("roc_plot", ""),
                "willr_plot": images_dict.get("willr_plot", ""),
                "price_plot": images_dict.get("price_plot", ""),
                "messages": []
            }
            
            # Get cached LLM clients (initialized once at module level)
            tool_llm, graph_llm = get_cached_llms()
            
            if tool_llm is None or graph_llm is None:
                raise ValueError("No API key found. Set either OPENROUTER_API_KEY or OPENAI_API_KEY environment variable.")
            
            # Create and run graph
            print(f"🤖 Analyzing {symbol}...")
            graph = create_trading_graph(tool_llm, graph_llm)
            result = graph.invoke(precomputed_state)
            
            # Save reports
            save_reports_immediately(
                symbol=symbol,
                window_start=window_start,
                window_end=window_end,
                kline_dict=kline_dict,
                indicators_dict=indicators_dict,
                images_dict=images_dict,
                agent_results=result
            )
            
            return pw.Json({
                "indicator_report": result.get("indicator_report", ""),
                "pattern_report": result.get("pattern_report", ""),
                "trend_report": result.get("trend_report", ""),
                "final_trade_decision": result.get("final_trade_decision", "HOLD"),
                "confidence_score": result.get("confidence_score", 0.5)
            })
            
        except Exception as e:
            print(f"❌ Error in agent analysis for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return pw.Json({
                "indicator_report": f"Error: {e}",
                "pattern_report": "",
                "trend_report": "",
                "final_trade_decision": "HOLD",
                "confidence_score": 0.0
            })

    # Prepare kline data and OHLC tuples for indicator calculation
    enriched = windowed_table.select(
        pw.this.symbol,
        pw.this.window_start,
        pw.this.window_end,
        pw.this.data_points,
        pw.this.latest_price,
        pw.this.latest_change,
        pw.this.latest_change_percent,
        pw.this.closes,
        pw.this.highs,
        pw.this.lows,
        kline_data=prepare_kline_data(
            pw.this.timestamps,
            pw.this.opens,
            pw.this.highs,
            pw.this.lows,
            pw.this.closes
        )
    )
    
    # Package indicators into JSON format for agents (uses TA-Lib for accurate calculations)
    @pw.udf
    def package_indicators(closes: tuple, highs: tuple, lows: tuple) -> pw.Json:
        """
        Calculate time-series indicators from OHLC tuples using TA-Lib.
        Returns LISTS of indicator values (one per data point), not single values.
        Uses TA-Lib for accurate technical indicator calculations.
        """
        # Convert tuples to numpy arrays for TA-Lib
        closes_arr = np.array(closes, dtype=float)
        highs_arr = np.array(highs, dtype=float)
        lows_arr = np.array(lows, dtype=float)

        n_points = len(closes)

        # Debug: Check input data quality
        print(f"\n📊 TA-Lib input data:")
        print(f"   Points: {n_points}")
        print(f"   Close range: [{min(closes):.2f}, {max(closes):.2f}]")
        print(f"   High range: [{min(highs):.2f}, {max(highs):.2f}]")
        print(f"   Low range: [{min(lows):.2f}, {max(lows):.2f}]")

        # Check for variance in data
        close_variance = np.var(closes_arr)
        close_std = np.std(closes_arr)
        print(f"   Close variance: {close_variance:.4f}, std: {close_std:.4f}")

        # Show first/last few values
        if n_points > 0:
            print(f"   First 5 closes: {list(closes[:min(5, n_points)])}")
            print(f"   Last 5 closes: {list(closes[-min(5, n_points):])}")

        # Check for duplicate/constant values
        unique_closes = len(set(closes))
        print(f"   Unique close values: {unique_closes}/{n_points}")

        if close_variance < 0.0001:
            print(f"   ⚠️ WARNING: Very low variance in price data - indicators may be flat!")

        if unique_closes < n_points * 0.5:
            print(f"   ⚠️ WARNING: Many duplicate values - possible data quality issue!")

        # Helper to forward-fill None values with last-seen or neutral fallback
        def _forward_fill(values, neutral):
            out = []
            last = None
            for v in values:
                if v is None:
                    out.append(last if last is not None else neutral)
                else:
                    out.append(v)
                    last = v
            return out

        # RSI - Using TA-Lib (14-period)
        rsi_arr = talib.RSI(closes_arr, timeperiod=14)
        rsi_list = [float(val) if not np.isnan(val) else None for val in rsi_arr]
        valid_rsi_count = sum(1 for v in rsi_list if v is not None)
        print(f"   RSI: {valid_rsi_count}/{n_points} valid values")

        # MACD - Using TA-Lib (12, 26, 9)
        macd_arr, macd_signal_arr, macd_hist_arr = talib.MACD(
            closes_arr,
            fastperiod=12,
            slowperiod=26,
            signalperiod=9
        )
        macd_list = [float(val) if not np.isnan(val) else None for val in macd_arr]
        macd_signal_list = [float(val) if not np.isnan(val) else None for val in macd_signal_arr]
        macd_hist_list = [float(val) if not np.isnan(val) else None for val in macd_hist_arr]

        valid_macd_count = sum(1 for v in macd_list if v is not None)
        print(f"   MACD: {valid_macd_count}/{n_points} valid values")

        # Stochastic - Using TA-Lib (14-period, 3-period SMA for %D)
        stoch_k_arr, stoch_d_arr = talib.STOCH(
            highs_arr,
            lows_arr,
            closes_arr,
            fastk_period=14,
            slowk_period=3,
            slowk_matype=0,  # SMA
            slowd_period=3,
            slowd_matype=0   # SMA
        )
        stoch_k_list = [float(val) if not np.isnan(val) else None for val in stoch_k_arr]
        stoch_d_list = [float(val) if not np.isnan(val) else None for val in stoch_d_arr]

        valid_stoch_count = sum(1 for v in stoch_k_list if v is not None)
        print(f"   Stochastic: {valid_stoch_count}/{n_points} valid values")

        # ROC - Using TA-Lib (10-period)
        roc_arr = talib.ROC(closes_arr, timeperiod=10)
        roc_list = [float(val) if not np.isnan(val) else None for val in roc_arr]

        valid_roc_count = sum(1 for v in roc_list if v is not None)
        print(f"   ROC: {valid_roc_count}/{n_points} valid values")

        # Williams %R - Using TA-Lib (14-period)
        willr_arr = talib.WILLR(highs_arr, lows_arr, closes_arr, timeperiod=14)
        willr_list = [float(val) if not np.isnan(val) else None for val in willr_arr]

        valid_willr_count = sum(1 for v in willr_list if v is not None)
        print(f"   WillR: {valid_willr_count}/{n_points} valid values")
        
        # Forward-fill None values sensibly (use last valid value or neutral fallback)
        rsi_ff = _forward_fill(rsi_list, 50.0)
        macd_ff = _forward_fill(macd_list, 0.0)
        macd_signal_ff = _forward_fill(macd_signal_list, 0.0)
        macd_hist_ff = _forward_fill(macd_hist_list, 0.0)
        stoch_k_ff = _forward_fill(stoch_k_list, 50.0)
        stoch_d_ff = _forward_fill(stoch_d_list, 50.0)
        roc_ff = _forward_fill(roc_list, 0.0)
        willr_ff = _forward_fill(willr_list, -50.0)

        # Debug output on the filled series
        if len(willr_ff) > 0:
            print(f"📊 TA-Lib indicators calculated: {n_points} points")
            print(f"   RSI range: [{min(rsi_ff):.1f}, {max(rsi_ff):.1f}]")
            print(f"   MACD range: [{min(macd_ff):.4f}, {max(macd_ff):.4f}]")
            print(f"   Stoch %K range: [{min(stoch_k_ff):.1f}, {max(stoch_k_ff):.1f}]")
            print(f"   WillR range: [{min(willr_ff):.1f}, {max(willr_ff):.1f}]")
            print(f"   ROC range: [{min(roc_ff):.4f}, {max(roc_ff):.4f}]")

        return pw.Json({
            'rsi': rsi_ff,
            'macd': macd_ff,
            'macd_signal': macd_signal_ff,
            'macd_hist': macd_hist_ff,
            'stoch_k': stoch_k_ff,
            'stoch_d': stoch_d_ff,
            'roc': roc_ff,
            'willr': willr_ff
        })
    
    enriched = enriched.select(
        pw.this.symbol,
        pw.this.window_start,
        pw.this.window_end,
        pw.this.data_points,
        pw.this.latest_price,
        pw.this.latest_change,
        pw.this.latest_change_percent,
        pw.this.kline_data,
        indicators=package_indicators(
            pw.this.closes, pw.this.highs, pw.this.lows
        )
    )
    
    # Generate images
    enriched = enriched.select(
        pw.this.symbol,
        pw.this.window_start,
        pw.this.window_end,
        pw.this.data_points,
        pw.this.latest_price,
        pw.this.latest_change,
        pw.this.latest_change_percent,
        pw.this.kline_data,
        pw.this.indicators,
        images=generate_images(pw.this.kline_data, pw.this.indicators)
    )
    
    # Run agent analysis
    analyzed = enriched.select(
        pw.this.symbol,
        pw.this.window_start,
        pw.this.window_end,
        pw.this.data_points,
        pw.this.latest_price,
        pw.this.latest_change,
        pw.this.latest_change_percent,
        pw.this.kline_data,
        pw.this.indicators,
        pw.this.images,
        agent_results=run_agent_analysis(
            pw.this.symbol,
            pw.this.kline_data,
            pw.this.indicators,
            pw.this.images,
            pw.this.window_start,
            pw.this.window_end
        )
    )
    
    return analyzed


def _setup_agent_report_saving(analyzed_table: pw.Table, reports_dir: Path):
    """Setup subscription to monitor analysis results."""
    
    def monitor_results(key, row, time, is_addition):
        if not is_addition:
            return
        
        symbol = row.get('symbol', 'UNKNOWN')
        print(f"✅ Analysis complete for {symbol}: {row.get('window_start')} to {row.get('window_end')}")
    
    # Subscribe to monitor results
    pw.io.subscribe(analyzed_table, on_change=monitor_results)