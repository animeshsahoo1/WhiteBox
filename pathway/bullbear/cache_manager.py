"""
Cache Manager for Bull-Bear Debate
Handles caching of reports and comparison for delta detection
"""
import os
import json
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from .config import DebateConfig, get_config
from .clients import Report

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages cached reports and computes deltas between old and new reports.
    """
    
    def __init__(self, config: Optional[DebateConfig] = None):
        self.config = config or get_config().debate
        self.cache_dir = Path(self.config.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, symbol: str, report_type: str) -> Path:
        """Get the cache file path for a report"""
        symbol_dir = self.cache_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        return symbol_dir / f"{report_type}.json"
    
    def get_cached_report(self, symbol: str, report_type: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached report.
        
        Args:
            symbol: Stock symbol
            report_type: One of 'news', 'sentiment', 'market', 'fundamental', 'facilitator'
            
        Returns:
            Cached report data or None if not found
        """
        cache_path = self._get_cache_path(symbol, report_type)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading cache for {symbol}/{report_type}: {e}")
            return None
    
    def save_to_cache(self, symbol: str, report: Report) -> None:
        """
        Save a report to cache.
        
        Args:
            symbol: Stock symbol
            report: Report object to cache
        """
        cache_path = self._get_cache_path(symbol, report.report_type)
        
        try:
            data = report.to_dict()
            data["cached_at"] = datetime.utcnow().isoformat()
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Cached {report.report_type} report for {symbol}")
        except Exception as e:
            logger.error(f"Error caching report: {e}")
    
    def get_all_cached_reports(self, symbol: str) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get all cached reports for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with all 5 report types (may contain None values)
        """
        report_types = ["news", "sentiment", "market", "fundamental", "facilitator"]
        return {
            rt: self.get_cached_report(symbol, rt)
            for rt in report_types
        }
    
    def update_cache(self, symbol: str, reports: Dict[str, Report]) -> None:
        """
        Update cache with new reports.
        
        Args:
            symbol: Stock symbol
            reports: Dict of Report objects to cache
        """
        for report_type, report in reports.items():
            self.save_to_cache(symbol, report)


class DeltaComputer:
    """
    Computes differences between old (cached) and new reports.
    Uses LLM to extract meaningful change points.
    """
    
    def __init__(self, llm=None):
        """
        Args:
            llm: LLM instance for extracting change points. If None, uses simple diff.
        """
        self.llm = llm
    
    def compute_delta(
        self,
        old_report: Optional[Dict[str, Any]],
        new_report: Report
    ) -> Dict[str, Any]:
        """
        Compute the delta between old and new report.
        Uses LLM for semantic comparison, with heuristic fallback.
        
        Args:
            old_report: Cached report data (or None if first run)
            new_report: New Report object
            
        Returns:
            Delta dict with new_points, removed_points, changed_points
        """
        if old_report is None:
            # First run - all points are new
            points = self._extract_key_points(new_report.content)
            return {
                "report_type": new_report.report_type,
                "new_points": points,
                "removed_points": [],
                "changed_points": [],
                "is_first_run": True
            }
        
        old_content = old_report.get("content", "")
        new_content = new_report.content
        
        if old_content == new_content:
            return {
                "report_type": new_report.report_type,
                "new_points": [],
                "removed_points": [],
                "changed_points": [],
                "no_change": True
            }
        
        # Use LLM for semantic delta computation
        if self.llm:
            return self._compute_delta_with_llm(old_content, new_content, new_report.report_type)
        
        # Fallback to heuristic-based comparison
        return self._compute_delta_heuristic(old_content, new_content, new_report.report_type)
    
    def _compute_delta_with_llm(
        self, 
        old_content: str, 
        new_content: str, 
        report_type: str
    ) -> Dict[str, Any]:
        """Use LLM for semantic delta computation"""
        try:
            # Truncate to fit context window
            old_truncated = old_content[:3000]
            new_truncated = new_content[:3000]
            
            prompt = f"""Compare these two {report_type} reports and identify the differences.

OLD REPORT:
{old_truncated}

NEW REPORT:
{new_truncated}

Analyze semantically (not just text matching) and output JSON:
{{
    "new_points": ["list of NEW information/insights not in old report"],
    "removed_points": ["list of information that was in old but removed/outdated"],
    "changed_points": [
        {{"old": "what it said before", "new": "what it says now", "significance": "HIGH/MEDIUM/LOW"}}
    ],
    "summary": "brief 1-2 sentence summary of key changes",
    "overall_sentiment_shift": "MORE_BULLISH / MORE_BEARISH / NEUTRAL / NO_CHANGE"
}}

Focus on investment-relevant changes: price targets, ratings, earnings, risks, catalysts."""
            
            messages = [
                {"role": "system", "content": "You are a financial analyst comparing reports. Find semantic differences, not just text differences. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            
            response = self.llm.complete_json(messages)
            
            return {
                "report_type": report_type,
                "new_points": response.get("new_points", []),
                "removed_points": response.get("removed_points", []),
                "changed_points": response.get("changed_points", []),
                "summary": response.get("summary", ""),
                "sentiment_shift": response.get("overall_sentiment_shift", "NO_CHANGE"),
                "method": "llm"
            }
            
        except Exception as e:
            logger.error(f"LLM delta computation failed: {e}. Falling back to heuristic.")
            return self._compute_delta_heuristic(old_content, new_content, report_type)
    
    def _compute_delta_heuristic(
        self, 
        old_content: str, 
        new_content: str, 
        report_type: str
    ) -> Dict[str, Any]:
        """Heuristic fallback for delta computation using fuzzy matching"""
        old_points = self._extract_key_points(old_content)
        new_points = self._extract_key_points(new_content)
        
        # Use fuzzy matching instead of exact set comparison
        added = []
        removed = []
        
        # Find new points (not similar to any old point)
        for new_pt in new_points:
            is_new = True
            for old_pt in old_points:
                if self._is_similar(new_pt, old_pt, threshold=0.7):
                    is_new = False
                    break
            if is_new:
                added.append(new_pt)
        
        # Find removed points (not similar to any new point)
        for old_pt in old_points:
            is_removed = True
            for new_pt in new_points:
                if self._is_similar(old_pt, new_pt, threshold=0.7):
                    is_removed = False
                    break
            if is_removed:
                removed.append(old_pt)
        
        return {
            "report_type": report_type,
            "new_points": added,
            "removed_points": removed,
            "changed_points": [],
            "total_old_points": len(old_points),
            "total_new_points": len(new_points),
            "method": "heuristic"
        }
    
    def _is_similar(self, text1: str, text2: str, threshold: float = 0.7) -> bool:
        """Check if two texts are similar using word overlap ratio"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return False
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        jaccard = intersection / union if union > 0 else 0
        return jaccard >= threshold
    
    def _extract_key_points(self, content: str) -> List[str]:
        """
        Extract key points from report content.
        Uses simple heuristics if LLM not available.
        """
        if not content:
            return []
        
        if self.llm:
            return self._extract_with_llm(content)
        
        # Simple extraction: split by common delimiters
        points = []
        
        # Try bullet points
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith(('- ', '• ', '* ', '→ ')):
                points.append(line[2:].strip())
            elif line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                points.append(line[2:].strip())
        
        # If no bullet points found, split by sentences
        if not points:
            sentences = re.split(r'[.!?]+', content)
            points = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        return points[:20]  # Limit to 20 points
    
    def _extract_with_llm(self, content: str) -> List[str]:
        """Extract key points using LLM"""
        if not self.llm or not content:
            return self._extract_key_points_simple(content)
        
        try:
            prompt = f"""Extract the key investment-relevant points from this financial report.

REPORT:
{content[:3000]}

Output JSON:
{{
    "key_points": ["list of 5-15 key points that would affect investment decisions"]
}}

Focus on:
- Price movements and targets
- Earnings/revenue data
- Analyst ratings
- Market sentiment
- Risks and opportunities
- Company announcements"""
            
            messages = [
                {"role": "system", "content": "You are a financial analyst extracting key points. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ]
            
            response = self.llm.complete_json(messages)
            points = response.get("key_points", [])
            
            if points:
                return points[:20]
            else:
                return self._extract_key_points_simple(content)
                
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}. Falling back to simple extraction.")
            return self._extract_key_points_simple(content)
    
    def _extract_key_points_simple(self, content: str) -> List[str]:
        """Simple extraction fallback"""
        sentences = re.split(r'[.!?]+', content)
        return [s.strip() for s in sentences if len(s.strip()) > 20][:20]
    
    def compute_all_deltas(
        self,
        cached_reports: Dict[str, Optional[Dict[str, Any]]],
        new_reports: Dict[str, Report]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute deltas for all 4 main reports.
        
        Args:
            cached_reports: Dict of cached report data
            new_reports: Dict of new Report objects
            
        Returns:
            Dict with deltas for each report type
        """
        deltas = {}
        for report_type in ["news", "sentiment", "market", "fundamental"]:
            old = cached_reports.get(report_type)
            new = new_reports.get(report_type)
            
            if new:
                deltas[report_type] = self.compute_delta(old, new)
            else:
                deltas[report_type] = {
                    "report_type": report_type,
                    "error": "Report not available"
                }
        
        return deltas


class FacilitatorValidator:
    """
    Validates the previous facilitator conclusion against actual market movement.
    """
    
    def __init__(self, llm=None):
        self.llm = llm
    
    def validate_conclusion(
        self,
        old_facilitator_report: Optional[Dict[str, Any]],
        old_market_report: Optional[Dict[str, Any]],
        new_market_report: Report
    ) -> Dict[str, Any]:
        """
        Validate if the previous facilitator conclusion was correct.
        
        Args:
            old_facilitator_report: Previous facilitator report
            old_market_report: Previous market report
            new_market_report: New market report
            
        Returns:
            Validation result with was_correct, reasoning, etc.
        """
        if old_facilitator_report is None:
            return {
                "was_correct": None,
                "reasoning": "No previous facilitator report to validate",
                "old_recommendation": None,
                "market_validation": None,
                "confidence": 0
            }
        
        old_rec = self._extract_recommendation(old_facilitator_report.get("content", ""))
        market_direction = self._determine_market_direction(
            old_market_report,
            new_market_report
        )
        
        was_correct = self._check_correctness(old_rec, market_direction)
        
        return {
            "was_correct": was_correct,
            "reasoning": self._generate_reasoning(old_rec, market_direction, was_correct),
            "old_recommendation": old_rec,
            "market_validation": market_direction,
            "confidence": 0.7 if was_correct is not None else 0.3
        }
    
    def _extract_recommendation(self, report: str) -> str:
        """Extract BUY/HOLD/SELL recommendation from report using word boundaries"""
        report_upper = report.upper()
        
        # Look for explicit "RECOMMENDATION: X" pattern first
        rec_match = re.search(r'RECOMMENDATION[:\s]+\**(STRONG\s+BUY|STRONG\s+SELL|BUY|SELL|HOLD)\**', report_upper)
        if rec_match:
            return rec_match.group(1).replace("\n", " ").strip()
        elif re.search(r'\bSTRONG\s+BUY\b', report_upper):
            return "STRONG BUY"
        elif re.search(r'\bSTRONG\s+SELL\b', report_upper):
            return "STRONG SELL"
        elif re.search(r'\bBUY\b', report_upper) and not re.search(r'\bSELL\b', report_upper):
            return "BUY"
        elif re.search(r'\bSELL\b', report_upper) and not re.search(r'\bBUY\b', report_upper):
            return "SELL"
        elif re.search(r'\bHOLD\b', report_upper):
            return "HOLD"
        else:
            return "UNKNOWN"
    
    def _determine_market_direction(
        self,
        old_market: Optional[Dict[str, Any]],
        new_market: Report
    ) -> str:
        """Determine if market went UP, DOWN, or FLAT using LLM analysis"""
        if old_market is None:
            return "UNKNOWN"
        
        old_content = old_market.get("content", "")[:1500]
        new_content = new_market.content[:1500]
        
        # Try LLM-based analysis first
        if self.llm:
            try:
                prompt = f"""Compare these two market reports and determine the market direction.

PREVIOUS MARKET REPORT:
{old_content}

CURRENT MARKET REPORT:
{new_content}

Analyze price movements, trends, and sentiment to determine market direction.

Output JSON:
{{
    "direction": "UP" or "DOWN" or "FLAT",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation of why",
    "key_indicators": ["list of key indicators used"]
}}"""
                
                messages = [
                    {"role": "system", "content": "You are a market analyst. Determine market direction. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ]
                
                response = self.llm.complete_json(messages)
                direction = response.get("direction", "UNKNOWN").upper()
                
                if direction in ["UP", "DOWN", "FLAT"]:
                    logger.info(f"LLM determined market direction: {direction} (confidence: {response.get('confidence', 'N/A')})")
                    return direction
                    
            except Exception as e:
                logger.error(f"LLM market direction analysis failed: {e}. Using heuristic fallback.")
        
        # Heuristic fallback
        return self._determine_market_direction_heuristic(new_content)
    
    def _determine_market_direction_heuristic(self, content: str) -> str:
        """Heuristic fallback for market direction"""
        content_lower = content.lower()
        
        positive_keywords = ["up", "gain", "surge", "rally", "bullish", "growth", "increase", 
                           "higher", "rose", "jumped", "soared", "climbed", "advancing"]
        negative_keywords = ["down", "loss", "drop", "decline", "bearish", "decrease", "fall",
                           "lower", "fell", "plunged", "tumbled", "slid", "retreating"]
        
        positive_count = sum(1 for k in positive_keywords if k in content_lower)
        negative_count = sum(1 for k in negative_keywords if k in content_lower)
        
        if positive_count > negative_count + 2:
            return "UP"
        elif negative_count > positive_count + 2:
            return "DOWN"
        else:
            return "FLAT"
    
    def _check_correctness(self, recommendation: str, market_direction: str) -> Optional[bool]:
        """Check if recommendation matched market direction"""
        if recommendation == "UNKNOWN" or market_direction == "UNKNOWN":
            return None
        
        correct_map = {
            ("BUY", "UP"): True,
            ("STRONG BUY", "UP"): True,
            ("SELL", "DOWN"): True,
            ("STRONG SELL", "DOWN"): True,
            ("HOLD", "FLAT"): True,
            ("BUY", "DOWN"): False,
            ("STRONG BUY", "DOWN"): False,
            ("SELL", "UP"): False,
            ("STRONG SELL", "UP"): False,
        }
        
        return correct_map.get((recommendation, market_direction), None)
    
    def _generate_reasoning(
        self,
        recommendation: str,
        market_direction: str,
        was_correct: Optional[bool]
    ) -> str:
        """Generate reasoning for the validation result"""
        if was_correct is None:
            return f"Unable to validate: recommendation was {recommendation}, market direction was {market_direction}"
        elif was_correct:
            return f"Previous {recommendation} recommendation was correct as market moved {market_direction}"
        else:
            return f"Previous {recommendation} recommendation was incorrect as market moved {market_direction}"
