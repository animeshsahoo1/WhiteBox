"""
Simple test to publish data to cloud Redis (Upstash)
"""
import os
import json
import redis
from datetime import datetime

# Get Redis URL from environment
REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    print("❌ REDIS_URL not set!")
    exit(1)

print(f"🔗 Connecting to Redis: {REDIS_URL[:50]}...")

# Connect to Redis
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Test 1: Simple key-value
print("\n📝 Test 1: Setting a simple key-value...")
r.set("test:hello", "world")
value = r.get("test:hello")
print(f"✅ Set 'test:hello' = '{value}'")

# Test 2: Store JSON data
print("\n📝 Test 2: Storing JSON data...")
test_data = {
    "symbol": "AAPL",
    "price": 175.50,
    "timestamp": datetime.now().isoformat(),
    "source": "redis_test"
}
r.set("test:stock_data", json.dumps(test_data))
stored = json.loads(r.get("test:stock_data"))
print(f"✅ Stored stock data: {stored}")

# Test 3: Pub/Sub publish
print("\n📝 Test 3: Publishing to Pub/Sub channel 'room:test123'...")
message = {
    "room_id": "test123",
    "type": "test_event",
    "data": {
        "message": "Hello from redis_test!",
        "timestamp": datetime.now().isoformat()
    }
}
r.publish("room:test123", json.dumps(message))
print(f"✅ Published message to 'room:test123'")

# Test 4: List all test keys
print("\n📝 Test 4: Listing all 'test:*' keys...")
keys = r.keys("test:*")
print(f"✅ Found keys: {keys}")

print("\n🎉 All tests passed! Check your Upstash dashboard to see the data.")
