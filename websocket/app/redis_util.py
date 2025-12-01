import os
import ssl
from redis.asyncio import Redis as AsyncRedis
import redis
from functools import lru_cache

REDIS_DEFAULT_HOST = "redis"
REDIS_DEFAULT_PORT = 6379
REDIS_DEFAULT_DB = 0

@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    """Return a cached Redis client configured via environment variables."""
    url = os.getenv("REDIS_URL")
    if url:
        return redis.Redis.from_url(url, decode_responses=True, ssl_cert_reqs=None)

    host = os.getenv("REDIS_HOST", REDIS_DEFAULT_HOST)
    port = int(os.getenv("REDIS_PORT", str(REDIS_DEFAULT_PORT)))
    db = int(os.getenv("REDIS_DB", str(REDIS_DEFAULT_DB)))

    return redis.Redis(host=host, port=port, db=db, decode_responses=True)

def get_async_redis():
    """Return an async Redis client. Don't cache this - create fresh per connection."""
    url = os.getenv("REDIS_URL")
    
    if url:
        # For Upstash (rediss:// URLs)
        if url.startswith("rediss://"):
            return AsyncRedis.from_url(
                url, 
                decode_responses=True,
                ssl_cert_reqs=ssl.CERT_NONE  # Fix: use ssl.CERT_NONE instead of ssl=True
            )
        else:
            return AsyncRedis.from_url(url, decode_responses=True)
    
    # For local Redis
    host = os.getenv("REDIS_HOST", REDIS_DEFAULT_HOST)
    port = int(os.getenv("REDIS_PORT", str(REDIS_DEFAULT_PORT)))
    db = int(os.getenv("REDIS_DB", str(REDIS_DEFAULT_DB)))

    return AsyncRedis(host=host, port=port, db=db, decode_responses=True)