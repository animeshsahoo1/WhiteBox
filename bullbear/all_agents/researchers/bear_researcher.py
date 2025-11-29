import functools
import pathway as pw
import pandas as pd
import os
import json
from dotenv import load_dotenv

from agentic_memory.memory_system import AgenticMemorySystem


# ============================================================
#  IMPORT ONLY ONE TOOL → Pathway Retriever
# ============================================================
from .researcher_tools import retrieve_from_pathway


# ============================================================
#  INIT
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
# STRICT JSON CONTRACT WITH ONLY ONE TOOL
# ============================================================
SYSTEM_JSON = """
You are a Bear Analyst.

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
  "final_answer": "<your bearish analysis>"
}

TOOL RULES:
- You have access to ONLY ONE TOOL: retrieve_from_pathway(question)
- You MUST call this tool whenever:
    • You need evidence for your bearish claims
    • You want more factual details
    • You want to rebut the bull strongly
    • You feel unsure and want more context

Never output anything outside JSON.
"""

# System prompt for Pass 2 - MUST give final answer, NO tool calls allowed
SYSTEM_JSON_FINAL = """
You are a Bear Analyst.

You have already called a tool and received the results. Now you MUST provide your final analysis.

You MUST output ONLY JSON in this EXACT format:
{
  "thought": "<your reasoning based on the tool results>",
  "final_answer": "<your complete bearish analysis>"
}

IMPORTANT: You CANNOT call any more tools. You MUST provide a final_answer NOW.
Never output anything outside JSON.
"""


# ============================================================
# JSON SAFETY HELPERS
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
# BEAR NODE — WITH RETRIEVAL TOOL ACCESS
# ============================================================
def create_bear_researcher(llm, bear_memory):
    
    def safe_mem(content, **kw):
        try:
            bear_memory.add_note(content=safe_str(content), **kw)
        except Exception as e:
            print(f"[A-MEM ERROR] Failed to save bear memory: {e}")
            # Don't retry if the first attempt failed - it will likely fail again

    def bear_node(state, name):

        company = state["company_of_interest"]
        inv = state["investment_debate_state"]

        # Combine reports
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
            retrieved = bear_memory.search_agentic(
                f"{company} downside risks weaknesses threats",
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

Bull Message:
{inv.get("bull_history","")}

Relevant Past Memory:
{retrieved_text}

Your turn. Bear Round {inv["count"]}.
"""

        # =====================================================
        # FIRST LLM CALL → DECIDE TOOL OR FINAL
        # =====================================================
        df = pw.debug.table_to_pandas(
            pw.debug.table_from_pandas(
                pd.DataFrame({"m": [[
                    {"role": "system", "content": SYSTEM_JSON},
                    {"role": "user", "content": USER}
                ]]})
            ).select(reply=llm(pw.this.m))
        )

        # Pathway LiteLLMChat returns RAW JSON in reply column
        llm1_raw = df["reply"].iloc[0]

        print("\n\n====== INPUT ======\n")
        print("A-MEM:", len(bear_memory.memories))  
        print(str(USER))
        print("\n============================================\n")

        print("\n\n====== 🟩 LLM PASS 1 — DECISION PHASE ======\n")
        print(json.dumps(json.loads(llm1_raw), indent=4))
        print("\n============================================\n")

        llm1 = strict_json_parse(llm1_raw)

        tool = llm1.get("tool_call")

        # =====================================================
        # IF TOOL CALL
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

            llm2_raw = df2["reply"].iloc[0]     # SAME WORKING EXTRACTION

            print("\n\n====== 🟨 LLM PASS 2 — FINAL ANSWER PHASE ======\n")
            print(json.dumps(json.loads(llm2_raw), indent=4))
            print("\n===============================================\n")

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
        safe_mem(final_answer,
                 keywords=[company, "bear"],
                 context=f"round {inv['count']}",
                 tags=["bear_research", company])

        # =====================================================
        # UPDATE DEBATE STATE
        # =====================================================
        inv2 = {
            **inv,
            "current_response": final_answer,
            "bear_history": (inv["bear_history"] + "\n" + final_answer).strip(),
            "history": (inv["history"] + "\n" + final_answer).strip(),
            "count": inv["count"] + 1,
            "last_speaker": "bear_researcher",
        }

        return {"investment_debate_state": inv2, "sender": name}

    return functools.partial(bear_node, name="Bear Analyst")


# ============================================================
# FULL TESTING — TOOL CALL + FORCED EVIDENCE USE
# ============================================================
if __name__ == "__main__":
    print("\n\n==========🔥 BEAR RETRIEVAL MULTI-ROUND TEST 🔥==========\n")

    base = {
        "company_of_interest": "Fire Safety Guidelines",

        "market_report": "Recent incidents indicate rising fire hazards.",
        "sentiment_report": "People are increasingly concerned about fire preparedness.",
        "news_report": "Several fire accidents reported due to poor evacuation planning.",
        "fundamentals_report": "Most buildings lack modern fire suppression systems.",

        "investment_debate_state": {
            "bear_history": "",
            "bull_history": "",
            "history": "",
            "count": 1,
            "last_speaker": "bull",
        }
    }

    bear_agent = create_bear_researcher(chat_model, bear_memory)

    # dummy bull message to simulate alternating debate
    DUMMY_BULL_REPLY = "I disagree — current fire safety guidelines are sufficient."

    state = json.loads(json.dumps(base))

    for round_num in range(1, 4):   # ✅ Run 3 rounds
        print(f"\n>>> 🧠 ROUND {round_num} — Bear Response\n")

        # Force bull to ask for evidence only in first round
        if round_num == 1:
            state["investment_debate_state"]["bull_history"] += (
                "\nShow evidence from stored fire safety documents."
            )

        # Run bear agent
        out = bear_agent(state)

        new_state = out["investment_debate_state"]
        print("\n--------- 🟦 BEAR RESPONSE ---------\n")
        print(new_state["current_response"])
        print("\n-----------------------------------\n")

        # ✅ Add dummy bull response for next round
        new_state["bull_history"] += "\n" + DUMMY_BULL_REPLY
        new_state["history"] += "\n" + DUMMY_BULL_REPLY
        new_state["last_speaker"] = "bull"

        state["investment_debate_state"] = new_state

    print("\n==========🔥 TEST END — 3 ROUNDS COMPLETE 🔥==========\n")

    print("\n✅ FULL DEBATE HISTORY:\n")
    print(state["investment_debate_state"]["history"])

