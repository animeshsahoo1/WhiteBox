
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from redis.asyncio import Redis

# Load .env from parent directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

async def monitor_redis():
    redis_url = os.getenv('REDIS_URL')
    
    if redis_url:
        # Use URL (Upstash)
        redis = Redis.from_url(
            redis_url, 
            decode_responses=True,
            ssl_cert_reqs=None  # Important for Upstash SSL
        )
        print(f"🔗 Connected to Upstash Redis")
    else:
        # Fallback to local
        redis = Redis(host='redis', port=6379, decode_responses=True)
        print(f"🔗 Connected to local Redis")
    
    pubsub = redis.pubsub()
    await pubsub.psubscribe("room:*", "alerts", "reports", "strategy:updates", "user:*")
    print("🔍 Monitoring room:*, alerts, reports, strategy:updates, user:*...")
    
    try:
        async for message in pubsub.listen():
            if message['type'] == 'pmessage':
                print(f"📩 {message['channel']}: {message['data']}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await redis.close()

if __name__ == "__main__":
    asyncio.run(monitor_redis())