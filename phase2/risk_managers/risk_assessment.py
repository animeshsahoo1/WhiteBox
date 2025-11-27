"""Risk Assessment Tool using 3 LLM agents"""

import pathway as pw
from pathway.xpacks.llm.mcp_server import McpServable, McpServer, PathwayMcp
from pathway.xpacks.llm.llms import OpenAIChat
import json
import logging
import requests
from typing import Dict, Any
import sys
from pathlib import Path
from .risk_managers_prompt import RiskManagerPrompts

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config

logger = logging.getLogger(__name__)

# Configuration from config.py
PATHWAY_LICENSE_KEY = config.trading.PATHWAY_LICENSE_KEY
OPENAI_API_KEY = config.openai.API_KEY
OPENAI_API_BASE = config.openai.API_BASE
OPENAI_MODEL_RISK = config.openai.MODEL_RISK
REPORTS_API_URL = config.pathway_api.REPORTS_API_URL
RISK_MANAGER_HOST = config.risk_manager.MCP_HOST
RISK_MANAGER_PORT = config.risk_manager.MCP_PORT

print(f"Risk Manager configured on: {RISK_MANAGER_HOST}:{RISK_MANAGER_PORT}")
print(f"Reports API URL: {REPORTS_API_URL}")
if OPENAI_API_KEY:
    print(f"OpenAI API Key loaded: {OPENAI_API_KEY[:8]}...")

# Set Pathway license key
if PATHWAY_LICENSE_KEY:
    pw.set_license_key(PATHWAY_LICENSE_KEY)
class TradingAnalysisRequestSchema(pw.Schema):
    pass
    # symbol: str
    # strategy: str
    # risk_levels: pw.Json

@pw.udf
def fetch_reports_from_api(symbol: str) -> pw.Json:
    """
    Fetch reports A, B, C, D, E from FastAPI endpoint
    """
    reports = {}
    
    try:
        response = requests.get(
            f"{REPORTS_API_URL}/reports/{symbol}",
            timeout=5
        )
        if response.status_code == 200:
            reports = response.json()
        else:
            reports = {
                "error": f"Failed to fetch reports for {symbol}"
            }
    except Exception as e:
        reports = {"error": str(e)}
    
    return reports

@pw.udf
def create_prompt(strategy: str, reports: Dict[str, Any], risk_level: str) -> str:
    """
    Create prompt for LLM based on risk level
    """
    system_prompt, user_prompt = "",""
    if risk_level == "no-risk":
        system_prompt = RiskManagerPrompts.NO_RISK_SYSTEM_PROMPT
        user_prompt = RiskManagerPrompts.NO_RISK_USER_PROMPT_TEMPLATE.format(
            strategy_json=strategy,
            news_report=reports.get("news_report", "N/A"),
            sentiment_report=reports.get("sentiment_report", "N/A"),
            fundamental_report=reports.get("fundamental_report", "N/A"),
            market_report=reports.get("market_report", "N/A"),
            facilitator_report=reports.get("facilitator_report", "N/A"),
        )
    elif risk_level == "neutral":
        system_prompt = RiskManagerPrompts.NEUTRAL_SYSTEM_PROMPT
        user_prompt = RiskManagerPrompts.NEUTRAL_USER_PROMPT_TEMPLATE.format(
            strategy_json=strategy,
            news_report=reports.get("news_report", "N/A"),
            sentiment_report=reports.get("sentiment_report", "N/A"),
            fundamental_report=reports.get("fundamental_report", "N/A"),
            market_report=reports.get("market_report", "N/A"),
            facilitator_report=reports.get("facilitator_report", "N/A"),
        )
    elif risk_level == "aggressive":
        system_prompt = RiskManagerPrompts.AGGRESSIVE_SYSTEM_PROMPT
        user_prompt = RiskManagerPrompts.AGGRESSIVE_USER_PROMPT_TEMPLATE.format(
            strategy_json=strategy,
            news_report=reports.get("news_report", "N/A"),
            sentiment_report=reports.get("sentiment_report", "N/A"),
            fundamental_report=reports.get("fundamental_report", "N/A"),
            market_report=reports.get("market_report", "N/A"),
            facilitator_report=reports.get("facilitator_report", "N/A"),
        )
    else:
        system_prompt = "You are an Investment Risk Manager."
        user_prompt = f"Assess the risk of the following trading strategy. \nStrategy: {strategy}"
    
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

@pw.udf
def extract_json(response: str) -> list:
    """
    Extract and parse json from LLM response
    
    Args:
        response: LLM response string

    """
    
    try:
        content = response
        
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()
        
        # Validate JSON
        analysis = json.loads(json_str)
        
        
        return analysis
        
    except Exception as e:
        logger.error(f"Failed to extract analysis: {e}")
        return []

class RiskAssessmentTool(McpServable):
    """
    MCP Tool for assessing risk across 3 tiers using LLM agents
    
    3 parallel GPT-4 calls: no-risk, neutral, aggressive
    """
    
    def analyze_trading_strategy(
        self, 
        request: pw.Table[TradingAnalysisRequestSchema]
    ) -> pw.Table:
        """
        Main handler for trading strategy analysis
        Takes symbol, strategy, and risk_levels list as input
        Returns final concatenated response
        """
        
        # Step 1: Fetch reports from API
        return request.select(result=1)

    
    def register_mcp(self, server: McpServer):
        """Register this tool with MCP server"""
        
        server.tool(
            name="assess_risk_all_tiers",
            request_handler=self.analyze_trading_strategy,
            schema=TradingAnalysisRequestSchema
        )
        
        logger.info("Registered assess_risk_all_tiers tool")


basic_tools = RiskAssessmentTool()

pathway_mcp_server = PathwayMcp(
    name="Streamable MCP Server",
    transport="streamable-http",
    host=RISK_MANAGER_HOST,
    port=RISK_MANAGER_PORT,
    serve=[basic_tools],
)

pw.run()