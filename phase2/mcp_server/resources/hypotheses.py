"""Hypotheses Resource for MCP"""

import pathway as pw
from pathway.xpacks.llm.mcp_server import McpServable, McpServer
import json
import logging
from typing import List, Dict, Any

from ...config.settings import kafka_settings

logger = logging.getLogger(__name__)


class HypothesesResource(McpServable):
    """
    MCP Resource providing access to current market hypotheses
    
    Exposes get_current_hypotheses tool
    """
    
    class HypothesesRequestSchema(pw.Schema):
        pass  # No input params needed
    
    def __init__(self):
        self.hypotheses_cache = []
        logger.info("Hypotheses Resource initialized")
        
        # Set up Kafka consumer for hypotheses
        self._setup_consumer()
    
    def _setup_consumer(self):
        """Set up Kafka consumer for hypotheses topic"""
        
        # Read hypotheses from Kafka
        hypotheses_stream = pw.io.kafka.read(
            rdkafka_settings={
                "bootstrap.servers": kafka_settings.bootstrap_servers,
                "security.protocol": kafka_settings.security_protocol,
                "group.id": "mcp-server-hypotheses",
            },
            topic=kafka_settings.topic_hypotheses,
            format="json",
            autocommit_duration_ms=1000,
        )
        
        # Cache latest hypotheses
        hypotheses_stream.subscribe(self._update_cache)
        
        logger.info("Hypotheses consumer configured")
    
    def _update_cache(self, row: Dict[str, Any]):
        """Update cache with latest hypotheses"""
        
        try:
            hypotheses = json.loads(row.get("hypotheses", "[]"))
            self.hypotheses_cache = hypotheses
            logger.info(f"Updated hypothesis cache: {len(hypotheses)} hypotheses")
        except Exception as e:
            logger.error(f"Failed to update hypothesis cache: {e}")
    
    def hypotheses_handler(self, request: pw.Table) -> pw.Table:
        """
        Handle get_current_hypotheses requests
        
        Returns:
            Table with top 5 hypotheses
        """
        
        return request.select(
            result=pw.apply(self._get_hypotheses)
        )
    
    def _get_hypotheses(self) -> str:
        """
        Get current hypotheses from cache
        
        Returns JSON string with hypotheses array
        """
        
        try:
            # Return cached hypotheses (already sorted by rank)
            return json.dumps(self.hypotheses_cache[:5])
        except Exception as e:
            logger.error(f"Failed to get hypotheses: {e}")
            return json.dumps([])
    
    def register_mcp(self, server: McpServer):
        """Register this resource with MCP server"""
        
        server.tool(
            name="get_current_hypotheses",
            description=(
                "Get top 5 current market hypotheses. "
                "Hypotheses are generated from Phase 1 reports and ranked by confidence. "
                "Each includes statement, confidence, supporting evidence, risk factors, and recommended action."
            ),
            request_handler=self.hypotheses_handler,
            schema=self.HypothesesRequestSchema
        )
        
        logger.info("Registered get_current_hypotheses resource")
