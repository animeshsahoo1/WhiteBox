import pathway as pw
from pathway.xpacks.llm import llms
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()


def process_market_stream(market_table: pw.Table, reports_directory: str = "./reports/market_reports") -> pw.Table:
    """
    Process market data stream: calculate indicators, apply windowing, and generate LLM reports.
    Uses tumbling window of 1 minute - processes only rows added in each 1-minute period.
    
    Args:
        market_table: Pathway table from MarketDataConsumer
        reports_directory: Directory to save market reports
        
    Returns:
        Pathway table with LLM analysis results
    """
    
    # Load API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    # Use Pathway's native OpenAI chat
    chat = llms.OpenAIChat(
        model="gpt-4o-mini",
        api_key=openai_api_key,
        temperature=0.0,
        cache_strategy=pw.udfs.DefaultCache()
    )
    
    # Create reports directory
    reports_dir = Path(reports_directory)
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📊 Applying tumbling window: 1 minute duration")
    
    # Step 1: Calculate technical indicators
    print("📊 Calculating technical indicators...")
    enriched_table = _calculate_technical_indicators(market_table)
    
    # Step 2: Apply tumbling window and group by symbol
    print("🔄 Applying windowing and grouping by symbol...")
    windowed_table = _apply_windowing(enriched_table)
    
    # Step 3: Add LLM analysis
    print("🤖 Setting up LLM analysis pipeline...")
    analyzed_table = _add_llm_analysis(windowed_table, chat)
    
    # Step 4: Subscribe to save reports
    _setup_report_saving(analyzed_table, reports_dir)
    
    return analyzed_table


def _calculate_technical_indicators(table: pw.Table) -> pw.Table:
    """
    Calculate technical indicators for stock data using Pathway operations.
    
    Args:
        table: Pathway table with OHLCV data
        
    Returns:
        Pathway table with technical indicators added
    """
    
    enriched_table = table.select(
        pw.this.symbol,
        pw.this.timestamp,
        pw.this.open,
        pw.this.high,
        pw.this.low,
        pw.this.current_price,
        pw.this.previous_close,
        pw.this.change,
        pw.this.change_percent,
        # Parse sent_at string to datetime for windowing
        sent_at=pw.this.sent_at.dt.strptime("%Y-%m-%dT%H:%M:%S.%f"),
        # Price Range
        price_range=pw.coalesce(pw.this.high, 0.0) - pw.coalesce(pw.this.low, 0.0),
        # Typical Price
        typical_price=(pw.coalesce(pw.this.high, 0.0) + pw.coalesce(pw.this.low, 0.0) + pw.coalesce(pw.this.current_price, 0.0)) / 3.0,
        # Price vs Open
        price_vs_open=pw.if_else(
            pw.this.open.is_not_none() & (pw.this.open != 0.0),
            ((pw.coalesce(pw.this.current_price, 0.0) - pw.coalesce(pw.this.open, 0.0)) / pw.coalesce(pw.this.open, 1.0)) * 100.0,
            0.0
        ),
        # Intraday Volatility
        intraday_volatility=pw.if_else(
            pw.this.low.is_not_none() & (pw.this.low != 0.0),
            ((pw.coalesce(pw.this.high, 0.0) - pw.coalesce(pw.this.low, 0.0)) / pw.coalesce(pw.this.low, 1.0)) * 100.0,
            0.0
        ),
        # Daily Return
        daily_return=pw.if_else(
            pw.this.previous_close.is_not_none() & (pw.this.previous_close != 0.0),
            ((pw.coalesce(pw.this.current_price, 0.0) - pw.coalesce(pw.this.previous_close, 0.0)) / pw.coalesce(pw.this.previous_close, 1.0)) * 100.0,
            0.0
        )
    )
    
    return enriched_table


def _apply_windowing(enriched_table: pw.Table) -> pw.Table:
    """
    Apply tumbling window and aggregate data by symbol.
    
    Args:
        enriched_table: Table with technical indicators
        
    Returns:
        Windowed and aggregated table
    """
    
    windowed_table = enriched_table.windowby(
        enriched_table.sent_at,
        window=pw.temporal.tumbling(duration=timedelta(minutes=1)),
        instance=enriched_table.symbol
    ).reduce(
        symbol=pw.this._pw_instance,
        window_start=pw.this._pw_window_start,
        window_end=pw.this._pw_window_end,
        # OHLCV aggregations
        avg_open=pw.reducers.avg(pw.coalesce(pw.this.open, 0.0)),
        avg_high=pw.reducers.avg(pw.coalesce(pw.this.high, 0.0)),
        avg_low=pw.reducers.avg(pw.coalesce(pw.this.low, 0.0)),
        avg_close=pw.reducers.avg(pw.coalesce(pw.this.current_price, 0.0)),
        max_high=pw.reducers.max(pw.coalesce(pw.this.high, 0.0)),
        min_low=pw.reducers.min(pw.coalesce(pw.this.low, 0.0)),
        latest_price=pw.reducers.latest(pw.coalesce(pw.this.current_price, 0.0)),
        latest_volume=pw.reducers.latest(pw.coalesce(pw.this.current_price, 0.0)),
        # Technical indicators
        avg_price_range=pw.reducers.avg(pw.this.price_range),
        avg_typical_price=pw.reducers.avg(pw.this.typical_price),
        avg_price_vs_open=pw.reducers.avg(pw.this.price_vs_open),
        avg_intraday_volatility=pw.reducers.avg(pw.this.intraday_volatility),
        avg_daily_return=pw.reducers.avg(pw.this.daily_return),
        # Price changes
        latest_change=pw.reducers.latest(pw.coalesce(pw.this.change, 0.0)),
        latest_change_percent=pw.reducers.latest(pw.coalesce(pw.this.change_percent, 0.0)),
        # Metadata
        data_points=pw.reducers.count(),
        latest_timestamp=pw.reducers.latest(pw.this.timestamp)
    )
    
    return windowed_table


def _add_llm_analysis(windowed_table: pw.Table, chat: llms.OpenAIChat) -> pw.Table:
    """
    Add LLM analysis to windowed market data.
    
    Args:
        windowed_table: Windowed and aggregated table
        chat: OpenAI chat instance
        
    Returns:
        Table with LLM analysis added
    """
    
    # Create a UDF to convert row to JSON structure
    @pw.udf
    def create_json_dict(
        symbol: str,
        window_start: pw.DateTimeNaive,
        window_end: pw.DateTimeNaive,
        latest_timestamp: str,
        avg_open: float,
        max_high: float,
        min_low: float,
        latest_price: float,
        latest_volume: float,
        avg_high: float,
        avg_low: float,
        avg_close: float,
        avg_price_range: float,
        latest_change: float,
        latest_change_percent: float,
        avg_daily_return: float,
        avg_intraday_volatility: float,
        avg_typical_price: float,
        avg_price_vs_open: float,
        data_points: int
    ) -> pw.Json:
        """Convert windowed data to JSON structure"""
        
        def timestamp_to_str(ts):
            if ts is None:
                return "N/A"
            return str(ts)
        
        return pw.Json({
            "symbol": symbol,
            "timestamp": latest_timestamp,
            "window": {
                "start": timestamp_to_str(window_start),
                "end": timestamp_to_str(window_end)
            },
            "ohlcv": {
                "open": float(avg_open),
                "high": float(max_high),
                "low": float(min_low),
                "close": float(latest_price),
                "volume": int(latest_volume)
            },
            "technical_indicators": {
                "price_metrics": {
                    "current_price": float(latest_price),
                    "average_open": float(avg_open),
                    "average_high": float(avg_high),
                    "average_low": float(avg_low),
                    "average_close": float(avg_close),
                    "max_high": float(max_high),
                    "min_low": float(min_low),
                    "avg_price_range": float(avg_price_range)
                },
                "momentum_indicators": {
                    "latest_change": float(latest_change),
                    "latest_change_percent": float(latest_change_percent),
                    "avg_daily_return": float(avg_daily_return)
                },
                "volatility_indicators": {
                    "avg_intraday_volatility": float(avg_intraday_volatility),
                    "price_stability": "high" if avg_intraday_volatility < 2.0 else "medium" if avg_intraday_volatility < 5.0 else "low"
                },
                "trend_indicators": {
                    "avg_typical_price": float(avg_typical_price),
                    "avg_price_vs_open": float(avg_price_vs_open),
                    "trend_direction": "bullish" if latest_change_percent > 0 else "bearish",
                    "trend_strength": "strong" if abs(latest_change_percent) > 2.0 else "moderate" if abs(latest_change_percent) > 1.0 else "weak"
                }
            },
            "metadata": {
                "data_points": int(data_points),
                "window_duration": "1 minute",
                "analysis_type": "windowed_technical_analysis"
            }
        })
    
    # Apply the JSON creation UDF
    analyzed_table = windowed_table.select(
        pw.this.symbol,
        pw.this.window_start,
        pw.this.window_end,
        pw.this.data_points,
        market_data_json=create_json_dict(
            pw.this.symbol,
            pw.this.window_start,
            pw.this.window_end,
            pw.this.latest_timestamp,
            pw.this.avg_open,
            pw.this.max_high,
            pw.this.min_low,
            pw.this.latest_price,
            pw.this.latest_volume,
            pw.this.avg_high,
            pw.this.avg_low,
            pw.this.avg_close,
            pw.this.avg_price_range,
            pw.this.latest_change,
            pw.this.latest_change_percent,
            pw.this.avg_daily_return,
            pw.this.avg_intraday_volatility,
            pw.this.avg_typical_price,
            pw.this.avg_price_vs_open,
            pw.this.data_points
        )
    )
    
    # Create prompts
    @pw.udf
    def create_prompt_from_json(market_data: pw.Json) -> str:
        """Create analysis prompt from JSON data"""
        
        market_data_dict = market_data.as_dict()
        symbol = market_data_dict["symbol"]
        
        return f"""You are an expert financial analyst. Analyze the following market data for {symbol} and provide a comprehensive report.

Market Data:
{json.dumps(market_data_dict, indent=2)}

Please provide a detailed analysis covering:

1. **Price Action Analysis**
   - Current price trends and movements
   - Key support and resistance levels
   - Price momentum assessment

2. **Technical Indicator Analysis**
   - Momentum indicators interpretation
   - Volatility analysis and implications
   - Trend strength and direction

3. **Risk Assessment**
   - Volatility-based risk evaluation
   - Price stability analysis
   - Potential risk factors

4. **Trading Recommendations**
   - Short-term outlook (1-5 days)
   - Entry/exit points consideration
   - Risk management suggestions

5. **Key Insights**
   - Notable patterns or anomalies
   - Market sentiment indicators
   - Overall investment perspective

Format your response as a professional market analysis report with clear sections and actionable insights."""
    
    analyzed_table = analyzed_table.select(
        pw.this.symbol,
        pw.this.window_start,
        pw.this.window_end,
        pw.this.data_points,
        pw.this.market_data_json,
        prompt=create_prompt_from_json(pw.this.market_data_json)
    )
    
    # Call LLM
    analyzed_table = analyzed_table.select(
        pw.this.symbol,
        pw.this.window_start,
        pw.this.window_end,
        pw.this.data_points,
        pw.this.market_data_json,
        pw.this.prompt,
        llm_analysis=chat(llms.prompt_chat_single_qa(pw.this.prompt))
    )
    
    return analyzed_table


def _setup_report_saving(analyzed_table: pw.Table, reports_dir: Path):
    """
    Setup subscription to save reports when windows close.
    
    Args:
        analyzed_table: Table with LLM analysis
        reports_dir: Directory to save reports
    """
    
    def save_report(key, row, time, is_addition):
        if not is_addition:
            return
        
        try:
            symbol = row['symbol']
            
            print(f"\n{'='*60}", flush=True)
            print(f"🔄 WINDOW CLOSED for {symbol}", flush=True)
            print(f"   Time range: {row['window_start']} to {row['window_end']}", flush=True)
            print(f"   Data points: {row['data_points']}", flush=True)
            print(f"{'='*60}\n", flush=True)
            
            analysis = row['llm_analysis']
            market_data = row['market_data_json']
            
            # Convert pw.Json to dict
            if hasattr(market_data, 'as_dict'):
                market_data = market_data.as_dict()
            
            # Create symbol directory
            symbol_dir = reports_dir / symbol
            symbol_dir.mkdir(parents=True, exist_ok=True)
            
            report_path = symbol_dir / "market_report.md"
            
            print(f"💾 Saving report to: {report_path}", flush=True)
            
            # Format comprehensive report
            report_content = f"""# Market Analysis Report: {symbol}

**Generated:** {market_data['timestamp']}  
**Analysis Type:** {market_data['metadata']['analysis_type']}

---

## Window Information
- **Window Start:** {market_data['window']['start']}
- **Window End:** {market_data['window']['end']}
- **Data Points in Window:** {market_data['metadata']['data_points']}

## OHLCV Data (Aggregated over window)
- **Average Open:** ${market_data['ohlcv']['open']:.2f}
- **Max High:** ${market_data['ohlcv']['high']:.2f}
- **Min Low:** ${market_data['ohlcv']['low']:.2f}
- **Latest Close:** ${market_data['ohlcv']['close']:.2f}
- **Volume:** {market_data['ohlcv']['volume']} data points

## Technical Indicators

### Price Metrics
- **Current Price:** ${market_data['technical_indicators']['price_metrics']['current_price']:.2f}
- **Average Open:** ${market_data['technical_indicators']['price_metrics']['average_open']:.2f}
- **Average High:** ${market_data['technical_indicators']['price_metrics']['average_high']:.2f}
- **Average Low:** ${market_data['technical_indicators']['price_metrics']['average_low']:.2f}
- **Average Close:** ${market_data['technical_indicators']['price_metrics']['average_close']:.2f}
- **Max High:** ${market_data['technical_indicators']['price_metrics']['max_high']:.2f}
- **Min Low:** ${market_data['technical_indicators']['price_metrics']['min_low']:.2f}
- **Price Range:** ${market_data['technical_indicators']['price_metrics']['avg_price_range']:.2f}

### Momentum Indicators
- **Latest Change:** ${market_data['technical_indicators']['momentum_indicators']['latest_change']:.2f}
- **Latest Change %:** {market_data['technical_indicators']['momentum_indicators']['latest_change_percent']:.2f}%
- **Avg Daily Return:** {market_data['technical_indicators']['momentum_indicators']['avg_daily_return']:.2f}%

### Volatility Indicators
- **Avg Intraday Volatility:** {market_data['technical_indicators']['volatility_indicators']['avg_intraday_volatility']:.2f}%
- **Price Stability:** {market_data['technical_indicators']['volatility_indicators']['price_stability']}

### Trend Indicators
- **Avg Typical Price:** ${market_data['technical_indicators']['trend_indicators']['avg_typical_price']:.2f}
- **Avg Price vs Open:** {market_data['technical_indicators']['trend_indicators']['avg_price_vs_open']:.2f}%
- **Trend Direction:** {market_data['technical_indicators']['trend_indicators']['trend_direction']}
- **Trend Strength:** {market_data['technical_indicators']['trend_indicators']['trend_strength']}

---

## AI-Powered Analysis

{analysis}

---
"""
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            print(f"✅ Report successfully saved: {report_path}", flush=True)
            
        except Exception as e:
            import traceback
            error_msg = f"Error processing {row.get('symbol', 'unknown')}: {str(e)}"
            print(f"❌ {error_msg}", flush=True)
            print(traceback.format_exc(), flush=True)
    
    # Subscribe to save reports
    pw.io.subscribe(analyzed_table, on_change=save_report)