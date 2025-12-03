# file: src/fmp_api_client.py

import os
import requests
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

class FmpApiClient:
    """Client for interacting with the Financial Modeling Prep (FMP) API."""

    BASE_URL = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize FMP API Client."""
        self.api_key = api_key or os.getenv('FMP_API_KEY')
        if not self.api_key:
            raise ValueError("FMP_API_KEY not found in .env file or as an argument.")
        
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Pathway-Fundamental-Analysis-Client/1.0'})

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Helper function to make requests to the FMP API."""
        if params is None:
            params = {}
        
        # This is the key part: The API key is always a parameter.
        params['apikey'] = self.api_key
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status() # Raises HTTPError for 4xx/5xx responses
            data = response.json()

            # Handle empty responses
            if not data:
                print(f"⚠️  API Warning ({endpoint}): Empty response")
                return None
            
            # Handle dictionary responses with error messages
            if isinstance(data, dict) and 'Error Message' in data:
                error_msg = data.get('Error Message', f"Error from {endpoint}")
                print(f"⚠️  API Warning ({endpoint}): {error_msg}")
                return None
            
            # Valid response (can be dict or list)
            return data
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 402:
                print(f"⚠️  Plan Error ({endpoint}): Your API key plan does not permit access.")
            else:
                print(f"❌ HTTP Error ({endpoint}): {e}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Error ({endpoint}): {e}")
        return None

    # --- Methods with Corrected API Call Structure ---

    def get_company_profile(self, symbol: str) -> Optional[Dict]:
        data = self._make_request("/profile", params={'symbol': symbol})
        return data[0] if isinstance(data, list) and data else None

    def get_stock_peers(self, symbol: str) -> Optional[List[str]]:
        data = self._make_request("/stock-peers", params={'symbol': symbol})
        return data[0].get('peersList') if isinstance(data, list) and data and 'peersList' in data[0] else None

    def get_income_statement(self, symbol: str, period: str = 'annual', limit: int = 5) -> Optional[List[Dict]]:
        params = {'symbol': symbol, 'period': period, 'limit': limit}
        return self._make_request("/income-statement", params=params)

    def get_balance_sheet(self, symbol: str, period: str = 'annual', limit: int = 5) -> Optional[List[Dict]]:
        params = {'symbol': symbol, 'period': period, 'limit': limit}
        return self._make_request("/balance-sheet-statement", params=params)

    def get_cash_flow(self, symbol: str, period: str = 'annual', limit: int = 5) -> Optional[List[Dict]]:
        params = {'symbol': symbol, 'period': period, 'limit': limit}
        return self._make_request("/cash-flow-statement", params=params)

    def get_ratios_ttm(self, symbol: str) -> Optional[Dict]:
        data = self._make_request("/ratios-ttm", params={'symbol': symbol})
        return data[0] if isinstance(data, list) and data else None

    def get_financial_growth(self, symbol: str, period: str = 'annual', limit: int = 5) -> Optional[List[Dict]]:
        params = {'symbol': symbol, 'period': period, 'limit': limit}
        return self._make_request("/financial-growth", params=params)

    def get_financial_scores(self, symbol: str, period: str = 'annual', limit: int = 5) -> Optional[List[Dict]]:
        params = {'symbol': symbol, 'period': period, 'limit': limit}
        return self._make_request("/financial-scores", params=params)
    
    def get_dividends(self, symbol: str, limit: int = 20) -> Optional[List[Dict]]:
        return self._make_request('/dividends', params={'symbol': symbol, 'limit': limit})
        
    def get_sec_filings(self, symbol: str, limit: int = 10) -> Optional[List[Dict]]:
        today = datetime.now()
        ninety_days_ago = today - timedelta(days=90)
        params = {
            'symbol': symbol, 'limit': limit, 'page': 0,
            'from': ninety_days_ago.strftime('%Y-%m-%d'),
            'to': today.strftime('%Y-%m-%d')
        }
        return self._make_request("/sec-filings-search/symbol", params=params)

    def get_grades_consensus(self, symbol: str) -> Optional[Dict]:
        data = self._make_request("/grades-consensus", params={'symbol': symbol})
        return data[0] if isinstance(data, list) and data else None

    def get_price_target_consensus(self, symbol: str) -> Optional[Dict]:
        data = self._make_request("/price-target-consensus", params={'symbol': symbol})
        return data[0] if isinstance(data, list) and data else None

    def get_stock_splits(self, symbol: str) -> Optional[List[Dict]]:
        return self._make_request("/splits", params={'symbol': symbol})

    def get_insider_trades(self, symbol: str, limit: int = 20) -> Optional[List[Dict]]:
        params = {'symbol': symbol, 'limit': limit, 'page': 0}
        return self._make_request("/insider-trading/search", params=params)

    def get_key_executives(self, symbol: str) -> Optional[List[Dict]]:
        return self._make_request("/key-executives", params={'symbol': symbol})

    def get_stock_news(self, symbol: str, limit: int = 10) -> Optional[List[Dict]]:
        params = {'symbols': symbol, 'limit': limit}
        return self._make_request("/news/stock", params=params)
    
    def gather_all_fundamental_data(self, symbol: str) -> Dict[str, Any]:
        """Gathers all fundamental data for a stock symbol."""
        print(f"\n{'='*50}\n Gathering fundamental data for {symbol.upper()}\n{'='*50}\n")
        
        fetch_plan = {
            "profile": (self.get_company_profile, [symbol]),
            "peers": (self.get_stock_peers, [symbol]),
            "income_annual": (self.get_income_statement, [symbol, 'annual', 5]),
            "balance_annual": (self.get_balance_sheet, [symbol, 'annual', 5]),
            "cashflow_annual": (self.get_cash_flow, [symbol, 'annual', 5]),
            "ratios_ttm": (self.get_ratios_ttm, [symbol]),
            "growth_annual": (self.get_financial_growth, [symbol, 'annual', 5]),
            "scores": (self.get_financial_scores, [symbol, 'annual', 5]),
            "grades_consensus": (self.get_grades_consensus, [symbol]),
            "price_target_consensus": (self.get_price_target_consensus, [symbol]),
            "dividends": (self.get_dividends, [symbol]),
            "splits": (self.get_stock_splits, [symbol]),
            "insider_trades": (self.get_insider_trades, [symbol]),
            "executives": (self.get_key_executives, [symbol]),
            "news": (self.get_stock_news, [symbol]),
            "sec_filings": (self.get_sec_filings, [symbol]),
        }

        data = {'symbol': symbol}
        for key, (func, args) in fetch_plan.items():
            print(f"Fetching {key.replace('_', ' ')}...")
            data[key] = func(*args)

        print(f"\n{'='*50}\n ✅ Data gathering complete for {symbol.upper()}\n{'='*50}\n")
        return data