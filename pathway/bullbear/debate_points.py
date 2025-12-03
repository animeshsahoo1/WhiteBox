"""
Debate Points Manager
Handles saving and loading debate points to/from JSON files
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import glob

from .config import DebateConfig, get_config
from .state import DebatePoint, DebateParty

logger = logging.getLogger(__name__)


class DebatePointsManager:
    """
    Manages debate points - saving new points, loading history, and cleanup.
    """
    
    def __init__(self, config: Optional[DebateConfig] = None):
        self.config = config or get_config().debate
        self.debate_dir = Path(self.config.debate_dir)
        self.debate_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_symbol_dir(self, symbol: str) -> Path:
        """Get the debate directory for a symbol (shared across all sessions)"""
        symbol_dir = self.debate_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        return symbol_dir
    
    def _get_symbol_debate_dir(self, symbol: str, session_id: str) -> Path:
        """Get the debate directory for a symbol and session (legacy, kept for compatibility)"""
        symbol_dir = self.debate_dir / symbol / session_id
        symbol_dir.mkdir(parents=True, exist_ok=True)
        return symbol_dir
    
    def _get_point_filename(self, point: DebatePoint, session_id: str = None) -> str:
        """Generate filename for a debate point"""
        timestamp = point.timestamp.replace(":", "-").replace(".", "-")
        session_prefix = f"{session_id}_" if session_id else ""
        return f"{session_prefix}{point.party.value}_{timestamp}_{point.id[:8]}.json"
    
    def save_point_to_symbol_folder(self, symbol: str, session_id: str, point: DebatePoint) -> Path:
        """
        Save a debate point to a JSON file in the symbol folder (shared across sessions).
        Points from all sessions accumulate in the same folder.
        
        Args:
            symbol: Stock symbol
            session_id: Debate session ID (used in filename for traceability)
            point: DebatePoint to save
            
        Returns:
            Path to the saved file
        """
        symbol_dir = self._get_symbol_dir(symbol)
        filename = self._get_point_filename(point, session_id)
        filepath = symbol_dir / filename
        
        # Add session_id to the point data for traceability
        point_data = point.to_dict()
        point_data["session_id"] = session_id
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(point_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved debate point to symbol folder: {filepath}")
            print(f"  📁 Persisted to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving debate point: {e}")
            raise
    
    def save_point(self, symbol: str, session_id: str, point: DebatePoint) -> Path:
        """
        Save a debate point to a JSON file.
        
        Args:
            symbol: Stock symbol
            session_id: Debate session ID
            point: DebatePoint to save
            
        Returns:
            Path to the saved file
        """
        debate_dir = self._get_symbol_debate_dir(symbol, session_id)
        filename = self._get_point_filename(point)
        filepath = debate_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(point.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved debate point: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving debate point: {e}")
            raise
    
    def save_all_points(
        self,
        symbol: str,
        session_id: str,
        points: List[DebatePoint]
    ) -> List[Path]:
        """
        Save all debate points from a session.
        
        Args:
            symbol: Stock symbol
            session_id: Debate session ID
            points: List of DebatePoints to save
            
        Returns:
            List of saved file paths
        """
        saved_paths = []
        for point in points:
            try:
                path = self.save_point(symbol, session_id, point)
                saved_paths.append(path)
            except Exception as e:
                logger.error(f"Failed to save point {point.id}: {e}")
        
        return saved_paths
    
    def load_session_points(self, symbol: str, session_id: str) -> List[Dict[str, Any]]:
        """
        Load all points from a debate session.
        
        Args:
            symbol: Stock symbol
            session_id: Session ID
            
        Returns:
            List of point dictionaries
        """
        debate_dir = self._get_symbol_debate_dir(symbol, session_id)
        points = []
        
        for filepath in sorted(debate_dir.glob("*.json")):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    points.append(json.load(f))
            except Exception as e:
                logger.error(f"Error loading point {filepath}: {e}")
        
        return points
    
    def load_latest_session(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        Load points from the most recent debate session.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            List of points or None if no sessions exist
        """
        symbol_dir = self.debate_dir / symbol
        if not symbol_dir.exists():
            return None
        
        sessions = sorted(symbol_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        
        if not sessions:
            return None
        
        latest_session = sessions[0].name
        return self.load_session_points(symbol, latest_session)
    
    def load_all_symbol_points(
        self,
        symbol: str,
        party: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Load all debate points from a symbol folder (across all sessions).
        Points are stored directly in the symbol folder.
        
        Args:
            symbol: Stock symbol
            party: Filter by 'bull' or 'bear' (optional)
            limit: Maximum points to return
            
        Returns:
            List of point dictionaries sorted by timestamp
        """
        symbol_dir = self._get_symbol_dir(symbol)
        if not symbol_dir.exists():
            return []
        
        all_points = []
        
        # Look for JSON files directly in symbol folder
        pattern = f"*_{party}_*.json" if party else "*.json"
        for filepath in symbol_dir.glob(pattern):
            if not filepath.is_file():
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    point = json.load(f)
                    all_points.append(point)
            except Exception as e:
                logger.error(f"Error loading point {filepath}: {e}")
        
        # Sort by timestamp and limit
        all_points.sort(key=lambda p: p.get("timestamp", ""))
        return all_points[:limit]
    
    def get_historical_points(
        self,
        symbol: str,
        party: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get historical debate points across all sessions.
        
        Args:
            symbol: Stock symbol
            party: Filter by 'bull' or 'bear'
            limit: Maximum points to return
            
        Returns:
            List of point dictionaries
        """
        symbol_dir = self.debate_dir / symbol
        if not symbol_dir.exists():
            return []
        
        all_points = []
        
        for session_dir in symbol_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            pattern = f"{party}_*.json" if party else "*.json"
            for filepath in session_dir.glob(pattern):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        point = json.load(f)
                        point["session_id"] = session_dir.name
                        all_points.append(point)
                except Exception as e:
                    logger.error(f"Error loading point {filepath}: {e}")
        
        # Sort by timestamp and limit
        all_points.sort(key=lambda p: p.get("timestamp", ""), reverse=True)
        return all_points[:limit]
    
    def cleanup_old_points(self, symbol: str, session_id: str) -> int:
        """
        Remove old point files from a session.
        Called before saving new points.
        
        Args:
            symbol: Stock symbol
            session_id: Session to clean up
            
        Returns:
            Number of files removed
        """
        debate_dir = self._get_symbol_debate_dir(symbol, session_id)
        removed_count = 0
        
        for filepath in debate_dir.glob("*.json"):
            try:
                filepath.unlink()
                removed_count += 1
            except Exception as e:
                logger.error(f"Error removing {filepath}: {e}")
        
        logger.info(f"Cleaned up {removed_count} old point files")
        return removed_count
    
    def cleanup_old_sessions(
        self,
        symbol: str,
        keep_sessions: int = 5
    ) -> int:
        """
        Remove old debate sessions, keeping only recent ones.
        
        Args:
            symbol: Stock symbol
            keep_sessions: Number of sessions to keep
            
        Returns:
            Number of sessions removed
        """
        symbol_dir = self.debate_dir / symbol
        if not symbol_dir.exists():
            return 0
        
        sessions = sorted(
            symbol_dir.iterdir(),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        removed_count = 0
        for session_dir in sessions[keep_sessions:]:
            if session_dir.is_dir():
                try:
                    import shutil
                    shutil.rmtree(session_dir)
                    removed_count += 1
                except Exception as e:
                    logger.error(f"Error removing session {session_dir}: {e}")
        
        return removed_count
    
    def save_session_summary(
        self,
        symbol: str,
        session_id: str,
        summary: Dict[str, Any]
    ) -> Path:
        """
        Save a session summary file.
        
        Args:
            symbol: Stock symbol
            session_id: Session ID
            summary: Summary data to save
            
        Returns:
            Path to saved file
        """
        debate_dir = self._get_symbol_debate_dir(symbol, session_id)
        filepath = debate_dir / "_session_summary.json"
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            return filepath
        except Exception as e:
            logger.error(f"Error saving session summary: {e}")
            raise


def convert_dict_to_debate_point(data: Dict[str, Any]) -> DebatePoint:
    """Convert a dictionary to a DebatePoint object"""
    return DebatePoint(
        id=data.get("id", ""),
        party=DebateParty(data.get("party", "bull")),
        content=data.get("content", ""),
        supporting_evidence=data.get("supporting_evidence", []),
        counter_to=data.get("counter_to"),
        confidence=data.get("confidence", 0.8),
        timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
        is_unique=data.get("is_unique", True),
        rag_sources=data.get("rag_sources", [])
    )
