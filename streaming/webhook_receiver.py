"""
Webhook receiver for Twitter data from TwitterAPI.io
This receives real-time tweets and stores them for the sentiment producer to fetch
"""
import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from collections import deque
import threading
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# In-memory storage for recent tweets (max 1000 per stock)
tweet_buffer = {
    'AAPL': deque(maxlen=1000),
    'GOOGL': deque(maxlen=1000),
    'TSLA': deque(maxlen=1000),
    'NVDA': deque(maxlen=1000),
}

# Thread lock for safe access
buffer_lock = threading.Lock()

# Mapping of rule tags to stocks
RULE_TAG_TO_STOCK = {
    'AAPL_sentiment': 'AAPL',
    'GOOGL_sentiment': 'GOOGL',
    'TSLA_sentiment': 'TSLA',
    'NVDA_sentiment': 'NVDA',
}

@app.route('/webhook/twitter', methods=['GET', 'POST'])
def receive_tweet():
    """Receive tweet from TwitterAPI.io webhook"""
    
    # Handle GET requests (TwitterAPI.io verification)
    if request.method == 'GET':
        print("✅ Received GET request (verification) - returning 200")
        return jsonify({
            "status": "ok",
            "message": "Webhook endpoint is ready",
            "service": "Twitter Webhook Receiver"
        }), 200
    
    # Handle POST requests (actual tweets)
    try:
        data = request.get_json()
        
        print(f"\n{'='*70}")
        print(f"🐦 Received Twitter webhook data")
        print(f"{'='*70}")
        print(f"Data: {json.dumps(data, indent=2)[:500]}...")
        
        # TwitterAPI.io webhook format:
        # {
        #   "event_type": "tweet",
        #   "rule_id": "rule_12345",
        #   "rule_tag": "elon_tweets",
        #   "tweets": [...],
        #   "timestamp": 1642789123456
        # }
        
        event_type = data.get('event_type', 'tweet')
        rule_tag = data.get('rule_tag', '')
        tweets = data.get('tweets', [])
        
        if event_type != 'tweet':
            print(f"⚠️  Ignoring event type: {event_type}")
            return jsonify({"status": "ignored", "reason": f"event_type is {event_type}"}), 200
        
        # Determine which stock from rule_tag (e.g., "AAPL_sentiment" -> "AAPL")
        stock = RULE_TAG_TO_STOCK.get(rule_tag, 'UNKNOWN')
        
        if stock == 'UNKNOWN' and rule_tag:
            # Try to extract stock from rule_tag (e.g., "AAPL_sentiment")
            parts = rule_tag.split('_')
            if parts and parts[0].upper() in ['AAPL', 'GOOGL', 'TSLA', 'NVDA']:
                stock = parts[0].upper()
                RULE_TAG_TO_STOCK[rule_tag] = stock  # Cache it
        
        if stock == 'UNKNOWN':
            print(f"⚠️  Unknown rule_tag: {rule_tag}")
            return jsonify({"status": "ignored", "reason": "unknown rule_tag"}), 200
        
        print(f"📊 Processing {len(tweets)} tweets for {stock} (rule: {rule_tag})")
        
        if stock in tweet_buffer:
            stored_count = 0
            with buffer_lock:
                for tweet in tweets:
                    # Add metadata
                    tweet['received_at'] = datetime.utcnow().isoformat()
                    tweet['rule_tag'] = rule_tag
                    tweet['stock_symbol'] = stock
                    
                    # Avoid duplicates by checking tweet ID
                    existing_ids = [t.get('id') for t in tweet_buffer[stock]]
                    if tweet.get('id') not in existing_ids:
                        tweet_buffer[stock].append(tweet)
                        stored_count += 1
            
            print(f"✅ Stored {stored_count}/{len(tweets)} tweets for {stock} (buffer size: {len(tweet_buffer[stock])})")
            return jsonify({
                "status": "success",
                "stock": stock,
                "stored": stored_count,
                "total_received": len(tweets),
                "buffer_size": len(tweet_buffer[stock])
            }), 200
        else:
            print(f"⚠️  Stock {stock} not in buffer")
            return jsonify({"status": "ignored", "reason": "stock not tracked"}), 200
            
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/tweets/<stock>', methods=['GET'])
def get_tweets(stock):
    """Get buffered tweets for a stock"""
    stock = stock.upper()
    
    if stock not in tweet_buffer:
        return jsonify({"error": f"Stock {stock} not tracked"}), 404
    
    with buffer_lock:
        tweets = list(tweet_buffer[stock])
        # Clear buffer after reading
        tweet_buffer[stock].clear()
    
    return jsonify({
        "stock": stock,
        "count": len(tweets),
        "tweets": tweets
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    with buffer_lock:
        buffer_status = {stock: len(tweets) for stock, tweets in tweet_buffer.items()}
    
    return jsonify({
        "status": "healthy",
        "buffer_sizes": buffer_status
    }), 200

@app.route('/', methods=['GET', 'POST'])
def root():
    """Root endpoint for testing and TwitterAPI.io webhook verification"""
    if request.method == 'POST':
        # Check if this is a TwitterAPI.io test webhook
        data = request.get_json()
        if data and data.get('event_type') == 'test_webhook_url':
            print("✅ Received TwitterAPI.io test webhook - returning 200")
            return jsonify({
                "status": "success",
                "message": "Webhook test successful",
                "service": "Twitter Webhook Receiver"
            }), 200
        
        # Otherwise, treat as a regular webhook
        return receive_tweet()
    
    return jsonify({
        "service": "Twitter Webhook Receiver",
        "endpoints": {
            "webhook": "/webhook/twitter (POST)",
            "get_tweets": "/tweets/<stock> (GET)",
            "health": "/health (GET)"
        }
    }), 200

if __name__ == '__main__':
    port = int(os.getenv('WEBHOOK_RECEIVER_PORT', '5001'))
    print("\n" + "="*70)
    print("🚀 Twitter Webhook Receiver Starting")
    print("="*70)
    print(f"Port: {port}")
    print(f"Webhook URL: http://localhost:{port}/webhook/twitter")
    print(f"Or use ngrok/webhook.site to expose publicly")
    print("="*70 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=True)
