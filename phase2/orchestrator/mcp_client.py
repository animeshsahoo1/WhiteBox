"""MCP Client wrapper for orchestrator"""

from fastmcp import Client
import asyncio
import json
import logging
from typing import Dict, Any, List

from ..config.settings import mcp_settings

logger = logging.getLogger(__name__)


class MCPClientWrapper:
    """Wrapper around fastmcp Client for easier usage"""
    
    def __init__(self):
        # For now, we'll create clients on-demand per tool
        # In production, you'd have different MCP server URLs
        self.mcp_base_url = mcp_settings.server_url
        logger.info(f"Initialized MCP Client: {self.mcp_base_url}")
    
    async def get_current_hypotheses(self) -> List[Dict[str, Any]]:
        """
        Get current market hypotheses
        
        MCP Tool: get_hypothesis (simple getter, no params)
        """
        try:
            async with Client(self.mcp_base_url) as client:
                result = await client.call_tool(
                    name="get_hypothesis",
                    arguments={}
                )
                
                # Parse result
                hypotheses = json.loads(result.content) if isinstance(result.content, str) else result.content
                return hypotheses if isinstance(hypotheses, list) else [hypotheses]
                
        except Exception as e:
            logger.error(f"Failed to get hypotheses: {e}")
            return []
    
    async def get_phase1_reports(self) -> Dict[str, Any]:
        """
        Get latest Phase 1 reports (news, sentiment, fundamental, market, facilitator)
        
        This would typically come from a separate MCP resource or API
        For now, returning empty dict as fallback
        """
        try:
            # In production, this would call a specific MCP tool
            # For now, return empty dict
            return {
                "news_report": "",
                "sentiment_report": "",
                "fundamental_report": "",
                "market_report": "",
                "facilitator_report": ""
            }
                
        except Exception as e:
            logger.error(f"Failed to get Phase 1 reports: {e}")
            return {}
    
    async def get_market_conditions(self) -> Dict[str, Any]:
        """
        Get current market conditions
        
        This would typically come from a separate MCP resource
        For now, returning basic structure
        """
        try:
            # In production, this would call a specific MCP tool
            return {
                "volatility": "moderate",
                "trend": "neutral",
                "sentiment": "neutral"
            }
                
        except Exception as e:
            logger.error(f"Failed to get market conditions: {e}")
            return {}
    
    async def search_strategies(
        self,
        filters: Dict[str, Any],
        sort_by: List[str],
        sort_by_weight: Dict[str, float],
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search backtesting API for strategies
        
        MCP Tool: strategy_search (takes JSON filters, returns strategies)
        In your case: takes strategy search json and returns resulting json
        """
        try:
            async with Client(self.mcp_base_url) as client:
                # Build search request JSON
                search_request = {
                    "filters": filters,
                    "sort_by": sort_by,
                    "sort_by_weight": sort_by_weight,
                    "limit": limit
                }
                
                result = await client.call_tool(
                    name="strategy_search",
                    arguments={
                        "search_json": json.dumps(search_request)
                    }
                )
                
                # Parse result
                response = json.loads(result.content) if isinstance(result.content, str) else result.content
                return response
                
        except Exception as e:
            logger.error(f"Failed to search strategies: {e}")
            return {"results": {"strategies": []}}
    
    async def assess_risk(
        self,
        strategy: Dict[str, Any],
        market: Dict[str, Any],
        phase1: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get risk assessments for all 3 tiers
        
        MCP Tool: risk_analysis
        Parameters: symbol, strategy, risk_levels (list with options: no-risk, neutral, aggressive)
        Returns: concatenated JSON for each risk level
        """
        try:
            async with Client(self.mcp_base_url) as client:
                # Extract symbol from strategy
                symbol = strategy.get("symbol", "AAPL")
                
                # Call risk analysis tool
                result = await client.call_tool(
                    name="risk_analysis",
                    arguments={
                        "symbol": symbol,
                        "strategy": json.dumps(strategy),
                        "risk_levels": ["no-risk", "neutral", "aggressive"]
                    }
                )
                
                # Parse concatenated result
                risk_json = result.content if isinstance(result.content, str) else json.dumps(result.content)
                
                # Try to parse as JSON
                try:
                    parsed = json.loads(risk_json)
                    return parsed
                except:
                    # If it's concatenated text, parse each section
                    return self._parse_concatenated_risk(risk_json)
                
        except Exception as e:
            logger.error(f"Failed to assess risk: {e}")
            return {
                "no_risk": {"approval_status": "error", "message": str(e)},
                "neutral": {"approval_status": "error", "message": str(e)},
                "aggressive": {"approval_status": "error", "message": str(e)}
            }
    
    def _parse_concatenated_risk(self, concatenated_text: str) -> Dict[str, Any]:
        """Parse concatenated risk analysis text into structured format"""
        
        try:
            # Split by risk level markers
            risk_data = {
                "no_risk": {},
                "neutral": {},
                "aggressive": {}
            }
            
            # Look for each risk level section
            for risk_level in ["no-risk", "neutral", "aggressive"]:
                marker = f"--- Risk Level: {risk_level} ---"
                if marker in concatenated_text:
                    # Extract section
                    start = concatenated_text.find(marker)
                    end = concatenated_text.find("---", start + len(marker))
                    if end == -1:
                        end = len(concatenated_text)
                    
                    section = concatenated_text[start + len(marker):end].strip()
                    
                    # Try to parse JSON from section
                    try:
                        risk_json = json.loads(section)
                        risk_key = risk_level.replace("-", "_")
                        risk_data[risk_key] = risk_json
                    except:
                        risk_key = risk_level.replace("-", "_")
                        risk_data[risk_key] = {"raw_text": section}
            
            return risk_data
            
        except Exception as e:
            logger.error(f"Failed to parse concatenated risk: {e}")
            return {
                "no_risk": {"raw_text": concatenated_text},
                "neutral": {},
                "aggressive": {}
            }
    
    async def web_search_strategy(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Search web for trading strategy information
        
        MCP Tool: web_search
        Parameters: query, max_results
        Returns: search results
        """
        try:
            async with Client(self.mcp_base_url) as client:
                result = await client.call_tool(
                    name="web_search",
                    arguments={
                        "query": query,
                        "max_results": max_results
                    }
                )
                
                # Parse result
                search_results = json.loads(result.content) if isinstance(result.content, str) else result.content
                return search_results
                
        except Exception as e:
            logger.error(f"Failed to web search strategy: {e}")
            return {"error": str(e), "results": []}
    
    async def save_conversation(
        self,
        user_id: str,
        user_query: str,
        assistant_response: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Save conversation turn to database
        
        This would typically be a separate MCP tool or database call
        For now, just log it
        """
        try:
            logger.info(f"Conversation saved for {user_id}: {user_query[:50]}...")
            return True
                
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
            return False

