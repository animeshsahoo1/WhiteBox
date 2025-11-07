import os
from redis import Redis
from rq import Queue, Retry
from dotenv import load_dotenv
from run_workflow import execute_trading_workflow
from datetime import datetime, timezone

load_dotenv()

redis_url = os.getenv("UPSTASH_REDIS_URL")
if not redis_url:
    raise ValueError("UPSTASH_REDIS_URL missing in environment variables")

redis_conn = Redis.from_url(redis_url)
q = Queue("trade_execution", connection=redis_conn)


def enqueue_trade(symbol: str):
    """
    enqueue job with retry logic
    run.py will be executed inside worker
    """

    trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")

    job = q.enqueue(
        execute_trading_workflow,
        symbol,
        trade_date,
        True,  # use_fallback default false
        retry=Retry(max=3),   # automatic retry 3 times
        failure_ttl=86400     # keep failed for 24h
    )

    print(f"[QUEUE] Job {job.id} enqueued for symbol {symbol}")
    return job.id
