import sys
sys.path.append("/app")

import os
from redis import Redis
from rq import Worker, Queue
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("UPSTASH_REDIS_URL")
if not redis_url:
    raise ValueError("UPSTASH_REDIS_URL missing in environment variables. Please set it in your .env file.")

print(f"[WORKER] Connecting to Redis...")
redis_conn = Redis.from_url(redis_url)

queue_list = [Queue("trade_execution", connection=redis_conn)]

if __name__ == "__main__":
    print("[WORKER] Starting RQ worker listening for trade_execution jobs...")
    print(f"[WORKER] Redis URL: {redis_url[:20]}...")
    worker = Worker(queue_list, connection=redis_conn)
    worker.work()
