"""
Workflow API Router
Provides POST /run_workflow endpoint that:
1. Fetches all reports for a symbol
2. Prints them to console
3. Runs Bull-Bear debate
4. Returns status updates throughout
"""
import os
import sys
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_cache import get_reports_for_symbol
from event_publisher import publish_agent_status, publish_event, publish_report
from bullbear.debate_runner import run_debate_and_generate_report, get_debate_progress

router = APIRouter(prefix="/workflow", tags=["Workflow"])

# Track workflow status
_workflow_status: Dict[str, Dict[str, Any]] = {}


class WorkflowRequest(BaseModel):
    """Request body for workflow."""
    room_id: str
    user_id: str
    symbol: str
    max_rounds: Optional[int] = 2


class WorkflowResponse(BaseModel):
    """Response from workflow endpoint."""
    room_id: str
    user_id: str
    symbol: str
    status: str
    steps_completed: List[str]
    current_step: Optional[str]
    reports_found: Dict[str, bool]
    debate_status: Optional[str]
    recommendation: Optional[str]
    error: Optional[str]
    started_at: str
    updated_at: str


def _update_workflow_status(
    room_id: str,
    status: str,
    current_step: str = None,
    step_completed: str = None,
    reports_found: Dict[str, bool] = None,
    debate_status: str = None,
    recommendation: str = None,
    error: str = None
):
    """Update workflow status in memory."""
    if room_id not in _workflow_status:
        return
    
    _workflow_status[room_id]["status"] = status
    _workflow_status[room_id]["updated_at"] = datetime.utcnow().isoformat()
    
    if current_step:
        _workflow_status[room_id]["current_step"] = current_step
    if step_completed:
        _workflow_status[room_id]["steps_completed"].append(step_completed)
    if reports_found:
        _workflow_status[room_id]["reports_found"] = reports_found
    if debate_status:
        _workflow_status[room_id]["debate_status"] = debate_status
    if recommendation:
        _workflow_status[room_id]["recommendation"] = recommendation
    if error:
        _workflow_status[room_id]["error"] = error


def _run_workflow_background(room_id: str, user_id: str, symbol: str, max_rounds: int):
    """Run the complete workflow in background."""
    try:
        # ============================================================
        # STEP 1: Fetch Reports
        # ============================================================
        _update_workflow_status(room_id, "in_progress", current_step="fetching_reports")
        publish_agent_status(room_id, "workflow", "RUNNING")
        publish_agent_status(room_id, "Analyst Agent", "FETCHING_REPORTS")
        
        if DEBUG:
            print(f"\n{'='*60}")
            print(f"🚀 WORKFLOW STARTED - Room: {room_id}, User: {user_id}, Symbol: {symbol}")
            print(f"{'='*60}\n")
        
        reports = get_reports_for_symbol(symbol)
        
        report_types = ["market", "sentiment", "news", "fundamental", "facilitator"]
        reports_found = {}
        
        for report_type in report_types:
            report_data = reports.get(report_type, {})
            content = report_data.get("content", "")
            has_content = bool(content and len(str(content)) > 10)
            reports_found[report_type] = has_content
            
            if DEBUG:
                print(f"📊 {report_type.upper()}: {'✅' if has_content else '❌'} ({len(str(content))} chars)")
            
            if has_content:
                publish_agent_status(room_id, "Analyst Agent", f"{report_type}_REPORT RECEIVED")
                # Publish the actual report content to Redis
                publish_report(room_id, "Analyst Agent", {
                    "report_type": report_type,
                    "symbol": symbol,
                    "content": str(content)
                })
            else:
                publish_agent_status(room_id, "Analyst Agent", f"{report_type}_REPORT NOT_FOUND")
        
        _update_workflow_status(
            room_id, 
            "in_progress", 
            step_completed="fetching_reports",
            reports_found=reports_found
        )
        
        # Check if we have minimum required reports
        if not any(reports_found.values()):
            error_msg = f"No reports found for {symbol}. Cannot proceed with debate."
            if DEBUG:
                print(f"❌ ERROR: {error_msg}")
            _update_workflow_status(room_id, "error", error=error_msg)
            publish_agent_status(room_id, "Analyst Agent", "FAILED")
            return
        
        if DEBUG:
            print(f"✅ Reports Summary: {reports_found}")
        
        # ============================================================
        # STEP 2: Run Bull-Bear Debate
        # ============================================================
        _update_workflow_status(room_id, "in_progress", current_step="bull_bear_debate")
        
        if DEBUG:
            print(f"🐂🐻 STARTING DEBATE for {symbol} (max {max_rounds} rounds)")
        
        try:
            # Run debate (blocking)
            debate_result = run_debate_and_generate_report(
                symbol=symbol,
                max_rounds=max_rounds,
                background=False,  # Run synchronously
                room_id=room_id  # Pass room_id for pub/sub events
            )
            
            _update_workflow_status(
                room_id,
                "in_progress",
                step_completed="bull_bear_debate",
                debate_status=debate_result.get("status", "completed")
            )
            
            if DEBUG:
                print(f"📋 DEBATE COMPLETED: {debate_result.get('rounds_completed')} rounds, {debate_result.get('total_exchanges')} exchanges")
            
            publish_agent_status(room_id, "Bull Bear Debate", "COMPLETED")
            
        except ValueError as e:
            error_msg = f"Debate failed: {str(e)}"
            if DEBUG:
                print(f"❌ DEBATE ERROR: {error_msg}")
            _update_workflow_status(room_id, "error", debate_status="error", error=error_msg)
            return
        
        # ============================================================
        # STEP 3: Facilitator Report (already published via facilitator.py)
        # ============================================================
        _update_workflow_status(room_id, "in_progress", current_step="facilitator_report")
        # Note: Facilitator Agent status (RUNNING/CLOSED) and report are published 
        # in real-time by facilitator.py, so we don't duplicate here
        
        recommendation = debate_result.get("recommendation", "N/A")
        facilitator_report = debate_result.get("facilitator_report", "")
        
        if DEBUG:
            print(f"📝 FACILITATOR: Recommendation={recommendation}")
        
        _update_workflow_status(
            room_id,
            "completed",
            step_completed="facilitator_report",
            recommendation=recommendation
        )
        
        # Workflow completion - only publish workflow CLOSED status
        
        if DEBUG:
            print(f"✅ WORKFLOW COMPLETED - Room: {room_id}, Recommendation: {recommendation}")
        
    except Exception as e:
        error_msg = f"Workflow error: {str(e)}"
        if DEBUG:
            print(f"❌ WORKFLOW ERROR: {error_msg}")
        _update_workflow_status(room_id, "error", error=error_msg)
        publish_agent_status(room_id, "workflow", "FAILED")


@router.post("/run_workflow")
async def run_workflow(request: WorkflowRequest):
    """
    Run complete workflow:
    1. Fetch all reports for symbol
    2. Print reports to console
    3. Run Bull-Bear debate
    4. Return status
    
    Publishes events to Redis pub/sub for real-time updates.
    """
    room_id = request.room_id
    user_id = request.user_id
    symbol = request.symbol.upper()
    max_rounds = max(1, min(request.max_rounds or 2, 5))
    
    # Initialize workflow status
    _workflow_status[room_id] = {
        "room_id": room_id,
        "user_id": user_id,
        "symbol": symbol,
        "status": "started",
        "steps_completed": [],
        "current_step": "initializing",
        "reports_found": {},
        "debate_status": None,
        "recommendation": None,
        "error": None,
        "started_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    
    # Start workflow in background
    thread = threading.Thread(
        target=_run_workflow_background,
        args=(room_id, user_id, symbol, max_rounds),
        daemon=True
    )
    thread.start()
    
    return {
        "status": "started",
        "room_id": room_id,
        "user_id": user_id,
        "symbol": symbol,
        "max_rounds": max_rounds,
        "message": f"Workflow started. Poll GET /workflow/{room_id}/status for updates.",
    }


@router.get("/{room_id}/status")
async def get_workflow_status(room_id: str):
    """
    Get workflow status and progress.
    
    Returns:
    - status: started, in_progress, completed, error
    - steps_completed: List of completed steps
    - current_step: Current step being executed
    - reports_found: Which reports were found
    - debate_status: Bull-Bear debate status
    - recommendation: Final recommendation (if complete)
    """
    if room_id not in _workflow_status:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {room_id} not found. Start one with POST /workflow/run_workflow"
        )
    
    return _workflow_status[room_id]


@router.get("/{room_id}/reports")
async def get_workflow_reports(room_id: str):
    """Get the reports that were fetched for this workflow."""
    if room_id not in _workflow_status:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {room_id} not found"
        )
    
    status = _workflow_status[room_id]
    symbol = status.get("symbol")
    
    if not symbol:
        raise HTTPException(status_code=400, detail="No symbol found for workflow")
    
    reports = get_reports_for_symbol(symbol)
    
    return {
        "room_id": room_id,
        "symbol": symbol,
        "reports": {
            report_type: {
                "found": bool(data.get("content")),
                "content": data.get("content", "")[:500] if data.get("content") else None,
                "timestamp": data.get("timestamp")
            }
            for report_type, data in reports.items()
        }
    }
