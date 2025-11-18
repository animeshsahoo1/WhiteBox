"""Configuration settings for Phase 2"""

import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings


class KafkaSettings(BaseSettings):
    """Kafka configuration"""
    bootstrap_servers: str = Field(default="kafka:9092", env="KAFKA_BOOTSTRAP_SERVERS")
    security_protocol: str = Field(default="PLAINTEXT", env="KAFKA_SECURITY_PROTOCOL")
    
    # Phase 1 input topics
    topic_news_reports: str = "phase1.news_reports"
    topic_sentiment_reports: str = "phase1.sentiment_reports"
    topic_fundamental_reports: str = "phase1.fundamental_reports"
    topic_market_reports: str = "phase1.market_reports"
    topic_facilitator_reports: str = "phase1.facilitator_reports"
    topic_market_data: str = "phase1.market_data"
    
    # Phase 2 output topics
    topic_hypotheses: str = "phase2.hypotheses"
    topic_market_conditions: str = "phase2.market_conditions"
    
    # Consumer group
    consumer_group: str = "phase2-hypothesis-generator"
    
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


class MCPSettings(BaseSettings):
    """MCP Server configuration"""
    host: str = Field(default="localhost", env="MCP_HOST")
    port: int = Field(default=8080, env="MCP_PORT")
    
    @property
    def server_url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    class Config:
        env_file = ".env"


# Global settings instances
kafka_settings = KafkaSettings()
db_settings = DatabaseSettings()
openai_settings = OpenAISettings()
backtesting_settings = BacktestingAPISettings()
mcp_settings = MCPSettings()
