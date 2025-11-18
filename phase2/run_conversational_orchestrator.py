#!/usr/bin/env python3
"""
Run the Conversational Strategy Orchestrator

This script starts the conversational interface that wraps the LangGraph workflow.
Users can chat naturally to explore strategies, get recommendations, and perform analysis.

Usage:
    python run_conversational_orchestrator.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.conversational_interface import main

if __name__ == "__main__":
    main()
