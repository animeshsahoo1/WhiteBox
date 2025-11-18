"""Hypothesis Generator using Pathway"""

import pathway as pw
from pathway.xpacks.llm.llms import OpenAIChat
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import requests
from pydantic import Field
import redis

from loguru import logger
from ..config.settings import (
    openai_settings, 
    redis_settings, 
    pathway_api_settings,
    trading_settings,
    mcp_settings
)
from pathway.xpacks.llm.mcp_server import McpServable, McpServer, PathwayMcp

# Set Pathway license key from config
if trading_settings.pathway_license_key:
    pw.set_license_key(trading_settings.pathway_license_key)

logger = logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS (UDFs)
# ============================================================================

@pw.udf
def prepare_llm_messages(
    news: str,
    sentiment: str,
    fundamental: str,
    market: str,
    facilitator: str
) -> list:
    """
    Prepare messages for LLM in OpenAI chat format
    
    Args:
        news: News report content
        sentiment: Sentiment analysis report
        fundamental: Fundamental analysis report
        market: Market report
        facilitator: Facilitator assessment report
    
    Returns:
        List of messages in OpenAI chat format
    """
    
    system_message = """You are a senior quantitative analyst at a hedge fund. Your task is to synthesize market intelligence reports and generate exactly 5 distinct, actionable market hypotheses ranked by confidence.

For each hypothesis, you must provide:
1. **Statement**: Clear, specific hypothesis about market direction, opportunity, or risk
2. **Confidence**: 0.0 - 1.0 (based on evidence strength)
3. **Supporting Evidence**: 3-5 bullet points citing specific data from reports
4. **Risk Factors**: Potential invalidation conditions
5. **Time Horizon**: Short-term (1-7 days), Medium-term (1-4 weeks), Long-term (1-3 months)
6. **Recommended Action**: BUY, SELL, or HOLD

Return ONLY valid JSON in this exact format:
```json
[
  {
    "rank": 1,
    "statement": "Due to CEO insider buying of 500K shares, stock likely to rally 5-8% in next 2 weeks",
    "confidence": 0.85,
    "supporting_evidence": [
      "CEO purchased 500K shares at $50.25 (10% above current price)",
      "Sentiment score improved to +0.65 from +0.32",
      "Volume spiked 200% above 30-day average"
    ],
    "risk_factors": [
      "Broader market downturn",
      "Negative earnings surprise"
    ],
    "time_horizon": "medium_term",
    "recommended_action": "BUY"
  }
]
```

Ensure hypotheses are:
- Specific and actionable
- Backed by concrete data from reports
- Non-overlapping (cover different aspects)
- Ranked by confidence (highest first)"""
    
    user_message = f"""Based on the following market intelligence reports, generate exactly 5 distinct, actionable market hypotheses ranked by confidence.

**News Report:**
{news}

**Sentiment Analysis:**
{sentiment}

**Fundamental Analysis:**
{fundamental}

**Market Report:**
{market}

**Facilitator Assessment:**
{facilitator}

---

Provide your analysis as a JSON array of exactly 5 hypotheses."""
    
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message},
    ]


@pw.udf
def extract_hypotheses(response: str) -> list:
    """
    Extract and parse hypotheses from LLM response
    
    Args:
        response: LLM response string
    
    Returns:
        List of hypothesis dictionaries
    """
    
    try:
        content = response
        
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()
        
        # Validate JSON
        hypotheses = json.loads(json_str)
        
        if not isinstance(hypotheses, list):
            logger.warning(f"Invalid hypothesis format: not a list")
            return []
        
        if len(hypotheses) != 5:
            logger.warning(f"Invalid hypothesis count: {len(hypotheses)}, expected 5")
        
        logger.info(f"Extracted {len(hypotheses)} hypotheses")
        return hypotheses
        
    except Exception as e:
        logger.error(f"Failed to extract hypotheses: {e}")
        return []


@pw.udf
def fetch_other_reports(symbol: str, api_base: str) -> Dict[str, str]:
    """
    Fetch all other reports (news, sentiment, fundamental, market)
    when facilitator report changes
    """
    try:
        url = f"{api_base}/reports/{symbol}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract only the reports we need (exclude facilitator)
        return {
            "news_report": data.get("news_report", ""),
            "sentiment_report": data.get("sentiment_report", ""),
            "fundamental_report": data.get("fundamental_report", ""),
            "market_report": data.get("market_report", "")
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch other reports for {symbol}: {e}")
        return {
            "news_report": "",
            "sentiment_report": "",
            "fundamental_report": "",
            "market_report": ""
        }
    except Exception as e:
        logger.error(f"Unexpected error fetching reports: {e}")
        return {
            "news_report": "",
            "sentiment_report": "",
            "fundamental_report": "",
            "market_report": ""
        }


@pw.udf
def extract_field(reports_dict: dict, field: str) -> str:
    """Extract a specific field from reports dictionary"""
    if isinstance(reports_dict, dict):
        return reports_dict.get(field, "")
    return ""


@pw.udf
def create_report_dict(
    hypotheses: list,
    timestamp: str
) -> dict:
    """Create the final report dictionary for caching"""
    return {
        "hypotheses": hypotheses,
        "hypothesis_count": len(hypotheses),
        "generated_at": datetime.utcnow().isoformat(),
        "timestamp": timestamp
    }



class HypothesisGenerator:
    """
    Generates market hypotheses from Phase 1 reports using LLM
    
    - Watches ONLY facilitator report for changes (efficient polling)
    - Fetches other reports on-demand when facilitator changes
    - Auto-regenerates hypotheses when facilitator report updates
    - Caches latest hypotheses in Redis (no expiration)
    - Serves cached hypotheses via REST API
    """
    
    def __init__(
        self, 
        symbol: str = None,
        pathway_api_host: str = None,
        pathway_api_port: int = None,
        redis_host: str = None,
        redis_port: int = None,
        redis_db: int = None
    ):
        # Use config settings as defaults
        self.symbol = symbol or trading_settings.symbol
        pathway_host = pathway_api_host or pathway_api_settings.host
        pathway_port = pathway_api_port or pathway_api_settings.port
        self.pathway_api_base = f"http://{pathway_host}:{pathway_port}"
        
        # Only watch facilitator report endpoint
        self.facilitator_url = f"{self.pathway_api_base}/reports/{self.symbol}/facilitator"
        
        # LLM for hypothesis generation
        self.llm = OpenAIChat(
            model=openai_settings.model_hypothesis,
            api_key=openai_settings.api_key,
            temperature=openai_settings.temperature,
            max_tokens=openai_settings.max_tokens
        )
        
        # Redis for caching latest hypotheses (no expiration)
        redis_host = redis_host or redis_settings.host
        redis_port = redis_port or redis_settings.port
        redis_db = redis_db if redis_db is not None else redis_settings.db
        
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )
        
        logger.info(f"Hypothesis Generator initialized for {self.symbol}")
        logger.info(f"Watching facilitator endpoint: {self.facilitator_url}")
    
    def create_pipeline(self):
        """Create Pathway pipeline for streaming hypothesis generation"""
        
        # 1. STREAMING INPUT: Poll ONLY facilitator report endpoint
        # This is the trigger - only regenerate when facilitator changes

        facilitator_stream = pw.io.http.read(
            url=self.facilitator_url,
            format="json",
            autocommit_duration_ms=1000,  # Check every second
        )
        
        # 2. Get the latest facilitator report (deduplication)
        latest_facilitator = facilitator_stream.reduce(
            content=pw.reducers.latest(pw.this.content),
            last_updated=pw.reducers.latest(pw.this.last_updated),
            timestamp=pw.reducers.latest(pw.this.timestamp),
            symbol=self.symbol,
            pathway_api_base=self.pathway_api_base
        )
        
        # 3. When facilitator changes, fetch ALL other reports
        all_reports = latest_facilitator.select(
            facilitator=pw.this.content,
            facilitator_updated=pw.this.last_updated,
            other_reports=fetch_other_reports(
                pw.this.symbol,
                pw.this.pathway_api_base
            ),
            timestamp=pw.this.timestamp
        )
        
        # 4. Extract individual reports from fetched data
        reports = all_reports.select(
            facilitator=pw.this.facilitator,
            facilitator_updated=pw.this.facilitator_updated,
            news=extract_field(pw.this.other_reports, "news_report"),
            sentiment=extract_field(pw.this.other_reports, "sentiment_report"),
            fundamental=extract_field(pw.this.other_reports, "fundamental_report"),
            market=extract_field(pw.this.other_reports, "market_report"),
            timestamp=pw.this.timestamp
        )
        
        # 5. Prepare LLM messages
        messages_table = reports.select(
            facilitator=pw.this.facilitator,
            facilitator_updated=pw.this.facilitator_updated,
            timestamp=pw.this.timestamp,
            messages=prepare_llm_messages(
                pw.this.news,
                pw.this.sentiment,
                pw.this.fundamental,
                pw.this.market,
                pw.this.facilitator
            )
        )
        
        # 6. Generate hypotheses via LLM (only runs when facilitator report changes)
        llm_responses = messages_table.select(
            facilitator=pw.this.facilitator,
            facilitator_updated=pw.this.facilitator_updated,
            timestamp=pw.this.timestamp,
            response=self.llm(pw.this.messages)
        )
        
        # 7. Extract and parse hypotheses from LLM response
        parsed_responses = llm_responses.select(
            symbol=self.symbol,
            facilitator=pw.this.facilitator,
            facilitator_updated=pw.this.facilitator_updated,
            timestamp=pw.this.timestamp,
            hypotheses_list=extract_hypotheses(pw.this.response)
        )
        
        # 8. Format final hypothesis report
        hypothesis_reports = parsed_responses.select(
            symbol=pw.this.symbol,
            facilitator_report=pw.this.facilitator,
            facilitator_updated_at=pw.this.facilitator_updated,
            hypotheses=pw.this.hypotheses_list,
            generated_at=datetime.utcnow().isoformat(),
            timestamp=pw.this.timestamp,
            report_data=create_report_dict(
                pw.this.hypotheses_list,
                pw.this.timestamp
            )
        )
        
        # 9. CACHE TO REDIS: Write to Redis whenever new hypotheses are generated
        # NO EXPIRATION - hypotheses persist indefinitely
        pw.io.subscribe(
            hypothesis_reports,
            on_change=self._cache_hypothesis_to_redis
        )
        
        logger.info("Hypothesis generation pipeline created (streaming mode)")
        logger.info("Watching for facilitator report changes...")
        return hypothesis_reports
    
    @staticmethod
    def _cache_hypothesis_to_redis(self, key, row: dict, time: int, is_addition: bool):
        """Cache latest hypothesis report to Redis (no expiration)"""
        if not is_addition:
            logger.info(f"Hypothesis deleted for {self.symbol} (removal detected)")
            return
        
        try:
            report_data = row.get('report_data', {})
            redis_key = f"hypotheses:{self.symbol}"
            
            # Store as JSON with NO EXPIRATION (ex parameter removed)
            self.redis_client.set(
                redis_key,
                json.dumps(report_data)
                # No 'ex' parameter = never expires
            )
            
            # Track symbols with hypotheses
            self.redis_client.sadd("hypotheses:symbols", self.symbol)
            
            # Store metadata for monitoring
            metadata_key = f"hypotheses:{self.symbol}:metadata"
            self.redis_client.hset(
                metadata_key,
                mapping={
                    "last_updated": datetime.utcnow().isoformat(),
                    "facilitator_updated_at": row.get('facilitator_updated_at', ''),
                    "hypothesis_count": len(report_data.get('hypotheses', []))
                }
            )
            
            logger.info(
                f"✅ Cached hypotheses for {self.symbol} to Redis "
                f"(count: {len(report_data.get('hypotheses', []))})"
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to cache hypotheses to Redis: {e}")


# ============================================================================
# MAIN RUNNERS
# ============================================================================
    
logger.info(f"🚀 Starting Hypothesis Generator for {trading_settings.symbol}")
logger.info(f"👁️  Watching facilitator report endpoint only")
logger.info(f"💾 Hypotheses will be cached in Redis (no expiration)")

generator = HypothesisGenerator()
hypothesis = generator.create_pipeline()



class ValueRequestSchema(pw.Schema):
    pass


class HypothesesResource(McpServable):

    def get_hypothesis(self, empty_row: pw.Table) -> pw.Table:
        """
        Return hypothesis
        """


        single_cell_table = hypothesis.reduce(
            report_data=pw.reducers.latest(pw.this.report_data),
        )
        results = empty_row.join_left(single_cell_table, id=empty_row.id).select(
            report_data=pw.right.report_data
        )
        results = results.select(
            result=pw.if_else(
                pw.this.report_data.is_none(),
                "No report available",
                pw.this.report_data
            )
        )
        return results

    def register_mcp(self, server: McpServer):
        server.tool(
            "get_hypothesis",
            request_handler=self.get_hypothesis,
            schema=ValueRequestSchema,
        )


function_to_serve = HypothesesResource()

pathway_mcp_server = PathwayMcp(
    name="Streamable MCP Server",
    transport="streamable-http",
    host=mcp_settings.host,
    port=mcp_settings.port,
    serve=[function_to_serve],
)

pw.run(
    monitoring_level=pw.MonitoringLevel.NONE,
    terminate_on_error=False,
)
