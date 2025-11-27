"""
Batch analysis module for historical market data.
Converts CSV/historical data to Pathway tables and runs market_agent2.py pipeline ONCE.
"""
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import pandas as pd
import pathway as pw


def run_historical_analysis_with_pathway(
    ticker: str,
    df: pd.DataFrame,
    report_id: str,
    output_dir: Path,
    indicators: list = None
) -> Dict[str, Any]:
    """
    Run market_agent2.py pipeline on historical data using Pathway tables.
    
    Process:
    1. Save DataFrame as CSV (Pathway reads from CSV)
    2. Create Pathway table from CSV
    3. Run process_market_stream_with_agents() ONCE on this static table
    4. Collect results from the reports directory
    
    Args:
        ticker: Stock symbol
        df: DataFrame with OHLCV data (from yfinance)
        report_id: Unique identifier for this report
        output_dir: Output directory for reports
        indicators: List of specific indicators to use (e.g., ['RSI', 'MACD'])
                   Note: Pipeline computes all indicators, filtering applied to results
        
    Returns:
        Dictionary with complete analysis results
    """
    try:
        # Import here to avoid circular dependencies
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from market_agent2 import process_market_stream_with_agents
        
        # Create temporary CSV file for Pathway to read
        temp_dir = Path(tempfile.gettempdir()) / "pathway_historical"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = temp_dir / f"{ticker}_{report_id}.csv"
        
        # Prepare data in the format expected by market_agent2
        # Need columns: symbol, timestamp, open, high, low, current_price, etc.
        df_pathway = pd.DataFrame({
            'symbol': ticker,
            'timestamp': df.index.strftime('%Y-%m-%dT%H:%M:%S'),
            'sent_at': df.index.strftime('%Y-%m-%dT%H:%M:%S.%f'),
            'open': df['Open'],
            'high': df['High'],
            'low': df['Low'],
            'current_price': df['Close'],
            'previous_close': df['Close'].shift(1).fillna(df['Close'].iloc[0]),
            'change': df['Close'].diff().fillna(0),
            'change_percent': df['Close'].pct_change().fillna(0) * 100,
        })
        
        # Save to CSV
        df_pathway.to_csv(csv_path, index=False)
        print(f"✅ Saved historical data to: {csv_path}")
        
        # Create Pathway table from CSV
        print(f"📊 Creating Pathway table from CSV...")
        
        # Define schema matching market_agent2 expectations
        class MarketDataSchema(pw.Schema):
            symbol: str
            timestamp: str
            sent_at: str
            open: float
            high: float
            low: float
            current_price: float
            previous_close: float
            change: float
            change_percent: float
        
        # Read CSV into Pathway table
        market_table = pw.io.csv.read(
            str(csv_path),
            schema=MarketDataSchema,
            mode="static"  # Static mode - read once, don't watch for changes
        )
        
        print(f"✅ Pathway table created with {len(df)} rows")
        
        # market_agent2 saves to ./reports/market/{ticker}/
        # We pass "./reports/market" as the base directory
        reports_base_dir = "./reports/market"
        
        # Run the market_agent2 pipeline on this static table
        print(f"🤖 Running market_agent2 pipeline...")
        
        # Storage for capturing results
        captured_results = []
        
        # Call process_market_stream_with_agents with appropriate parameters
        # This will process the entire table once and generate reports
        # Note: indicators param is for informational purposes in the pipeline
        analyzed_table = process_market_stream_with_agents(
            market_table=market_table,
            lookback_minutes=int((df.index[-1] - df.index[0]).total_seconds() / 60),  # Full duration
            hop_minutes=int((df.index[-1] - df.index[0]).total_seconds() / 60),  # Single window
            min_data_points=max(5, len(df) // 10),  # At least 10% of data or 5 points
            reports_directory=reports_base_dir,  # market_agent2 will create {ticker} subdirs
            indicators=indicators  # Pass to pipeline (currently for metadata only)
        )
        
        # Capture results using pw.io.subscribe with on_change callback
        def capture_result(key, row, time, is_addition):
            """Capture analysis results as they're generated"""
            if is_addition:
                try:
                    agent_results = row.get("agent_results", {})
                    
                    # Extract from pw.Json if needed
                    if hasattr(agent_results, 'as_dict'):
                        agent_dict = agent_results.as_dict()
                    else:
                        agent_dict = agent_results if isinstance(agent_results, dict) else {}
                    
                    # Build comprehensive report from agent results
                    symbol = row.get("symbol", "")
                    window_start = row.get("window_start", "")
                    window_end = row.get("window_end", "")
                    data_points = row.get("data_points", 0)
                    
                    comprehensive_report = f"""# 📊 Comprehensive Market Analysis: {symbol}

**Generated:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}  
**Period:** {window_start} to {window_end}  
**Data Points:** {data_points}

---

## 📈 Price Action & Patterns

**Pattern Agent Analysis:**
{agent_dict.get('pattern_report', 'No analysis available')}

**Trend Agent Analysis:**
{agent_dict.get('trend_report', 'No analysis available')}

---

## 📊 Technical Indicators

### Indicator Agent Analysis
{agent_dict.get('indicator_report', 'No analysis available')}

---

## 🎯 Trading Decision

**Decision:** {agent_dict.get('final_trade_decision', 'HOLD')}  
**Confidence:** {agent_dict.get('confidence_score', 0.5):.2%}

---
"""
                    
                    result_data = {
                        "symbol": symbol,
                        "comprehensive_report": comprehensive_report,
                        "final_trade_decision": agent_dict.get("final_trade_decision", "HOLD"),
                        "confidence_score": agent_dict.get("confidence_score", 0.5),
                        "window_start": str(window_start),
                        "window_end": str(window_end)
                    }
                    
                    captured_results.append(result_data)
                    print(f"✅ Captured analysis result for {symbol}")
                    print(f"   Report length: {len(comprehensive_report)} chars")
                    
                except Exception as e:
                    print(f"⚠️ Error capturing result: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Subscribe to table changes to capture results
        pw.io.subscribe(analyzed_table, on_change=capture_result)
        
        # Run Pathway computation (this actually executes the pipeline)
        print(f"⚙️ Executing Pathway computation...")
        pw.run()
        
        print(f"✅ Pipeline execution complete!")
        print(f"📊 Captured {len(captured_results)} analysis results")
        
        # Collect generated reports from ./reports/market/{ticker}/
        actual_reports_dir = Path(reports_base_dir)
        print(f"🔍 Checking reports directory: {actual_reports_dir / ticker}")
        
        if actual_reports_dir.exists():
            ticker_dir = actual_reports_dir / ticker
            if ticker_dir.exists():
                print(f"📁 Contents of {ticker_dir}:")
                for item in ticker_dir.rglob("*"):
                    if item.is_file():
                        print(f"   📄 {item.relative_to(actual_reports_dir)}")
        
        # Collect generated reports from the actual location
        report_files = collect_generated_reports(actual_reports_dir, ticker)
        
        # Clean up temporary CSV
        if csv_path.exists():
            csv_path.unlink()
        
        # Return captured results along with file info
        return {
            "status": "success",
            "captured_results": captured_results,
            "report_files": report_files,
            "reports_directory": str(actual_reports_dir / ticker),
            "ticker": ticker,
            "data_points": len(df)
        }
        
    except Exception as e:
        print(f"❌ Error in Pathway analysis: {e}")
        import traceback
        traceback.print_exc()
        raise


def collect_generated_reports(reports_dir: Path, ticker: str) -> Dict[str, Any]:
    """
    Collect the comprehensive report and images from the market_agent2 output.
    
    Args:
        reports_dir: Directory where market_agent2 saved reports (e.g., ./reports/market)
        ticker: Stock symbol
        
    Returns:
        Dictionary with paths to comprehensive report and all image files
    """
    # market_agent2 saves to: reports/market/{ticker}/reports/*.md and reports/market/{ticker}/images/*.png
    symbol_dir = reports_dir / ticker
    
    if not symbol_dir.exists():
        print(f"⚠️ Warning: No reports found for {ticker} in {reports_dir}")
        print(f"   Expected directory: {symbol_dir}")
        return {}
    
    reports_subdir = symbol_dir / "reports"
    images_dir = symbol_dir / "images"
    
    result = {
        "comprehensive_report": None,
        "images": []
    }
    
    # Find the comprehensive analysis report
    if reports_subdir.exists():
        comprehensive_reports = list(reports_subdir.glob("comprehensive_analysis_*.md"))
        if comprehensive_reports:
            # Get the most recent one
            result["comprehensive_report"] = str(sorted(comprehensive_reports)[-1])
            print(f"✅ Found comprehensive report: {comprehensive_reports[-1].name}")
        else:
            print(f"⚠️ No comprehensive_analysis_*.md found in {reports_subdir}")
    else:
        print(f"⚠️ Reports directory does not exist: {reports_subdir}")
    
    # Collect all images
    if images_dir.exists():
        for img_file in images_dir.glob("*.png"):
            result["images"].append(str(img_file))
        print(f"✅ Collected {len(result['images'])} images")
    else:
        print(f"⚠️ Images directory does not exist: {images_dir}")
    
    return result


def load_report_content(report_files: Dict[str, Any]) -> Dict[str, str]:
    """
    Load content from the comprehensive markdown report.
    
    Args:
        report_files: Dictionary from collect_generated_reports
        
    Returns:
        Dictionary with comprehensive report content
    """
    content = {"comprehensive_report": ""}
    
    # Load comprehensive report
    if report_files.get("comprehensive_report"):
        try:
            with open(report_files["comprehensive_report"], "r", encoding="utf-8") as f:
                content["comprehensive_report"] = f.read()
            print(f"✅ Loaded comprehensive report ({len(content['comprehensive_report'])} chars)")
        except Exception as e:
            print(f"⚠️ Error loading comprehensive report: {e}")
            content["comprehensive_report"] = ""
    else:
        print(f"⚠️ No comprehensive report path provided")
    
    return content


def load_images_as_base64(report_files: Dict[str, Any]) -> Dict[str, str]:
    """
    Load image files and convert to base64.
    
    Args:
        report_files: Dictionary with paths to image files
        
    Returns:
        Dictionary with base64 encoded images
    """
    import base64
    
    images = {}
    
    for img_path in report_files.get("images", []):
        img_name = Path(img_path).stem  # filename without extension
        
        try:
            with open(img_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
                images[img_name] = img_b64
        except Exception as e:
            print(f"⚠️ Failed to load image {img_path}: {e}")
    
    return images
