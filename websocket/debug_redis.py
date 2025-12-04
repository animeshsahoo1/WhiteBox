# import asyncio
# from redis.asyncio import Redis
#debug redis ran through docker-compose
# async def monitor_redis():
#     redis = Redis(host='redis', port=6379, decode_responses=True)
#     pubsub = redis.pubsub()
#     await pubsub.psubscribe('room:*')
    
#     print("🔍 Monitoring all room:* channels...")
#     async for message in pubsub.listen():
#         if message['type'] == 'pmessage':
#             print(f"📩 {message['channel']}: {message['data']}")

# asyncio.run(monitor_redis())

# debug upstash redis
# docker-compose exec fastapi-app python debug_redis.py

import asyncio
import os
from redis.asyncio import Redis

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
    await pubsub.psubscribe("room:*", "alerts", "reports")
    print("🔍 Monitoring room:*, alerts, reports...")
    
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