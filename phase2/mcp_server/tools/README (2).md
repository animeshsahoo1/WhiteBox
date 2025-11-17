# Continuous Backtesting API Specification

## **Search Parameters**

### **Option 1: Structured Search (Recommended)**

```json
{
  "filters": {
    "strategy_ids": ["uuid1", "uuid2"],  // Optional: specific strategies
    "category": "book | user | llm | all",  // Optional: filter by type
    "technical_indicators": ["RSI", "MACD", "MA"],  // Optional: must use these
    "performance_criteria": {
      "min_win_rate": 0.60,  // Optional: >= 60%
      "min_sharpe_ratio": 1.5,  // Optional: >= 1.5
      "max_drawdown": 0.15,  // Optional: <= 15%
      "min_trade_count": 10  // Optional: minimum trades for statistical significance
    },
    "time_window": "30d | 90d | 180d | all",  // Performance period
    "market_conditions": {  // Optional: filter by conditions
      "volatility": "low | moderate | high | any",
      "trend": "bullish | bearish | sideways | any"
    }
  },
  "sort_by": {
    "conditions": {
      "sharpe_ratio": 0.30,  // Weight for Sharpe ratio (can be negative)
      "win_rate": 0.25,  // Weight for win rate
      "profit_factor": 0.25,  // Weight for profit factor
      "max_drawdown": -0.20  // Negative weight (penalize high drawdown)
    }
  },
  "limit": 10  // Max results to return
}
```

---

## **Expected JSON Response Structure**

```json
{
  "request_id": "uuid",
  "timestamp": "2025-11-15T10:30:00Z",
  "query_params": {
    // Echo back the search parameters used
  },
  "results": {
    "total_found": 15,
    "returned": 10,
    "strategies": [
      {
        "strategy_id": "uuid-1234",
        "name": "RSI Divergence Reversal",
        "category": "book",
        
        "definition": {
          "technical_indicators": ["RSI", "Price", "Volume"],
          "entry_rules": {
            "conditions": [
              "RSI < 30",
              "Price making lower low",
              "RSI making higher low"
            ],
            "logic": "AND"
          },
          "exit_rules": {
            "stop_loss_pct": 5.0,
            "take_profit_pct": 10.0,
            "trailing_stop": false,
            "max_hold_days": 30
          }
        },
        
        "performance_metrics": {
          "time_window": "30d",
          "period_start": "2025-10-15T00:00:00Z",
          "period_end": "2025-11-15T00:00:00Z",
          
          "returns": {
            "total_return": 0.156,  // 15.6%
            "annualized_return": 1.87,  // 187% annualized
            "avg_trade_return": 0.032,  // 3.2% per trade
            "best_trade": 0.089,  // 8.9%
            "worst_trade": -0.041  // -4.1%
          },
          
          "risk_metrics": {
            "sharpe_ratio": 1.85,
            "sortino_ratio": 2.31,
            "max_drawdown": 0.12,  // 12%
            "volatility": 0.18,  // 18% annualized
            "var_95": -0.025  // 95% VaR: -2.5%
          },
          
          "trade_statistics": {
            "total_trades": 12,
            "winning_trades": 8,
            "losing_trades": 4,
            "win_rate": 0.667,  // 66.7%
            "profit_factor": 2.45,  // gross_profit / gross_loss
            "avg_win": 0.051,  // 5.1%
            "avg_loss": -0.032,  // -3.2%
            "win_loss_ratio": 1.59,
            "expectancy": 0.021  // Expected value per trade: 2.1%
          },
          
          "timing_metrics": {
            "avg_hold_time_hours": 48.5,
            "median_hold_time_hours": 36.0,
            "avg_time_to_profit_hours": 18.2,
            "avg_time_to_loss_hours": 42.1
          },
          
          "market_condition_breakdown": {
            "high_volatility": {
              "trades": 4,
              "win_rate": 0.75,
              "avg_return": 0.042
            },
            "moderate_volatility": {
              "trades": 6,
              "win_rate": 0.667,
              "avg_return": 0.028
            },
            "low_volatility": {
              "trades": 2,
              "win_rate": 0.50,
              "avg_return": 0.015
            }
          }
        },
        
        "multi_window_performance": {
          "30d": {
            "sharpe": 1.85,
            "win_rate": 0.667,
            "total_return": 0.156,
            "max_drawdown": 0.12,
            "trade_count": 12
          },
          "90d": {
            "sharpe": 1.72,
            "win_rate": 0.643,
            "total_return": 0.412,
            "max_drawdown": 0.18,
            "trade_count": 34
          },
          "180d": {
            "sharpe": 1.68,
            "win_rate": 0.621,
            "total_return": 0.785,
            "max_drawdown": 0.22,
            "trade_count": 68
          }
        },
        
        "ranking": {
          "overall_rank": 0.87,  // 0-1 composite score
          "rank_position": 2,  // #2 out of total strategies
          "rank_components": {
            "sharpe_weight": 0.30,
            "win_rate_weight": 0.25,
            "profit_factor_weight": 0.25,
            "drawdown_weight": 0.20
          }
        },
        
        "metadata": {
          "created_at": "2025-10-01T12:00:00Z",
          "last_evaluated": "2025-11-15T10:25:00Z",
          "last_trade": "2025-11-14T16:30:00Z",
          "usage_count": 45,
          "user_ratings": {
            "avg_rating": 4.2,
            "total_ratings": 8
          }
        }
      },
      
      // ... more strategies (up to limit)
      
    ]
  },
  
  "aggregated_stats": {
    "avg_sharpe": 1.62,
    "avg_win_rate": 0.641,
    "best_performer": {
      "strategy_id": "uuid-1234",
      "name": "RSI Divergence Reversal",
      "metric": "sharpe_ratio",
      "value": 1.85
    },
    "most_consistent": {
      "strategy_id": "uuid-5678",
      "name": "MA Crossover",
      "metric": "win_rate",
      "value": 0.712
    }
  },
  
  "market_context": {
    "evaluation_period": "30d",
    "market_conditions": {
      "avg_volatility": "moderate",
      "dominant_trend": "bullish",
      "major_events": [
        "Fed rate decision (2025-11-07)",
        "Earnings season peak (2025-10-25)"
      ]
    }
  }
}
```

---

## **API Endpoint Design**

### **Primary Endpoint**
```
POST /api/backtesting/search
Content-Type: application/json

Body: {search parameters as shown above}
Response: {JSON structure as shown above}
```

---

## **Error Handling**

```json
{
  "error": true,
  "error_code": "INSUFFICIENT_DATA",
  "message": "Strategy 'uuid-1234' has insufficient trades (3) in 30d window. Minimum required: 10",
  "timestamp": "2025-11-15T10:30:00Z",
  "request_id": "uuid"
}
```

**Error Codes:**
- `INSUFFICIENT_DATA`: Not enough trades for statistical significance
- `INVALID_WINDOW`: Time window not supported
- `STRATEGY_NOT_FOUND`: Strategy ID doesn't exist
- `NO_RESULTS`: No strategies match filters
- `INVALID_PARAMETERS`: Malformed search parameters

---

## **Key Design Decisions**

### **Why This Structure?**

1. **Comprehensive Metrics**: Covers returns, risk, trade stats, timing - everything Risk Managers need
2. **Multi-Window Support**: 30d/90d/180d in single response avoids multiple API calls
3. **Market Context**: Helps understand if performance was environment-specific
4. **Condition Breakdown**: Shows strategy behavior in different volatility regimes
5. **Ranking Transparency**: Exposes how composite rank is calculated
6. **Metadata**: Usage stats help identify battle-tested strategies

### **What Orchestrator Will Use Most:**

- `performance_metrics.risk_metrics.sharpe_ratio`
- `performance_metrics.trade_statistics.win_rate`
- `performance_metrics.returns.total_return`
- `performance_metrics.risk_metrics.max_drawdown`
- `ranking.overall_rank`
- `market_condition_breakdown` → for Risk Manager assessment

### **Flexible Search Examples:**

```json
// Example 1: Top performers last 30 days
{
  "filters": {
    "performance_criteria": {
      "min_trade_count": 10
    },
    "time_window": "30d"
  },
  "sort_by": "rank",
  "limit": 5
}

// Example 2: RSI strategies for high volatility
{
  "filters": {
    "technical_indicators": ["RSI"],
    "market_conditions": {
      "volatility": "high"
    },
    "time_window": "30d"
  },
  "sort_by": "sharpe",
  "limit": 10
}

// Example 3: Specific strategies comparison
{
  "filters": {
    "strategy_ids": ["uuid1", "uuid2", "uuid3"],
    "time_window": "90d"
  }
}
```

---

**This gives you everything needed to integrate with the continuous backtesting service!** The response format is rich enough for Risk Managers to make informed decisions while remaining clean and structured.