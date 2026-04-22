# =========================
# LIVE EVENT STREAMING
# =========================
# Real-time event system for dashboard visualization

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import deque
from threading import Lock

# Event storage
EVENTS_DIR = Path(__file__).parent.parent / "memory" / "events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory event buffer for real-time access
_event_buffer = deque(maxlen=1000)
_buffer_lock = Lock()
_last_flush = time.time()

# Event types
EVENT_TYPES = {
    "task_started": "Task workflow started",
    "task_classified": "Task classified",
    "model_selected": "Model selected",
    "llm_started": "LLM request started",
    "llm_completed": "LLM request completed",
    "llm_failed": "LLM request failed",
    "tools_selected": "Tools selected",
    "tool_started": "Tool execution started",
    "tool_progress": "Tool progress update",
    "subtask_started": "Subtask execution started",
    "subtask_completed": "Subtask execution completed",
    "subtask_failed": "Subtask execution failed",
    "agent_assigned": "Agent assigned",
    "execution_started": "Execution started",
    "execution_completed": "Execution completed",
    "execution_failed": "Execution failed",
    "tool_executed": "Tool executed",
    "external_service_accessed": "External service accessed",
    "memory_accessed": "Memory accessed",
    "routine_updated": "Daily routine updated",
    "result_generated": "Result generated",
    "task_completed": "Task completed",
    "error_occurred": "Error occurred",
}


class LiveEventStream:
    """Live event streaming for dashboard visualization."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def emit(self, event_type: str, data: Dict[str, Any], level: str = "info") -> None:
        """
        Emit a live event.
        
        Args:
            event_type: Type of event (from EVENT_TYPES)
            data: Event data
            level: "info", "warning", "error"
        """
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type}")
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "description": EVENT_TYPES[event_type],
            "level": level,
            "data": data
        }
        
        with _buffer_lock:
            _event_buffer.append(event)
        self._append_event_to_disk(event)
        
        # Periodically flush to disk
        global _last_flush
        if time.time() - _last_flush > 5:  # Flush every 5 seconds
            self._flush_to_disk()
            _last_flush = time.time()
    
    def get_events(self, limit: int = 100, event_type: str = None, level: str = None) -> List[Dict[str, Any]]:
        """
        Get recent events.
        
        Args:
            limit: Maximum events to return
            event_type: Optional filter by event type
            level: Optional filter by level
        
        Returns:
            List of events
        """
        with _buffer_lock:
            events = list(_event_buffer)
        if not events:
            events = self.load_events_from_disk(hours=24)
        
        # Filter
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        if level:
            events = [e for e in events if e["level"] == level]
        
        # Return latest N
        return events[-limit:]
    
    def get_timeline(self, task_id: str = None) -> List[Dict[str, Any]]:
        """
        Get event timeline for a task.
        
        Args:
            task_id: Optional task ID to filter
        
        Returns:
            Chronological list of events
        """
        events = self.get_events(limit=1000)
        
        if task_id:
            events = [e for e in events if e.get("data", {}).get("task_id") == task_id]
        
        return events
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get event statistics.
        
        Returns:
            Dictionary with event stats
        """
        events = self.get_events(limit=1000)
        
        stats = {
            "total_events": len(events),
            "events_by_type": {},
            "events_by_level": {
                "info": len([e for e in events if e["level"] == "info"]),
                "warning": len([e for e in events if e["level"] == "warning"]),
                "error": len([e for e in events if e["level"] == "error"]),
            },
            "recent_errors": [e for e in events if e["level"] == "error"][-5:],
        }
        
        for event_type in EVENT_TYPES:
            count = len([e for e in events if e["type"] == event_type])
            if count > 0:
                stats["events_by_type"][event_type] = count
        
        return stats
    
    def clear_events(self) -> None:
        """Clear all events from buffer."""
        global _last_flush
        with _buffer_lock:
            _event_buffer.clear()
        _last_flush = time.time()
        try:
            for file in EVENTS_DIR.glob("events_*.json"):
                file.unlink()
        except Exception:
            pass

    def _append_event_to_disk(self, event: Dict[str, Any]) -> None:
        try:
            day_file = EVENTS_DIR / f"events_{datetime.now().strftime('%Y%m%d')}.jsonl"
            with day_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception:
            pass
    
    def _flush_to_disk(self) -> None:
        """Flush recent events to disk."""
        try:
            with _buffer_lock:
                events = list(_event_buffer)
            
            flush_file = EVENTS_DIR / f"events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(flush_file, 'w') as f:
                json.dump(events, f, indent=2)
        except Exception as e:
            print(f"Error flushing events: {e}")
    
    def load_events_from_disk(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Load events from disk (for recovery/history).
        
        Args:
            hours: Load events from last N hours
        
        Returns:
            List of events
        """
        try:
            cutoff = datetime.now().timestamp() - (hours * 3600)
            all_events = []
            
            for file in list(EVENTS_DIR.glob("events_*.json")) + list(EVENTS_DIR.glob("events_*.jsonl")):
                try:
                    if file.suffix == ".jsonl":
                        with open(file, encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                event = json.loads(line)
                                event_time = datetime.fromisoformat(event["timestamp"]).timestamp()
                                if event_time > cutoff:
                                    all_events.append(event)
                    else:
                        with open(file, encoding="utf-8") as f:
                            events = json.load(f)
                            for event in events:
                                event_time = datetime.fromisoformat(event["timestamp"]).timestamp()
                                if event_time > cutoff:
                                    all_events.append(event)
                except Exception:
                    pass
            
            return sorted(all_events, key=lambda x: x["timestamp"])
        
        except Exception as e:
            print(f"Error loading events from disk: {e}")
            return []


# Singleton instance
event_stream = LiveEventStream()
