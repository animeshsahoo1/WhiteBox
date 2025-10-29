import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import pathway as pw
import pathway as pw
from pathway.xpacks.llm import llms

load_dotenv('/app/.env')

class SentimentReportProducer:
    def __init__(self, output_dir="/app/output/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    
    def build_prompt(self, symbol, company, post_data, current_report):
        new_post = f"""
        Post: {post_data['post_title']}
        Content: {post_data['post_content'][:300]}
        Sentiment: Title={post_data['sentiment_post_title']:.2f}, Content={post_data['sentiment_post_content']:.2f}, Comments={post_data['sentiment_comments']:.2f}
        Engagement: {post_data['score']} upvotes, {post_data['num_comments']} comments
        """
        if current_report:
            return f"Update {symbol} report with new data:\n{current_report}\n\nNew:{new_post}"
        else:
            return f"Create {symbol} ({company}) sentiment report:\n{new_post}\n\nFormat: # {symbol} Report\n## Sentiment\n## Signal\n## Key Points"
    
    # def call_openai(self, prompt):
    #     try:
    #         response = self.client.chat.completions.create(
    #             model=self.model,
    #             messages=[{"role": "user", "content": prompt}],
    #             temperature=0.0,
    #             max_tokens=1500
    #         )
    #         return response.choices[0].message.content
    #     except Exception as e:
    #         print(f"OpenAI error: {e}")
    #         return None


    def call_openai(self, prompt):
        try:
            # Create OpenAI chat instance
            chat_model = llms.OpenAIChat(
                model=self.model,
                temperature=0.0,
                max_tokens=100,
                api_key=self.client.api_key if hasattr(self.client, 'api_key') else None
            )
            
            # Create a table with the prompt
            prompt_table = pw.debug.table_from_rows(
                pw.schema_from_types(prompt=str),
                rows=[(prompt,)]
            )
            
            # Apply chat model with proper message formatting
            result_table = prompt_table.select(
                response=chat_model(llms.prompt_chat_single_qa(pw.this.prompt))
            )
            
            # Compute and extract the response
            result = pw.debug.compute_and_print_update_stream(result_table)
            
            # Extract the actual response value
            response_value = None
            for row in result_table:
                response_value = row.response
                break
                
            return response_value
            
        except Exception as e:
            print(f"OpenAI error: {e}")
            return None
    
    def save_report(self, symbol, content):
        symbol_dir = self.output_dir / symbol
        symbol_dir.mkdir(exist_ok=True)
        (symbol_dir / "sentiment_report.md").write_text(content)
    
    def create_stateful_reducer(self):
        @pw.reducers.stateful_single
        def reducer(current_report, symbol, post_id, ticker_symbol, company_name, subreddit, 
                   post_title, post_content, post_comments, sentiment_post_title, 
                   sentiment_post_content, sentiment_comments, post_url, num_comments, 
                   score, created_utc, match_type):
            
            if not symbol:
                return current_report or ""
            
            status = "NEW" if current_report is None else "UPDATE"
            print(f"[{symbol}] {status} - Post: {post_id[:8]} | Report: {len(current_report or '')} chars")
            
            post_data = {
                'post_title': post_title, 'post_content': post_content,
                'sentiment_post_title': sentiment_post_title,
                'sentiment_post_content': sentiment_post_content,
                'sentiment_comments': sentiment_comments,
                'score': score, 'num_comments': num_comments
            }
            
            prompt = self.build_prompt(symbol, company_name, post_data, current_report)
            updated = self.call_openai(prompt)
            
            if updated:
                self.save_report(symbol, updated)
                print(f"[{symbol}] Saved → {len(updated)} chars\n")
                return updated
            return current_report or ""
        
        return reducer

def create_report_reducer(output_dir="/app/output/reports"):
    return SentimentReportProducer(output_dir).create_stateful_reducer()
