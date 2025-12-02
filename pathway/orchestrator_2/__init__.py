"""
Orchestrator 2 - LangGraph + Mem0 Strategist Agent with MCP Server

A production-ready ReAct agent for trading strategy backtesting and analysis.

Components:
- server.py: FastMCP server exposing trading tools
- langgraph_agent.py: LangGraph Strategist agent with Mem0 memory
- config.py: Configuration and environment settings
- api_clients.py: HTTP clients for Reports API and Backtesting API
- tools/: MCP tool implementations (backtesting, risk, search, reports)

Usage (Docker):
    # Start MCP server
    docker-compose up mcp-server
    
    # Start with interactive agent
    docker-compose --profile agent up

Usage (Local):
    # Start MCP server
    python server.py
    
    # Run agent
    python langgraph_agent.py

API Integration:
    The Strategist agent is exposed via the reports-api FastAPI server:
    - POST /strategist/chat - Send message and get response
    - POST /strategist/chat/stream - SSE streaming response
    - POST /strategist/new - Start new conversation
    - GET /strategist/memory/{user_id} - Get user memories
    - DELETE /strategist/memory/{user_id} - Clear memories
"""

from .config import MCP_SERVER_HOST, MCP_SERVER_PORT, OPENAI_MODEL_RISK
from .langgraph_agent import Strategist, create_strategist_agent

