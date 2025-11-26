"""
Phase 2 Configuration Module
Centralized configuration management for all Phase 2 services.
Sensitive values are loaded from environment variables.
"""

import os
from typing import Optional


class OpenAIConfig:
    """OpenAI and LLM Configuration"""
    API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    API_BASE: str = "https://openrouter.ai/api/v1"
    MODEL_HYPOTHESIS: str = "google/gemini-2.0-flash-lite-001"
    MODEL_RISK: str = "google/gemini-2.0-flash-lite-001"
    MODEL_ORCHESTRATOR: str = "google/gemini-2.0-flash-lite-001"


class TradingConfig:
    """Trading Configuration"""
    SYMBOL: str = "AAPL"
    PATHWAY_LICENSE_KEY: str = os.getenv("PATHWAY_LICENSE_KEY", "")


class PathwayAPIConfig:
    """Pathway API Configuration (Phase 1 Reports)"""
    REPORTS_API_URL: str = "http://reports-api:8000/"


class HypothesisConfig:
    """Hypothesis Generator and Caching Configuration"""
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 9001
    API_URL: str = "http://hypothesis-generator:9001/"
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 9002
    MCP_URL: str = "http://hypothesis-generator:9002/mcp/"


class RedisConfig:
    """Redis Configuration"""
    HOST: str = "redis"
    PORT: int = 9003
    DB: int = 0


class RiskManagerConfig:
    """Risk Manager Configuration"""
    MCP_HOST: str = "0.0.0.0"
    MCP_PORT: int = 9004
    MCP_URL: str = "http://risk-managers:9004/mcp/"


class BacktestingConfig:
    """Backtesting Configuration"""
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 9005
    API_URL: str = "http://backtesting-api:9005/strategies"


class OrchestratorLLMSettings:
    """Orchestrator LLM Settings"""
    TEMPERATURE: float = 0.0
    MAX_TOKENS: int = 500


class OrchestratorSearchSettings:
    """Orchestrator Search Settings"""
    TIME_WINDOW: str = "30d"
    STRATEGY_LIMIT: int = 5
    MAX_WEB_SEARCHES: int = 2
    MAX_SYNTHESIS_ITERATIONS: int = 5


class OrchestratorPerformanceThresholds:
    """Orchestrator Performance Thresholds"""
    MIN_WIN_RATE: float = 0.60
    MIN_SHARPE: float = 1.5
    MIN_TRADE_COUNT: int = 10


class OrchestratorAPITimeouts:
    """Orchestrator API Timeouts"""
    STRATEGY_API_SEARCH_TIMEOUT: int = 20
    STRATEGY_API_BACKTEST_TIMEOUT: int = 30
    WEB_SEARCH_RESULT_LENGTH: int = 1000


class Config:
    """Main Configuration Class"""
    openai = OpenAIConfig
    trading = TradingConfig
    pathway_api = PathwayAPIConfig
    hypothesis = HypothesisConfig
    redis = RedisConfig
    risk_manager = RiskManagerConfig
    backtesting = BacktestingConfig
    orch_llm = OrchestratorLLMSettings
    orch_search = OrchestratorSearchSettings
    orch_performance = OrchestratorPerformanceThresholds
    orch_timeouts = OrchestratorAPITimeouts

    @classmethod
    def validate(cls) -> bool:
        """Validate that required environment variables are set"""
        required_vars = {
            "OPENAI_API_KEY": cls.openai.API_KEY,
            "PATHWAY_LICENSE_KEY": cls.trading.PATHWAY_LICENSE_KEY,
        }
        
        missing = [key for key, value in required_vars.items() if not value]
        
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Please set them in your environment before running the application."
            )
        
        return True


# Create a singleton instance
config = Config()
