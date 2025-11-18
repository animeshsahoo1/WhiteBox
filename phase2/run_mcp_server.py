#!/usr/bin/env python3
"""
Entry point for MCP Server

Run: python -m phase2.run_mcp_server
"""

import logging
from phase2.mcp_server.server import run_mcp_server

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Start MCP server"""
    logger.info("=" * 60)
    logger.info("PHASE 2: MCP SERVER")
    logger.info("=" * 60)
    
    try:
        run_mcp_server()
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
