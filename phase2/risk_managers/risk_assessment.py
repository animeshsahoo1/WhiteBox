"""Risk Assessment Tool using 3 LLM agents"""

import pathway as pw
from pathway.xpacks.llm.mcp_server import McpServable, McpServer, PathwayMcp
from pathway.xpacks.llm.llms import OpenAIChat
import json
import logging
import requests
from typing import Dict, Any
from .risk_managers_prompt import RiskManagerPrompts

from ..config.settings import openai_settings, trading_settings, risk_manager_settings

logger = logging.getLogger(__name__)

# Set Pathway license key from config
if trading_settings.pathway_license_key:
    pw.set_license_key(trading_settings.pathway_license_key)
class TradingAnalysisRequestSchema(pw.Schema):
    symbol: str
    strategy: str
    risk_levels: pw.Json

@pw.udf
def fetch_reports_from_api(symbol: str) -> pw.Json:
    """
    Fetch reports A, B, C, D, E from FastAPI endpoint
    """
    base_url = risk_manager_settings.reports_api_url
    reports = {}
    
    try:
        response = requests.get(
            f"{base_url}/reports/{symbol}",
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
        enriched = request.select(
            pw.this.symbol,
            pw.this.strategy,
            pw.this.risk_levels,
            reports=fetch_reports_from_api(pw.this.symbol)
        )

        flattened = enriched.flatten(pw.this.risk_levels).select(
            pw.this.symbol,
            pw.this.strategy,
            pw.this.reports,
            risk_level=pw.this.risk_levels
        )

        prompts = flattened.select(
            pw.this.symbol,
            pw.this.strategy,
            pw.this.reports,
            pw.this.risk_level,
            prompt=create_prompt(
                pw.this.strategy,
                pw.this.reports,
                pw.this.risk_level
            )
        )

        llm = OpenAIChat(
            model=openai_settings.model_risk,
            api_key=openai_settings.api_key,
            temperature=openai_settings.temperature,
            max_tokens=openai_settings.max_tokens
        )
        responses = prompts.select(
            pw.this.symbol,
            pw.this.strategy,
            pw.this.risk_level,
            response=extract_json(llm(pw.this.prompt))
        )

        @pw.udf
        def label_response(risk_level: str, response: tuple) -> str:
            
            """Label response with risk level"""
            return f"--- Risk Level: {risk_level} ---\n{json.dumps(response, indent=2)}"
        
        responses = responses.select(
            pw.this.symbol,
            pw.this.strategy,
            llm_response=label_response(
                pw.this.risk_level,
                pw.this.response
            )
        )

        final = responses.groupby(
            pw.this.symbol,
            pw.this.strategy
        ).reduce(
            pw.this.symbol,
            pw.this.strategy,
            responses=pw.reducers.sorted_tuple(pw.this.llm_response)
        )

        @pw.udf
        def concat_responses(responses: tuple) -> str:
            """Concatenate all LLM responses"""
            separator = "\n\n" + "="*80 + "\n\n"
            return separator.join(responses)
        
        result = final.select(
            result=concat_responses(pw.this.responses)
        )
        
        return result

    
    def register_mcp(self, server: McpServer):
        """Register this tool with MCP server"""
        
        server.tool(
            name="assess_risk_all_tiers",
            description=(
                "Assess trading strategy risk across all 3 tiers (no-risk, neutral, aggressive). "
                "Returns approval status, recommended parameters, warnings, and reasoning for each tier. "
                "Uses LLM-based risk managers with tier-specific constraints."
            ),
            request_handler=self.analyze_trading_strategy,
            schema=TradingAnalysisRequestSchema
        )
        
        logger.info("Registered assess_risk_all_tiers tool")


basic_tools = RiskAssessmentTool()

pathway_mcp_server = PathwayMcp(
    name="Streamable MCP Server",
    transport="streamable-http",
    host=risk_manager_settings.host,
    port=risk_manager_settings.port,
    serve=[basic_tools],
)

pw.run()