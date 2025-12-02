"""
Bull Researcher for Bull-Bear Debate.
Adapted from bullbear/all_agents/researchers/bull_researcher.py
"""
import functools
import os
import json
import pandas as pd
import pathway as pw
from dotenv import load_dotenv

from .tools import retrieve_from_pathway

# from event_publisher import publish_agent_status, publish_report
from guardrails import get_bull_guardrails

# Initialize guardrails
_guardrails = get_bull_guardrails()

from event_publisher import publish_agent_status, publish_report
from redis_cache import get_redis_client


load_dotenv()

# JSON output contract for Bull
SYSTEM_JSON = """
You are a Bull Analyst.

You MUST output ONLY JSON. TWO valid formats:

1️⃣ TOOL CALL FORMAT:
{
  "thought": "<reason>",
  "tool_call": {
     "name": "retrieve_from_pathway",
     "arguments": { "question": "<string>" }
  }
}

2️⃣ FINAL ANSWER FORMAT:
{
  "thought": "<reason>",
  "final_answer": "<your bullish analysis>"
}

TOOL RULES:
- You have access to ONLY ONE TOOL: retrieve_from_pathway(question)
- You MUST call this tool whenever:
    • You need evidence for bullish claims
    • You want more factual details
    • You want to rebut Bear strongly
    • You feel unsure and want more context

Never output anything outside JSON.
"""

SYSTEM_JSON_FINAL = """
You are a Bull Analyst.

You have already called a tool and received the results. Now you MUST provide your final analysis.

You MUST output ONLY JSON in this EXACT format:
{
  "thought": "<your reasoning based on the tool results>",
  "final_answer": "<your complete bullish analysis>"
}

IMPORTANT: You CANNOT call any more tools. You MUST provide a final_answer NOW.
Never output anything outside JSON.
"""


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


def create_bull_researcher(llm, bull_memory):
    """Create a Bull researcher node for LangGraph."""

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
Research:
{research_text}

Debate History:
{inv.get("history","")}

Bear Message:
{inv.get("bear_history","")}

Relevant Past Memory:
{retrieved_text}

Your turn. Bull Round {inv['count']}.
"""

        # PASS 1 — Decide Tool Or Final
        df = pw.debug.table_to_pandas(
            pw.debug.table_from_pandas(
                pd.DataFrame({"m": [[
                    {"role": "system", "content": SYSTEM_JSON},
                    {"role": "user", "content": USER}
                ]]})
            ).select(reply=llm(pw.this.m))
        )

        llm1_raw = df["reply"].iloc[0]

        print("\n====== 🟩 BULL — LLM PASS 1 (DECISION) ======")
        try:
            print(json.dumps(json.loads(llm1_raw), indent=2)[:500])
        except:
            print(str(llm1_raw)[:500])
        print("==============================================\n")

        llm1 = strict_json_parse(llm1_raw)
        tool = llm1.get("tool_call")

        # TOOL CALL
        if tool:
            args = tool["arguments"]
            tool_result = retrieve_from_pathway(**args)

            messages2 = [
                {"role": "system", "content": SYSTEM_JSON_FINAL},
                {"role": "user", "content": USER},
                {"role": "assistant", "content": json.dumps(llm1)},
                {"role": "user", "content": f"Tool results: {json.dumps(tool_result)}\n\nNow provide your final_answer based on this information. Do NOT call any more tools."}
            ]

            df2 = pw.debug.table_to_pandas(
                pw.debug.table_from_pandas(pd.DataFrame({"m": [messages2]}))
                .select(reply=llm(pw.this.m))
            )

            llm2_raw = df2["reply"].iloc[0]

            print("\n====== 🟨 BULL — LLM PASS 2 (FINAL) ======")
            try:
                print(json.dumps(json.loads(llm2_raw), indent=2)[:500])
            except:
                print(str(llm2_raw)[:500])
            print("===========================================\n")

            llm2 = strict_json_parse(llm2_raw)
            final_answer = llm2.get("final_answer", "")
            
            if not final_answer and llm2.get("tool_call"):
                print("⚠️  LLM tried to call tool in Pass 2, using thought as final answer")
                final_answer = llm2.get("thought", "Unable to generate analysis.")
        else:
            final_answer = llm1.get("final_answer", "")

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
        safe_mem(
            final_answer,
            keywords=[company, "bull"],
            context=f"round {inv['count']}",
            tags=["bull_research", company],
        )

        publish_agent_status(room_id, "Bull Agent", "UPLOADING BULL REPORT", redis_sync=client)
        publish_report(room_id, "Bull Agent", final_answer, redis_sync=client, event_type="bull_chat")
        publish_agent_status(room_id, "Bull Agent", "CLOSED", redis_sync=client)

        # UPDATE STATE
        inv2 = {
            **inv,
            "current_response": final_answer,
            "bull_history": (inv["bull_history"] + "\n" + final_answer).strip(),
            "history": (inv["history"] + "\n[BULL]: " + final_answer).strip(),
            "count": inv["count"] + 1,
            "last_speaker": "bull_researcher",
        }

        return {"investment_debate_state": inv2, "sender": name}

    return functools.partial(bull_node, name="Bull Analyst")
