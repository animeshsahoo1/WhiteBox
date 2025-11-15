import os
import pathway as pw
from pathway.xpacks.llm.llms import LiteLLMChat
from datetime import datetime
from dotenv import load_dotenv
import json

load_dotenv()


class SentimentReportUpdater:
    """Maintains and updates sentiment reports for trading agents using OpenAI's LLM."""

    def __init__(self, reports_directory: str):
        self.reports_directory = reports_directory

        try:
            self.symbol_mapping = json.loads(os.environ.get("STOCK_COMPANY_MAP", "{}"))
        except json.JSONDecodeError:
            print("Warning: Could not parse STOCK_COMPANY_MAP, using empty mapping")
            self.symbol_mapping = {}

        # Use LiteLLM with OpenRouter
        model_name = os.getenv('OPENAI_MODEL', 'openai/gpt-4o-mini')
        if not model_name.startswith('openrouter/') and not model_name.startswith('openai/'):
            model_name = f'openrouter/{model_name}'
            
        self.llm = LiteLLMChat(
            model=model_name,
            api_key=os.environ.get("OPENAI_API_KEY"),
            api_base="https://openrouter.ai/api/v1",
            temperature=0.0,
            max_tokens=1500,
        )

        os.makedirs(self.reports_directory, exist_ok=True)

    def _get_report_path(self, symbol: str) -> str:
        company_dir = os.path.join(self.reports_directory, symbol)
        os.makedirs(company_dir, exist_ok=True)
        return os.path.join(company_dir, "sentiment_report.md")

    def _load_report(self, symbol: str) -> str:
        report_path = self._get_report_path(symbol)

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            company_name = self.symbol_mapping.get(symbol, symbol)
            initial_report = f"""# {company_name} ({symbol}) - Social Sentiment Analysis Report

## Summary
No social media data analyzed yet for {company_name}.

## Recent Sentiment Overview
*Awaiting sentiment updates...*

## Sentiment Breakdown
- **Title Sentiment**: N/A
- **Content Sentiment**: N/A
- **Comments Sentiment**: N/A
- **Overall Sentiment**: Neutral

## Key Discussion Points
*No posts analyzed yet*

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

    def _format_sentiment_batch(self, symbol: str, posts_items: list) -> str:
        company = self.symbol_mapping.get(symbol, symbol)
        formatted_posts = []

        for item in posts_items:
            (post_id, ticker_symbol, company_name, subreddit, post_title, 
             post_content, post_comments, sentiment_post_title, sentiment_post_content,
             sentiment_comments, post_url, num_comments, score, created_utc, 
             match_type, post_timestamp, sent_at) = item

            # Classify sentiments
            def classify_sentiment(score):
                if score >= 0.05:
                    return "Bullish 📈"
                elif score <= -0.05:
                    return "Bearish 📉"
                else:
                    return "Neutral ➡️"

            formatted_posts.append(
                f"""
---
**Post Title**: {post_title}
**Subreddit**: r/{subreddit}
**Content Preview**: {post_content[:200]}{'...' if len(post_content) > 200 else ''}
**URL**: {post_url}

**Sentiment Analysis**:
- Title Sentiment: {sentiment_post_title:.3f} - {classify_sentiment(sentiment_post_title)}
- Content Sentiment: {sentiment_post_content:.3f} - {classify_sentiment(sentiment_post_content)}
- Comments Sentiment: {sentiment_comments:.3f} - {classify_sentiment(sentiment_comments)}

**Engagement**:
- Score: {score} upvotes
- Comments: {num_comments}
- Posted: {created_utc}
- Match Type: {match_type}
"""
            )

        header = f"## Sentiment Batch for {company} ({symbol})\n"
        header += f"Total posts in this batch: {len(posts_items)}\n"
        
        # Calculate average sentiments
        if posts_items:
            avg_title = sum(item[7] for item in posts_items) / len(posts_items)
            avg_content = sum(item[8] for item in posts_items) / len(posts_items)
            avg_comments = sum(item[9] for item in posts_items) / len(posts_items)
            
            header += f"\n**Batch Averages**:\n"
            header += f"- Avg Title Sentiment: {avg_title:.3f}\n"
            header += f"- Avg Content Sentiment: {avg_content:.3f}\n"
            header += f"- Avg Comments Sentiment: {avg_comments:.3f}\n"

        return header + "\n".join(formatted_posts)

    def _create_update_prompt(
        self, symbol: str, current_report: str, sentiment_batch: str
    ) -> list[dict]:

        company_name = self.symbol_mapping.get(symbol, symbol)

        system_message = f"""You are a financial analyst AI assistant specializing in social sentiment analysis for {company_name} ({symbol}).
Your task is to update the trading report by analyzing new social media posts (Reddit) and their sentiment scores to assess market sentiment.

Focus on:
1. **Sentiment Trends**: Analyze if sentiment is turning bullish, bearish, or remaining neutral
2. **Discussion Volume**: More engagement often signals stronger conviction
3. **Key Topics**: Identify what aspects of {company_name} people are discussing
4. **Sentiment Shifts**: Track changes in sentiment over time
5. **Trading Signals**: Provide clear BUY/SELL/HOLD recommendations based on sentiment analysis

Sentiment scores range from -1 (very bearish) to +1 (very bullish):
- Scores > 0.05 are bullish
- Scores < -0.05 are bearish
- Scores between -0.05 and 0.05 are neutral

Keep the report concise, actionable, and well-structured in markdown format.
Preserve the overall structure but update content based on new information.
Always update the "Last Analysis" timestamp at the bottom.
"""

        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        user_message = f"""Here is the CURRENT REPORT for {company_name} ({symbol}):

{current_report}

---

Here are NEW SOCIAL MEDIA POSTS with sentiment analysis to incorporate:

{sentiment_batch}

---

TASK: Update the report by:
1. Analyzing the sentiment trends from the new posts
2. Updating the "Recent Sentiment Overview" with latest insights
3. Updating "Sentiment Breakdown" with average scores
4. Adding key discussion points from the posts
5. Updating the "Trading Signals" with actionable BUY/SELL/HOLD recommendation based on sentiment
6. Updating the timestamp to: {current_time} UTC

Return ONLY the updated markdown report. Do not include explanations outside the report."""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]


def process_sentiment_stream(
    sentiment_table: pw.Table, reports_directory: str = "./reports/sentiment"
) -> pw.Table:
    """Process sentiment stream and create/update company-specific reports."""

    os.makedirs(reports_directory, exist_ok=True)
    report_updater = SentimentReportUpdater(reports_directory=reports_directory)

    @pw.reducers.stateful_many
    def universal_update_report_reducer(
        current_state: tuple[str, str] | None, posts_batch: list[tuple[list, int]]
    ) -> str:

        posts_items = []
        symbol = None

        for row_values, count in posts_batch:
            if count > 0:
                if symbol is None:
                    symbol = row_values[0]
                for _ in range(count):
                    posts_items.append(row_values[1:])

        if current_state is None:
            if symbol is None:
                return None
            current_report = report_updater._load_report(symbol)
        else:
            symbol, current_report = current_state

        if not posts_items:
            return current_report

        formatted_posts = report_updater._format_sentiment_batch(symbol, posts_items)

        messages = report_updater._create_update_prompt(
            symbol, current_report, formatted_posts
        )
        return messages

    @pw.udf
    def _save_report(symbol: str, report_content: str) -> str:
        report_path = report_updater._get_report_path(symbol)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(
            f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] Saved sentiment report for {symbol} to {report_path}"
        )
        return report_content

    prompts_table = sentiment_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        prompts=universal_update_report_reducer(
            pw.this.symbol,
            pw.this.post_id,
            pw.this.ticker_symbol,
            pw.this.company_name,
            pw.this.subreddit,
            pw.this.post_title,
            pw.this.post_content,
            pw.this.post_comments,
            pw.this.sentiment_post_title,
            pw.this.sentiment_post_content,
            pw.this.sentiment_comments,
            pw.this.post_url,
            pw.this.num_comments,
            pw.this.score,
            pw.this.created_utc,
            pw.this.match_type,
            pw.this.post_timestamp,
            pw.this.sent_at,
        ),
    )

    response_table = prompts_table.select(
        symbol=pw.this.symbol,
        response=_save_report(pw.this.symbol, report_updater.llm(pw.this.prompts))
    )

    return response_table