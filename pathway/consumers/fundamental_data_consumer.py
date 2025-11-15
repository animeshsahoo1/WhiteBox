import pathway as pw
from consumers.base_consumer import BaseConsumer

class FundamentalDataConsumer(BaseConsumer):
    """Consumer for fundamental data from Kafka"""
    
    def __init__(self):
        super().__init__(topic_name="fundamental-data")
    
    def get_output_schema(self):
        """Define how to extract fundamental data fields"""
        return {
            "symbol": pw.this.data["symbol"].as_str(),
            "profile": pw.this.data["profile"],
            "peers": pw.this.data["peers"],
            "income_annual": pw.this.data["income_annual"],
            "balance_annual": pw.this.data["balance_annual"],
            "cashflow_annual": pw.this.data["cashflow_annual"],
            "ratios_ttm": pw.this.data["ratios_ttm"],
            "growth_annual": pw.this.data["growth_annual"],
            "scores": pw.this.data["scores"],
            "grades_consensus": pw.this.data["grades_consensus"],
            "price_target_consensus": pw.this.data["price_target_consensus"],
            "dividends": pw.this.data["dividends"],
            "splits": pw.this.data["splits"],
            "insider_trades": pw.this.data["insider_trades"],
            "executives": pw.this.data["executives"],
            "news": pw.this.data["news"],
            "sec_filings": pw.this.data["sec_filings"],
            # Use pw.coalesce to provide a default empty Json object if web_intelligence is missing
            "web_intelligence": pw.coalesce(pw.this.data.get("web_intelligence"), pw.Json({})),
            "sent_at": pw.this.sent_at
        }
