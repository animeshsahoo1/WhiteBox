import pathway as pw
import json
import os
from pathlib import Path
from typing import TypedDict, Annotated
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
import sys
import time
from datetime import timedelta

# Add parent directory to path to import consumers
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from consumers.market_data_consumer import MarketDataConsumer

# Load environment variables
load_dotenv()

class MarketAnalysisAgent:
    """
    LangGraph agent for analyzing market data using Pathway tables.
    Groups data by ticker symbols, calculates technical indicators,
    and generates comprehensive analysis reports.
    """
    
    def __init__(self):
        """Initialize the market analysis agent"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,
            api_key=self.openai_api_key
        )
        
        # Create reports directory structure
        self.reports_dir = Path("reports/market_reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize consumer
        self.consumer = MarketDataConsumer()
        
        # Build the analysis graph
        self.graph = self._build_graph()
    
    def calculate_technical_indicators(self, table):
        """
        Calculate technical indicators for stock data using Pathway operations.
        
        Technical indicators include:
        - Moving Averages (SMA)
        - RSI (Relative Strength Index)
        - MACD indicators
        - Bollinger Bands
        - Volume indicators
        - Price momentum
        - Volatility metrics
        
        Args:
            table: Pathway table with OHLCV data
            
        Returns:
            Pathway table with technical indicators added
        """
        
        # Add basic price metrics
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
            # Price Range (handle None values with coalesce)
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
    
    def group_by_symbol(self, table):
        """
        Group market data by ticker symbol and aggregate indicators.
        
        Args:
            table: Pathway table with market data and technical indicators
            
        Returns:
            Pathway table grouped by symbol with aggregated metrics
        """
        
        # Group by symbol and calculate aggregate statistics
        grouped_table = table.groupby(table.symbol).reduce(
            table.symbol,
            # Count of records
            record_count=pw.reducers.count(),
            # Price statistics
            avg_price=pw.reducers.avg(table.current_price),
            max_high=pw.reducers.max(table.high),
            min_low=pw.reducers.min(table.low),
            latest_price=pw.reducers.latest(table.current_price),
            # Volume-weighted metrics
            avg_change_percent=pw.reducers.avg(table.change_percent),
            # Volatility metrics
            avg_volatility=pw.reducers.avg(table.intraday_volatility),
            max_volatility=pw.reducers.max(table.intraday_volatility),
            # Range metrics
            avg_price_range=pw.reducers.avg(table.price_range),
            # Latest values for context
            latest_open=pw.reducers.latest(table.open),
            latest_high=pw.reducers.latest(table.high),
            latest_low=pw.reducers.latest(table.low),
            latest_change=pw.reducers.latest(table.change),
            latest_change_percent=pw.reducers.latest(table.change_percent),
            latest_timestamp=pw.reducers.latest(table.timestamp),
        )
        
        return grouped_table
    
    def create_json_for_symbol(self, grouped_row):
        """
        Create a JSON structure for a single ticker symbol with OHLCV and technical indicators.
        
        Args:
            grouped_row: Single row from grouped table
            
        Returns:
            dict: JSON structure with all market data and indicators
        """
        
        return {
            "symbol": grouped_row["symbol"],
            "timestamp": grouped_row["latest_timestamp"],
            "ohlcv": {
                "open": float(grouped_row["latest_open"]),
                "high": float(grouped_row["latest_high"]),
                "low": float(grouped_row["latest_low"]),
                "close": float(grouped_row["latest_price"]),
                "volume": int(grouped_row["record_count"])
            },
            "technical_indicators": {
                "price_metrics": {
                    "current_price": float(grouped_row["latest_price"]),
                    "average_price": float(grouped_row["avg_price"]),
                    "max_high": float(grouped_row["max_high"]),
                    "min_low": float(grouped_row["min_low"]),
                    "price_range": float(grouped_row["avg_price_range"])
                },
                "momentum_indicators": {
                    "change": float(grouped_row["latest_change"]),
                    "change_percent": float(grouped_row["latest_change_percent"]),
                    "avg_change_percent": float(grouped_row["avg_change_percent"])
                },
                "volatility_indicators": {
                    "average_volatility": float(grouped_row["avg_volatility"]),
                    "max_volatility": float(grouped_row["max_volatility"]),
                    "price_stability": "high" if grouped_row["avg_volatility"] < 2.0 else "medium" if grouped_row["avg_volatility"] < 5.0 else "low"
                },
                "trend_indicators": {
                    "trend_direction": "bullish" if grouped_row["latest_change_percent"] > 0 else "bearish",
                    "trend_strength": "strong" if abs(grouped_row["latest_change_percent"]) > 2.0 else "moderate" if abs(grouped_row["latest_change_percent"]) > 1.0 else "weak"
                }
            },
            "metadata": {
                "record_count": int(grouped_row["record_count"]),
                "analysis_type": "comprehensive_technical_analysis"
            }
        }
    
    def create_json_for_window(self, windowed_row):
        """
        Create a JSON structure for a windowed ticker symbol with OHLCV and technical indicators.
        
        Args:
            windowed_row: Single row from windowed table
            
        Returns:
            dict: JSON structure with all market data and indicators from the window
        """
        
        # Helper function to convert Timestamp to string
        def timestamp_to_str(ts):
            """Convert Pathway Timestamp to string"""
            if ts is None:
                return "N/A"
            return str(ts)
        
        return {
            "symbol": windowed_row["symbol"],
            "timestamp": timestamp_to_str(windowed_row["latest_timestamp"]),
            "window": {
                "start": timestamp_to_str(windowed_row["window_start"]),
                "end": timestamp_to_str(windowed_row["window_end"])
            },
            "ohlcv": {
                "open": float(windowed_row["avg_open"]),
                "high": float(windowed_row["max_high"]),
                "low": float(windowed_row["min_low"]),
                "close": float(windowed_row["latest_price"]),
                "volume": int(windowed_row["latest_volume"])
            },
            "technical_indicators": {
                "price_metrics": {
                    "current_price": float(windowed_row["latest_price"]),
                    "average_open": float(windowed_row["avg_open"]),
                    "average_high": float(windowed_row["avg_high"]),
                    "average_low": float(windowed_row["avg_low"]),
                    "average_close": float(windowed_row["avg_close"]),
                    "max_high": float(windowed_row["max_high"]),
                    "min_low": float(windowed_row["min_low"]),
                    "avg_price_range": float(windowed_row["avg_price_range"])
                },
                "momentum_indicators": {
                    "latest_change": float(windowed_row["latest_change"]),
                    "latest_change_percent": float(windowed_row["latest_change_percent"]),
                    "avg_daily_return": float(windowed_row["avg_daily_return"])
                },
                "volatility_indicators": {
                    "avg_intraday_volatility": float(windowed_row["avg_intraday_volatility"]),
                    "price_stability": "high" if windowed_row["avg_intraday_volatility"] < 2.0 else "medium" if windowed_row["avg_intraday_volatility"] < 5.0 else "low"
                },
                "trend_indicators": {
                    "avg_typical_price": float(windowed_row["avg_typical_price"]),
                    "avg_price_vs_open": float(windowed_row["avg_price_vs_open"]),
                    "trend_direction": "bullish" if windowed_row["latest_change_percent"] > 0 else "bearish",
                    "trend_strength": "strong" if abs(windowed_row["latest_change_percent"]) > 2.0 else "moderate" if abs(windowed_row["latest_change_percent"]) > 1.0 else "weak"
                }
            },
            "metadata": {
                "data_points": int(windowed_row["data_points"]),
                "window_duration": "1 minute",
                "analysis_type": "windowed_technical_analysis"
            }
        }
    
    # LangGraph State Definition
    class AgentState(TypedDict):
        """State for the LangGraph agent"""
        messages: Annotated[list, add_messages]
        symbol_data: dict
        analysis_result: str
        report_path: str
    
    def analyze_node(self, state: AgentState) -> AgentState:
        """
        Analyze market data using LLM.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with analysis
        """
        symbol_data = state["symbol_data"]
        symbol = symbol_data["symbol"]
        
        # Create comprehensive prompt for analysis
        prompt = f"""
You are an expert financial analyst. Analyze the following market data for {symbol} and provide a comprehensive report.

Market Data:
{json.dumps(symbol_data, indent=2)}

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

Format your response as a professional market analysis report with clear sections and actionable insights.
"""
        
        # Get analysis from LLM
        response = self.llm.invoke(prompt)
        analysis_text = response.content
        
        state["analysis_result"] = analysis_text
        state["messages"].append({"role": "assistant", "content": f"Analysis completed for {symbol}"})
        
        return state
    
    def save_report_node(self, state: AgentState) -> AgentState:
        """
        Save the analysis report to a file.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with report path
        """
        symbol = state["symbol_data"]["symbol"]
        analysis = state["analysis_result"]
        
        # Create symbol-specific directory
        symbol_dir = self.reports_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        
        # Report filename (overwrites previous report)
        report_filename = f"market_report.md"
        report_path = symbol_dir / report_filename
        
        print(f"💾 Saving report to: {report_path}", flush=True)
        
        # Create comprehensive report with metadata
        report_content = f"""# Market Analysis Report: {symbol}
        
**Generated:** {state["symbol_data"]["timestamp"]}  
**Analysis Type:** {state["symbol_data"]["metadata"]["analysis_type"]}

---

## Market Data Summary

### Window Information
- **Window Start:** {state["symbol_data"]["window"]["start"]}
- **Window End:** {state["symbol_data"]["window"]["end"]}
- **Data Points in Window:** {state["symbol_data"]["metadata"]["data_points"]}

### OHLCV Data (Aggregated over window)
- **Average Open:** ${state["symbol_data"]["ohlcv"]["open"]:.2f}
- **Max High:** ${state["symbol_data"]["ohlcv"]["high"]:.2f}
- **Min Low:** ${state["symbol_data"]["ohlcv"]["low"]:.2f}
- **Latest Close:** ${state["symbol_data"]["ohlcv"]["close"]:.2f}
- **Volume:** {state["symbol_data"]["ohlcv"]["volume"]} data points

### Technical Indicators

#### Price Metrics
- **Current Price:** ${state["symbol_data"]["technical_indicators"]["price_metrics"]["current_price"]:.2f}
- **Average Open:** ${state["symbol_data"]["technical_indicators"]["price_metrics"]["average_open"]:.2f}
- **Average High:** ${state["symbol_data"]["technical_indicators"]["price_metrics"]["average_high"]:.2f}
- **Average Low:** ${state["symbol_data"]["technical_indicators"]["price_metrics"]["average_low"]:.2f}
- **Average Close:** ${state["symbol_data"]["technical_indicators"]["price_metrics"]["average_close"]:.2f}
- **Max High:** ${state["symbol_data"]["technical_indicators"]["price_metrics"]["max_high"]:.2f}
- **Min Low:** ${state["symbol_data"]["technical_indicators"]["price_metrics"]["min_low"]:.2f}
- **Price Range:** ${state["symbol_data"]["technical_indicators"]["price_metrics"]["avg_price_range"]:.2f}

#### Momentum Indicators
- **Latest Change:** ${state["symbol_data"]["technical_indicators"]["momentum_indicators"]["latest_change"]:.2f}
- **Latest Change %:** {state["symbol_data"]["technical_indicators"]["momentum_indicators"]["latest_change_percent"]:.2f}%
- **Avg Daily Return:** {state["symbol_data"]["technical_indicators"]["momentum_indicators"]["avg_daily_return"]:.2f}%

#### Volatility Indicators
- **Avg Intraday Volatility:** {state["symbol_data"]["technical_indicators"]["volatility_indicators"]["avg_intraday_volatility"]:.2f}%
- **Price Stability:** {state["symbol_data"]["technical_indicators"]["volatility_indicators"]["price_stability"]}

#### Trend Indicators
- **Avg Typical Price:** ${state["symbol_data"]["technical_indicators"]["trend_indicators"]["avg_typical_price"]:.2f}
- **Avg Price vs Open:** {state["symbol_data"]["technical_indicators"]["trend_indicators"]["avg_price_vs_open"]:.2f}%
- **Trend Direction:** {state["symbol_data"]["technical_indicators"]["trend_indicators"]["trend_direction"]}
- **Trend Strength:** {state["symbol_data"]["technical_indicators"]["trend_indicators"]["trend_strength"]}

---

## AI-Powered Analysis

{analysis}

---

"""
        
        # Save report
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        print(f"✅ Report successfully saved: {report_path}")
        
        state["report_path"] = str(report_path)
        state["messages"].append({"role": "assistant", "content": f"Report saved to {report_path}"})
        
        return state
    
    def _build_graph(self):
        """Build the LangGraph workflow"""
        workflow = StateGraph(self.AgentState)
        
        # Add nodes
        workflow.add_node("analyze", self.analyze_node)
        workflow.add_node("save_report", self.save_report_node)
        
        # Add edges
        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", "save_report")
        workflow.add_edge("save_report", END)
        
        return workflow.compile()
    
    def process_symbol_data(self, symbol_data_dict):
        """
        Process a single symbol's data through the LangGraph agent.
        
        Args:
            symbol_data_dict: Dictionary containing symbol data and indicators
        """
        initial_state = {
            "messages": [{"role": "user", "content": f"Analyze market data for {symbol_data_dict['symbol']}"}],
            "symbol_data": symbol_data_dict,
            "analysis_result": "",
            "report_path": ""
        }
        
        # Run the graph
        final_state = self.graph.invoke(initial_state)
        
        print(f"✅ Analysis complete for {symbol_data_dict['symbol']}")
        print(f"📄 Report saved: {final_state['report_path']}")
        
        return final_state
    
    def process_market_data_table(self, market_table):
        """
        Process the entire market data table: calculate indicators, group by symbol, 
        and generate reports for each ticker.
        
        Uses tumbling window of 1 minute - processes only rows added in each 1-minute period.
        
        Args:
            market_table: Pathway table from MarketDataConsumer
        """
        
        print(f"📊 Applying tumbling window: 1 minute duration")
        
        # Step 1: Calculate technical indicators on all incoming data
        print("📊 Calculating technical indicators...")
        enriched_table = self.calculate_technical_indicators(market_table)
        
        # Step 2: Apply tumbling window and group by symbol
        # Tumbling window creates non-overlapping 1-minute windows
        print("🔄 Applying windowing and grouping by symbol...")
        windowed_table = enriched_table.windowby(
            enriched_table.sent_at,
            window=pw.temporal.tumbling(
                duration=timedelta(minutes=1)  # Process data from each 1-minute period
            ),
            instance=enriched_table.symbol
        ).reduce(
            symbol=pw.this._pw_instance,
            window_start=pw.this._pw_window_start,
            window_end=pw.this._pw_window_end,
            # OHLCV aggregations - use coalesce to handle nullable columns
            avg_open=pw.reducers.avg(pw.coalesce(pw.this.open, 0.0)),
            avg_high=pw.reducers.avg(pw.coalesce(pw.this.high, 0.0)),
            avg_low=pw.reducers.avg(pw.coalesce(pw.this.low, 0.0)),
            avg_close=pw.reducers.avg(pw.coalesce(pw.this.current_price, 0.0)),
            max_high=pw.reducers.max(pw.coalesce(pw.this.high, 0.0)),
            min_low=pw.reducers.min(pw.coalesce(pw.this.low, 0.0)),
            latest_price=pw.reducers.latest(pw.coalesce(pw.this.current_price, 0.0)),
            latest_volume=pw.reducers.latest(pw.coalesce(pw.this.current_price, 0.0)),  # Placeholder
            
            # Technical indicators - already computed as non-nullable
            avg_price_range=pw.reducers.avg(pw.this.price_range),
            avg_typical_price=pw.reducers.avg(pw.this.typical_price),
            avg_price_vs_open=pw.reducers.avg(pw.this.price_vs_open),
            avg_intraday_volatility=pw.reducers.avg(pw.this.intraday_volatility),
            avg_daily_return=pw.reducers.avg(pw.this.daily_return),
            
            # Price changes - handle nullable
            latest_change=pw.reducers.latest(pw.coalesce(pw.this.change, 0.0)),
            latest_change_percent=pw.reducers.latest(pw.coalesce(pw.this.change_percent, 0.0)),
            
            # Metadata
            data_points=pw.reducers.count(),
            latest_timestamp=pw.reducers.latest(pw.this.timestamp)
        )
        
        # Step 3: Process each windowed symbol and generate reports
        print("🤖 Starting LLM analysis for each symbol window...", flush=True)
        
        # Add a simple apply to trigger processing per row
        def generate_report(row):
            """Generate report for a windowed row"""
            try:
                print(f"\n{'='*60}", flush=True)
                print(f"🔄 WINDOW CLOSED for {row['symbol']}", flush=True)
                print(f"   Time range: {row['window_start']} to {row['window_end']}", flush=True)
                print(f"   Data points: {row['data_points']}", flush=True)
                print(f"{'='*60}\n", flush=True)
                
                # Create JSON for the symbol window
                symbol_json = self.create_json_for_window(row)
                
                print(f"📊 Calling OpenAI for {row['symbol']} analysis...", flush=True)
                
                # Process through LangGraph agent (this saves the report)
                result = self.process_symbol_data(symbol_json)
                
                print(f"✅ Report generation complete for {row['symbol']}", flush=True)
                
                return f"Report saved: {result['report_path']}"
                
            except Exception as e:
                import traceback
                error_msg = f"Error processing {row.get('symbol', 'unknown')}: {str(e)}"
                print(f"❌ {error_msg}", flush=True)
                print(traceback.format_exc(), flush=True)
                return error_msg
        
        # Subscribe directly to the windowed table with ALL columns
        pw.io.subscribe(
            windowed_table,
            on_change=lambda key, row, time, is_addition: generate_report(row) if is_addition else None
        )
        
        return windowed_table
    
    def run(self):
        """
        Main execution method: consume market data, process, and generate reports.
        """
        print("🚀 Starting Market Analysis Agent...")
        print(f"📁 Reports will be saved to: {self.reports_dir.absolute()}")
        
        # Consume market data from Kafka
        print("📥 Consuming market data from Kafka...")
        market_table = self.consumer.consume()
        
        # Process the table and generate reports
        self.process_market_data_table(market_table)
        
        # Run Pathway computation
        print("⚙️  Running Pathway computation...")
        pw.run()
        
        print("✅ Market Analysis Agent completed successfully!")


def main():
    """Main entry point"""
    try:
        agent = MarketAnalysisAgent()
        agent.run()
    except KeyboardInterrupt:
        print("\n👋 Market Analysis Agent stopped by user")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise


if __name__ == "__main__":
    main()
