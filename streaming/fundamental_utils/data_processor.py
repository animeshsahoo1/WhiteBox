# file: src/data_processor.py

from typing import Dict, List, Optional, Any

class FundamentalDataProcessor:
    """Processes and formats raw FMP API data for reporting."""

    @staticmethod
    def format_number(value: Any, decimals: int = 2, prefix: str = "") -> str:
        """Formats a number with commas and an optional prefix."""
        if value is None or value == "":
            return "N/A"
        try:
            num = float(value)
            return f"{prefix}{num:,.{decimals}f}"
        except (ValueError, TypeError):
            return str(value) # Return original value if formatting fails

    @staticmethod
    def format_large_number(value: Any, prefix: str = "$") -> str:
        """Formats large currency numbers into B/M/K format."""
        if value is None or value == "":
            return "N/A"
        try:
            num = float(value)
            if abs(num) >= 1_000_000_000_000:
                return f"{prefix}{num / 1_000_000_000_000:.2f}T"
            if abs(num) >= 1_000_000_000:
                return f"{prefix}{num / 1_000_000_000:.2f}B"
            elif abs(num) >= 1_000_000:
                return f"{prefix}{num / 1_000_000:.2f}M"
            elif abs(num) >= 1_000:
                return f"{prefix}{num / 1_000:.1f}K"
            else:
                return f"{prefix}{num:.2f}"
        except (ValueError, TypeError):
            return "N/A"

    @staticmethod
    def format_percentage(value: Any, multiply: bool = False) -> str:
        """Formats a value as a percentage string."""
        if value is None or value == "":
            return "N/A"
        try:
            num = float(value)
            if multiply:
                num *= 100
            return f"{num:.2f}%"
        except (ValueError, TypeError):
            return "N/A"