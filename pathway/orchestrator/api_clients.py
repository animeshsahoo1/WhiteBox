"""
API client helpers for backtesting, reports, and LLM calls.
"""

import httpx
from typing import Optional

from config import (
    BACKTESTING_API_URL,
    REPORTS_API_URL,
    OPENAI_MODEL_RISK,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS,
    openai_client
)
from risk_managers_prompt import RiskManagerPrompts


# ============================================================================
# BACKTESTING API CLIENT
# ============================================================================

async def call_backtesting_api(endpoint: str, method: str = "GET", json_data: dict = None) -> dict:
    """Make HTTP request to backtesting API."""
    
    url = f"{BACKTESTING_API_URL}/{endpoint.lstrip('/')}"
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        try:
            if method == "GET":
                response = await http_client.get(url)
            elif method == "POST":
                response = await http_client.post(url, json=json_data)
            elif method == "DELETE":
                response = await http_client.delete(url)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API returned {response.status_code}", "detail": response.text}
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# REPORTS API CLIENT
# ============================================================================

async def fetch_reports(symbol: str) -> dict:
    """Fetch market and facilitator reports from Reports API."""
    reports = {}
    async with httpx.AsyncClient() as http_client:
        # Fetch market report
        try:
            response = await http_client.get(
                f"{REPORTS_API_URL}/reports/{symbol}/market",
                timeout=10.0
            )
            if response.status_code == 200:
                reports["market_report"] = response.json()
        except Exception as e:
            print(f"[ERROR] Failed to fetch market report: {e}")
        
        # Fetch facilitator report
        try:
            response = await http_client.get(
                f"{REPORTS_API_URL}/reports/{symbol}/facilitator",
                timeout=10.0
            )
            if response.status_code == 200:
                reports["facilitator_report"] = response.json()
        except Exception as e:
            print(f"[ERROR] Failed to fetch facilitator report: {e}")
    
    return reports


async def fetch_facilitator_report(symbol: str) -> dict:
    """Fetch facilitator report from Reports API."""
    symbol = symbol.upper()
    
    async with httpx.AsyncClient() as http_client:
        try:
            response = await http_client.get(
                f"{REPORTS_API_URL}/reports/{symbol}/facilitator",
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Failed to fetch report: {response.status_code}"}
        except Exception as e:
            print(f"[ERROR] Failed to fetch facilitator report: {e}")
            return {"error": str(e)}


# ============================================================================
# LLM CLIENT
# ============================================================================

def build_prompt(strategy_str: str, reports: dict, risk_level: str) -> list[dict]:
    """Build the prompt for a specific risk level."""
    
    if risk_level == "no-risk":
        system_prompt = RiskManagerPrompts.NO_RISK_SYSTEM_PROMPT
        user_prompt = RiskManagerPrompts.NO_RISK_USER_PROMPT_TEMPLATE.format(
            strategy_json=strategy_str,
            market_report=reports.get("market_report", "N/A"),
            facilitator_report=reports.get("facilitator_report", "N/A"),
        )
    elif risk_level == "neutral":
        system_prompt = RiskManagerPrompts.NEUTRAL_RISK_SYSTEM_PROMPT
        user_prompt = RiskManagerPrompts.NEUTRAL_RISK_USER_PROMPT_TEMPLATE.format(
            strategy_json=strategy_str,
            market_report=reports.get("market_report", "N/A"),
            facilitator_report=reports.get("facilitator_report", "N/A"),
        )
    elif risk_level == "aggressive":
        system_prompt = RiskManagerPrompts.AGGRESSIVE_RISK_SYSTEM_PROMPT
        user_prompt = RiskManagerPrompts.AGGRESSIVE_RISK_USER_PROMPT_TEMPLATE.format(
            strategy_json=strategy_str,
            market_report=reports.get("market_report", "N/A"),
            facilitator_report=reports.get("facilitator_report", "N/A"),
        )
    else:
        system_prompt = "You are an Investment Risk Manager."
        user_prompt = f"Assess the risk of the following trading strategy.\nStrategy: {strategy_str}"
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


async def call_llm(messages: list[dict]) -> str:
    """Call the LLM and return the response."""
    try:
        response = await openai_client.chat.completions.create(
            model=OPENAI_MODEL_RISK,
            messages=messages,
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        return f"Error calling LLM: {str(e)}"
