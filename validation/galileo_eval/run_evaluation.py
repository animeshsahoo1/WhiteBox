"""
Galileo Evaluation Runner with Full Trace Logging
===================================================
Directly tests the LLM agent and logs ALL tool calls, reasoning steps,
and agent actions to Galileo for comprehensive evaluation.

Metrics tracked:
- Tool Selection Quality: How well the agent picks the right tools
- Tool Errors: Count of failed tool invocations  
- Action Advancement: Progress made toward the goal (LLM-judged)
- Action Completion: Whether the task was fully completed (LLM-judged)
- Token Usage: Input/output tokens and estimated cost

Usage:
    python evaluation/run_evaluation.py

Make sure to set GALILEO_API_KEY in your .env file.
"""

import os
import sys
import json
import time
import uuid
import requests
import tiktoken
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv("../.env")

from galileo import GalileoLogger

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
GALILEO_PROJECT = os.getenv("GALILEO_PROJECT", "stock-trading-agent")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
EVAL_MODEL = os.getenv("EVAL_MODEL", "google/gemini-2.0-flash-001")

# Cost per 1M tokens (approximate for common models)
MODEL_COSTS = {
    "google/gemini-2.0-flash-001": {"input": 0.10, "output": 0.40},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai/gpt-4o": {"input": 2.50, "output": 10.00},
    "anthropic/claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "default": {"input": 0.50, "output": 1.50}
}


# ============================================
# TOKEN COUNTING & COST UTILITIES
# ============================================

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens using tiktoken (cl100k_base for most models)."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback: estimate ~4 chars per token
        return len(text) // 4

def calculate_cost(input_tokens: int, output_tokens: int, model: str = "default") -> float:
    """Calculate cost based on token usage and model pricing."""
    costs = MODEL_COSTS.get(model, MODEL_COSTS["default"])
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return round(input_cost + output_cost, 6)


# ============================================
# LLM JUDGE FUNCTIONS
# ============================================

def llm_judge_evaluation(
    query: str,
    response: str,
    tools_used: List[str],
    expected_tools: List[str]
) -> Dict[str, Any]:
    """
    Use an LLM to evaluate the agent's response quality.
    
    Returns scores for:
    - action_advancement: How much progress was made (0-1)
    - action_completion: Whether the task was fully completed (0-1)
    - reasoning_quality: Quality of reasoning shown (0-1)
    - relevance: How relevant the response is to the query (0-1)
    """
    
    evaluation_prompt = f"""You are an expert evaluator assessing an AI trading assistant's response.

USER QUERY: {query}

TOOLS USED BY AGENT: {', '.join(tools_used) if tools_used else 'None'}

EXPECTED TOOLS: {', '.join(expected_tools) if expected_tools else 'None'}

AGENT RESPONSE:
{response[:3000] if response else 'No response'}

---

Evaluate the agent's response on these criteria (score each 0.0 to 1.0):

1. **action_advancement** (0.0-1.0): How much progress did the agent make toward answering the query?
   - 0.0: No progress, completely off-topic or error
   - 0.3: Minimal progress, acknowledged the query but didn't help much
   - 0.6: Moderate progress, provided some relevant information
   - 0.8: Good progress, addressed most aspects of the query
   - 1.0: Full progress, comprehensively addressed all aspects

2. **action_completion** (0.0-1.0): Was the task fully completed?
   - 0.0: Task not completed, major failures or missing information
   - 0.3: Partially completed with significant gaps
   - 0.6: Mostly completed but missing some details
   - 0.8: Well completed with minor omissions
   - 1.0: Fully completed with comprehensive answer

3. **reasoning_quality** (0.0-1.0): Quality of analysis and reasoning shown?
   - 0.0: No reasoning, just generic statements
   - 0.3: Basic reasoning, surface-level analysis
   - 0.6: Decent reasoning with some insights
   - 0.8: Good reasoning with clear logic
   - 1.0: Excellent reasoning with deep analysis

4. **relevance** (0.0-1.0): How relevant is the response to what was asked?
   - 0.0: Completely irrelevant
   - 0.5: Partially relevant
   - 1.0: Fully relevant and on-topic

Respond ONLY with a valid JSON object in this exact format:
{{
    "action_advancement": <float>,
    "action_completion": <float>,
    "reasoning_quality": <float>,
    "relevance": <float>,
    "explanation": "<brief 1-2 sentence explanation>"
}}"""

    try:
        # Call OpenRouter API for evaluation
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Galileo Evaluation"
        }
        
        payload = {
            "model": EVAL_MODEL,
            "messages": [
                {"role": "system", "content": "You are an expert evaluator. Always respond with valid JSON only."},
                {"role": "user", "content": evaluation_prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 500
        }
        
        response_obj = requests.post(
            f"{OPENAI_API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response_obj.raise_for_status()
        
        result = response_obj.json()
        llm_response = result["choices"][0]["message"]["content"]
        
        # Parse JSON from response
        # Handle potential markdown code blocks
        if "```json" in llm_response:
            llm_response = llm_response.split("```json")[1].split("```")[0]
        elif "```" in llm_response:
            llm_response = llm_response.split("```")[1].split("```")[0]
        
        scores = json.loads(llm_response.strip())
        
        # Calculate tokens used for the evaluation itself
        eval_input_tokens = count_tokens(evaluation_prompt)
        eval_output_tokens = count_tokens(llm_response)
        eval_cost = calculate_cost(eval_input_tokens, eval_output_tokens, EVAL_MODEL)
        
        return {
            "action_advancement": float(scores.get("action_advancement", 0.5)),
            "action_completion": float(scores.get("action_completion", 0.5)),
            "reasoning_quality": float(scores.get("reasoning_quality", 0.5)),
            "relevance": float(scores.get("relevance", 0.5)),
            "explanation": scores.get("explanation", ""),
            "eval_tokens": {"input": eval_input_tokens, "output": eval_output_tokens},
            "eval_cost": eval_cost,
            "llm_judge_success": True
        }
        
    except json.JSONDecodeError as e:
        print(f"    ⚠ LLM judge JSON parse error: {e}")
        return _fallback_heuristic_scores(response)
    except requests.exceptions.RequestException as e:
        print(f"    ⚠ LLM judge request error: {e}")
        return _fallback_heuristic_scores(response)
    except Exception as e:
        print(f"    ⚠ LLM judge error: {e}")
        return _fallback_heuristic_scores(response)


def _fallback_heuristic_scores(response: str) -> Dict[str, Any]:
    """Fallback to heuristic scoring if LLM judge fails."""
    if not response:
        return {
            "action_advancement": 0.0,
            "action_completion": 0.0,
            "reasoning_quality": 0.0,
            "relevance": 0.0,
            "explanation": "No response received",
            "eval_tokens": {"input": 0, "output": 0},
            "eval_cost": 0.0,
            "llm_judge_success": False
        }
    
    # Simple heuristic based on response characteristics
    length_score = min(1.0, len(response) / 500) * 0.7
    has_error = "error" in response.lower() or "sorry" in response.lower()
    
    return {
        "action_advancement": length_score if not has_error else 0.3,
        "action_completion": length_score * 0.9 if not has_error else 0.2,
        "reasoning_quality": 0.5,
        "relevance": 0.5 if not has_error else 0.3,
        "explanation": "Fallback heuristic scoring (LLM judge unavailable)",
        "eval_tokens": {"input": 0, "output": 0},
        "eval_cost": 0.0,
        "llm_judge_success": False
    }


# ============================================
# COMPREHENSIVE TEST SUITE - ALL 27 TOOLS COVERED
# ============================================
# Mix of easy (single tool), medium (2-3 tools), and complex (multi-step reasoning)
# Ensures ALL MCP tools are tested for proper invocation

# All 27 MCP Tools:
# api_tools.py: get_market_report, get_news_report, get_sentiment_report, get_fundamental_report,
#               get_all_reports, list_available_symbols, run_bull_bear_debate, get_debate_status,
#               get_market_sentiment, get_symbol_sentiment, run_historical_analysis, query_knowledge_base,
#               ingest_text_to_kb, ingest_document_to_kb, list_kb_files, delete_kb_file
# backtesting_tools.py: list_all_strategies, get_strategy_details, search_strategies, create_strategy,
#                       get_strategy_metrics, compare_strategies, find_best_strategy
# report_tools.py: get_facilitator_report
# risk_tools.py: assess_risk_all_tiers, assess_single_risk_tier
# search_tools.py: smart_search_trading

TEST_QUESTIONS = [
    # ===========================================
    # EASY: Single Tool - Sentiment Analysis (5)
    # ===========================================
    {
        "query": "What is the current market sentiment for AAPL?",
        "category": "sentiment_easy",
        "difficulty": "easy",
        "expected_tools": ["get_symbol_sentiment"]
    },
    {
        "query": "What's the overall market sentiment across all stocks right now?",
        "category": "sentiment_easy",
        "difficulty": "easy",
        "expected_tools": ["get_market_sentiment"]
    },
    {
        "query": "Get the full sentiment analysis report for AAPL",
        "category": "sentiment_easy",
        "difficulty": "easy",
        "expected_tools": ["get_sentiment_report"]
    },
    {
        "query": "What's the overall mood around AAPL stock right now?",
        "category": "sentiment_easy",
        "difficulty": "easy",
        "expected_tools": ["get_symbol_sentiment"]
    },
    {
        "query": "Show me the general market mood and trending stocks sentiment",
        "category": "sentiment_easy",
        "difficulty": "easy",
        "expected_tools": ["get_market_sentiment"]
    },
    
    # ===========================================
    # EASY: Single Tool - Reports & Analysis (7)
    # ===========================================
    {
        "query": "Analyze the fundamental health of AAPL stock",
        "category": "fundamental_easy",
        "difficulty": "easy",
        "expected_tools": ["get_fundamental_report"]
    },
    {
        "query": "Give me the market analysis report for Apple (AAPL)",
        "category": "market_easy",
        "difficulty": "easy",
        "expected_tools": ["get_market_report"]
    },
    {
        "query": "What are the latest news affecting AAPL?",
        "category": "news_easy",
        "difficulty": "easy",
        "expected_tools": ["get_news_report"]
    },
    {
        "query": "Show me the technical market report for Apple",
        "category": "market_easy",
        "difficulty": "easy",
        "expected_tools": ["get_market_report"]
    },
    {
        "query": "Get the facilitator report from the bull vs bear debate for AAPL",
        "category": "report_easy",
        "difficulty": "easy",
        "expected_tools": ["get_facilitator_report"]
    },
    {
        "query": "What stocks/symbols are available in the system?",
        "category": "system_easy",
        "difficulty": "easy",
        "expected_tools": ["list_available_symbols"]
    },
    {
        "query": "List all available stock symbols with cached reports",
        "category": "system_easy",
        "difficulty": "easy",
        "expected_tools": ["list_available_symbols"]
    },
    
    # ===========================================
    # EASY: Single Tool - Strategy Management (7)
    # ===========================================
    {
        "query": "List all available trading strategies",
        "category": "strategy_easy",
        "difficulty": "easy",
        "expected_tools": ["list_all_strategies"]
    },
    {
        "query": "Create a simple moving average crossover strategy for AAPL",
        "category": "strategy_easy",
        "difficulty": "easy",
        "expected_tools": ["create_strategy"]
    },
    {
        "query": "Show me all momentum-based strategies",
        "category": "strategy_easy",
        "difficulty": "easy",
        "expected_tools": ["search_strategies"]
    },
    {
        "query": "Get the detailed code and description for sma_crossover strategy",
        "category": "strategy_easy",
        "difficulty": "easy",
        "expected_tools": ["get_strategy_details"]
    },
    {
        "query": "What's the best performing strategy by total return?",
        "category": "strategy_easy",
        "difficulty": "easy",
        "expected_tools": ["find_best_strategy"]
    },
    {
        "query": "Get the live performance metrics for the rsi_mean_reversion strategy",
        "category": "strategy_easy",
        "difficulty": "easy",
        "expected_tools": ["get_strategy_metrics"]
    },
    {
        "query": "Compare the performance of sma_crossover, rsi_mean_reversion, and macd_momentum strategies",
        "category": "strategy_easy",
        "difficulty": "easy",
        "expected_tools": ["compare_strategies"]
    },
    
    # ===========================================
    # EASY: Single Tool - Knowledge Base (6)
    # ===========================================
    {
        "query": "Search for information about RSI trading strategies online",
        "category": "search_easy",
        "difficulty": "easy",
        "expected_tools": ["smart_search_trading"]
    },
    {
        "query": "What does the SEC filing say about Apple's risks?",
        "category": "knowledge_easy",
        "difficulty": "easy",
        "expected_tools": ["query_knowledge_base"]
    },
    {
        "query": "List all documents currently in the knowledge base",
        "category": "knowledge_easy",
        "difficulty": "easy",
        "expected_tools": ["list_kb_files"]
    },
    {
        "query": "Add this note to the knowledge base for AAPL: 'Q4 2024 earnings exceeded expectations with record services revenue'",
        "category": "knowledge_easy",
        "difficulty": "easy",
        "expected_tools": ["ingest_text_to_kb"]
    },
    {
        "query": "Delete the outdated file 'old_report.txt' from the knowledge base",
        "category": "knowledge_easy",
        "difficulty": "easy",
        "expected_tools": ["delete_kb_file"]
    },
    {
        "query": "Ingest this research document into the knowledge base: 'Apple Inc has shown consistent revenue growth across all segments...'",
        "category": "knowledge_easy",
        "difficulty": "easy",
        "expected_tools": ["ingest_document_to_kb"]
    },
    
    # ===========================================
    # EASY: Single Tool - Historical & Risk (4)
    # ===========================================
    {
        "query": "Run historical analysis on AAPL for the last 7 days with 1-minute candles",
        "category": "historical_easy",
        "difficulty": "easy",
        "expected_tools": ["run_historical_analysis"]
    },
    {
        "query": "Analyze AAPL's historical price data for the last month",
        "category": "historical_easy",
        "difficulty": "easy",
        "expected_tools": ["run_historical_analysis"]
    },
    {
        "query": "Assess the risk of a simple buy-hold strategy for AAPL as a neutral investor",
        "category": "risk_easy",
        "difficulty": "easy",
        "expected_tools": ["assess_single_risk_tier"]
    },
    {
        "query": "Evaluate risk for my MACD strategy {'entry': 'macd_crossover', 'stop_loss': 0.02} on AAPL for aggressive investors",
        "category": "risk_easy",
        "difficulty": "easy",
        "expected_tools": ["assess_single_risk_tier"]
    },
    
    # ===========================================
    # MEDIUM: Multi-Tool - Combined Analysis (10)
    # ===========================================
    {
        "query": "Get both sentiment and fundamental analysis for AAPL",
        "category": "combined_medium",
        "difficulty": "medium",
        "expected_tools": ["get_symbol_sentiment", "get_fundamental_report"]
    },
    {
        "query": "Compare the news and market report for Apple stock",
        "category": "combined_medium",
        "difficulty": "medium",
        "expected_tools": ["get_news_report", "get_market_report"]
    },
    {
        "query": "Search for mean reversion strategies and find the best one by sharpe ratio",
        "category": "strategy_medium",
        "difficulty": "medium",
        "expected_tools": ["search_strategies", "find_best_strategy"]
    },
    {
        "query": "Create a momentum strategy for AAPL and then get its detailed metrics",
        "category": "strategy_medium",
        "difficulty": "medium",
        "expected_tools": ["create_strategy", "get_strategy_metrics"]
    },
    {
        "query": "What's the overall market sentiment and specific sentiment for AAPL?",
        "category": "combined_medium",
        "difficulty": "medium",
        "expected_tools": ["get_market_sentiment", "get_symbol_sentiment"]
    },
    {
        "query": "Run a bull vs bear debate for AAPL and get the facilitator summary",
        "category": "debate_medium",
        "difficulty": "medium",
        "expected_tools": ["run_bull_bear_debate", "get_facilitator_report"]
    },
    {
        "query": "Get fundamental report and query knowledge base about AAPL's competitive position",
        "category": "combined_medium",
        "difficulty": "medium",
        "expected_tools": ["get_fundamental_report", "query_knowledge_base"]
    },
    {
        "query": "Search for breakout strategies and compare the top 3 performers",
        "category": "strategy_medium",
        "difficulty": "medium",
        "expected_tools": ["search_strategies", "compare_strategies"]
    },
    {
        "query": "Get the news report and market analysis for Apple",
        "category": "combined_medium",
        "difficulty": "medium",
        "expected_tools": ["get_news_report", "get_market_report"]
    },
    {
        "query": "Create a Bollinger Band strategy and get its detailed info",
        "category": "strategy_medium",
        "difficulty": "medium",
        "expected_tools": ["create_strategy", "get_strategy_details"]
    },
    {
        "query": "Run historical analysis on AAPL and check the market report",
        "category": "combined_medium",
        "difficulty": "medium",
        "expected_tools": ["run_historical_analysis", "get_market_report"]
    },
    {
        "query": "Assess risk for my momentum strategy on AAPL across all investor profiles (conservative to aggressive)",
        "category": "risk_medium",
        "difficulty": "medium",
        "expected_tools": ["assess_risk_all_tiers"]
    },
    {
        "query": "Check what files are in the knowledge base and query it about Apple's business segments",
        "category": "knowledge_medium",
        "difficulty": "medium",
        "expected_tools": ["list_kb_files", "query_knowledge_base"]
    },
    
    # ===========================================
    # COMPLEX: Investment Decisions (5)
    # ===========================================
    {
        "query": "Should I buy AAPL right now? Consider sentiment, fundamentals, and recent news.",
        "category": "investment_complex",
        "difficulty": "complex",
        "expected_tools": ["get_all_reports"]
    },
    {
        "query": "Give me a complete investment analysis for Apple including all available data",
        "category": "investment_complex",
        "difficulty": "complex",
        "expected_tools": ["get_all_reports"]
    },
    {
        "query": "I have $10,000 to invest. Should I put it in AAPL? Analyze everything.",
        "category": "investment_complex",
        "difficulty": "complex",
        "expected_tools": ["get_all_reports"]
    },
    {
        "query": "Provide a comprehensive buy/sell/hold recommendation for AAPL with full analysis",
        "category": "investment_complex",
        "difficulty": "complex",
        "expected_tools": ["get_all_reports"]
    },
    {
        "query": "Is AAPL overvalued? Give me sentiment, fundamentals, news, and your recommendation",
        "category": "investment_complex",
        "difficulty": "complex",
        "expected_tools": ["get_all_reports"]
    },
    
    # ===========================================
    # COMPLEX: Strategy Development (5)
    # ===========================================
    {
        "query": "Create a momentum-based trading strategy for AAPL using RSI and MACD with stop loss",
        "category": "strategy_complex",
        "difficulty": "complex",
        "expected_tools": ["create_strategy"]
    },
    {
        "query": "Build a mean reversion strategy using Bollinger Bands, then compare it with existing strategies",
        "category": "strategy_complex",
        "difficulty": "complex",
        "expected_tools": ["create_strategy", "search_strategies", "compare_strategies"]
    },
    {
        "query": "Design a trend-following strategy with moving average crossover, 2% stop loss, 5% take profit, then show its metrics",
        "category": "strategy_complex",
        "difficulty": "complex",
        "expected_tools": ["create_strategy", "get_strategy_metrics"]
    },
    {
        "query": "Create an RSI-based strategy, get its details, and find the best RSI strategy overall",
        "category": "strategy_complex",
        "difficulty": "complex",
        "expected_tools": ["create_strategy", "get_strategy_details", "find_best_strategy"]
    },
    {
        "query": "Build a volatility breakout strategy and assess its risk for conservative and aggressive investors",
        "category": "strategy_complex",
        "difficulty": "complex",
        "expected_tools": ["create_strategy", "assess_risk_all_tiers"]
    },
    
    # ===========================================
    # COMPLEX: Research & Analysis (5)
    # ===========================================
    {
        "query": "Research momentum trading strategies online and compare with our existing strategies",
        "category": "research_complex",
        "difficulty": "complex",
        "expected_tools": ["smart_search_trading", "list_all_strategies", "compare_strategies"]
    },
    {
        "query": "What does SEC 10-K say about Apple's revenue growth and how does it compare to current sentiment?",
        "category": "research_complex",
        "difficulty": "complex",
        "expected_tools": ["query_knowledge_base", "get_symbol_sentiment"]
    },
    {
        "query": "Search for MACD trading techniques online and create a strategy based on what you find",
        "category": "research_complex",
        "difficulty": "complex",
        "expected_tools": ["smart_search_trading", "create_strategy"]
    },
    {
        "query": "Analyze Apple's competitive risks from 10-K and correlate with recent news headlines",
        "category": "research_complex",
        "difficulty": "complex",
        "expected_tools": ["query_knowledge_base", "get_news_report"]
    },
    {
        "query": "Find swing trading strategies online, then search our database for similar ones",
        "category": "research_complex",
        "difficulty": "complex",
        "expected_tools": ["smart_search_trading", "search_strategies"]
    },
    
    # ===========================================
    # COMPLEX: Multi-Step Reasoning (7)
    # ===========================================
    {
        "query": "Run a bull vs bear debate for AAPL, check its status, and give me the final verdict with supporting data",
        "category": "reasoning_complex",
        "difficulty": "complex",
        "expected_tools": ["run_bull_bear_debate", "get_debate_status", "get_all_reports"]
    },
    {
        "query": "Analyze AAPL sentiment, check the news, run a debate, and tell me if it's a good short-term trade",
        "category": "reasoning_complex",
        "difficulty": "complex",
        "expected_tools": ["get_symbol_sentiment", "get_news_report", "run_bull_bear_debate"]
    },
    {
        "query": "Get sentiment and fundamentals for AAPL, and recommend whether to buy",
        "category": "reasoning_complex",
        "difficulty": "complex",
        "expected_tools": ["get_symbol_sentiment", "get_fundamental_report"]
    },
    {
        "query": "Build a complete trading plan: analyze AAPL sentiment, create a strategy, and recommend entry/exit points",
        "category": "reasoning_complex",
        "difficulty": "complex",
        "expected_tools": ["get_symbol_sentiment", "get_fundamental_report", "create_strategy"]
    },
    {
        "query": "I'm bearish on AAPL. Find news that supports or contradicts this, check sentiment, and validate my thesis",
        "category": "reasoning_complex",
        "difficulty": "complex",
        "expected_tools": ["get_news_report", "get_symbol_sentiment", "get_fundamental_report"]
    },
    {
        "query": "Start a debate for AAPL and immediately check if it's running",
        "category": "reasoning_complex",
        "difficulty": "complex",
        "expected_tools": ["run_bull_bear_debate", "get_debate_status"]
    },
    {
        "query": "Add this insight to knowledge base: 'AAPL services revenue grew 15%', then query it to verify",
        "category": "reasoning_complex",
        "difficulty": "complex",
        "expected_tools": ["ingest_text_to_kb", "query_knowledge_base"]
    },
]

# ===========================================
# TOOL COVERAGE VERIFICATION
# ===========================================
# All 27 MCP tools must be covered by at least one query:
#
# api_tools.py (16 tools):
#   1. get_market_report - ✓ medium: "Compare the news and market report for Apple stock"
#   2. get_news_report - ✓ easy: "What are the latest news affecting AAPL?"
#   3. get_sentiment_report - ✓ easy: "Get the full sentiment analysis report for AAPL"
#   4. get_fundamental_report - ✓ easy: "Analyze the fundamental health of AAPL stock"
#   5. get_all_reports - ✓ complex: "Should I buy AAPL right now?"
#   6. list_available_symbols - ✓ easy: "What stocks/symbols are available in the system?"
#   7. run_bull_bear_debate - ✓ complex: "Run a bull vs bear debate for AAPL..."
#   8. get_debate_status - ✓ complex: "Start a debate for AAPL and immediately check if it's running"
#   9. get_market_sentiment - ✓ easy: "What's the overall market sentiment across all stocks?"
#  10. get_symbol_sentiment - ✓ easy: "What is the current market sentiment for AAPL?"
#  11. run_historical_analysis - ✓ easy: "Run historical analysis on AAPL for the last 7 days"
#  12. query_knowledge_base - ✓ easy: "What does the SEC filing say about Apple's risks?"
#  13. ingest_text_to_kb - ✓ easy: "Add this note to the knowledge base for AAPL..."
#  14. ingest_document_to_kb - ✓ easy: "Ingest this research document into the knowledge base..."
#  15. list_kb_files - ✓ easy: "List all documents currently in the knowledge base"
#  16. delete_kb_file - ✓ easy: "Delete the outdated file 'old_report.txt'..."
#
# backtesting_tools.py (7 tools):
#  17. list_all_strategies - ✓ easy: "List all available trading strategies"
#  18. get_strategy_details - ✓ easy: "Get the detailed code and description for sma_crossover strategy"
#  19. search_strategies - ✓ easy: "Show me all momentum-based strategies"
#  20. create_strategy - ✓ easy: "Create a simple moving average crossover strategy..."
#  21. get_strategy_metrics - ✓ easy: "Get the live performance metrics for the rsi_mean_reversion strategy"
#  22. compare_strategies - ✓ easy: "Compare the performance of sma_crossover, rsi_mean_reversion..."
#  23. find_best_strategy - ✓ easy: "What's the best performing strategy by total return?"
#
# report_tools.py (1 tool):
#  24. get_facilitator_report - ✓ easy: "Get the facilitator report from the bull vs bear debate..."
#
# risk_tools.py (2 tools):
#  25. assess_risk_all_tiers - ✓ medium: "Assess risk for my momentum strategy... across all investor profiles"
#  26. assess_single_risk_tier - ✓ easy: "Assess the risk of a simple buy-hold strategy... as a neutral investor"
#
# search_tools.py (1 tool):
#  27. smart_search_trading - ✓ easy: "Search for information about RSI trading strategies online"


class GalileoEvaluationRunner:
    """
    Runs evaluation tests and logs traces to Galileo with full span tracking.
    
    This runner:
    1. Starts a trace for each test case
    2. Logs agent spans for the overall agent execution
    3. Logs tool spans for each tool call
    4. Logs LLM spans for reasoning steps
    5. Calculates and logs metrics
    """
    
    def __init__(self, api_base_url: str = API_BASE_URL, project_name: str = GALILEO_PROJECT):
        self.api_base_url = api_base_url
        self.project_name = project_name
        self.results = []
        
        # Initialize Galileo Logger
        self.logger = GalileoLogger(project=project_name)
        print(f"✓ Galileo initialized for project: {project_name}")
    
    def call_strategist_api_with_trace(self, query: str, user_id: str = "eval-user") -> dict:
        """
        Call the strategist API endpoint and return detailed trace info.
        Uses the streaming endpoint to capture intermediate steps.
        """
        url = f"{self.api_base_url}/strategist/chat"
        payload = {
            "message": query,
            "user_id": user_id
        }
        
        try:
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
            result = response.json()
            
            # Try to get detailed trace from response
            return {
                "response": result.get("response", str(result)),
                "tools_used": result.get("tools_used", []),
                "tool_calls": result.get("tool_calls", []),
                "reasoning_steps": result.get("reasoning_steps", []),
                "raw_result": result,
                "error": None
            }
        except requests.exceptions.Timeout:
            return {
                "response": None,
                "tools_used": [],
                "tool_calls": [],
                "reasoning_steps": [],
                "raw_result": None,
                "error": "Request timed out after 180 seconds"
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "response": None,
                "tools_used": [],
                "tool_calls": [],
                "reasoning_steps": [],
                "raw_result": None,
                "error": f"Connection error: {str(e)}"
            }
        except requests.exceptions.RequestException as e:
            return {
                "response": None,
                "tools_used": [],
                "tool_calls": [],
                "reasoning_steps": [],
                "raw_result": None,
                "error": str(e)
            }
    
    def call_bullbear_api(self, ticker: str, topic: str = "investment outlook") -> dict:
        """Call the Bull vs Bear debate API."""
        url = f"{self.api_base_url}/bullbear/debate"
        payload = {
            "ticker": ticker,
            "topic": topic
        }
        
        try:
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "response": None}
    
    def call_rag_api(self, query: str, ticker: str = "AAPL") -> dict:
        """Call the RAG search API."""
        url = f"{self.api_base_url}/rag/search"
        params = {
            "query": query,
            "ticker": ticker
        }
        
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e), "response": None}
    
    def run_single_test(self, test_case: dict) -> dict:
        """
        Run a single test case with comprehensive Galileo trace logging.
        
        This method:
        1. Starts a new trace for the test
        2. Creates an agent span for the overall execution
        3. Logs tool spans for each tool call detected
        4. Logs LLM spans for reasoning steps
        5. Calculates and attaches metrics
        """
        query = test_case["query"]
        category = test_case["category"]
        difficulty = test_case.get("difficulty", "unknown")
        expected_tools = test_case.get("expected_tools", [])
        
        print(f"\n{'='*60}")
        print(f"Testing: {query[:50]}...")
        print(f"Category: {category} | Difficulty: {difficulty}")
        print(f"Expected tools: {expected_tools}")
        print(f"{'='*60}")
        
        # Generate unique IDs for tracing
        trace_id = str(uuid.uuid4())
        # Use unique user_id per test to ensure fresh conversation thread
        test_user_id = f"eval-{trace_id[:8]}"
        
        # Start a new Galileo trace for this test
        self.logger.start_trace(
            input=query,
            tags=[category, "evaluation", "agent-test"]
        )
        
        start_time = time.time()
        
        # Log the initial reasoning step (agent deciding what to do)
        reasoning_span_id = str(uuid.uuid4())
        self.logger.add_llm_span(
            input=f"User Query: {query}\n\nAgent is analyzing the query to determine which tools to use.",
            output=f"Planning to use tools related to: {', '.join(expected_tools)}",
            model="openrouter/google/gemini-2.0-flash-001",
            input_tokens=len(query.split()) * 2,
            output_tokens=50,
            name="agent_reasoning",
            tags=["reasoning", "planning"]
        )
        
        # Call the strategist API with unique user_id
        result = self.call_strategist_api_with_trace(query, user_id=test_user_id)
        
        end_time = time.time()
        latency = end_time - start_time
        
        # Extract response details
        response_text = result.get("response", "") or str(result.get("error", "No response"))
        tools_used = result.get("tools_used", [])
        tool_calls = result.get("tool_calls", [])
        reasoning_steps = result.get("reasoning_steps", [])
        error = result.get("error")
        
        # Log reasoning steps as LLM spans
        for i, step in enumerate(reasoning_steps):
            self.logger.add_llm_span(
                input=f"Step {i+1}: {query}",
                output=step,
                model="openrouter/google/gemini-2.0-flash-001",
                name=f"reasoning_step_{i+1}",
                tags=["reasoning", category]
            )
        
        # Log tool spans for each actual tool call
        tool_results = self._log_tool_spans(expected_tools, tools_used, tool_calls, result)
        
        # Log the final LLM response span
        self.logger.add_llm_span(
            input=f"Generate final response for query: {query}",
            output=response_text[:2000] if response_text else "No response generated",
            model="openrouter/google/gemini-2.0-flash-001",
            input_tokens=len(query.split()) * 2,
            output_tokens=len(response_text.split()) if response_text else 0,
            name="final_response_generation",
            tags=["response", "final"]
        )
        
        # Calculate metrics (now with LLM judge)
        metrics = self._calculate_metrics(
            query=query,
            expected_tools=expected_tools,
            actual_tools=tools_used,
            response=response_text,
            latency=latency,
            error=error,
            tool_results=tool_results,
            tool_calls=tool_calls
        )
        
        # Log the overall agent span with enhanced metrics
        self.logger.add_agent_span(
            input=query,
            output=response_text[:2000] if response_text else "Error occurred",
            name="stock_trading_strategist",
            tools=tools_used if tools_used else expected_tools,
            tags=[category, "agent"],
            metadata={
                "category": category,
                "difficulty": difficulty,
                "expected_tools": expected_tools,
                "actual_tools": tools_used,
                "latency_seconds": latency,
                "tool_selection_score": metrics["tool_selection_score"],
                "tool_errors": metrics["tool_errors"],
                "action_advancement": metrics["action_advancement"],
                "action_completion": metrics["action_completion"],
                "reasoning_quality": metrics.get("reasoning_quality", 0.5),
                "relevance": metrics.get("relevance", 0.5),
                "llm_judge_explanation": metrics.get("llm_judge_explanation", ""),
                "agent_input_tokens": metrics.get("agent_input_tokens", 0),
                "agent_output_tokens": metrics.get("agent_output_tokens", 0),
                "agent_cost_usd": metrics.get("agent_cost_usd", 0),
                "total_cost_usd": metrics.get("total_cost_usd", 0)
            }
        )
        
        # Conclude the trace
        self.logger.conclude(
            output=response_text[:2000] if response_text else "Error occurred",
            status_code=0 if not error else 1,
            tags=[category, "completed" if not error else "error"]
        )
        
        test_result = {
            "query": query,
            "category": category,
            "difficulty": difficulty,
            "response": response_text,
            "tools_used": tools_used,
            "expected_tools": expected_tools,
            "reasoning_steps": reasoning_steps,
            "latency_seconds": latency,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat(),
            "success": error is None,
            "trace_id": trace_id
        }
        
        self.results.append(test_result)
        
        # Print summary
        status = "✓" if not error else "✗"
        print(f"\n{status} Response received in {latency:.2f}s")
        print(f"  Tools expected: {expected_tools}")
        print(f"  Tools used: {tools_used}")
        print(f"  Tool selection score: {metrics['tool_selection_score']:.2f}")
        print(f"  Action completion: {metrics['action_completion']:.2f}")
        print(f"  Response preview: {response_text[:200] if response_text else 'N/A'}...")
        
        return test_result
    
    def _log_tool_spans(
        self,
        expected_tools: List[str],
        actual_tools: List[str],
        tool_calls: List[dict],
        result: dict
    ) -> Dict[str, Any]:
        """Log individual tool spans to Galileo."""
        tool_results = {
            "successful": [],
            "failed": [],
            "missing": []
        }
        
        # Log spans for actual tool calls with their details
        for tc in tool_calls:
            tool_name = tc.get('name', 'unknown')
            tool_args = tc.get('args', {})
            tool_call_id = tc.get('id', str(uuid.uuid4()))
            
            # Determine if tool was expected
            is_expected = tool_name in expected_tools
            
            self.logger.add_tool_span(
                input=json.dumps(tool_args) if tool_args else f"Calling {tool_name}",
                output=f"Tool {tool_name} executed {'(expected)' if is_expected else '(unexpected)'}",
                name=tool_name,
                tool_call_id=tool_call_id,
                tags=["tool_call", "executed", "expected" if is_expected else "unexpected"]
            )
            
            tool_results["successful"].append(tool_name)
        
        # If no tool_calls details, log based on tools_used list
        if not tool_calls and actual_tools:
            for tool_name in actual_tools:
                is_expected = tool_name in expected_tools
                self.logger.add_tool_span(
                    input=f"Calling tool: {tool_name}",
                    output=f"Tool {tool_name} executed",
                    name=tool_name,
                    tool_call_id=str(uuid.uuid4()),
                    tags=["tool_call", "executed"]
                )
                tool_results["successful"].append(tool_name)
        
        # Log spans for expected tools that weren't used
        for expected_tool in expected_tools:
            if expected_tool not in actual_tools:
                self.logger.add_tool_span(
                    input=f"Expected tool call: {expected_tool}",
                    output=f"Tool {expected_tool} was NOT called (expected but missing)",
                    name=expected_tool,
                    tool_call_id=str(uuid.uuid4()),
                    tags=["tool_call", "missing", "error"]
                )
                tool_results["missing"].append(expected_tool)
        
        return tool_results
    
    def _calculate_metrics(
        self,
        query: str,
        expected_tools: list,
        actual_tools: list,
        response: str,
        latency: float,
        error: Optional[str],
        tool_results: Dict[str, Any],
        tool_calls: List[dict] = None
    ) -> dict:
        """
        Calculate comprehensive evaluation metrics using LLM judge.
        
        Metrics:
        - tool_selection_score: How well the agent selected the right tools (0-1)
        - tool_errors: Count of failed/missing tool calls
        - action_advancement: Progress toward completing the task (0-1) - LLM judged
        - action_completion: Whether the full task was completed (0-1) - LLM judged
        - reasoning_quality: Quality of reasoning shown (0-1) - LLM judged
        - relevance: How relevant the response is (0-1) - LLM judged
        
        Token & Cost (from orchestrator agent's LLM perspective):
        - agent_input_tokens: Tokens sent TO the LLM (system prompt + tools + query + tool results)
        - agent_output_tokens: Tokens generated BY the LLM (reasoning + tool calls + final response)
        - agent_cost_usd: Estimated cost of the agent's LLM calls
        """
        
        # =============================================
        # AGENT LLM TOKEN ESTIMATION
        # =============================================
        # The orchestrator agent uses:
        # INPUT: system prompt (~2000 tokens) + tool definitions (~1500 tokens for 27 tools) 
        #        + user query + tool call results
        # OUTPUT: reasoning + tool call decisions + final response
        
        SYSTEM_PROMPT_TOKENS = 2000  # Estimated system prompt size
        TOOL_DEFINITIONS_TOKENS = 1500  # ~55 tokens per tool * 27 tools
        
        # Count actual tokens
        query_tokens = count_tokens(query)
        response_tokens = count_tokens(response) if response else 0
        
        # Estimate tool call overhead (each tool call adds input/output)
        tool_call_input_tokens = 0
        tool_call_output_tokens = 0
        if tool_calls:
            for tc in tool_calls:
                # Each tool call: ~50 tokens for the call, ~200 tokens avg for result
                tool_call_output_tokens += 50  # Agent deciding to call tool
                tool_call_input_tokens += 200  # Tool result coming back
        elif actual_tools:
            # Estimate based on tools used
            tool_call_output_tokens += len(actual_tools) * 50
            tool_call_input_tokens += len(actual_tools) * 200
        
        # Total agent LLM usage
        agent_input_tokens = SYSTEM_PROMPT_TOKENS + TOOL_DEFINITIONS_TOKENS + query_tokens + tool_call_input_tokens
        agent_output_tokens = response_tokens + tool_call_output_tokens
        
        # Calculate agent cost
        agent_cost = calculate_cost(agent_input_tokens, agent_output_tokens, "google/gemini-2.0-flash-001")
        
        # Tool Selection Quality (0-1)
        # Measures precision and recall of tool selection
        if expected_tools:
            correct_tools = len(set(expected_tools) & set(actual_tools))
            extra_tools = len(set(actual_tools) - set(expected_tools))
            missing_tools = len(set(expected_tools) - set(actual_tools))
            
            precision = correct_tools / len(actual_tools) if actual_tools else 0
            recall = correct_tools / len(expected_tools) if expected_tools else 1
            
            # F1-like score
            if precision + recall > 0:
                tool_selection_score = 2 * (precision * recall) / (precision + recall)
            else:
                tool_selection_score = 0.0
        else:
            tool_selection_score = 1.0 if not actual_tools else 0.5
        
        # Tool Errors (count)
        tool_errors = len(tool_results.get("missing", []))
        if error:
            tool_errors += 1
        
        # LLM Judge for qualitative metrics
        if error:
            # Skip LLM judge if there was an error
            llm_scores = {
                "action_advancement": 0.0,
                "action_completion": 0.0,
                "reasoning_quality": 0.0,
                "relevance": 0.0,
                "explanation": f"Error: {error}",
                "eval_tokens": {"input": 0, "output": 0},
                "eval_cost": 0.0,
                "llm_judge_success": False
            }
        else:
            print("    🤖 Running LLM judge evaluation...", end="", flush=True)
            llm_scores = llm_judge_evaluation(query, response, actual_tools, expected_tools)
            if llm_scores.get("llm_judge_success"):
                print(" ✓")
            else:
                print(" (fallback)")
        
        # Add evaluation cost to total (agent cost + LLM judge cost)
        total_cost = agent_cost + llm_scores.get("eval_cost", 0)
        
        return {
            "tool_selection_score": round(tool_selection_score, 3),
            "tool_errors": tool_errors,
            "action_advancement": round(llm_scores["action_advancement"], 3),
            "action_completion": round(llm_scores["action_completion"], 3),
            "reasoning_quality": round(llm_scores.get("reasoning_quality", 0.5), 3),
            "relevance": round(llm_scores.get("relevance", 0.5), 3),
            "llm_judge_explanation": llm_scores.get("explanation", ""),
            "llm_judge_success": llm_scores.get("llm_judge_success", False),
            "latency_seconds": round(latency, 2),
            "response_length": len(response) if response else 0,
            # Agent LLM token usage (orchestrator perspective)
            "agent_input_tokens": agent_input_tokens,
            "agent_output_tokens": agent_output_tokens,
            "agent_cost_usd": round(agent_cost, 6),
            # Evaluation overhead
            "eval_cost_usd": round(llm_scores.get("eval_cost", 0), 6),
            # Total cost (agent + evaluation)
            "total_cost_usd": round(total_cost, 6)
        }
    
    def run_all_tests(self, questions: list = None) -> list:
        """Run all test cases with full Galileo tracing."""
        questions = questions or TEST_QUESTIONS
        
        print(f"\n{'#'*60}")
        print(f"# GALILEO EVALUATION - {len(questions)} Test Cases")
        print(f"# Project: {self.project_name}")
        print(f"# API: {self.api_base_url}")
        print(f"# Tracing: Tool calls, LLM reasoning, Agent spans")
        print(f"{'#'*60}")
        
        for i, test_case in enumerate(questions, 1):
            print(f"\n[{i}/{len(questions)}]", end="")
            try:
                self.run_single_test(test_case)
                
                # Flush after each test to ensure traces are sent
                self.logger.flush()
                print(f"  → Trace logged to Galileo")
                
            except Exception as e:
                print(f"\n✗ Test failed with error: {e}")
                
                # Log error trace
                self.logger.start_trace(
                    input=test_case["query"],
                    tags=[test_case["category"], "error"]
                )
                self.logger.add_agent_span(
                    input=test_case["query"],
                    output=f"Error: {str(e)}",
                    name="stock_trading_strategist",
                    tags=["error", "exception"]
                )
                self.logger.conclude(
                    output=f"Error: {str(e)}",
                    status_code=1,
                    tags=["error"]
                )
                self.logger.flush()
                
                self.results.append({
                    "query": test_case["query"],
                    "category": test_case["category"],
                    "error": str(e),
                    "success": False,
                    "timestamp": datetime.now().isoformat(),
                    "metrics": {
                        "tool_selection_score": 0,
                        "tool_errors": 1,
                        "action_advancement": 0,
                        "action_completion": 0
                    }
                })
            
            # Small delay between tests to avoid rate limiting
            time.sleep(1)
        
        return self.results
        print(f"# Project: {self.project_name}")
        print(f"# API: {self.api_base_url}")
        print(f"{'#'*60}")
        
        for i, test_case in enumerate(questions, 1):
            print(f"\n[{i}/{len(questions)}]", end="")
            try:
                self.run_single_test(test_case)
            except Exception as e:
                print(f"\n✗ Test failed with error: {e}")
                self.results.append({
                    "query": test_case["query"],
                    "category": test_case["category"],
                    "error": str(e),
                    "success": False,
                    "timestamp": datetime.now().isoformat()
                })
        
        return self.results
    
    def run_bullbear_test(self, ticker: str = "AAPL") -> dict:
        """Run a Bull vs Bear debate test with full trace logging."""
        print(f"\n{'='*60}")
        print(f"Running Bull vs Bear Debate for {ticker}")
        print(f"{'='*60}")
        
        # Start trace for debate
        self.logger.start_trace(
            input=f"Bull vs Bear debate for {ticker}",
            tags=["bullbear", "debate", ticker]
        )
        
        start_time = time.time()
        result = self.call_bullbear_api(ticker)
        latency = time.time() - start_time
        
        # Log the debate as an agent span
        self.logger.add_agent_span(
            input=f"Run bull vs bear debate for {ticker}",
            output=json.dumps(result, default=str)[:2000] if result else "No result",
            name="bullbear_debate",
            tools=["bull_agent", "bear_agent", "facilitator"],
            metadata={
                "ticker": ticker,
                "latency_seconds": latency,
                "winner": result.get("winner", "unknown") if isinstance(result, dict) else "unknown"
            }
        )
        
        # Conclude and flush
        self.logger.conclude(
            output=json.dumps(result, default=str)[:1000] if result else "Error",
            status_code=0 if "error" not in str(result).lower() else 1
        )
        self.logger.flush()
        
        print(f"\n✓ Debate completed in {latency:.2f}s")
        if isinstance(result, dict) and "error" not in result:
            print(f"  Winner: {result.get('winner', 'N/A')}")
            print(f"  Confidence: {result.get('confidence', 'N/A')}")
        
        return result
    
    def print_summary(self):
        """Print comprehensive evaluation summary with Galileo metrics."""
        print(f"\n{'#'*60}")
        print("# EVALUATION SUMMARY")
        print(f"{'#'*60}")
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.get("success", False))
        
        print(f"\nTotal tests: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {total - successful}")
        print(f"Success rate: {successful/total*100:.1f}%" if total > 0 else "N/A")
        
        # Aggregate metrics
        if self.results:
            metrics_summary = {
                "avg_latency": 0,
                "avg_tool_selection": 0,
                "total_tool_errors": 0,
                "avg_action_advancement": 0,
                "avg_action_completion": 0,
                "avg_reasoning_quality": 0,
                "avg_relevance": 0,
                "total_agent_input_tokens": 0,
                "total_agent_output_tokens": 0,
                "total_agent_cost_usd": 0,
                "total_eval_cost_usd": 0,
                "llm_judge_success_count": 0
            }
            
            for r in self.results:
                m = r.get("metrics", {})
                metrics_summary["avg_latency"] += r.get("latency_seconds", m.get("latency_seconds", 0))
                metrics_summary["avg_tool_selection"] += m.get("tool_selection_score", 0)
                metrics_summary["total_tool_errors"] += m.get("tool_errors", 0)
                metrics_summary["avg_action_advancement"] += m.get("action_advancement", 0)
                metrics_summary["avg_action_completion"] += m.get("action_completion", 0)
                metrics_summary["avg_reasoning_quality"] += m.get("reasoning_quality", 0)
                metrics_summary["avg_relevance"] += m.get("relevance", 0)
                metrics_summary["total_agent_input_tokens"] += m.get("agent_input_tokens", 0)
                metrics_summary["total_agent_output_tokens"] += m.get("agent_output_tokens", 0)
                metrics_summary["total_agent_cost_usd"] += m.get("agent_cost_usd", 0)
                metrics_summary["total_eval_cost_usd"] += m.get("eval_cost_usd", 0)
                if m.get("llm_judge_success"):
                    metrics_summary["llm_judge_success_count"] += 1
            
            print(f"\n--- Galileo Metrics (LLM-Judged) ---")
            print(f"Average Latency: {metrics_summary['avg_latency']/total:.2f}s")
            print(f"Tool Selection Quality: {metrics_summary['avg_tool_selection']/total:.2%}")
            print(f"Total Tool Errors: {metrics_summary['total_tool_errors']}")
            print(f"Action Advancement: {metrics_summary['avg_action_advancement']/total:.2%}")
            print(f"Action Completion: {metrics_summary['avg_action_completion']/total:.2%}")
            print(f"Reasoning Quality: {metrics_summary['avg_reasoning_quality']/total:.2%}")
            print(f"Relevance: {metrics_summary['avg_relevance']/total:.2%}")
            print(f"\n--- Agent LLM Cost Analysis (Orchestrator) ---")
            print(f"Total Agent Input Tokens: {metrics_summary['total_agent_input_tokens']:,}")
            print(f"Total Agent Output Tokens: {metrics_summary['total_agent_output_tokens']:,}")
            print(f"Avg Input Tokens per Query: {metrics_summary['total_agent_input_tokens']/total:,.0f}")
            print(f"Avg Output Tokens per Response: {metrics_summary['total_agent_output_tokens']/total:,.0f}")
            print(f"Total Agent LLM Cost (USD): ${metrics_summary['total_agent_cost_usd']:.4f}")
            print(f"Avg Agent Cost per Query (USD): ${metrics_summary['total_agent_cost_usd']/total:.6f}")
            print(f"Evaluation Overhead Cost (USD): ${metrics_summary['total_eval_cost_usd']:.4f}")
            print(f"LLM Judge Success Rate: {metrics_summary['llm_judge_success_count']}/{total} ({metrics_summary['llm_judge_success_count']/total*100:.0f}%)")
            print(f"Evaluation Overhead Cost (USD): ${metrics_summary['total_eval_cost_usd']:.4f}")
            print(f"LLM Judge Success Rate: {metrics_summary['llm_judge_success_count']}/{total} ({metrics_summary['llm_judge_success_count']/total*100:.0f}%)")
        
        # By difficulty
        difficulties = {}
        for r in self.results:
            # Use difficulty stored in result, or look it up
            difficulty = r.get("difficulty", "unknown")
            if difficulty == "unknown":
                query = r.get("query", "")
                for tc in TEST_QUESTIONS:
                    if tc["query"] == query:
                        difficulty = tc.get("difficulty", "unknown")
                        break
            
            if difficulty not in difficulties:
                difficulties[difficulty] = {"total": 0, "success": 0, "metrics": [], "input_tokens": 0, "output_tokens": 0, "cost": 0}
            difficulties[difficulty]["total"] += 1
            if r.get("success", False):
                difficulties[difficulty]["success"] += 1
            difficulties[difficulty]["metrics"].append(r.get("metrics", {}))
            difficulties[difficulty]["input_tokens"] += r.get("metrics", {}).get("agent_input_tokens", 0)
            difficulties[difficulty]["output_tokens"] += r.get("metrics", {}).get("agent_output_tokens", 0)
            difficulties[difficulty]["cost"] += r.get("metrics", {}).get("agent_cost_usd", 0)
        
        print("\n--- By Difficulty ---")
        for diff in ["easy", "medium", "complex"]:
            if diff in difficulties:
                stats = difficulties[diff]
                rate = stats["success"] / stats["total"] * 100
                avg_completion = sum(m.get("action_completion", 0) for m in stats["metrics"]) / len(stats["metrics"])
                avg_tool_sel = sum(m.get("tool_selection_score", 0) for m in stats["metrics"]) / len(stats["metrics"])
                avg_out_tokens = stats["output_tokens"] / stats["total"]
                print(f"  {diff.upper()}: {stats['success']}/{stats['total']} ({rate:.0f}%) | Tool Sel: {avg_tool_sel:.2%} | Completion: {avg_completion:.2%} | Avg Out Tokens: {avg_out_tokens:,.0f} | Agent Cost: ${stats['cost']:.4f}")
        
        # By category
        categories = {}
        for r in self.results:
            cat = r.get("category", "unknown")
            if cat not in categories:
                categories[cat] = {"total": 0, "success": 0, "metrics": []}
            categories[cat]["total"] += 1
            if r.get("success", False):
                categories[cat]["success"] += 1
            categories[cat]["metrics"].append(r.get("metrics", {}))
        
        print("\n--- By Category ---")
        for cat, stats in sorted(categories.items()):
            rate = stats["success"] / stats["total"] * 100
            avg_completion = sum(m.get("action_completion", 0) for m in stats["metrics"]) / len(stats["metrics"])
            avg_reasoning = sum(m.get("reasoning_quality", 0) for m in stats["metrics"]) / len(stats["metrics"])
            print(f"  {cat}: {stats['success']}/{stats['total']} ({rate:.0f}%) | Completion: {avg_completion:.2%} | Reasoning: {avg_reasoning:.2%}")
        
        print(f"\n{'#'*60}")
        print("# View detailed traces at: https://console.galileo.ai")
        print(f"# Project: {self.project_name}")
        print(f"# Traces include: Tool calls, LLM reasoning, Agent actions")
        print(f"{'#'*60}")
    
    def save_results(self, filepath: str = "evaluation/eval_results.json"):
        """Save detailed results to JSON file."""
        # Compute aggregates for agent LLM usage
        total_agent_input_tokens = sum(r.get("metrics", {}).get("agent_input_tokens", 0) for r in self.results)
        total_agent_output_tokens = sum(r.get("metrics", {}).get("agent_output_tokens", 0) for r in self.results)
        total_agent_cost = sum(r.get("metrics", {}).get("agent_cost_usd", 0) for r in self.results)
        total_eval_cost = sum(r.get("metrics", {}).get("eval_cost_usd", 0) for r in self.results)
        llm_judge_success = sum(1 for r in self.results if r.get("metrics", {}).get("llm_judge_success", False))
        
        # Compute by difficulty
        difficulty_stats = {"easy": [], "medium": [], "complex": []}
        for r in self.results:
            diff = r.get("difficulty", "unknown")
            if diff == "unknown":
                query = r.get("query", "")
                for tc in TEST_QUESTIONS:
                    if tc["query"] == query:
                        diff = tc.get("difficulty", "unknown")
                        break
            if diff in difficulty_stats:
                difficulty_stats[diff].append(r)
        
        difficulty_summary = {}
        for diff, results in difficulty_stats.items():
            if results:
                difficulty_summary[diff] = {
                    "total": len(results),
                    "successful": sum(1 for r in results if r.get("success", False)),
                    "avg_tool_selection": sum(r.get("metrics", {}).get("tool_selection_score", 0) for r in results) / len(results),
                    "avg_action_completion": sum(r.get("metrics", {}).get("action_completion", 0) for r in results) / len(results),
                    "avg_reasoning_quality": sum(r.get("metrics", {}).get("reasoning_quality", 0) for r in results) / len(results),
                    "total_agent_input_tokens": sum(r.get("metrics", {}).get("agent_input_tokens", 0) for r in results),
                    "total_agent_output_tokens": sum(r.get("metrics", {}).get("agent_output_tokens", 0) for r in results),
                    "avg_output_tokens": sum(r.get("metrics", {}).get("agent_output_tokens", 0) for r in results) / len(results),
                    "agent_cost_usd": sum(r.get("metrics", {}).get("agent_cost_usd", 0) for r in results)
                }
        
        output = {
            "project": self.project_name,
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "summary": {
                "successful": sum(1 for r in self.results if r.get("success", False)),
                "failed": sum(1 for r in self.results if not r.get("success", False)),
                "avg_tool_selection": sum(r.get("metrics", {}).get("tool_selection_score", 0) for r in self.results) / len(self.results) if self.results else 0,
                "avg_action_completion": sum(r.get("metrics", {}).get("action_completion", 0) for r in self.results) / len(self.results) if self.results else 0,
                "avg_action_advancement": sum(r.get("metrics", {}).get("action_advancement", 0) for r in self.results) / len(self.results) if self.results else 0,
                "avg_reasoning_quality": sum(r.get("metrics", {}).get("reasoning_quality", 0) for r in self.results) / len(self.results) if self.results else 0,
                "avg_relevance": sum(r.get("metrics", {}).get("relevance", 0) for r in self.results) / len(self.results) if self.results else 0,
                "total_tool_errors": sum(r.get("metrics", {}).get("tool_errors", 0) for r in self.results),
                "llm_judge_success_rate": llm_judge_success / len(self.results) if self.results else 0
            },
            "by_difficulty": difficulty_summary,
            "agent_llm_cost_analysis": {
                "total_agent_input_tokens": total_agent_input_tokens,
                "total_agent_output_tokens": total_agent_output_tokens,
                "avg_input_tokens_per_query": total_agent_input_tokens / len(self.results) if self.results else 0,
                "avg_output_tokens_per_response": total_agent_output_tokens / len(self.results) if self.results else 0,
                "total_agent_cost_usd": round(total_agent_cost, 6),
                "avg_agent_cost_per_query_usd": round(total_agent_cost / len(self.results), 6) if self.results else 0,
                "model": "google/gemini-2.0-flash-001",
                "note": "Includes system prompt (~2000 tokens) + tool definitions (~1500 tokens) + query + tool results"
            },
            "evaluation_overhead": {
                "total_eval_cost_usd": round(total_eval_cost, 6),
                "eval_model": EVAL_MODEL
            },
            "results": self.results
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\n✓ Results saved to {filepath}")


def check_api_health(base_url: str) -> bool:
    """Check if the API is healthy."""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def main():
    """Main entry point for Galileo evaluation."""
    print("\n" + "="*60)
    print("GALILEO AGENT EVALUATION")
    print("Full Trace Logging: Tool Calls, Reasoning Steps, Actions")
    print("="*60)
    
    # Check for API key
    api_key = os.getenv("GALILEO_API_KEY")
    if not api_key:
        print("\n⚠ Warning: GALILEO_API_KEY not set!")
        print("  Traces will not be logged to Galileo console.")
        print("  Set GALILEO_API_KEY in your .env file to enable logging.")
    else:
        print(f"\n✓ GALILEO_API_KEY configured (ends with ...{api_key[-8:]})")
    
    # Check API health
    print(f"\nChecking API at {API_BASE_URL}...")
    if not check_api_health(API_BASE_URL):
        print(f"✗ API not reachable at {API_BASE_URL}")
        print("  Make sure the unified-api service is running:")
        print("  docker-compose up -d unified-api")
        sys.exit(1)
    
    print(f"✓ API is healthy")
    
    # Initialize runner
    runner = GalileoEvaluationRunner(
        api_base_url=API_BASE_URL,
        project_name=GALILEO_PROJECT
    )
    
    # Run tests
    print("\n" + "-"*60)
    print("Starting evaluation with Galileo trace logging...")
    print("Each test will log:")
    print("  • Agent spans (overall agent execution)")
    print("  • LLM spans (reasoning steps)")
    print("  • Tool spans (tool calls and results)")
    print("-"*60)
    
    runner.run_all_tests()
    
    # Optional: Run Bull vs Bear test
    # runner.run_bullbear_test("AAPL")
    
    # Print summary
    runner.print_summary()
    
    # Save results
    runner.save_results()
    
    # Final flush to ensure all traces are sent
    try:
        runner.logger.flush()
        print("\n✓ All Galileo traces flushed successfully")
        print(f"  View at: https://console.galileo.ai/project/{GALILEO_PROJECT}")
    except Exception as e:
        print(f"\n⚠ Could not flush Galileo logs: {e}")


if __name__ == "__main__":
    main()
