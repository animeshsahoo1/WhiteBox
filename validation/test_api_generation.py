#!/usr/bin/env python3
"""
API Strategy Generation Test

Tests the /backtesting/generate-strategy API endpoint with various prompts
to verify the LLM can generate valid, working strategies.
"""

import requests
import json
import time

API_BASE_URL = "http://localhost:8000"

# Test prompts - same ones used to create validation strategies
TEST_PROMPTS = [
    {
        "name": "SMA Crossover",
        "prompt": "Create a simple SMA crossover strategy: buy when SMA 20 crosses above SMA 50, sell when it crosses below. Use 1d interval and 2y lookback.",
        "expected_indicators": ["sma_20", "sma_50"]
    },
    {
        "name": "EMA Crossover", 
        "prompt": "Create an EMA crossover strategy: buy when EMA 9 crosses above EMA 12, sell when it crosses below. Use 1h interval and 3mo lookback.",
        "expected_indicators": ["ema_9", "ema_12"]
    },
    {
        "name": "MACD Crossover",
        "prompt": "Create a MACD strategy: buy when MACD line crosses above signal line, sell when it crosses below. Use 1h interval and 3mo lookback.",
        "expected_indicators": ["macd_line", "macd_signal"]
    },
    {
        "name": "RSI Oversold/Overbought",
        "prompt": "Create an RSI strategy: buy when RSI falls below 30 (oversold), sell when RSI rises above 70 (overbought). Use 1h interval and 3mo lookback.",
        "expected_indicators": ["rsi_14"]
    },
    {
        "name": "Bollinger Band Breakout",
        "prompt": "Create a Bollinger Band strategy: buy when price breaks above the upper band, sell when price falls below the lower band. Use 4h interval and 6mo lookback.",
        "expected_indicators": ["bb_upper", "bb_lower"]
    },
]


def test_strategy_generation():
    """Test strategy generation API endpoint."""
    print("=" * 70)
    print("🧪 STRATEGY GENERATION API TEST")
    print("=" * 70)
    
    results = []
    
    for test in TEST_PROMPTS:
        print(f"\n📝 Testing: {test['name']}")
        print(f"   Prompt: {test['prompt'][:60]}...")
        
        # Call API
        try:
            response = requests.post(
                f"{API_BASE_URL}/backtesting/generate-strategy",
                json={
                    "prompt": test["prompt"],
                    "strategy_name": f"test_{test['name'].lower().replace(' ', '_')}"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                strategy_code = data.get("strategy_code", "")
                
                # Check for expected indicators
                indicators_found = []
                for ind in test["expected_indicators"]:
                    if ind in strategy_code:
                        indicators_found.append(ind)
                
                if len(indicators_found) == len(test["expected_indicators"]):
                    print(f"   ✅ Generated successfully")
                    print(f"   ✅ Found indicators: {indicators_found}")
                    results.append({"name": test["name"], "status": "PASS", "indicators": indicators_found})
                else:
                    print(f"   ⚠️ Generated but missing indicators")
                    print(f"   Found: {indicators_found}")
                    print(f"   Expected: {test['expected_indicators']}")
                    results.append({"name": test["name"], "status": "PARTIAL", "indicators": indicators_found})
                
                # Show first few lines of strategy
                lines = strategy_code.split('\n')[:5]
                print(f"   Strategy preview:")
                for line in lines:
                    print(f"      {line}")
                    
            else:
                print(f"   ❌ API error: {response.status_code}")
                print(f"   {response.text[:200]}")
                results.append({"name": test["name"], "status": "FAIL", "error": response.text[:200]})
                
        except requests.exceptions.Timeout:
            print(f"   ❌ Timeout (60s)")
            results.append({"name": test["name"], "status": "TIMEOUT"})
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append({"name": test["name"], "status": "ERROR", "error": str(e)})
        
        # Rate limit
        time.sleep(2)
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 GENERATION TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in results if r["status"] == "PASS")
    partial = sum(1 for r in results if r["status"] == "PARTIAL")
    failed = sum(1 for r in results if r["status"] in ["FAIL", "TIMEOUT", "ERROR"])
    
    for r in results:
        status_icon = {"PASS": "✅", "PARTIAL": "⚠️", "FAIL": "❌", "TIMEOUT": "⏰", "ERROR": "❌"}
        print(f"   {status_icon.get(r['status'], '?')} {r['name']}: {r['status']}")
    
    print(f"\nTotal: ✅ {passed} passed | ⚠️ {partial} partial | ❌ {failed} failed")
    
    # Save results
    with open("generation_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📁 Results saved to generation_results.json")
    
    return passed == len(TEST_PROMPTS)


if __name__ == "__main__":
    success = test_strategy_generation()
    exit(0 if success else 1)
