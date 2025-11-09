"""
Quick diagnostic script to test Trading Agents connections
Run this to verify all services are accessible
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("TRADING AGENTS DIAGNOSTIC TEST")
print("=" * 60)

# Test 1: Environment Variables
print("\n1. ENVIRONMENT VARIABLES CHECK")
print("-" * 60)
required_vars = {
    "DATABASE_URL": os.getenv("DATABASE_URL"),
    "MONGODB_URI": os.getenv("MONGODB_URI"),
    "UPSTASH_REDIS_REST_URL": os.getenv("UPSTASH_REDIS_REST_URL"),
    "UPSTASH_REDIS_REST_TOKEN": os.getenv("UPSTASH_REDIS_REST_TOKEN"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "PATHWAY_API_URL": os.getenv("PATHWAY_API_URL", "http://pathway-reports-api:8000"),
}

for var, value in required_vars.items():
    if value:
        masked = value[:20] + "..." if len(value) > 20 else value
        print(f"✅ {var}: {masked}")
    else:
        print(f"❌ {var}: NOT SET")

# Test 2: Redis Connection
print("\n2. REDIS CONNECTION TEST")
print("-" * 60)
try:
    from redis import Redis
    
    upstash_url = os.getenv("UPSTASH_REDIS_REST_URL")
    upstash_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    
    if upstash_url and upstash_token:
        redis_host = upstash_url.replace("https://", "").replace("http://", "")
        redis_url = f"rediss://default:{upstash_token}@{redis_host}:6379"
        
        print(f"Connecting to: {redis_host}:6379")
        redis_conn = Redis.from_url(
            redis_url,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        redis_conn.ping()
        print("✅ Redis connection successful!")
    else:
        print("❌ Redis credentials not set")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")

# Test 3: Pathway API
print("\n3. PATHWAY API CONNECTION TEST")
print("-" * 60)
try:
    import requests
    pathway_url = os.getenv("PATHWAY_API_URL", "http://localhost:8000")
    response = requests.get(f"{pathway_url}/health", timeout=5)
    if response.status_code == 200:
        print(f"✅ Pathway API accessible at {pathway_url}")
    else:
        print(f"⚠️  Pathway API returned status {response.status_code}")
except Exception as e:
    print(f"❌ Pathway API connection failed: {e}")

# Test 4: Database Connection
print("\n4. DATABASE CONNECTION TEST")
print("-" * 60)
try:
    import psycopg2
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        conn = psycopg2.connect(db_url, sslmode="require")
        conn.close()
        print("✅ Database connection successful!")
    else:
        print("❌ DATABASE_URL not set")
except Exception as e:
    print(f"❌ Database connection failed: {e}")

# Test 5: Trading Agents API (if running)
print("\n5. TRADING AGENTS API TEST")
print("-" * 60)
try:
    import requests
    response = requests.get("http://localhost:8001/health", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print("✅ Trading Agents API is running!")
        print(f"   Database connected: {data.get('database_connected')}")
        print(f"   Pathway API connected: {data.get('pathway_api_connected')}")
    else:
        print(f"⚠️  API returned status {response.status_code}")
except Exception as e:
    print(f"❌ Trading Agents API not accessible: {e}")
    print("   Make sure the container is running: docker-compose ps trading-agents-api")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
