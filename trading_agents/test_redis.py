from redis import Redis
import os

url = os.getenv("UPSTASH_REDIS_URL")
print("URL:", url)

r = Redis.from_url(url, ssl=True, socket_timeout=5, socket_connect_timeout=5)

try:
    print("PING:", r.ping())
except Exception as e:
    print("Error:", e)
