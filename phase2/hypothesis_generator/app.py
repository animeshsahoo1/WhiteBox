from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import redis
from datetime import datetime
import json
from loguru import logger
import uvicorn

app = FastAPI(
    title="Hypothesis Query API",
    version="1.0.0",
    description="Serves latest AI-generated market hypotheses from Redis cache"
)

# Redis client for reading cached hypotheses
redis_client = redis.Redis(
    host="localhost",
    port=9004,
    db=0,
    decode_responses=True
)


class HypothesisMetadata(BaseModel):
    last_updated: str
    facilitator_updated_at: str
    hypothesis_count: int


class HypothesisResponse(BaseModel):
    symbol: str
    facilitator_report: str
    facilitator_updated_at: str
    hypotheses: List[str]
    hypothesis_count: int
    generated_at: str
    timestamp: str


@app.get("/")
async def root():
    """API information"""
    return {
        "service": "Hypothesis Query API",
        "version": "1.0.0",
        "description": "Serves latest market hypotheses generated from facilitator reports",
        "endpoints": [
            "GET /health - Health check and cache statistics",
            "GET /symbols - List symbols with cached hypotheses",
            "GET /hypotheses/{symbol} - Get latest hypotheses for a symbol",
            "GET /hypotheses/{symbol}/metadata - Get metadata about cached hypotheses"
        ],
        "note": "Hypotheses are cached indefinitely until new facilitator report triggers regeneration"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with cache statistics"""
    try:
        redis_client.ping()
        symbols = redis_client.smembers("hypotheses:symbols")
        
        # Get metadata for each symbol
        symbol_info = {}
        for symbol in symbols:
            metadata_key = f"hypotheses:{symbol}:metadata"
            metadata = redis_client.hgetall(metadata_key)
            if metadata:
                symbol_info[symbol] = metadata
        
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "cached_symbols": sorted(list(symbols)),
            "count": len(symbols),
            "symbol_metadata": symbol_info,
            "redis_connected": True
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service unavailable: {str(e)}"
        )


@app.get("/symbols")
async def list_symbols():
    """List all symbols with cached hypotheses"""
    try:
        symbols = redis_client.smembers("hypotheses:symbols")
        
        # Get metadata for each
        symbols_with_info = []
        for symbol in sorted(symbols):
            metadata_key = f"hypotheses:{symbol}:metadata"
            metadata = redis_client.hgetall(metadata_key)
            
            symbols_with_info.append({
                "symbol": symbol,
                "last_updated": metadata.get("last_updated", "unknown"),
                "hypothesis_count": int(metadata.get("hypothesis_count", 0))
            })
        
        return {
            "symbols": symbols_with_info,
            "count": len(symbols),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/hypotheses/{symbol}", response_model=HypothesisResponse)
async def get_hypotheses(symbol: str):
    """Get latest cached hypotheses for a symbol"""
    try:
        redis_key = f"hypotheses:{symbol.upper()}"
        cached_data = redis_client.get(redis_key)
        
        if not cached_data:
            raise HTTPException(
                status_code=404,
                detail=f"No hypotheses found for symbol {symbol.upper()}. "
                       f"The generator may not be running for this symbol."
            )
        
        return json.loads(cached_data)
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Failed to parse cached hypothesis data"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/hypotheses/{symbol}/metadata", response_model=HypothesisMetadata)
async def get_hypothesis_metadata(symbol: str):
    """Get metadata about cached hypotheses for a symbol"""
    try:
        metadata_key = f"hypotheses:{symbol.upper()}:metadata"
        metadata = redis_client.hgetall(metadata_key)
        
        if not metadata:
            raise HTTPException(
                status_code=404,
                detail=f"No metadata found for symbol {symbol.upper()}"
            )
        
        return {
            "last_updated": metadata.get("last_updated", "unknown"),
            "facilitator_updated_at": metadata.get("facilitator_updated_at", "unknown"),
            "hypothesis_count": int(metadata.get("hypothesis_count", 0))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    """Run the query API server (separate process)"""
    
    logger.info("🌐 Starting Hypothesis Query API on port 8002")
    logger.info("📚 Hypotheses cached indefinitely until facilitator report changes")
    uvicorn.run(app, host="0.0.0.0", port=8002)
