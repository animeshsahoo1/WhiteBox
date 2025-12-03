"""
Facilitator for Bull-Bear Debate - Pathway Streaming Version.
Watches bear_debate.md for changes and auto-generates facilitator reports.
"""
import os
import json
import threading
from datetime import datetime
from typing import Dict, Optional
import litellm
from dotenv import load_dotenv

load_dotenv()

# Reports directory for facilitator reports
REPORTS_DIR = os.environ.get("REPORTS_DIR", "./reports/bullbear")

# Track active facilitator streams per symbol
_active_streams: Dict[str, bool] = {}
_facilitator_status: Dict[str, Dict] = {}


class FacilitatorManager:
    """Manages facilitator report generation using litellm directly."""

    def __init__(self, reports_directory: str = REPORTS_DIR):
        self.reports_directory = reports_directory
        os.makedirs(self.reports_directory, exist_ok=True)

        # Get model and API key
        self.model_name = os.getenv('OPENAI_MODEL', 'openai/gpt-4o-mini')
        if not self.model_name.startswith('openrouter/') and not self.model_name.startswith('openai/'):
            self.model_name = f'openrouter/{self.model_name}'
        
        self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.api_base = "https://openrouter.ai/api/v1"
        
        print(f"✅ [FACILITATOR] Initialized with model: {self.model_name}")

    def get_symbol_dir(self, symbol: str) -> str:
        """Get directory path for symbol."""
        return os.path.join(self.reports_directory, symbol)

    def _get_report_path(self, symbol: str) -> str:
        """Get path for facilitator report file."""
        company_dir = self.get_symbol_dir(symbol)
        os.makedirs(company_dir, exist_ok=True)
        return os.path.join(company_dir, "facilitator_report.md")

    def _load_file(self, filepath: str) -> str:
        """Load file content safely."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def load_bull_history(self, symbol: str) -> str:
        """Load bull debate history."""
        path = os.path.join(self.get_symbol_dir(symbol), "bull_debate.md")
        return self._load_file(path)

    def load_bear_history(self, symbol: str) -> str:
        """Load bear debate history."""
        path = os.path.join(self.get_symbol_dir(symbol), "bear_debate.md")
        return self._load_file(path)

    def _load_report_history(self, symbol: str) -> str:
        """Load existing facilitator report history."""
        return self._load_file(self._get_report_path(symbol))

    def _save_report(self, symbol: str, report: str, round_num: int = 0) -> str:
        """Save facilitator report to file with round number."""
        report_path = self._get_report_path(symbol)
        
        # Add round metadata header to report
        round_header = f"<!-- Round: {round_num} -->\n\n"
        report_with_round = round_header + report
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_with_round)

        print(f"✈️ [FACILITATOR] Saved report for {symbol} (Round {round_num}) to {report_path}")
        return report_path

    def _get_llm_response(self, messages: list[dict]) -> str:
        """Get LLM response using litellm directly (synchronous)."""
        try:
            response = litellm.completion(
                model=self.model_name,
                messages=messages,
                api_key=self.api_key,
                api_base=self.api_base,
                temperature=0.3,
                max_tokens=3000,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ [FACILITATOR] LLM call failed: {e}")
            return f"Error generating report: {str(e)}"


# Global facilitator manager instance
_facilitator_manager = None

def get_facilitator_manager():
    """Get or create facilitator manager singleton."""
    global _facilitator_manager
    if _facilitator_manager is None:
        _facilitator_manager = FacilitatorManager()
    return _facilitator_manager


def _count_rounds_from_history(history: str) -> int:
    """Count completed rounds from debate history."""
    if not history:
        return 0
    return history.count("### Round")


def _update_facilitator_status(symbol: str, status: str, report: str = None, round_num: int = 0):
    """Update facilitator status for API."""
    global _facilitator_status
    
    # Preserve existing round if not provided
    existing = _facilitator_status.get(symbol, {})
    if round_num == 0 and existing:
        round_num = existing.get("round", 0)
    
    _facilitator_status[symbol] = {
        "symbol": symbol,
        "status": status,
        "report": report,
        "recommendation": extract_recommendation(report) if report else None,
        "round": round_num,
        "updated_at": datetime.utcnow().isoformat(),
    }


def generate_facilitator_report(
    symbol: str,
    bull_history: str = None,
    bear_history: str = None,
    total_exchanges: int = None,
    max_rounds: int = None
) -> str:
    """Generate facilitator report using litellm directly.
    
    If bull_history/bear_history not provided, loads from files.
    """
    facilitator = get_facilitator_manager()
    
    # Load from files if not provided
    if bull_history is None:
        bull_history = facilitator.load_bull_history(symbol)
    if bear_history is None:
        bear_history = facilitator.load_bear_history(symbol)
    
    # Calculate exchanges if not provided
    if total_exchanges is None:
        bull_rounds = _count_rounds_from_history(bull_history)
        bear_rounds = _count_rounds_from_history(bear_history)
        total_exchanges = bull_rounds + bear_rounds
    
    if max_rounds is None:
        max_rounds = max(_count_rounds_from_history(bull_history), _count_rounds_from_history(bear_history))
    
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    # Load previous report history for context
    previous_report = facilitator._load_report_history(symbol)
    history_context = ""
    if previous_report and len(previous_report) > 100:
        history_context = f"\n\n**Previous Facilitator Report (for context):**\n{previous_report[:2000]}...\n"
    
    system_prompt = f"""You are a Senior Financial Analyst acting as a Debate Facilitator for {symbol}.

Your role is to:
1. **Summarize** the bull-bear debate objectively
2. **Identify** key arguments from both sides
3. **Highlight** consensus points and major disagreements
4. **Assess** the strength of each position
5. **Provide** a balanced market outlook based on the debate
6. **Recommend** actionable insights with a clear BUY/HOLD/SELL recommendation

Output a well-structured markdown report with these sections:
- Executive Summary
- Bull Arguments (top 3-5 points)
- Bear Arguments (top 3-5 points)
- Areas of Agreement
- Major Disagreements
- Facilitator's Assessment (with BUY/HOLD/SELL recommendation)
- Risk Considerations
- Action Items

Be objective and balanced. Include confidence level (High/Medium/Low).
"""

    user_prompt = f"""Analyze this bull-bear debate for {symbol}:

**BULL ARGUMENTS:**
{bull_history}

**BEAR ARGUMENTS:**
{bear_history}
{history_context}
**Debate Info:**
- Total Exchanges: {total_exchanges}
- Rounds Completed: {max_rounds}
- Timestamp: {current_time} UTC

Generate a comprehensive facilitator report in markdown format.
End with "Last Analysis: {current_time} UTC"
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    print(f"\n====== 📋 FACILITATOR — GENERATING REPORT ======")
    print(f"Symbol: {symbol}, Exchanges: {total_exchanges}, Model: {facilitator.model_name}")
    print(f"================================================\n")
    
    report = facilitator._get_llm_response(messages)
    
    if not report.startswith("Error"):
        # Get current round from status or calculate from history
        current_round = _facilitator_status.get(symbol, {}).get("round", 0)
        if current_round == 0:
            current_round = max_rounds or _count_rounds_from_history(bear_history)
        
        # Save report to file with round number
        facilitator._save_report(symbol, report, round_num=current_round)
        # Save to Redis with round number
        save_facilitator_report_to_redis(symbol, report, round_num=current_round)
        # Update status
        _update_facilitator_status(symbol, "completed", report, round_num=current_round)
        print(f"✅ [FACILITATOR] Generated report ({len(report)} chars) - Round {current_round}")
    else:
        _update_facilitator_status(symbol, "error", report)
    
    return report


def get_facilitator_status(symbol: str) -> Optional[Dict]:
    """Get current facilitator status for a symbol."""
    symbol = symbol.upper()
    
    # Check in-memory status first
    if symbol in _facilitator_status:
        return _facilitator_status[symbol]
    
    # Try loading from file
    facilitator = get_facilitator_manager()
    report = facilitator._load_report_history(symbol)
    
    if report:
        # Try to extract round from report content
        round_num = 0
        import re
        
        # First try HTML comment format: <!-- Round: X -->
        match = re.search(r"<!-- Round: (\d+) -->", report)
        if match:
            round_num = int(match.group(1))
        # Fallback to "Rounds Completed:" format
        elif "Rounds Completed:" in report:
            try:
                match = re.search(r"Rounds Completed:\s*(\d+)", report)
                if match:
                    round_num = int(match.group(1))
            except:
                pass
        
        return {
            "symbol": symbol,
            "status": "completed",
            "report": report,
            "recommendation": extract_recommendation(report),
            "round": round_num,
            "updated_at": None,
            "source": "file"
        }
    
    return None


def extract_recommendation(report: str) -> str:
    """Extract BUY/HOLD/SELL recommendation from report."""
    if not report:
        return "UNKNOWN"
    
    report_upper = report.upper()
    
    if "STRONG BUY" in report_upper:
        return "STRONG BUY"
    elif "STRONG SELL" in report_upper:
        return "STRONG SELL"
    elif "BUY" in report_upper and "SELL" not in report_upper:
        return "BUY"
    elif "SELL" in report_upper and "BUY" not in report_upper:
        return "SELL"
    elif "HOLD" in report_upper:
        return "HOLD"
    else:
        return "HOLD"


def save_facilitator_report_to_redis(symbol: str, report: str, round_num: int = 0):
    """Save facilitator report to Redis and publish."""
    try:
        from redis_cache import get_redis_client, _build_symbol_key
        from event_publisher import publish_report
        
        client = get_redis_client()
        symbol_key = _build_symbol_key(symbol)
        
        # Get round from status if not provided
        if round_num == 0 and symbol in _facilitator_status:
            round_num = _facilitator_status[symbol].get("round", 0)
        
        entry = {
            "symbol": symbol,
            "report_type": "facilitator",
            "content": report,
            "recommendation": extract_recommendation(report),
            "round": round_num,
            "last_updated": datetime.utcnow().isoformat(),
            "received_at": datetime.utcnow().isoformat(),
        }
        
        client.hset(symbol_key, "facilitator", json.dumps(entry))
        client.sadd("reports:symbols", symbol)
        
        # Publish report update
        publish_report(symbol, "facilitator", report, redis_sync=client)
        
        print(f"✅ [FACILITATOR] Saved report to Redis for {symbol} (Round {round_num})")
    except Exception as e:
        print(f"⚠️  [FACILITATOR] Failed to save to Redis: {e}")


# ============================================================
# STREAMING FACILITATOR - File Watcher
# ============================================================

def _on_bear_file_change(symbol: str, bear_content: str):
    """Callback when bear_debate.md changes - triggers facilitator report generation."""
    
    # Count rounds from bear content
    current_round = _count_rounds_from_history(bear_content)
    
    print(f"\n🔔 [FACILITATOR] Detected change in bear_debate.md for {symbol} (Round {current_round})")
    
    # Update status to processing with current round
    _update_facilitator_status(symbol, "processing", round_num=current_round)
    
    # Generate new facilitator report
    try:
        report = generate_facilitator_report(symbol)
        # Update status to completed with report and round
        _update_facilitator_status(symbol, "completed", report, round_num=current_round)
        print(f"✅ [FACILITATOR] Auto-generated report for {symbol} (Round {current_round})")
    except Exception as e:
        print(f"❌ [FACILITATOR] Failed to generate report: {e}")
        _update_facilitator_status(symbol, "error", str(e), round_num=current_round)


def start_facilitator_stream(symbol: str, room_id: str = None):
    """
    Start streaming facilitator for a symbol.
    Watches bear_debate.md for changes and auto-generates facilitator reports.
    
    Args:
        symbol: Stock symbol (e.g., "AAPL")
        room_id: Room ID for pub/sub events
    """
    global _active_streams
    
    symbol = symbol.upper()
    
    if symbol in _active_streams and _active_streams[symbol]:
        print(f"⚠️  [FACILITATOR] Stream already active for {symbol}")
        return
    
    _active_streams[symbol] = True
    _update_facilitator_status(symbol, "waiting", round_num=0)  # Start with waiting status
    
    facilitator = get_facilitator_manager()
    bear_file_path = os.path.join(facilitator.get_symbol_dir(symbol), "bear_debate.md")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(bear_file_path), exist_ok=True)
    
    print(f"\n🎬 [FACILITATOR] Starting stream for {symbol}")
    print(f"   Watching: {bear_file_path}")
    
    def watch_file():
        """Watch bear_debate.md for changes using polling."""
        import time
        
        last_content = ""
        last_mtime = 0
        last_round_count = 0
        
        while _active_streams.get(symbol, False):
            try:
                if os.path.exists(bear_file_path):
                    mtime = os.path.getmtime(bear_file_path)
                    
                    if mtime > last_mtime:
                        with open(bear_file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        # Count rounds in current content
                        current_round_count = content.count("### Round")
                        
                        # Only trigger if a NEW round was added (not just any change)
                        # This prevents triggering on file clear or initial template
                        if current_round_count > last_round_count and current_round_count > 0:
                            last_content = content
                            last_mtime = mtime
                            last_round_count = current_round_count
                            
                            print(f"📊 [FACILITATOR] Round count: {last_round_count} -> {current_round_count}")
                            
                            # Trigger facilitator report generation
                            _on_bear_file_change(symbol, content)
                        elif content != last_content:
                            # Update tracking without triggering
                            last_content = content
                            last_mtime = mtime
                            last_round_count = current_round_count
                
                # Poll every 2 seconds
                time.sleep(2)
                
            except Exception as e:
                print(f"⚠️  [FACILITATOR] Watch error for {symbol}: {e}")
                time.sleep(5)
        
        print(f"🛑 [FACILITATOR] Stream stopped for {symbol}")
    
    # Start watching in background thread
    thread = threading.Thread(target=watch_file, daemon=True)
    thread.start()
    
    print(f"✅ [FACILITATOR] Stream started for {symbol}")


def stop_facilitator_stream(symbol: str):
    """Stop facilitator stream for a symbol."""
    global _active_streams
    
    symbol = symbol.upper()
    
    if symbol in _active_streams:
        _active_streams[symbol] = False
        _update_facilitator_status(symbol, "stopped")
        print(f"🛑 [FACILITATOR] Stopping stream for {symbol}")


def is_stream_active(symbol: str) -> bool:
    """Check if facilitator stream is active for a symbol."""
    return _active_streams.get(symbol.upper(), False)
