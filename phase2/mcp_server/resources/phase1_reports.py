"""Phase 1 Reports Resource for MCP"""

import pathway as pw
from pathway.xpacks.llm.mcp_server import McpServable, McpServer
import json
import logging
from typing import Dict, Any

from ...config.settings import kafka_settings

logger = logging.getLogger(__name__)


class Phase1ReportsResource(McpServable):
    """
    MCP Resource providing access to Phase 1 reports
    
    Exposes get_phase1_reports tool
    """
    
    class Phase1RequestSchema(pw.Schema):
        pass  # No input params needed
    
    def __init__(self):
        self.reports_cache = {
            "news": {},
            "sentiment": {},
            "fundamental": {},
            "market": {},
            "facilitator": {}
        }
        logger.info("Phase 1 Reports Resource initialized")
        
        # Set up Kafka consumers
        self._setup_consumers()
    
    def _setup_consumers(self):
        """Set up Kafka consumers for all Phase 1 report topics"""
        
        # News reports
        news_stream = pw.io.kafka.read(
            rdkafka_settings={
                "bootstrap.servers": kafka_settings.bootstrap_servers,
                "security.protocol": kafka_settings.security_protocol,
                "group.id": "mcp-server-phase1",
            },
            topic=kafka_settings.topic_news_reports,
            format="json",
            autocommit_duration_ms=1000,
        )
        news_stream.subscribe(lambda row: self._update_cache("news", row))
        
        # Sentiment reports
        sentiment_stream = pw.io.kafka.read(
            rdkafka_settings={
                "bootstrap.servers": kafka_settings.bootstrap_servers,
                "security.protocol": kafka_settings.security_protocol,
                "group.id": "mcp-server-phase1",
            },
            topic=kafka_settings.topic_sentiment_reports,
            format="json",
            autocommit_duration_ms=1000,
        )
        sentiment_stream.subscribe(lambda row: self._update_cache("sentiment", row))
        
        # Fundamental reports
        fundamental_stream = pw.io.kafka.read(
            rdkafka_settings={
                "bootstrap.servers": kafka_settings.bootstrap_servers,
                "security.protocol": kafka_settings.security_protocol,
                "group.id": "mcp-server-phase1",
            },
            topic=kafka_settings.topic_fundamental_reports,
            format="json",
            autocommit_duration_ms=1000,
        )
        fundamental_stream.subscribe(lambda row: self._update_cache("fundamental", row))
        
        # Market reports
        market_stream = pw.io.kafka.read(
            rdkafka_settings={
                "bootstrap.servers": kafka_settings.bootstrap_servers,
                "security.protocol": kafka_settings.security_protocol,
                "group.id": "mcp-server-phase1",
            },
            topic=kafka_settings.topic_market_reports,
            format="json",
            autocommit_duration_ms=1000,
        )
        market_stream.subscribe(lambda row: self._update_cache("market", row))
        
        # Facilitator reports
        facilitator_stream = pw.io.kafka.read(
            rdkafka_settings={
                "bootstrap.servers": kafka_settings.bootstrap_servers,
                "security.protocol": kafka_settings.security_protocol,
                "group.id": "mcp-server-phase1",
            },
            topic=kafka_settings.topic_facilitator_reports,
            format="json",
            autocommit_duration_ms=1000,
        )
        facilitator_stream.subscribe(lambda row: self._update_cache("facilitator", row))
        
        logger.info("Phase 1 report consumers configured")
    
    def _update_cache(self, report_type: str, row: Dict[str, Any]):
        """Update cache with latest report"""
        
        try:
            self.reports_cache[report_type] = row.get("data", {})
            logger.info(f"Updated {report_type} report cache")
        except Exception as e:
            logger.error(f"Failed to update {report_type} cache: {e}")
    
    def reports_handler(self, request: pw.Table) -> pw.Table:
        """
        Handle get_phase1_reports requests
        
        Returns:
            Table with all Phase 1 reports
        """
        
        return request.select(
            result=pw.apply(self._get_reports)
        )
    
    def _get_reports(self) -> str:
        """
        Get all Phase 1 reports from cache
        
        Returns JSON string with reports dict
        """
        
        try:
            return json.dumps(self.reports_cache)
        except Exception as e:
            logger.error(f"Failed to get Phase 1 reports: {e}")
            return json.dumps({})
    
    def register_mcp(self, server: McpServer):
        """Register this resource with MCP server"""
        
        server.tool(
            name="get_phase1_reports",
            description=(
                "Get latest Phase 1 intelligence reports. "
                "Includes news, sentiment, fundamental, market, and facilitator reports. "
                "Provides comprehensive market context for strategy recommendations."
            ),
            request_handler=self.reports_handler,
            schema=self.Phase1RequestSchema
        )
        
        logger.info("Registered get_phase1_reports resource")
