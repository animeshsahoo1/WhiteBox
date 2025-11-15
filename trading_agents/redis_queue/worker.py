import sys
sys.path.append("/app")

import os
from redis import Redis
from rq import Worker, Queue
from dotenv import load_dotenv

load_dotenv()

# Use local Redis server (shared with Pathway)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 1))  # DB 1 for trading agents job queue

# Fallback to Upstash if configured (for backwards compatibility)
redis_url = os.getenv("UPSTASH_REDIS_URL")

if redis_url:
    print(f"[WORKER] Using Upstash Redis from UPSTASH_REDIS_URL")
    redis_conn = Redis.from_url(redis_url)
else:
    print(f"[WORKER] Using local Redis at {REDIS_HOST}:{REDIS_PORT} DB {REDIS_DB}")
    redis_conn = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=False)

queue_list = [Queue("analysis_execution", connection=redis_conn)]

if __name__ == "__main__":
    print("[WORKER] Starting RQ worker listening for analysis_execution jobs...")
    worker = Worker(queue_list, connection=redis_conn)
    worker.work()
