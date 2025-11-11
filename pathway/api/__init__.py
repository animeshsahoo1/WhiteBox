"""
Pathway Reports API Package
Exposes FastAPI endpoints to serve pathway consumer reports
"""
import sys
from pathlib import Path

# Add parent directory to path to ensure redis_cache can be imported
_parent_dir = Path(__file__).parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))
