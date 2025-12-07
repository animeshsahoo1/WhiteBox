#!/usr/bin/env python3
"""
Bull-Bear Evaluation Dataset Generator using OpenRouter API
============================================================

This script automatically generates evaluation datasets for the Bull-Bear debate system.

Usage:
    python generate_with_openrouter.py --count 10 --category clear_signals
    python generate_with_openrouter.py --count 20 --all-categories
    python generate_with_openrouter.py --count 5 --category ambiguous --model anthropic/claude-3.5-sonnet

Environment:
    OPENAI_API_KEY: Your OpenRouter API key (required)
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required if env var already set

try:
    from openai import OpenAI
except ImportError:
    print("❌ Error: openai package not installed. Run: pip install openai")
    sys.exit(1)


# ============================================================
# CONFIGURATION
# ============================================================

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"

CATEGORIES = {
    "clear_buy": {
        "description": "Clear BUY signals - obvious bullish scenarios",
        "count": 5,
        "examples": ["earnings beat", "analyst upgrades", "acquisition announcement", "product success", "guidance raise"]
    },
    "clear_sell": {
        "description": "Clear SELL signals - obvious bearish scenarios", 
        "count": 5,
        "examples": ["fraud investigation", "earnings miss", "CEO scandal", "product recall", "bankruptcy risk"]
    },
    "clear_hold": {
        "description": "Clear HOLD signals - mixed or neutral scenarios",
        "count": 5,
        "examples": ["fair valuation", "no catalysts", "mixed earnings", "sector uncertainty", "transition period"]
    },
    "ambiguous": {
        "description": "Ambiguous cases where reasonable analysts could disagree",
        "count": 10,
        "examples": ["sentiment vs fundamentals conflict", "growth vs valuation tension", "turnaround story", "competitive disruption", "macro headwinds vs micro tailwinds"]
    },
    "adversarial": {
        "description": "Adversarial/edge cases to stress test the system",
        "count": 5,
        "examples": ["meme stock frenzy", "pump and dump signals", "incomplete data", "contradictory reports", "black swan event"]
    }
}


# ============================================================
# GENERATION PROMPTS
# ============================================================

SYSTEM_PROMPT = """You are a financial data generator creating realistic evaluation datasets for an AI investment debate system.

You MUST output ONLY valid JSON. No markdown, no explanation, just the JSON array.

Rules:
1. All numbers must be realistic (P/E 5-500, RSI 0-100, prices coherent)
2. Reports must be internally consistent
3. Use fictional but realistic ticker symbols (3-5 letters)
4. Each report should be detailed (200-400 words)
5. Ground truth must logically follow from the data
6. Include 3-5 bull points and 3-5 bear points"""

GENERATION_PROMPT = """Generate {count} evaluation scenarios for category: {category}

Category description: {description}
Example scenarios: {examples}

Each scenario must have this EXACT JSON structure:

{{
  "dataset_id": "{category}_NNN",
  "scenario_name": "Descriptive name",
  "category": "{category}",
  "difficulty": "easy|medium|hard",
  "symbol": "TICKER",
  "company_name": "Full Company Name",
  "sector": "Technology|Healthcare|Finance|Energy|Consumer|Industrial",
  "inputs": {{
    "news_report": "# News Summary for TICKER\\n\\n## Latest Headlines\\n\\n1. **Headline** - Source, Date\\n   Summary with specific numbers.\\n\\n2. **Headline 2**...\\n\\n## Key Events\\n- Event 1\\n- Event 2\\n\\n## Analyst Actions\\n- Action 1\\n\\nLast Updated: timestamp",
    "sentiment_report": "# Sentiment Analysis for TICKER\\n\\n## Overall Sentiment: BULLISH|BEARISH|NEUTRAL (Score: X.X/10)\\n\\n### Social Media Metrics\\n- Twitter: X% Positive...\\n- Reddit: description, mentions\\n- StockTwits: messages, sentiment\\n\\n### Analyst Sentiment\\n- Buy: X, Hold: X, Sell: X\\n- Average PT: $X\\n\\n### Key Themes\\n- Theme 1\\n- Theme 2",
    "market_report": "# Technical Analysis for TICKER\\n\\n## Price Action\\n- Current: $X\\n- 24h Change: X%\\n- 52-Week: $low - $high\\n- Volume: XM (vs avg)\\n\\n## Technical Indicators\\n- RSI (14): X (interpretation)\\n- MACD: status\\n- 50-Day MA: $X (relation)\\n- 200-Day MA: $X (relation)\\n\\n## Support/Resistance\\n- Support: $X, $Y\\n- Resistance: $X, $Y\\n\\n## Trend Analysis\\nParagraph.",
    "fundamental_report": "# Fundamental Analysis for TICKER\\n\\n## Valuation Metrics\\n- P/E: X (Industry: Y)\\n- Forward P/E: X\\n- P/S: X\\n- EV/EBITDA: X\\n\\n## Financial Health\\n- Revenue: $XB (X% YoY)\\n- Net Income: $XB (X% YoY)\\n- FCF: $XB\\n- Debt/Equity: X\\n\\n## Growth Metrics\\n- Revenue CAGR: X%\\n- EPS CAGR: X%\\n\\n## Competitive Position\\nParagraph."
  }},
  "ground_truth": {{
    "expected_recommendation": "BUY|HOLD|SELL",
    "expected_confidence": "HIGH|MEDIUM|LOW",
    "reasoning": "1-2 sentence explanation",
    "key_bull_points": ["Point 1", "Point 2", "Point 3"],
    "key_bear_points": ["Point 1", "Point 2", "Point 3"]
  }}
}}

Generate exactly {count} scenarios as a JSON array. Output ONLY the JSON array, nothing else."""


# ============================================================
# GENERATOR CLASS
# ============================================================

class DatasetGenerator:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL
        )
        self.model = model
        self.output_dir = Path(__file__).parent / "datasets"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_scenarios(self, category: str, count: int) -> List[Dict]:
        """Generate scenarios for a category using OpenRouter"""
        
        if category not in CATEGORIES:
            raise ValueError(f"Unknown category: {category}. Choose from: {list(CATEGORIES.keys())}")
        
        cat_info = CATEGORIES[category]
        
        print(f"\n🤖 Generating {count} scenarios for '{category}'...")
        print(f"   Using model: {self.model}")
        
        prompt = GENERATION_PROMPT.format(
            count=count,
            category=category,
            description=cat_info["description"],
            examples=", ".join(cat_info["examples"])
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=16000  # Need lots of tokens for detailed reports
            )
            
            content = response.choices[0].message.content
            
            # Parse JSON (handle potential markdown wrapping)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            scenarios = json.loads(content.strip())
            
            # Ensure it's a list
            if isinstance(scenarios, dict):
                scenarios = [scenarios]
            
            print(f"   ✅ Generated {len(scenarios)} scenarios")
            return scenarios
            
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parsing failed: {e}")
            print(f"   Raw response: {content[:500]}...")
            return []
        except Exception as e:
            print(f"   ❌ API error: {e}")
            return []
    
    def save_scenarios(self, scenarios: List[Dict], category: str) -> int:
        """Save scenarios to individual JSON files"""
        
        # Create category directory
        cat_dir = self.output_dir / category.replace("clear_", "clear_signals/")
        if "clear_" in category:
            cat_dir = self.output_dir / "clear_signals"
        elif category == "ambiguous":
            cat_dir = self.output_dir / "ambiguous"
        elif category == "adversarial":
            cat_dir = self.output_dir / "adversarial"
        else:
            cat_dir = self.output_dir / category
            
        cat_dir.mkdir(parents=True, exist_ok=True)
        
        saved = 0
        for i, scenario in enumerate(scenarios):
            # Generate unique ID if missing
            if "dataset_id" not in scenario or not scenario["dataset_id"]:
                scenario["dataset_id"] = f"{category}_{str(i+1).zfill(3)}"
            
            # Add metadata
            scenario["_generated_at"] = datetime.now().isoformat()
            scenario["_model_used"] = self.model
            
            # Determine filename
            filename = f"{scenario['dataset_id']}.json"
            filepath = cat_dir / filename
            
            # Don't overwrite existing
            counter = 1
            while filepath.exists():
                scenario["dataset_id"] = f"{category}_{str(len(list(cat_dir.glob('*.json'))) + counter).zfill(3)}"
                filename = f"{scenario['dataset_id']}.json"
                filepath = cat_dir / filename
                counter += 1
            
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(scenario, f, indent=2, ensure_ascii=False)
                print(f"   📄 Saved: {filepath.name}")
                saved += 1
            except Exception as e:
                print(f"   ❌ Failed to save {filename}: {e}")
        
        return saved
    
    def generate_all_categories(self, counts: Optional[Dict[str, int]] = None):
        """Generate scenarios for all categories"""
        
        if counts is None:
            counts = {cat: info["count"] for cat, info in CATEGORIES.items()}
        
        total_generated = 0
        total_saved = 0
        
        for category, count in counts.items():
            scenarios = self.generate_scenarios(category, count)
            saved = self.save_scenarios(scenarios, category)
            total_generated += len(scenarios)
            total_saved += saved
            
            # Rate limiting - wait between categories
            if category != list(counts.keys())[-1]:
                print("   ⏳ Waiting 2 seconds (rate limit)...")
                time.sleep(2)
        
        return total_generated, total_saved
    
    def update_manifest(self):
        """Update the manifest file with all datasets"""
        manifest = {
            "updated_at": datetime.now().isoformat(),
            "categories": {},
            "total_scenarios": 0
        }
        
        for cat_dir in self.output_dir.iterdir():
            if cat_dir.is_dir():
                files = list(cat_dir.glob("*.json"))
                manifest["categories"][cat_dir.name] = {
                    "count": len(files),
                    "files": [f.name for f in files]
                }
                manifest["total_scenarios"] += len(files)
        
        with open(self.output_dir / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"\n📋 Updated manifest: {manifest['total_scenarios']} total scenarios")


# ============================================================
# VALIDATION
# ============================================================

def validate_scenario(scenario: Dict) -> List[str]:
    """Validate a generated scenario"""
    errors = []
    
    required = ["dataset_id", "scenario_name", "symbol", "inputs", "ground_truth"]
    for field in required:
        if field not in scenario:
            errors.append(f"Missing: {field}")
    
    if "inputs" in scenario:
        for report in ["news_report", "sentiment_report", "market_report", "fundamental_report"]:
            content = scenario["inputs"].get(report, "")
            if not content:
                errors.append(f"Empty: inputs.{report}")
            elif len(content) < 200:
                errors.append(f"Too short: inputs.{report} ({len(content)} chars)")
    
    if "ground_truth" in scenario:
        rec = scenario["ground_truth"].get("expected_recommendation", "")
        if rec not in ["BUY", "HOLD", "SELL"]:
            errors.append(f"Invalid recommendation: {rec}")
    
    return errors


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Generate Bull-Bear evaluation datasets using OpenRouter")
    parser.add_argument("--count", type=int, default=5, help="Number of scenarios per category")
    parser.add_argument("--category", type=str, choices=list(CATEGORIES.keys()) + ["all"], 
                       default="all", help="Category to generate")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, 
                       help=f"OpenRouter model (default: {DEFAULT_MODEL})")
    parser.add_argument("--validate-only", action="store_true", 
                       help="Only validate existing datasets")
    
    args = parser.parse_args()
    
    # Get API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key and not args.validate_only:
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("   Set it with: export OPENAI_API_KEY=your_openrouter_key")
        sys.exit(1)
    
    if args.validate_only:
        # Validate existing datasets
        datasets_dir = Path(__file__).parent / "datasets"
        print(f"🔍 Validating datasets in {datasets_dir}...")
        
        total = 0
        valid = 0
        for json_file in datasets_dir.rglob("*.json"):
            if json_file.name == "manifest.json":
                continue
            total += 1
            with open(json_file) as f:
                scenario = json.load(f)
            errors = validate_scenario(scenario)
            if errors:
                print(f"❌ {json_file.name}: {', '.join(errors)}")
            else:
                valid += 1
        
        print(f"\n✅ Valid: {valid}/{total}")
        return
    
    # Generate datasets
    generator = DatasetGenerator(api_key, args.model)
    
    print("=" * 60)
    print("🚀 BULL-BEAR DATASET GENERATOR")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Category: {args.category}")
    print(f"Count per category: {args.count}")
    
    if args.category == "all":
        # Generate all categories
        counts = {cat: args.count for cat in CATEGORIES.keys()}
        generated, saved = generator.generate_all_categories(counts)
    else:
        # Generate single category
        scenarios = generator.generate_scenarios(args.category, args.count)
        saved = generator.save_scenarios(scenarios, args.category)
        generated = len(scenarios)
    
    generator.update_manifest()
    
    print("\n" + "=" * 60)
    print(f"✅ COMPLETE: Generated {generated} scenarios, saved {saved}")
    print("=" * 60)


if __name__ == "__main__":
    main()
