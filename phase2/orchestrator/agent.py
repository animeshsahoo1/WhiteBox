"""Main orchestrator agent using MCP client"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .mcp_client import MCPClientWrapper
from .response_formatter import (
    format_strategy_response,
    format_simple_response,
    format_error_response
)

logger = logging.getLogger(__name__)


class StrategyOrchestrator:
    """
    Main orchestrator agent for Phase 2
    
    Handles user queries, coordinates MCP tools, generates responses
    """
    
    def __init__(self):
        self.mcp = MCPClientWrapper()
        logger.info("Strategy Orchestrator initialized")
    
    async def handle_query(self, user_id: str, query: str) -> str:
        """
        Main entry point for user queries
        
        Args:
            user_id: User identifier
            query: User's natural language query
        
        Returns:
            Formatted response string
        """
        
        logger.info(f"Processing query from {user_id}: {query}")
        
        try:
            # Classify query type
            query_type = self._classify_query(query)
            logger.info(f"Query classified as: {query_type}")
            
            # Route to appropriate handler
            if query_type == "hypothesis_based":
                response = await self._handle_hypothesis_query(user_id, query)
            elif query_type == "general":
                response = await self._handle_general_query(user_id, query)
            elif query_type == "risk_based":
                response = await self._handle_risk_query(user_id, query)
            elif query_type == "performance":
                response = await self._handle_performance_query(user_id, query)
            else:
                response = format_simple_response(
                    "I can help you with:\n"
                    "- Finding strategies for current market conditions\n"
                    "- Searching for specific types of strategies\n"
                    "- Comparing risk tiers for strategies\n"
                    "- Showing top performing strategies\n\n"
                    "What would you like to explore?"
                )
            
            # Save conversation
            context = {
                "query_type": query_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.mcp.save_conversation(
                user_id=user_id,
                user_query=query,
                assistant_response=response,
                context=context
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling query: {e}", exc_info=True)
            return format_error_response(str(e))
    
    def _classify_query(self, query: str) -> str:
        """
        Classify user query into type
        
        Returns: "hypothesis_based" | "general" | "risk_based" | "performance" | "unknown"
        """
        query_lower = query.lower()
        
        # Hypothesis-based queries
        if any(phrase in query_lower for phrase in [
            "what should i trade",
            "what to trade",
            "recommend",
            "right now",
            "current market",
            "what's good"
        ]):
            return "hypothesis_based"
        
        # Risk-based queries
        if any(phrase in query_lower for phrase in [
            "low risk",
            "high risk",
            "conservative",
            "aggressive",
            "safe",
            "risky"
        ]):
            return "risk_based"
        
        # Performance queries
        if any(phrase in query_lower for phrase in [
            "top performing",
            "best strategies",
            "highest win rate",
            "best sharpe",
            "performing well"
        ]):
            return "performance"
        
        # General queries (strategy search)
        if any(phrase in query_lower for phrase in [
            "momentum",
            "reversal",
            "rsi",
            "macd",
            "moving average",
            "show me",
            "find"
        ]):
            return "general"
        
        return "unknown"
    
    async def _handle_hypothesis_query(self, user_id: str, query: str) -> str:
        """Handle 'What should I trade now?' type queries"""
        
        logger.info("Handling hypothesis-based query")
        
        # Get current context
        hypotheses = await self.mcp.get_current_hypotheses()
        market = await self.mcp.get_market_conditions()
        phase1 = await self.mcp.get_phase1_reports()
        
        if not hypotheses:
            return format_error_response("No current market hypotheses available. Please try again later.")
        
        # Use top hypothesis
        top_hypothesis = hypotheses[0]
        logger.info(f"Using top hypothesis: {top_hypothesis['statement']}")
        
        # Search for strategies aligned with hypothesis
        filters = {
            "performance_criteria": {
                "min_win_rate": 0.60,
                "min_trade_count": 10
            },
            "time_window": "30d"
        }
        
        sort_by = ["rank", "sharpe", "win_rate"]
        sort_by_weight = {
            "rank": 0.5,
            "sharpe": 1.0,
            "win_rate": 0.7,
            "max_drawdown": -0.6
        }
        
        search_result = await self.mcp.search_strategies(
            filters=filters,
            sort_by=sort_by,
            sort_by_weight=sort_by_weight,
            limit=3
        )
        
        strategies = search_result.get("results", {}).get("strategies", [])
        
        if not strategies:
            return format_error_response("No strategies found matching current market conditions.")
        
        logger.info(f"Found {len(strategies)} strategies")
        
        # Assess risk for each strategy
        for strategy in strategies:
            logger.info(f"Assessing risk for: {strategy['name']}")
            
            risk_assessment = await self.mcp.assess_risk(
                strategy=strategy,
                market=market,
                phase1=phase1
            )
            
            strategy['risk_tiers'] = risk_assessment
        
        # Format response
        return format_strategy_response(
            hypothesis=top_hypothesis,
            strategies=strategies,
            market=market,
            phase1=phase1
        )
    
    async def _handle_general_query(self, user_id: str, query: str) -> str:
        """Handle general strategy search queries"""
        
        logger.info("Handling general strategy search")
        
        # Extract indicators/keywords from query
        indicators = self._extract_indicators(query)
        
        if not indicators:
            return format_simple_response(
                "Please specify what type of strategies you're looking for.\n"
                "For example: 'Show me RSI strategies' or 'Find momentum strategies'"
            )
        
        # Search strategies
        filters = {
            "technical_indicators": indicators,
            "performance_criteria": {
                "min_win_rate": 0.55,
                "min_trade_count": 5
            },
            "time_window": "30d"
        }
        
        search_result = await self.mcp.search_strategies(
            filters=filters,
            sort_by=["sharpe", "win_rate"],
            sort_by_weight={"sharpe": 1.0, "win_rate": 0.8},
            limit=5
        )
        
        strategies = search_result.get("results", {}).get("strategies", [])
        
        if not strategies:
            # Fallback to web search
            logger.info(f"No strategies found, trying web search for: {query}")
            web_result = await self.mcp.web_search_strategy(query, max_results=5)
            
            if "error" in web_result:
                return format_error_response(
                    f"No strategies found for '{query}'. Try different keywords or indicators."
                )
            
            return format_simple_response(
                f"Found a new strategy concept from web search:\n\n"
                f"**{web_result.get('name', 'Unknown')}**\n"
                f"{web_result.get('description', 'No description')}\n\n"
                f"This strategy has been added to the backtesting system for evaluation."
            )
        
        # Get market context
        market = await self.mcp.get_market_conditions()
        phase1 = await self.mcp.get_phase1_reports()
        
        # Create simple hypothesis for formatting
        simple_hypothesis = {
            "statement": f"User requested {', '.join(indicators)} strategies",
            "confidence": 1.0,
            "supporting_evidence": ["User query", "Strategy search", ""]
        }
        
        # Assess risk for top 3
        for strategy in strategies[:3]:
            risk_assessment = await self.mcp.assess_risk(
                strategy=strategy,
                market=market,
                phase1=phase1
            )
            strategy['risk_tiers'] = risk_assessment
        
        return format_strategy_response(
            hypothesis=simple_hypothesis,
            strategies=strategies[:3],
            market=market,
            phase1=phase1
        )
    
    async def _handle_risk_query(self, user_id: str, query: str) -> str:
        """Handle risk-tier specific queries"""
        
        logger.info("Handling risk-based query")
        
        # Determine requested risk tier
        risk_tier = self._extract_risk_tier(query)
        
        # Adjust search filters based on risk tier
        if risk_tier == "no_risk":
            max_drawdown = 0.10
            min_sharpe = 1.5
        elif risk_tier == "aggressive":
            max_drawdown = 0.30
            min_sharpe = 1.0
        else:  # neutral
            max_drawdown = 0.20
            min_sharpe = 1.2
        
        filters = {
            "performance_criteria": {
                "min_sharpe_ratio": min_sharpe,
                "max_drawdown": max_drawdown,
                "min_trade_count": 10
            },
            "time_window": "30d"
        }
        
        search_result = await self.mcp.search_strategies(
            filters=filters,
            sort_by=["sharpe", "win_rate"],
            sort_by_weight={"sharpe": 1.0, "win_rate": 0.8, "max_drawdown": -1.0},
            limit=3
        )
        
        strategies = search_result.get("results", {}).get("strategies", [])
        
        if not strategies:
            return format_error_response(
                f"No {risk_tier.replace('_', '-')} strategies found. Try adjusting criteria."
            )
        
        market = await self.mcp.get_market_conditions()
        phase1 = await self.mcp.get_phase1_reports()
        
        # Assess all tiers but highlight requested one
        for strategy in strategies:
            risk_assessment = await self.mcp.assess_risk(
                strategy=strategy,
                market=market,
                phase1=phase1
            )
            strategy['risk_tiers'] = risk_assessment
        
        simple_hypothesis = {
            "statement": f"User requested {risk_tier.replace('_', '-')} strategies",
            "confidence": 1.0,
            "supporting_evidence": ["User query", f"{risk_tier} tier filter", ""]
        }
        
        return format_strategy_response(
            hypothesis=simple_hypothesis,
            strategies=strategies,
            market=market,
            phase1=phase1
        )
    
    async def _handle_performance_query(self, user_id: str, query: str) -> str:
        """Handle top-performing strategy queries"""
        
        logger.info("Handling performance query")
        
        # Search for top performers
        filters = {
            "performance_criteria": {
                "min_trade_count": 10
            },
            "time_window": "30d"
        }
        
        search_result = await self.mcp.search_strategies(
            filters=filters,
            sort_by=["rank", "sharpe", "total_return"],
            sort_by_weight={
                "rank": 1.0,
                "sharpe": 0.8,
                "total_return": 0.6,
                "win_rate": 0.5
            },
            limit=5
        )
        
        strategies = search_result.get("results", {}).get("strategies", [])
        
        if not strategies:
            return format_error_response("No performance data available.")
        
        market = await self.mcp.get_market_conditions()
        phase1 = await self.mcp.get_phase1_reports()
        
        # Assess top 3
        for strategy in strategies[:3]:
            risk_assessment = await self.mcp.assess_risk(
                strategy=strategy,
                market=market,
                phase1=phase1
            )
            strategy['risk_tiers'] = risk_assessment
        
        simple_hypothesis = {
            "statement": "Top performing strategies by overall rank",
            "confidence": 1.0,
            "supporting_evidence": ["Historical performance", "Sharpe ratio", "Win rate"]
        }
        
        return format_strategy_response(
            hypothesis=simple_hypothesis,
            strategies=strategies[:3],
            market=market,
            phase1=phase1
        )
    
    def _extract_indicators(self, query: str) -> list:
        """Extract technical indicators from query"""
        query_lower = query.lower()
        indicators = []
        
        indicator_map = {
            "rsi": "RSI",
            "macd": "MACD",
            "moving average": "MA",
            "ma": "MA",
            "ema": "EMA",
            "bollinger": "BB",
            "volume": "Volume",
            "momentum": "Momentum",
            "stochastic": "Stochastic"
        }
        
        for keyword, indicator in indicator_map.items():
            if keyword in query_lower:
                indicators.append(indicator)
        
        return indicators
    
    def _extract_risk_tier(self, query: str) -> str:
        """Extract risk tier from query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["conservative", "safe", "low risk", "no risk"]):
            return "no_risk"
        elif any(word in query_lower for word in ["aggressive", "risky", "high risk"]):
            return "aggressive"
        else:
            return "neutral"


# Global orchestrator instance
orchestrator = StrategyOrchestrator()


async def handle_user_query(user_id: str, query: str) -> str:
    """
    Main entry point for user queries
    
    Args:
        user_id: User identifier
        query: Natural language query
    
    Returns:
        Formatted response
    """
    return await orchestrator.handle_query(user_id, query)
