# Fundamental Data Utilities

Utilities for fetching fundamental data from Financial Modeling Prep (FMP) API and web scraping.

## 📋 Overview

- **fmp_api_client.py** - Comprehensive FMP API wrapper
- **web_scraper.py** - Web scraping utilities for Yahoo Finance, MarketWatch, etc.

## 📊 FMP API Client

### Features
- Complete FMP API coverage
- Error handling and retries
- Response validation
- Rate limit handling

### Usage

```python
from fundamental_utils.fmp_api_client import FmpApiClient

# Initialize
client = FmpApiClient(api_key='your_fmp_key')

# Company profile
profile = client.get_company_profile('AAPL')
print(f"Company: {profile['companyName']}")
print(f"Industry: {profile['industry']}")

# Financial statements
income = client.get_income_statement('AAPL', period='annual', limit=5)
balance = client.get_balance_sheet('AAPL', period='annual', limit=5)
cashflow = client.get_cash_flow('AAPL', period='annual', limit=5)

# Ratios
ratios = client.get_ratios_ttm('AAPL')
print(f"P/E Ratio: {ratios['peRatioTTM']}")
print(f"ROE: {ratios['returnOnEquityTTM']}")

# Growth metrics
growth = client.get_financial_growth('AAPL', period='annual', limit=5)
print(f"Revenue Growth: {growth[0]['revenueGrowth']}")

# Dividends
dividends = client.get_dividends('AAPL', limit=20)

# SEC filings
filings = client.get_sec_filings('AAPL', limit=10)
```

### Available Methods

#### Company Information
- `get_company_profile(symbol)` - Company details, sector, industry
- `get_stock_peers(symbol)` - Peer companies

#### Financial Statements
- `get_income_statement(symbol, period='annual', limit=5)` - Income statements
- `get_balance_sheet(symbol, period='annual', limit=5)` - Balance sheets
- `get_cash_flow(symbol, period='annual', limit=5)` - Cash flow statements

#### Financial Metrics
- `get_ratios_ttm(symbol)` - Trailing twelve months ratios
- `get_financial_growth(symbol, period='annual', limit=5)` - Growth metrics
- `get_financial_scores(symbol, period='annual', limit=5)` - Piotroski F-Score, etc.

#### Corporate Actions
- `get_dividends(symbol, limit=20)` - Dividend history
- `get_sec_filings(symbol, limit=10)` - SEC documents (10-K, 10-Q, etc.)

### Response Format

All methods return:
- **Dict** for single item (profile, ratios)
- **List[Dict]** for multiple items (statements, growth)
- **None** on errors (logged automatically)

### Error Handling

```python
# API errors handled gracefully
profile = client.get_company_profile('INVALID')
if profile is None:
    print("Failed to fetch profile")
    # Client logs: "⚠️  API Warning: Empty response"

# HTTP errors
try:
    data = client._make_request('/invalid-endpoint')
except Exception as e:
    print(f"Request failed: {e}")
```

## 🌐 Web Scraper

### Features
- BeautifulSoup-based scraping
- User-agent rotation
- Rate limiting
- Error handling

### Usage

```python
from fundamental_utils.web_scraper import scrape_yahoo_finance

# Scrape Yahoo Finance
data = scrape_yahoo_finance('AAPL')
print(data['price'])
print(data['pe_ratio'])
```

### Supported Sites
- Yahoo Finance
- MarketWatch
- Seeking Alpha (when available)

## 🔧 Configuration

### FMP API Key
```bash
# In .env
FMP_API_KEY=your_fmp_api_key
```

### Rate Limits
FMP rate limits vary by plan:
- **Free**: 250 requests/day
- **Starter**: 750 requests/day
- **Professional**: Unlimited

The client handles rate limits gracefully:
```python
# Rate limit error (402 status code)
# Client logs: "⚠️  Plan Error: Your API key plan does not permit access."
# Returns: None
```

## 🧪 Testing

### Test FMP Client
```python
# Test basic functionality
python -c "
from fundamental_utils.fmp_api_client import FmpApiClient
client = FmpApiClient()
profile = client.get_company_profile('AAPL')
print(f'Company: {profile[\"companyName\"]}')
print(f'Industry: {profile[\"industry\"]}')
"
```

### Test Web Scraper
```python
# Test scraping
python -c "
from fundamental_utils.web_scraper import scrape_yahoo_finance
data = scrape_yahoo_finance('AAPL')
print(f'Price: {data[\"price\"]}')
"
```

## 📝 Notes

### FMP Endpoints
The client uses FMP API v3 (stable) endpoints:
- Base URL: `https://financialmodelingprep.com/stable`
- Authentication: API key in query parameters
- Response: JSON format

### Best Practices
1. **Cache results** - Don't re-fetch static data
2. **Respect rate limits** - Space out requests
3. **Handle None returns** - Always check for failures
4. **Use appropriate periods** - 'annual' or 'quarter'

### Common Issues

**Empty Response**
```python
# FMP returns [] for invalid symbols
data = client.get_company_profile('INVALID')
# Returns: None
# Logs: "⚠️  API Warning: Empty response"
```

**Plan Limitations**
```python
# Some endpoints require paid plans
data = client.get_advanced_metrics('AAPL')
# Returns: None
# Logs: "⚠️  Plan Error: Your API key plan does not permit access."
```

## 🔗 Related
- [FMP API Documentation](https://site.financialmodelingprep.com/developer/docs)
- [streaming/producers/fundamental_data_producer.py](../producers/fundamental_data_producer.py)
