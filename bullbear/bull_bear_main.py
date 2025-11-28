"""
Bull-Bear FastAPI Server
Minimal implementation to fetch reports from Pathway API and run bull-bear debate.
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

# Add current directory to path to import bull_bear_graph
sys.path.insert(0, str(Path(__file__).parent))

from bull_bear_graph import run_bull_bear_debate
from facilitator_main import process_debate_stream

# Configuration
PATHWAY_API_URL = os.getenv("PATHWAY_API_URL", "http://host.docker.internal:8000")
PATHWAY_API_URL = "http://host.docker.internal:8000" #MAUNUAL OVERRIDE


app = FastAPI(
    title="Bull-Bear Debate API",
    version="1.0.0",
    description="Fetch reports from Pathway API and run bull-bear debate",
)


class BeginDebateRequest(BaseModel):
    symbol: str
    max_rounds: Optional[int] = 2


class DebateResponse(BaseModel):
    status: str
    symbol: str
    message: str
    rounds_completed: int
    output_file: str
    timestamp: str


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Bull-Bear Debate API",
        "version": "1.0.0",
        "pathway_api": PATHWAY_API_URL,
        "endpoints": {
            "POST /begin_debate": "Start bull-bear debate for a symbol (fetches reports from Pathway)",
            "GET /health": "Health check",
        }
    }


@app.post("/begin_debate", response_model=DebateResponse)
async def begin_debate(request: BeginDebateRequest):
    """
    Begin bull-bear debate for a symbol.
    
    Steps:
    1. Fetch 4 reports from Pathway API
    2. Run bull-bear debate
    3. Save results to debate_points.json
    4. Return summary
    """
    symbol = request.symbol.upper()

    print(f"\n{'='*60}")
    print(f"🎯 Starting debate process for {symbol}")
    print(f"{'='*60}\n")
    
    # Step 1: Fetch reports from Pathway API
    print(f"📡 Fetching reports from Pathway API: {PATHWAY_API_URL}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{PATHWAY_API_URL}/reports/{symbol}")
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch reports from Pathway API: {response.text}"
                )
            
            reports_data = response.json()
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to Pathway API at {PATHWAY_API_URL}: {str(e)}"
        )
    
    # Extract the 4 reports from Pathway API response
    market_report = reports_data.get("market_report", "")
    sentiment_report = reports_data.get("sentiment_report", "")
    news_report = reports_data.get("news_report", "")
    fundamental_report = reports_data.get("fundamental_report", "")
    
    # Validate that we have all reports
    missing_reports = []
    if not market_report:
        missing_reports.append("market")
    if not sentiment_report:
        missing_reports.append("sentiment")
    if not news_report:
        missing_reports.append("news")
    if not fundamental_report:
        missing_reports.append("fundamental")
    
    if missing_reports:
        raise HTTPException(
            status_code=404,
            detail=f"Missing reports for {symbol}: {', '.join(missing_reports)}"
        )
    
    print(f"✅ Successfully fetched all 4 reports for {symbol}")
    print(f"  - Market report: {len(market_report)} chars")
    print(f"  - Sentiment report: {len(sentiment_report)} chars")
    print(f"  - News report: {len(news_report)} chars")
    print(f"  - Fundamental report: {len(fundamental_report)} chars")
    
    # Step 2: Run bull-bear debate
    print(f"\n🎭 Running bull-bear debate (max_rounds={request.max_rounds})...")
    
    try:
        debate_result = run_bull_bear_debate(
            market_report=market_report,
            sentiment_report=sentiment_report,
            news_report=news_report,
            fundamental_report=fundamental_report,
            symbol=symbol,
            max_rounds=request.max_rounds
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during debate execution: {str(e)}"
        )
    
    # Step 3: Trigger facilitator report generation
    print(f"\n{'='*60}")
    print(f"📝 Triggering facilitator report generation...")
    print(f"{'='*60}\n")
    
    try:
        # Convert debate_points.json to jsonlines format for Pathway
        debate_json_path = debate_result["output_file"]
        jsonl_path = debate_json_path.replace(".json", ".jsonl")
        
        with open(debate_json_path, 'r') as f:
            debate_data = json.load(f)
        
        # Rename field for Pathway schema compatibility
        debate_data["full_transcript"] = debate_data.pop("full_debate_transcript", "")
        debate_data["summary"] = json.dumps(debate_data.get("summary", {}))
        
        # Write as jsonlines
        with open(jsonl_path, 'w') as f:
            f.write(json.dumps(debate_data) + '\n')
        
        print(f"✅ Converted debate data to jsonlines format")
        print(f"📄 JSONL file: {jsonl_path}")
        
        # Note: To run Pathway streaming, you would need to call:
        # python facilitator_main.py
        # For now, we just prepare the file
        
        print(f"\n💡 To generate facilitator report, run:")
        print(f"   python facilitator_main.py")
        
    except Exception as e:
        print(f"⚠️  Warning: Could not prepare facilitator input: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Step 4: Return results
    print(f"\n{'='*60}")
    print(f"✅ Complete workflow finished!")
    print(f"📄 Debate points: {debate_result['output_file']}")
    print(f"📄 Facilitator input: debate_points.jsonl")
    print(f"{'='*60}\n")
    
    return DebateResponse(
        status="success",
        symbol=symbol,
        message=f"Bull-bear debate completed for {symbol}. Run facilitator_main.py to generate summary.",
        rounds_completed=debate_result["rounds"],
        output_file=debate_result["output_file"],
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    
    # Check if Pathway API is reachable
    pathway_status = "unknown"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{PATHWAY_API_URL}/health")
            if response.status_code == 200:
                pathway_status = "connected"
            else:
                pathway_status = "error"
    except Exception:
        pathway_status = "unreachable"
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "pathway_api": {
            "url": PATHWAY_API_URL,
            "status": pathway_status
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Bull-Bear Debate API Server")
    print(f"📡 Pathway API: {PATHWAY_API_URL}")
    print(f"🔥 Endpoint: POST /begin_debate")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=2000)
