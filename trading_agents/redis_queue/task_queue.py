import os
from redis import Redis
from rq import Queue, Retry
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

# Use local Redis server (shared with Pathway)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 1))  # DB 1 for trading agents job queue

# Fallback to Upstash if configured (for backwards compatibility)
redis_url = os.getenv("UPSTASH_REDIS_URL")

if redis_url:
    print(f"[QUEUE] Using Upstash Redis from UPSTASH_REDIS_URL")
    redis_conn = Redis.from_url(redis_url)
else:
    print(f"[QUEUE] Using local Redis at {REDIS_HOST}:{REDIS_PORT} DB {REDIS_DB}")
    redis_conn = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=False)

q = Queue("trade_execution", connection=redis_conn)


def enqueue_trade(symbol: str, use_fallback: bool = False):
    """
    Enqueue job with retry logic.
    execute_trading_workflow will be executed inside worker.
    
    Args:
        symbol: Stock ticker symbol
        use_fallback: Whether to use fallback/sample data if reports unavailable
    
    Returns:
        job_id: The RQ job ID
    """

    trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")

    # Use string path instead of importing the function
    # This prevents loading the entire workflow module at import time
    job = q.enqueue(
        "run_workflow.execute_trading_workflow",
        symbol,
        trade_date,
        use_fallback,
        retry=Retry(max=3),   # automatic retry 3 times
        failure_ttl=86400     # keep failed for 24h
    )

    print(f"[QUEUE] Job {job.id} enqueued for symbol {symbol}")
    return job.id
