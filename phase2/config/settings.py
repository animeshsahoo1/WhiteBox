"""Configuration settings for Phase 2"""

import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings




class RedisSettings(BaseSettings):
    """Redis configuration"""
    host: str = Field(default="localhost", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    db: int = Field(default=0, env="REDIS_DB")
    
    class Config:
        env_file = ".env"


class PathwayAPISettings(BaseSettings):
    """Pathway API configuration"""
    host: str = Field(default="localhost", env="PATHWAY_API_HOST")
    port: int = Field(default=9000, env="PATHWAY_API_PORT")
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    class Config:
        env_file = ".env"


class HypothesisAPISettings(BaseSettings):
    """Hypothesis Query API configuration"""
    host: str = Field(default="0.0.0.0", env="HYPOTHESIS_API_HOST")
    port: int = Field(default=8002, env="HYPOTHESIS_API_PORT")
    
    class Config:
        env_file = ".env"


class TradingSettings(BaseSettings):
    """Trading configuration"""
    symbol: str = Field(default="AAPL", env="SYMBOL")
    pathway_license_key: str = Field(default="", env="PATHWAY_LICENSE_KEY")
    
    class Config:
        env_file = ".env"


class DatabaseSettings(BaseSettings):
    """PostgreSQL configuration"""
    host: str = Field(default="postgres", env="POSTGRES_HOST")
    port: int = Field(default=5432, env="POSTGRES_PORT")
    database: str = Field(default="trading_system", env="POSTGRES_DB")
    user: str = Field(default="postgres", env="POSTGRES_USER")
    password: str = Field(default="", env="POSTGRES_PASSWORD")
    
    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    class Config:
        env_file = ".env"


class OpenAISettings(BaseSettings):
    """OpenAI configuration"""
    api_key: str = Field(default="", env="OPENAI_API_KEY")
    model_hypothesis: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL_HYPOTHESIS")
    model_risk: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL_RISK")
    model_orchestrator: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL_ORCHESTRATOR")
    temperature: float = 1.0
    max_tokens: int = 500
    api_base: str = Field(default="https://api.operout.com/v1", env="OPENAI_API_BASE")
    
    class Config:
        env_file = ".env"


class BacktestingAPISettings(BaseSettings):
    """Backtesting API configuration"""
    base_url: str = Field(default="http://backtesting-api:8000", env="BACKTESTING_API_URL")
    timeout: int = 30
    
    class Config:
        env_file = ".env"


class BacktestingServerSettings(BaseSettings):
    """Backtesting API Server configuration"""
    host: str = Field(default="0.0.0.0", env="BACKTESTING_SERVER_HOST")
    port: int = Field(default=8001, env="BACKTESTING_SERVER_PORT")
    
    class Config:
        env_file = ".env"


class MCPSettings(BaseSettings):
    """MCP Server configuration"""
    host: str = Field(default="localhost", env="MCP_HOST")
    port: int = Field(default=8080, env="MCP_PORT")
    
    @property
    def server_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    class Config:
        env_file = ".env"


class RiskManagerSettings(BaseSettings):
    """Risk Manager MCP Server configuration"""
    host: str = Field(default="localhost", env="RISK_MANAGER_HOST")
    port: int = Field(default=9001, env="RISK_MANAGER_PORT")
    reports_api_url: str = Field(default="http://localhost:8000", env="REPORTS_API_URL")
    
    class Config:
        env_file = ".env"


class OrchestratorSettings(BaseSettings):
    """Orchestrator configuration"""
    # API endpoints
    strategy_api_endpoint: str = Field(
        default="http://localhost:8006/strategy-operations",
        env="STRATEGY_API_ENDPOINT"
    )
    risk_analysis_mcp: str = Field(
        default="http://localhost:9001/mcp/",
        env="RISK_ANALYSIS_MCP_URL"
    )
    hypothesis_mcp: str = Field(
        default="http://localhost:9000/mcp/",
        env="HYPOTHESIS_MCP_URL"
    )
    
    # LLM settings
    llm_temperature: float = Field(default=0.7, env="ORCH_LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=4096, env="ORCH_LLM_MAX_TOKENS")
    
    # Search defaults
    default_time_window: str = Field(default="30d", env="ORCH_TIME_WINDOW")
    default_strategy_limit: int = Field(default=5, env="ORCH_STRATEGY_LIMIT")
    max_web_searches: int = Field(default=2, env="ORCH_MAX_WEB_SEARCHES")
    max_synthesis_iterations: int = Field(default=5, env="ORCH_MAX_SYNTHESIS_ITERATIONS")
    
    # Performance thresholds
    min_win_rate: float = Field(default=0.60, env="ORCH_MIN_WIN_RATE")
    min_sharpe_ratio: float = Field(default=1.5, env="ORCH_MIN_SHARPE")
    min_trade_count: int = Field(default=10, env="ORCH_MIN_TRADE_COUNT")
    
    # API timeouts
    strategy_api_search_timeout: int = Field(default=20, env="STRATEGY_API_SEARCH_TIMEOUT")
    strategy_api_backtest_timeout: int = Field(default=30, env="STRATEGY_API_BACKTEST_TIMEOUT")
    web_search_result_length: int = Field(default=1000, env="WEB_SEARCH_RESULT_LENGTH")
    
    class Config:
        env_file = ".env"


# Global settings instances
redis_settings = RedisSettings()
pathway_api_settings = PathwayAPISettings()
hypothesis_api_settings = HypothesisAPISettings()
trading_settings = TradingSettings()
db_settings = DatabaseSettings()
openai_settings = OpenAISettings()
backtesting_settings = BacktestingAPISettings()
backtesting_server_settings = BacktestingServerSettings()
mcp_settings = MCPSettings()
risk_manager_settings = RiskManagerSettings()
orchestrator_settings = OrchestratorSettings()
