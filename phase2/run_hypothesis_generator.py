#!/usr/bin/env python3
"""
Entry point for Hypothesis Generator

Run: python -m phase2.run_hypothesis_generator
"""

import logging
from phase2.hypothesis_generator.generator import run_hypothesis_generator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Start hypothesis generator"""
    logger.info("=" * 60)
    logger.info("PHASE 2: HYPOTHESIS GENERATOR")
    logger.info("=" * 60)
    
    try:
        run_hypothesis_generator()
    except KeyboardInterrupt:
        logger.info("Hypothesis Generator stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
