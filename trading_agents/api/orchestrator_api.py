import sys
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from all_agents.orchestrator.orchestrator_agent import run_orchestrator

load_dotenv()

app = FastAPI(title="Orchestrator Agent API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class QueryRequest(BaseModel):
    query: str
    symbol: str = "AAPL"

class QueryResponse(BaseModel):
    query: str
    symbol: str
    answer: str
    timestamp: str

@app.get("/health")
async def health():
    return {"status": "ok", "service": "orchestrator-agent", "timestamp": datetime.utcnow().isoformat()}

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    try:
        answer = run_orchestrator(request.query, request.symbol)
        return QueryResponse(query=request.query, symbol=request.symbol, answer=answer, timestamp=datetime.utcnow().isoformat())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7002)
