"""
Bull Researcher for Bull-Bear Debate.
Pure Pathway Streaming Implementation (like news_agent.py)
"""
import functools
import os
import json
from datetime import datetime
import litellm
from dotenv import load_dotenv

from .tools import retrieve_from_pathway

# from event_publisher import publish_agent_status, publish_report
from guardrails import get_bull_guardrails

# Initialize guardrails
_guardrails = get_bull_guardrails()

from event_publisher import publish_agent_status, publish_report
from redis_cache import get_redis_client


load_dotenv()

# Reports directory for debate history
REPORTS_DIR = os.environ.get("REPORTS_DIR", "./reports/bullbear")

# JSON output contract for Bull - ALWAYS request tool
SYSTEM_JSON = """
You are a Bull Analyst advocating for bullish positions.

You MUST output ONLY JSON in this EXACT format:
{
  "thought": "<your reasoning for why you need more information>",
  "tool_call": {
     "name": "retrieve_from_pathway",
     "arguments": { "question": "<your question to retrieve relevant data>" }
  }
}

IMPORTANT:
- You MUST call the tool to gather evidence for your bullish analysis
- Ask questions about growth potential, positive catalysts, market opportunities
- Focus on finding supporting data for the company's upside

Never output anything outside JSON.
"""

SYSTEM_JSON_FINAL = """
You are a Bull Analyst advocating for bullish positions.

You have called a tool and received the results. Now provide your final bullish analysis.

You MUST output ONLY JSON in this EXACT format:
{
  "thought": "<your reasoning based on the tool results>",
  "final_answer": "<your complete bullish analysis arguing for the stock>"
}

IMPORTANT: 
- Provide a compelling bullish case
- Use the tool results as evidence
- Be persuasive but factual
- Do NOT call any more tools

Never output anything outside JSON.
"""


class BullDebateManager:
    """Manages Bull debate history and LLM calls using litellm directly."""

    def __init__(self, reports_directory: str = REPORTS_DIR):
        self.reports_directory = reports_directory
        os.makedirs(self.reports_directory, exist_ok=True)

        # Get model and API key
        self.model_name = os.getenv('OPENAI_MODEL', 'openai/gpt-4o-mini')
        if not self.model_name.startswith('openrouter/') and not self.model_name.startswith('openai/'):
            self.model_name = f'openrouter/{self.model_name}'
        
        self.api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.api_base = "https://openrouter.ai/api/v1"
        
        print(f"✅ [BULL] Initialized with model: {self.model_name}")

    def _get_report_path(self, symbol: str) -> str:
        """Get path for bull debate history file."""
        company_dir = os.path.join(self.reports_directory, symbol)
        os.makedirs(company_dir, exist_ok=True)
        return os.path.join(company_dir, "bull_debate.md")

    def _load_debate_history(self, symbol: str) -> str:
        """Load existing debate history or create initial template."""
        report_path = self._get_report_path(symbol)

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            initial_report = f"""# Bull Analyst Debate History - {symbol}

## Debate Rounds
*No rounds yet...*

---
*Last Updated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC*
"""
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(initial_report)
            return initial_report

    def _save_debate_round(self, symbol: str, round_num: int, content: str) -> str:
        """Append new round to debate history file."""
        report_path = self._get_report_path(symbol)
        
        # Load existing
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                existing = f.read()
        except FileNotFoundError:
            existing = self._load_debate_history(symbol)

        # Append new round
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        new_round = f"""
### Round {round_num} - {timestamp} UTC
{content}

---
"""
        # Replace "No rounds yet" if present
        if "*No rounds yet...*" in existing:
            existing = existing.replace("*No rounds yet...*", "")
        
        # Insert before last updated line
        if "*Last Updated:" in existing:
            parts = existing.rsplit("*Last Updated:", 1)
            updated = parts[0] + new_round + f"*Last Updated: {timestamp} UTC*"
        else:
            updated = existing + new_round

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(updated)

        print(f"✈️ [BULL] Saved Round {round_num} for {symbol} to {report_path}")
        return updated

    def _get_llm_response(self, messages: list[dict]) -> str:
        """Get LLM response using litellm directly (synchronous)."""
        try:
            response = litellm.completion(
                model=self.model_name,
                messages=messages,
                api_key=self.api_key,
                api_base=self.api_base,
                temperature=0.3,
                max_tokens=1500,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ [BULL] LLM call failed: {e}")
            return json.dumps({"thought": "LLM_ERROR", "final_answer": f"Error: {str(e)}"})


def strict_json_parse(raw):
    """Parse JSON, handling common issues."""
    try:
        return json.loads(raw)
    except:
        try:
            cleaned = raw.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned)
        except:
            return {"thought": "JSON_ERROR", "final_answer": raw}


def safe_str(x):
    """Convert to string safely."""
    if isinstance(x, str):
        return x
    try:
        return json.dumps(x, ensure_ascii=False)
    except:
        return str(x)


# Global debate manager instance
_debate_manager = None

def get_debate_manager():
    """Get or create debate manager singleton."""
    global _debate_manager
    if _debate_manager is None:
        _debate_manager = BullDebateManager()
    return _debate_manager


def create_bull_researcher(llm, bull_memory):
    """Create a Bull researcher node with Pathway streaming."""

    # Get debate manager (singleton)
    debate_manager = get_debate_manager()

    def safe_mem(content, **kw):
        try:
            bull_memory.add_note(content=safe_str(content), **kw)
        except Exception as e:
            print(f"[A-MEM ERROR] Failed to save bull memory: {e}")

    def bull_node(state, name):
        client = get_redis_client()
        room_id = state.get("room_id", "default")
        publish_agent_status(room_id, "Bull Agent", "RUNNING", redis_sync=client)

        company = state["company_of_interest"]
        inv = state["investment_debate_state"]

        # Load debate history from file (Pathway streaming state)
        debate_history = debate_manager._load_debate_history(company)
        print(f"📂 [BULL] Loaded debate history for {company}")

        # Combine reports
        research_text = f"""Market: {state["market_report"]}
Sentiment: {state["sentiment_report"]}
News: {state["news_report"]}
Fundamentals: {state["fundamentals_report"]}"""

        # A-Mem retrieval
        try:
            retrieved = bull_memory.search_agentic(
                f"{company} upside growth strengths opportunities",
                k=5
            )
            retrieved_text = "\n".join("- " + safe_str(m["content"]) for m in retrieved)
        except:
            retrieved_text = "[A-MEM retrieval error]"

        USER = f"""
Company: {company}

Research Reports:
{research_text}

Previous Debate History (from file):
{debate_history}

Current Debate State:
{inv.get("history", "")}

Bear's Latest Message:
{inv.get("bear_history", "")}

Relevant Past Memory (A-MEM):
{retrieved_text}

Your turn. Bull Round {inv['count']}.
You MUST call the tool to gather evidence for your bullish case.
"""

        # ============================================
        # PASS 1 — Always call tool (Pathway streaming)
        # ============================================
        messages1 = [
            {"role": "system", "content": SYSTEM_JSON},
            {"role": "user", "content": USER}
        ]

        print("\n====== 🟩 BULL — LLM PASS 1 (TOOL REQUEST) ======")
        llm1_raw = debate_manager._get_llm_response(messages1)
        
        try:
            print(json.dumps(json.loads(llm1_raw), indent=2)[:500])
        except:
            print(str(llm1_raw)[:500])
        print("=================================================\n")

        llm1 = strict_json_parse(llm1_raw)

        # ============================================
        # TOOL CALL — Always execute
        # ============================================
        tool = llm1.get("tool_call")
        if tool and tool.get("arguments"):
            args = tool["arguments"]
            question = args.get("question", f"{company} growth potential bullish factors")
        else:
            # Force tool call if LLM didn't provide one
            question = f"{company} growth potential upside opportunities bullish factors"
            print("⚠️  [BULL] LLM didn't request tool, forcing tool call")

        print(f"🔧 [BULL] Calling tool: retrieve_from_pathway('{question}')")
        tool_result = retrieve_from_pathway(question=question)
        print(f"🔧 [BULL] Tool returned {len(str(tool_result))} chars")

        # ============================================
        # PASS 2 — Final answer with tool results (Pathway streaming)
        # ============================================
        messages2 = [
            {"role": "system", "content": SYSTEM_JSON_FINAL},
            {"role": "user", "content": USER},
            {"role": "assistant", "content": json.dumps(llm1)},
            {"role": "user", "content": f"Tool results:\n{json.dumps(tool_result, indent=2)}\n\nNow provide your final_answer with a compelling bullish analysis."}
        ]

        print("\n====== 🟨 BULL — LLM PASS 2 (FINAL ANSWER) ======")
        llm2_raw = debate_manager._get_llm_response(messages2)
        
        try:
            print(json.dumps(json.loads(llm2_raw), indent=2)[:500])
        except:
            print(str(llm2_raw)[:500])
        print("=================================================\n")

        llm2 = strict_json_parse(llm2_raw)
        final_answer = llm2.get("final_answer", "")

        if not final_answer:
            final_answer = llm2.get("thought", "Unable to generate bullish analysis.")
            print("⚠️  [BULL] No final_answer, using thought")

        final_answer = safe_str(final_answer)

        # ========== GUARDRAILS OUTPUT CHECK ==========
        if _guardrails.enabled:
            print("🛡️  [GUARDRAILS] Checking Bull output...")
            original_answer = final_answer  # Keep backup
            try:
                guardrails_result = _guardrails.check_output_sync(final_answer)
                guarded_message = guardrails_result.get("message", "")
                if guarded_message and guarded_message != final_answer:
                    print("🛡️  [GUARDRAILS] Output was modified by guardrails")
                    final_answer = guarded_message
                elif not guarded_message:
                    print("⚠️  [GUARDRAILS] Empty response, keeping original")
                    final_answer = original_answer
            except Exception as e:
                print(f"⚠️  [GUARDRAILS] Error: {e}, keeping original")
                final_answer = original_answer
        # =============================================

        # SAVE MEMORY
        # ============================================
        # SAVE TO FILE (Pathway streaming state)
        # ============================================
        # Round number: Bull goes first, so round = (count // 2) + 1
        # count=0 -> round 1, count=2 -> round 2, count=4 -> round 3
        round_num = (inv['count'] // 2) + 1
        debate_manager._save_debate_round(company, round_num, final_answer)

        # ============================================
        # SAVE TO A-MEM
        # ============================================
        safe_mem(
            final_answer,
            keywords=[company, "bull"],
            context=f"round {round_num}",
            tags=["bull_research", company],
        )

        # ============================================
        # PUBLISH TO REDIS
        # ============================================
        publish_agent_status(room_id, "Bull Agent", "UPLOADING BULL REPORT", redis_sync=client)
        publish_report(room_id, "Bull Agent", final_answer, redis_sync=client, event_type="bull_chat")
        publish_agent_status(room_id, "Bull Agent", "CLOSED", redis_sync=client)

        # ============================================
        # UPDATE STATE (for StateGraph compatibility)
        # ============================================
        inv2 = {
            **inv,
            "current_response": final_answer,
            "bull_history": (inv["bull_history"] + "\n" + final_answer).strip(),
            "history": (inv["history"] + "\n[BULL]: " + final_answer).strip(),
            "count": inv["count"] + 1,
            "last_speaker": "bull_researcher",
        }

        print(f"✅ [BULL] Round {round_num} complete for {company}")
        return {"investment_debate_state": inv2, "sender": name}

    return functools.partial(bull_node, name="Bull Analyst")
