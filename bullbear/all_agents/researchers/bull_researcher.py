import functools
import pathway as pw
import pandas as pd
import os
import json
from dotenv import load_dotenv

from agentic_memory.memory_system import AgenticMemorySystem
from .researcher_tools import retrieve_from_pathway     # SAME TOOL AS BEAR

# ============================================================
# INIT
# ============================================================
load_dotenv()

from pathway.xpacks.llm import llms

chat_model = llms.LiteLLMChat(
    model="openrouter/openai/gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)

# ============================================================
# STRICT JSON CONTRACT (MIRROR OF BEAR, BULL VERSION)
# ============================================================
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

# System prompt for Pass 2 - MUST give final answer, NO tool calls allowed
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


# ============================================================
# JSON UTILS
# ============================================================
def strict_json_parse(raw):
    try:
        return json.loads(raw)
    except:
        try:
            cleaned = raw.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned)
        except:
            return {"thought": "JSON_ERROR", "final_answer": raw}


def safe_str(x):
    if isinstance(x, str):
        return x
    try:
        return json.dumps(x, ensure_ascii=False)
    except:
        return str(x)


# ============================================================
# BULL NODE — SAME AS BEAR NODE
# ============================================================
def create_bull_researcher(llm, bull_memory):

    def safe_mem(content, **kw):
        try:
            bull_memory.add_note(content=safe_str(content), **kw)
        except Exception as e:
            print(f"[A-MEM ERROR] Failed to save bull memory: {e}")
            # Don't retry if the first attempt failed - it will likely fail again

    def bull_node(state, name):

        company = state["company_of_interest"]
        inv = state["investment_debate_state"]

        # Combine reports like Bear
        @pw.udf
        def combine(m, s, n, f):
            return f"Market: {m}\nSentiment: {s}\nNews: {n}\nFundamentals: {f}"

        research_text = combine(
            state["market_report"],
            state["sentiment_report"],
            state["news_report"],
            state["fundamentals_report"],
        )

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

        # =====================================================
        # PASS 1 — Decide Tool Or Final
        # =====================================================
        df = pw.debug.table_to_pandas(
            pw.debug.table_from_pandas(
                pd.DataFrame({"m": [[
                    {"role": "system", "content": SYSTEM_JSON},
                    {"role": "user", "content": USER}
                ]]})
            ).select(reply=llm(pw.this.m))
        )

        llm1_raw = df["reply"].iloc[0]

        print("\n\n====== 🟩 BULL — LLM PASS 1 (DECISION) ======\n")
        try:
            print(json.dumps(json.loads(llm1_raw), indent=4))
        except:
            print(llm1_raw)
        print("\n==============================================\n")

        llm1 = strict_json_parse(llm1_raw)
        tool = llm1.get("tool_call")

        # =====================================================
        # TOOL CALL
        # =====================================================
        if tool:
            args = tool["arguments"]
            tool_result = retrieve_from_pathway(**args)

            # SECOND CALL — FEED RESULT BACK (use SYSTEM_JSON_FINAL to force final answer)
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

            print("\n\n====== 🟨 BULL — LLM PASS 2 (FINAL) ======\n")
            try:
                print(json.dumps(json.loads(llm2_raw), indent=4))
            except:
                print(llm2_raw)
            print("\n===========================================\n")

            llm2 = strict_json_parse(llm2_raw)
            final_answer = llm2.get("final_answer", "")
            
            # Edge case: if LLM still tries to call tool in Pass 2, use thought as answer
            if not final_answer and llm2.get("tool_call"):
                print("⚠️  LLM tried to call tool in Pass 2, using thought as final answer")
                final_answer = llm2.get("thought", "Unable to generate analysis.")

        else:
            final_answer = llm1.get("final_answer", "")

        final_answer = safe_str(final_answer)

        # =====================================================
        # SAVE MEMORY
        # =====================================================
        print(f"\n💾 Starting to Save Bull Memory. Total memories: {len(bull_memory.memories)}\n")

        safe_mem(
            final_answer,
            keywords=[company, "bull"],
            context=f"round {inv['count']}",
            tags=["bull_research", company],
        )

        print(f"\n💾 Saved Bull Memory. Total memories: {len(bull_memory.memories)}\n")

        # =====================================================
        # UPDATE STATE
        # =====================================================
        inv2 = {
            **inv,
            "current_response": final_answer,
            "bull_history": (inv["bull_history"] + "\n" + final_answer).strip(),
            "history": (inv["history"] + "\n" + final_answer).strip(),
            "count": inv["count"] + 1,
            "last_speaker": "bull_researcher",
        }

        return {"investment_debate_state": inv2, "sender": name}

    return functools.partial(bull_node, name="Bull Analyst")


# ============================================================
# TEST BLOCK (Matches Bear Testing)
# ============================================================
if __name__ == "__main__":
    print("\n\n========== 🐂 BULL RETRIEVAL TEST START ==========\n")

    base = {
        "company_of_interest": "Fire Safety Guidelines",

        "market_report": "Fire awareness improving.",
        "sentiment_report": "Public sentiment strongly favors safety upgrades.",
        "news_report": "Government mandates stricter fire regulations.",
        "fundamentals_report": "Industry expected to grow significantly.",

        "investment_debate_state": {
            "bull_history": "",
            "bear_history": "Fire safety guidelines are already too weak.",
            "history": "",
            "count": 1,
            "last_speaker": "bear",
        }
    }

    bull_agent = create_bull_researcher(chat_model, bull_memory)

    print("\n>>> 🧠 ROUND 1 — Bull Response (FORCED RETRIEVAL)\n")
    state = json.loads(json.dumps(base))
    state["investment_debate_state"]["bear_history"] += "\nProvide factual bullish evidence."

    out = bull_agent(state)

    print("\n--------- 🟧 FINAL BULL RESPONSE ---------\n")
    print(out["investment_debate_state"]["current_response"])
    print("\n------------------------------------------\n")

    print("\n========== 🐂 TEST END ==========\n")
