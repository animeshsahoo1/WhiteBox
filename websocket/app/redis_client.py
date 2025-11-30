#redis_client.py
from dotenv import load_dotenv
from app.redis_util import get_redis_client

load_dotenv()

redis_sync = get_redis_client()