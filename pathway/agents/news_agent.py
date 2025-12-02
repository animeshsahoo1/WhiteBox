import os
import pathway as pw
from pathway.xpacks.llm.llms import LiteLLMChat
from datetime import datetime
from dotenv import load_dotenv
import json

# Import PostgreSQL save function
try:
    from redis_cache import save_report_to_postgres
except ImportError:
    from .redis_cache import save_report_to_postgres

load_dotenv()


class NewsReportUpdater:
    """Maintains and updates news reports for trading agents using OpenAI's LLM."""

    def __init__(self, reports_directory: str):
        self.reports_directory = reports_directory

        try:
            self.symbol_mapping = json.loads(os.environ.get("STOCK_COMPANY_MAP", "{}"))
        except json.JSONDecodeError:
            print("Warning: Could not parse STOCK_COMPANY_MAP, using empty mapping")
            self.symbol_mapping = {}

        self.llm = LiteLLMChat(
            model="openrouter/openai/gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY"),
            api_base="https://openrouter.ai/api/v1",
            temperature=0.0,
            max_tokens=500,
        )

        os.makedirs(self.reports_directory, exist_ok=True)

    def _get_llm_response(self, messages: list[dict]) -> str:
        temp_table = pw.debug.table_from_rows(
            schema=pw.schema_from_types(messages=list), rows=[(messages,)]
        )
        result_table = temp_table.select(response=self.llm(pw.this.messages))

        computed_result = pw.debug.compute_and_print(result_table, include_id=False)

        for row in computed_result:
            response_value = row.response
            break
            
        return response_value


    def _get_report_path(self, symbol: str) -> str:
        company_dir = os.path.join(self.reports_directory, symbol)
        os.makedirs(company_dir, exist_ok=True)
        return os.path.join(company_dir, "news_report.md")

    def _load_report(self, symbol: str) -> str:
        report_path = self._get_report_path(symbol)

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            company_name = self.symbol_mapping.get(symbol, symbol)
            initial_report = f"""# {company_name} ({symbol}) - Market News Analysis Report

## Summary
No news analyzed yet for {company_name}.

## Recent Developments
*Awaiting news updates...*

## Market Impact Analysis
- **Current Sentiment**: Neutral
- **Price Impact Expectation**: None
- **Last Updated**: Never

## Trading Signals
- **Signal**: HOLD
- **Confidence**: N/A
- **Reasoning**: Insufficient data

---
*This report is automatically updated by the AI Trading Agent*
*Last Analysis: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC*
"""
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(initial_report)
            return initial_report
        
    

    def _format_news_batch(self, symbol: str, news_items: list) -> str:
        company = self.symbol_mapping.get(symbol, symbol)
        formatted_news = []

        for item in news_items:
            timestamp, title, description, source, url, published_at, sent_at = item

            formatted_news.append(
                f"""
---
**Title**: {title}
**Description**: {description}
**Source**: {source}
**Published**: {published_at}
**URL**: {url}
**Received**: {timestamp}
"""
            )

        header = f"## News Batch for {company} ({symbol})\n"
        header += f"Total articles in this batch: {len(news_items)}\n"

        return header + "\n".join(formatted_news)

    def _create_update_prompt(
        self, symbol: str, current_report: str, news_batch: str
    ) -> list[dict]:

        company_name = self.symbol_mapping.get(symbol, symbol)

        system_message = f"""You are a financial analyst AI assistant specializing in market impact analysis for {company_name} ({symbol}).
Your task is to update the trading report by analyzing new news articles and their potential impact on {symbol}'s stock price.

Focus on:
1. **Price Impact**: Assess whether news is bullish (positive), bearish (negative), or neutral for {symbol}
2. **Magnitude**: Evaluate the significance (High/Medium/Low impact)
3. **Timeframe**: Consider short-term vs long-term implications
4. **Market Sentiment**: Update sentiment specific to {company_name}
5. **Trading Signals**: Provide clear BUY/SELL/HOLD recommendations with confidence levels

Keep the report concise, actionable, and well-structured in markdown format.
Preserve the overall structure but update content based on new information.
Always update the "Last Analysis" timestamp at the bottom.
"""

        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        user_message = f"""Here is the CURRENT REPORT for {company_name} ({symbol}):

{current_report}

---

Here are NEW NEWS ARTICLES to analyze and incorporate:

{news_batch}

---

TASK: Update the report by:
1. Analyzing each news item's potential market impact on {symbol}
2. Updating the "Recent Developments" section with new information
3. Adjusting the "Market Impact Analysis" based on the news
4. Updating the "Trading Signals" with actionable BUY/SELL/HOLD recommendation
5. Updating the timestamp to: {current_time} UTC

Return ONLY the updated markdown report. Do not include explanations outside the report."""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]


def process_news_stream(
    news_table: pw.Table, reports_directory: str = "./reports"
) -> pw.Table:
    """Process news stream and create/update company-specific reports."""

    os.makedirs(reports_directory, exist_ok=True)
    report_updater = NewsReportUpdater(reports_directory=reports_directory)

    @pw.reducers.stateful_many
    def universal_update_report_reducer(
        current_state: tuple[str, str] | None, news_batch: list[tuple[list, int]]
    ) -> str:

        news_items = []
        symbol = None

        for row_values, count in news_batch:
            if count > 0:
                if symbol is None:
                    symbol = row_values[0]
                for _ in range(count):
                    news_items.append(row_values[1:])

        if current_state is None:
            if symbol is None:
                return None
            current_report = report_updater._load_report(symbol)
        else:
            symbol, current_report = current_state

        if not news_items:
            return current_report

        formatted_news = report_updater._format_news_batch(symbol, news_items)

        messages = report_updater._create_update_prompt(
            symbol, current_report, formatted_news
        )
        return messages

    @pw.udf
    def _save_report(symbol: str, report_content: str) -> str:
        report_path = report_updater._get_report_path(symbol)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(
            f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] Saved report for {symbol} to {report_path}"
        )
        
        # Save to PostgreSQL for historical storage
        try:
            entry = {
                "symbol": symbol,
                "report_type": "news",
                "content": report_content,
                "last_updated": datetime.utcnow().isoformat(),
            }
            save_report_to_postgres(symbol, "news", entry)
        except Exception as e:
            print(f"⚠️ [{symbol}] Failed to save news to PostgreSQL: {e}")
        
        return report_content

    prompts_table = news_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        prompts=universal_update_report_reducer(
            pw.this.symbol,
            pw.this.timestamp,
            pw.this.title,
            pw.this.description,
            pw.this.source,
            pw.this.url,
            pw.this.published_at,
            pw.this.sent_at,
        ),
    )

    response_table = prompts_table.select(
        symbol = pw.this.symbol,
        response = _save_report(pw.this.symbol, report_updater.llm(pw.this.prompts))
    )


    return response_table
