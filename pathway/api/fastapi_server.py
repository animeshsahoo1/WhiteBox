"""
FastAPI server to expose current reports from Pathway consumers.
This allows the trading agents to fetch the latest reports for any stock symbol.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import glob
from datetime import datetime

app = FastAPI(title="Pathway Reports API", version="1.0.0")


class ReportsResponse(BaseModel):
    """Response model for all reports of a stock"""
    symbol: str
    fundamental_report: Optional[str] = None
    market_report: Optional[str] = None
    news_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    timestamp: str
    status: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str

class QueryChatBody(BaseModel):
    query: str
    history: List[Message]


def read_report_file(report_path: str) -> Optional[str]:
    """Read a report file and return its content"""
    try:
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    except Exception as e:
        print(f"Error reading report from {report_path}: {e}")
        return None


@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "message": "Pathway Reports API",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/reports/{symbol}": "Get all reports for a stock symbol",
            "/reports/{symbol}/fundamental": "Get fundamental report",
            "/reports/{symbol}/market": "Get market report",
            "/reports/{symbol}/news": "Get news report",
            "/reports/{symbol}/sentiment": "Get sentiment report"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/reports/{symbol}", response_model=ReportsResponse)
async def get_all_reports(symbol: str):
    """
    Get all available reports for a given stock symbol.
    
    Args:
        symbol: Stock ticker symbol (e.g., AAPL, GOOGL, TSLA)
    
    Returns:
        ReportsResponse with all available reports
    """
    symbol = symbol.upper()
    reports_base_dir = "/app/reports"
    
    # Read each report type
    fundamental_path = os.path.join(reports_base_dir, "fundamental", symbol, "fundamental_report.md")
    market_path = os.path.join(reports_base_dir, "market", symbol, "market_report.md")
    news_path = os.path.join(reports_base_dir, "news", symbol, "news_report.md")
    sentiment_path = os.path.join(reports_base_dir, "sentiment", symbol, "sentiment_report.md")
    
    fundamental_report = read_report_file(fundamental_path)
    market_report = read_report_file(market_path)
    news_report = read_report_file(news_path)
    sentiment_report = read_report_file(sentiment_path)
    
    # Check if at least one report exists
    if not any([fundamental_report, market_report, news_report, sentiment_report]):
        raise HTTPException(
            status_code=404,
            detail=f"No reports found for symbol {symbol}. Make sure the symbol is correct and data has been processed."
        )
    
    return ReportsResponse(
        symbol=symbol,
        fundamental_report=fundamental_report,
        market_report=market_report,
        news_report=news_report,
        sentiment_report=sentiment_report,
        timestamp=datetime.utcnow().isoformat(),
        status="success"
    )


@app.get("/reports/{symbol}/fundamental")
async def get_fundamental_report(symbol: str):
    """Get fundamental analysis report for a stock"""
    symbol = symbol.upper()
    reports_base_dir = "/app/reports"
    report_path = os.path.join(reports_base_dir, "fundamental", symbol, "fundamental_report.md")
    
    report = read_report_file(report_path)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Fundamental report not found for symbol {symbol}"
        )
    
    return {
        "symbol": symbol,
        "report_type": "fundamental",
        "content": report,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/reports/{symbol}/market")
async def get_market_report(symbol: str):
    """Get market analysis report for a stock"""
    symbol = symbol.upper()
    reports_base_dir = "/app/reports"
    report_path = os.path.join(reports_base_dir, "market", symbol, "market_report.md")
    
    report = read_report_file(report_path)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Market report not found for symbol {symbol}"
        )
    
    return {
        "symbol": symbol,
        "report_type": "market",
        "content": report,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/reports/{symbol}/news")
async def get_news_report(symbol: str):
    """Get news analysis report for a stock"""
    symbol = symbol.upper()
    reports_base_dir = "/app/reports"
    report_path = os.path.join(reports_base_dir, "news", symbol, "news_report.md")
    
    report = read_report_file(report_path)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"News report not found for symbol {symbol}"
        )
    
    return {
        "symbol": symbol,
        "report_type": "news",
        "content": report,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/reports/{symbol}/sentiment")
async def get_sentiment_report(symbol: str):
    """Get sentiment analysis report for a stock"""
    symbol = symbol.upper()
    reports_base_dir = "/app/reports"
    report_path = os.path.join(reports_base_dir, "sentiment", symbol, "sentiment_report.md")
    
    report = read_report_file(report_path)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"Sentiment report not found for symbol {symbol}"
        )
    
    return {
        "symbol": symbol,
        "report_type": "sentiment",
        "content": report,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/available-symbols")
async def get_available_symbols():
    """
    Get list of all stock symbols that have at least one report available.
    """
    reports_base_dir = "/app/reports"
    symbols = set()
    
    # Check all report types
    for report_type in ["fundamental", "market", "news", "sentiment"]:
        type_dir = os.path.join(reports_base_dir, report_type)
        if os.path.exists(type_dir):
            # Get all subdirectories (each represents a symbol)
            for item in os.listdir(type_dir):
                item_path = os.path.join(type_dir, item)
                if os.path.isdir(item_path) and item.isupper():
                    symbols.add(item)
    
    return {
        "symbols": sorted(list(symbols)),
        "count": len(symbols),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/get_graph_report/{graph_id}")
async def get_graph_report(
    graph_id: str,
    report_type: str,  # trader,bull,bear,risk_manager
):
    """
    Get reports for a given graph_id
    If report_type not passed -> return ALL reports
    """
    
    # retrieval logic based on report_type....
        
    
    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"reports not found for graph_id {graph_id}"
        )
    
    return {
        "graph_id": graph_id,
        "requested_type": report_type,
        "content": report,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/get_portfolio_details/{user_id}")
async def get_portfolio_details(user_id: str):
    """
    Get portfolio details of a given user
    """

    # retrieval logic here....
    # portfolio = await fetch_portfolio(user_id)

    if not portfolio:
        raise HTTPException(
            status_code=404,
            detail=f"portfolio not found for user_id {user_id}"
        )

    # example return structure (same as you showed)
    return {
        "user_id": user_id,
        "total_value": portfolio.total_value,
        "cash_balance": portfolio.cash_balance,
        "holdings": portfolio.holdings,     #get holdings dict from holdings table by querying with user_id
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/query_chat_bot/{graph_id}")
async def query_chat_bot(
    graph_id: str,
    body: QueryChatBody  # <-- this is your req.body
):
    history=body.history
    query=body.query
    
    # do processing here ....
    # response = await run_chain(graph_id, body.query, body.history)

    return {
        "graph_id": graph_id,
        "query": body.query,
        "history": body.history,
        "response": "generated response goes here",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/get_arena_summary/{arena_id}")
async def get_arena_summary(arena_id: str):
    """
    Get summary stats + leaderboard of an Arena
    """

    # retrieval logic...
    # summary = await fetch_arena_summary(arena_id)

    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"arena summary not found for arena_id {arena_id}"
        )

    return {
        "arena_id": arena_id,
        "total_agents": summary.total_agents,
        "total_trades": summary.total_trades,
        "symbols_traded": summary.symbols_traded, # list of symbols or coins traded ex:[BTC,ETH,SOL]
        "total_volume_usd": summary.total_volume_usd,
        "start_time": summary.start_time,
        "last_update": summary.last_update,
        "leaderboard": summary.leaderboard,   # list of agents leaderboard items
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/get_arena_feed/{arena_id}")
async def get_arena_feed(arena_id: str):
    """
    Get the event feed for a given arena
    """

    # retrieval logic here....
    # feed = await fetch_arena_events(arena_id)

    if not feed:
        raise HTTPException(
            status_code=404,
            detail=f"arena feed not found for arena_id {arena_id}"
        )

    return {
        "arena_id": arena_id,
        "events": feed,   # feed should be a list of event dicts
        "timestamp": datetime.utcnow().isoformat()
    }

async def get_agent_trades(agent_id: str):
    """
    Get all trades executed by a specific agent
    """

    # retrieval logic here
    # agent_data = await fetch_agent_trades(agent_id)

    if not agent_data:
        raise HTTPException(
            status_code=404,
            detail=f"trades not found for agent_id {agent_id}"
        )

    return {
        "agent_id": agent_id,
        "agent_name": agent_data.agent_name,
        "trades": agent_data.trades,     # list of trade record dicts
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/get_agent_stats/{agent_id}")
async def get_agent_stats(agent_id: str):
    """
    Get performance stats summary for a single agent
    """

    # retrieval logic
    # stats = await fetch_agent_stats(agent_id)

    if not stats:
        raise HTTPException(
            status_code=404,
            detail=f"agent stats not found for agent_id {agent_id}"
        )

    return {
        "agent_id": agent_id,
        "agent_name": stats.agent_name,
        "model": stats.model,
        "starting_balance": stats.starting_balance,
        "current_balance": stats.current_balance,
        "roi": stats.roi,
        "total_trades": stats.total_trades,
        "win_rate": stats.win_rate,
        "avg_holding_time": stats.avg_holding_time,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/get_top_companies")
async def get_top_companies(sector: str = Query(...)):
    """
    Get top rated companies in a given sector to show in the leaderboard in frontend
    """

    # retrieval logic here...
    # companies = await fetch_top_companies_by_sector(sector)

    if not companies:
        raise HTTPException(
            status_code=404,
            detail=f"no top companies found for sector {sector}"
        )

    return {
        "sector": sector,
        "top_companies": companies,
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
