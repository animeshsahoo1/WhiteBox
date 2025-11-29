"""
Facilitator Report Generator using Pathway
Follows the same pattern as news_agent.py but reads from JSON file instead of Kafka
"""
import os
import pathway as pw
from pathway.xpacks.llm.llms import LiteLLMChat
from datetime import datetime
from dotenv import load_dotenv
import json

load_dotenv()


class FacilitatorReportUpdater:
    """Maintains and updates facilitator reports using Pathway streaming pattern."""

    def __init__(self, reports_directory: str):
        self.reports_directory = reports_directory

        self.llm = LiteLLMChat(
            model="openrouter/openai/gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY"),
            api_base="https://openrouter.ai/api/v1",
            temperature=0.3,
            max_tokens=1500,
        )

        os.makedirs(self.reports_directory, exist_ok=True)

    def _get_report_path(self, symbol: str) -> str:
        """Get path for facilitator report."""
        company_dir = os.path.join(self.reports_directory, symbol)
        os.makedirs(company_dir, exist_ok=True)
        return os.path.join(company_dir, "facilitator_report.md")

    def _load_report(self, symbol: str) -> str:
        """Load existing report or create initial template."""
        report_path = self._get_report_path(symbol)

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            initial_report = f"""# Bull-Bear Debate Facilitator Report - {symbol}

## Executive Summary
No debates analyzed yet for {symbol}.

## Recent Debate Overview
*Awaiting debate results...*

## Key Arguments

### Bullish Position
- No arguments yet

### Bearish Position
- No arguments yet

## Consensus & Divergence Points

### Areas of Agreement
- None identified

### Major Disagreements
- None identified

## Facilitator's Assessment

### Market Outlook
- **Overall Sentiment**: Neutral
- **Confidence Level**: N/A
- **Recommendation**: HOLD

### Risk Considerations
- Insufficient data for risk assessment

## Action Items
- Waiting for first debate

---
*This report is automatically updated by the Facilitator AI Agent*
*Last Analysis: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC*
"""
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(initial_report)
            return initial_report

    def _format_debate_data(self, symbol: str, debate_items: list) -> str:
        """Format debate data for LLM processing."""
        formatted_debates = []

        for item in debate_items:
            (
                timestamp,
                rounds_completed,
                total_exchanges,
                bull_history,
                bear_history,
                full_transcript,
                summary_json,
            ) = item

            formatted_debates.append(
                f"""
---
**Debate Timestamp**: {timestamp}
**Rounds Completed**: {rounds_completed}
**Total Exchanges**: {total_exchanges}

**BULL ARGUMENTS:**
{bull_history}

**BEAR ARGUMENTS:**
{bear_history}

**FULL TRANSCRIPT:**
{full_transcript}

**SUMMARY:**
{summary_json}
"""
            )

        header = f"## Debate Data for {symbol}\n"
        header += f"Total debates in this batch: {len(debate_items)}\n"

        return header + "\n".join(formatted_debates)

    def _create_update_prompt(
        self, symbol: str, current_report: str, debate_batch: str
    ) -> list[dict]:
        """Create update prompt following news_agent pattern."""

        system_message = f"""You are a Senior Financial Analyst acting as a Debate Facilitator for {symbol}.

Your role is to:
1. **Summarize** the bull-bear debate objectively
2. **Identify** key arguments from both sides
3. **Highlight** consensus points and major disagreements
4. **Assess** the strength of each position
5. **Provide** a balanced market outlook based on the debate
6. **Recommend** actionable insights for traders

Keep the report:
- Professional and well-structured in markdown
- Objective and balanced (don't favor bull or bear)
- Actionable with clear trading implications
- Concise but comprehensive

Preserve the overall structure but update content based on new debate information.
Always update the "Last Analysis" timestamp at the bottom.
"""

        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        user_message = f"""Here is the CURRENT FACILITATOR REPORT for {symbol}:

{current_report}

---

Here are NEW DEBATE RESULTS to analyze and incorporate:

{debate_batch}

---

TASK: Update the report by:
1. Analyzing the debate arguments from both bull and bear perspectives
2. Updating the "Executive Summary" with key takeaways
3. Listing the strongest bullish points (3-5 bullet points)
4. Listing the strongest bearish points (3-5 bullet points)
5. Identifying consensus and divergence points
6. Providing balanced "Facilitator's Assessment" with BUY/SELL/HOLD recommendation
7. Highlighting key risk considerations
8. Suggesting actionable next steps
9. Updating the timestamp to: {current_time} UTC

Return ONLY the updated markdown report. Do not include explanations outside the report."""

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]


def process_debate_stream(
    debate_table: pw.Table, reports_directory: str = "./reports"
) -> pw.Table:
    """
    Process debate stream and create/update facilitator reports.
    Follows the exact pattern from news_agent.py
    """

    os.makedirs(reports_directory, exist_ok=True)
    report_updater = FacilitatorReportUpdater(reports_directory=reports_directory)

    @pw.reducers.stateful_many
    def universal_update_report_reducer(
        current_state: tuple[str, str] | None, debate_batch: list[tuple[list, int]]
    ) -> str:

        debate_items = []
        symbol = None

        for row_values, count in debate_batch:
            if count > 0:
                if symbol is None:
                    symbol = row_values[0]
                for _ in range(count):
                    debate_items.append(row_values[1:])

        if current_state is None:
            if symbol is None:
                return None
            current_report = report_updater._load_report(symbol)
        else:
            symbol, current_report = current_state

        if not debate_items:
            return current_report

        formatted_debate = report_updater._format_debate_data(symbol, debate_items)

        messages = report_updater._create_update_prompt(
            symbol, current_report, formatted_debate
        )
        return messages

    @pw.udf
    def _save_report(symbol: str, report_content: str) -> str:
        report_path = report_updater._get_report_path(symbol)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(
            f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC] Saved facilitator report for {symbol} to {report_path}"
        )
        return report_content

    prompts_table = debate_table.groupby(pw.this.symbol).reduce(
        symbol=pw.this.symbol,
        prompts=universal_update_report_reducer(
            pw.this.symbol,
            pw.this.timestamp,
            pw.this.rounds_completed,
            pw.this.total_exchanges,
            pw.this.bull_history,
            pw.this.bear_history,
            pw.this.full_transcript,
            pw.this.summary,
        ),
    )

    response_table = prompts_table.select(
        symbol=pw.this.symbol,
        response=_save_report(pw.this.symbol, report_updater.llm(pw.this.prompts)),
    )

    return response_table


def main():
    """Main function following pathway streaming pattern."""
    print("=" * 70)
    print("Pathway Facilitator Report System")
    print("=" * 70)

    # Read from JSON file using pathway's jsonlines connector
    # This will watch the file for updates
    debate_json_path = os.path.join(os.path.dirname(__file__), "debate_points.json")
    
    print(f"📥 Watching debate points file: {debate_json_path}")
    
    # Use pw.io.jsonlines to read the file
    # Note: For streaming updates, we'd use pw.io.fs.read with mode="streaming"
    # For now, we'll use a simpler approach with manual triggering
    
    debate_table = pw.io.jsonlines.read(
        debate_json_path,
        schema=pw.schema_builder(
            {
                "symbol": pw.column_definition(dtype=str),
                "timestamp": pw.column_definition(dtype=str),
                "rounds_completed": pw.column_definition(dtype=int),
                "total_exchanges": pw.column_definition(dtype=int),
                "bull_history": pw.column_definition(dtype=str),
                "bear_history": pw.column_definition(dtype=str),
                "full_debate_transcript": pw.column_definition(dtype=str),
                "summary": pw.column_definition(dtype=str),
            }
        ),
        mode="static",
    )

    # Process debates and generate reports
    reports_directory = os.path.join(os.path.dirname(__file__), "reports")
    updated_reports = process_debate_stream(
        debate_table, reports_directory=reports_directory
    )

    # Write output
    output_path = os.path.join(reports_directory, "facilitator_reports.csv")
    pw.io.csv.write(updated_reports, output_path)
    print(f"📝 Writing reports stream to CSV: {output_path}")

    print("\n✅ Facilitator pipeline initialized. Processing debates...")
    pw.run()


if __name__ == "__main__":
    main()
