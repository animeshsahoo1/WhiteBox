"""Market Conditions Resource for MCP"""

import pathway as pw
from pathway.xpacks.llm.mcp_server import McpServable, McpServer
import json
import logging
from typing import Dict, Any

from ...config.settings import kafka_settings

logger = logging.getLogger(__name__)


class MarketConditionsResource(McpServable):
    """
    MCP Resource providing access to current market conditions
    
    Exposes get_market_conditions tool
    """
    
    class MarketRequestSchema(pw.Schema):
        pass  # No input params needed
    
    def __init__(self):
        self.market_cache = {}
        logger.info("Market Conditions Resource initialized")
        
        # Set up Kafka consumer
        self._setup_consumer()
    
    def _setup_consumer(self):
        """Set up Kafka consumer for market conditions topic"""
        
        # Read market conditions from Kafka
        market_stream = pw.io.kafka.read(
            rdkafka_settings={
                "bootstrap.servers": kafka_settings.bootstrap_servers,
                "security.protocol": kafka_settings.security_protocol,
                "group.id": "mcp-server-market",
            },
            topic=kafka_settings.topic_market_conditions,
            format="json",
            autocommit_duration_ms=1000,
        )
        
        # Cache latest market conditions
        market_stream.subscribe(self._update_cache)
        
        logger.info("Market conditions consumer configured")
    
    def _update_cache(self, row: Dict[str, Any]):
        """Update cache with latest market conditions"""
        
        try:
            conditions = json.loads(row.get("conditions", "{}"))
            self.market_cache = conditions
            logger.info("Updated market conditions cache")
        except Exception as e:
            logger.error(f"Failed to update market cache: {e}")
    
    def market_handler(self, request: pw.Table) -> pw.Table:
        """
        Handle get_market_conditions requests
        
        Returns:
            Table with current market conditions
        """
        
        return request.select(
            result=pw.apply(self._get_conditions)
        )
    
    def _get_conditions(self) -> str:
        """
        Get current market conditions from cache
        
        Returns JSON string with conditions dict
        """
        
        try:
            return json.dumps(self.market_cache)
        except Exception as e:
            logger.error(f"Failed to get market conditions: {e}")
            return json.dumps({})
    
    def register_mcp(self, server: McpServer):
        """Register this resource with MCP server"""
        
        server.tool(
            name="get_market_conditions",
            description=(
                "Get current market conditions including volatility, VIX, price, trend, "
                "support/resistance levels. Essential for risk assessment and strategy selection."
            ),
            request_handler=self.market_handler,
            schema=self.MarketRequestSchema
        )
        
        logger.info("Registered get_market_conditions resource")
