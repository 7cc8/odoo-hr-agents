"""
Agent Events Service - Phase 3, Task 3.4.1

This service provides event tracking for agent execution in the Odoo HR Agents system.
It enables real-time monitoring and debugging of agent behavior through structured event logging.

Features:
- Emit agent events with timestamp, action, decision, reasoning, and status
- Retrieve event history for a specific operation
- Clear events for testing
- JSONL format for efficient append operations
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Events directory configuration
EVENTS_DIR = Path("logs/agent_events")
EVENTS_DIR.mkdir(parents=True, exist_ok=True)


def emit_agent_event(
    operation_id: str,
    agent: str,
    action: str,
    decision: Optional[str] = None,
    reasoning: Optional[str] = None,
    status: str = "in_progress"
) -> None:
    """
    Emit an agent event for tracking and observability.
    
    Events are written in JSONL format (one JSON object per line) to allow
    efficient appending and streaming reads.
    
    Args:
        operation_id: Unique identifier for the operation (e.g., run_id)
        agent: Name of the agent (e.g., "Seraj Meta-Agent", "Fahas", "Mudaqqiq")
        action: Action being performed (e.g., "orchestrate", "perceive", "plan", "execute")
        decision: Optional decision made by the agent
        reasoning: Optional reasoning or explanation for the action
        status: Current status - "in_progress", "success", or "failed"
    
    Example:
        emit_agent_event(
            operation_id="run_123",
            agent="Fahas (Query)",
            action="execute",
            decision="Fetched 45 departments",
            reasoning="User requested department list",
            status="success"
        )
    """
    if not operation_id:
        logger.warning("Cannot emit agent event without operation_id")
        return
    
    event = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent,
        "action": action,
        "decision": decision,
        "reasoning": reasoning,
        "status": status
    }
    
    event_file = EVENTS_DIR / f"{operation_id}.jsonl"
    
    try:
        with open(event_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        
        logger.debug(f"Agent event emitted: {agent} - {action} - {status}")
    except Exception as exc:
        logger.error(f"Failed to emit agent event: {exc}")


def get_agent_events(operation_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all agent events for a specific operation.
    
    Returns events in chronological order (order of writing).
    
    Args:
        operation_id: The operation ID to retrieve events for
        
    Returns:
        List of event dictionaries, empty list if no events exist
        
    Example:
        events = get_agent_events("run_123")
        for event in events:
            print(f"{event['timestamp']} - {event['agent']}: {event['action']}")
    """
    event_file = EVENTS_DIR / f"{operation_id}.jsonl"
    
    if not event_file.exists():
        logger.debug(f"No events found for operation: {operation_id}")
        return []
    
    events = []
    
    try:
        with open(event_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:  # Skip empty lines
                    events.append(json.loads(line))
        
        logger.debug(f"Retrieved {len(events)} events for operation: {operation_id}")
        return events
    except Exception as exc:
        logger.error(f"Failed to read agent events: {exc}")
        return []


def clear_agent_events(operation_id: str) -> bool:
    """
    Clear all agent events for a specific operation.
    
    Useful for testing and cleanup.
    
    Args:
        operation_id: The operation ID to clear events for
        
    Returns:
        bool: True if events were cleared, False if file didn't exist
    """
    event_file = EVENTS_DIR / f"{operation_id}.jsonl"
    
    if not event_file.exists():
        return False
    
    try:
        event_file.unlink()
        logger.info(f"Cleared agent events for operation: {operation_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to clear agent events: {exc}")
        return False


def get_recent_operations(limit: int = 10) -> List[str]:
    """
    Get list of recent operation IDs that have event logs.
    
    Args:
        limit: Maximum number of operation IDs to return
        
    Returns:
        List of operation IDs, most recent first
    """
    if not EVENTS_DIR.exists():
        return []
    
    try:
        event_files = sorted(
            EVENTS_DIR.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        operation_ids = [f.stem for f in event_files[:limit]]
        return operation_ids
    except Exception as exc:
        logger.error(f"Failed to get recent operations: {exc}")
        return []


def get_event_summary(operation_id: str) -> Dict[str, Any]:
    """
    Get a summary of events for an operation.
    
    Args:
        operation_id: The operation ID to summarize
        
    Returns:
        Dict with summary statistics
    """
    events = get_agent_events(operation_id)
    
    if not events:
        return {
            "operation_id": operation_id,
            "total_events": 0,
            "agents": [],
            "status": "no_events"
        }
    
    agents = list(set(e.get("agent", "unknown") for e in events))
    statuses = [e.get("status", "unknown") for e in events]
    
    # Determine overall status
    if "failed" in statuses:
        overall_status = "failed"
    elif all(s == "success" for s in statuses if s != "in_progress"):
        overall_status = "success"
    else:
        overall_status = "in_progress"
    
    return {
        "operation_id": operation_id,
        "total_events": len(events),
        "agents": agents,
        "status": overall_status,
        "first_event": events[0].get("timestamp") if events else None,
        "last_event": events[-1].get("timestamp") if events else None
    }
