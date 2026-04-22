# =========================
# TODO LIST TOOLS
# =========================

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from app.event_streaming import event_stream
from .base_tool import BaseTool

# TodoList storage directory
TODO_DIR = Path(__file__).parent.parent / "memory" / "todos"
TODO_DIR.mkdir(parents=True, exist_ok=True)

TODO_FILE = TODO_DIR / "todos.json"


def _load_todos() -> List[Dict[str, Any]]:
    """Load todos from file."""
    if not TODO_FILE.exists():
        return []
    try:
        with open(TODO_FILE) as f:
            return json.load(f)
    except:
        return []


def _save_todos(todos: List[Dict[str, Any]]) -> None:
    """Save todos to file."""
    with open(TODO_FILE, 'w') as f:
        json.dump(todos, f, indent=2)


class CreateTodoTool(BaseTool):
    """Create a new todo item."""
    
    name = "create_todo"
    description = "Create a new todo item"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Create a todo.
        
        Args:
            title: Todo title
            description: Optional description
            priority: "high", "medium", "low" (default: "medium")
            due_date: Optional due date (YYYY-MM-DD)
            tags: Optional list of tags
        """
        try:
            title = kwargs.get("title", "")
            description = kwargs.get("description", "")
            priority = kwargs.get("priority", "medium")
            due_date = kwargs.get("due_date", "")
            tags = kwargs.get("tags", [])
            
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_create_started", "title": title[:120], "priority": priority},
            )
            if not title:
                return {
                    "success": False,
                    "error": "title is required"
                }
            
            if priority not in ("high", "medium", "low"):
                priority = "medium"
            
            todo = {
                "id": str(uuid.uuid4()),
                "title": title,
                "description": description,
                "priority": priority,
                "due_date": due_date,
                "tags": tags if isinstance(tags, list) else [tags],
                "completed": False,
                "created_at": datetime.now().isoformat(),
                "completed_at": None,
            }
            
            todos = _load_todos()
            todos.append(todo)
            _save_todos(todos)
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_create_completed", "todo_id": todo["id"], "priority": priority},
            )
            
            return {
                "success": True,
                "result": {
                    "id": todo["id"],
                    "title": title,
                    "priority": priority,
                    "status": "created"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class ListTodosTool(BaseTool):
    """List todos with optional filtering."""
    
    name = "list_todos"
    description = "List todos with optional filtering"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        List todos.
        
        Args:
            status: "all" (default), "completed", or "pending"
            priority: Optional filter by priority ("high", "medium", "low")
            tag: Optional filter by tag
            limit: Maximum results (default: 50)
        """
        try:
            status = kwargs.get("status", "all")
            priority = kwargs.get("priority", None)
            tag = kwargs.get("tag", None)
            limit = kwargs.get("limit", 50)
            
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_list_started", "status": status, "priority": priority, "tag": tag},
            )
            todos = _load_todos()
            
            # Filter by status
            if status == "completed":
                todos = [t for t in todos if t.get("completed")]
            elif status == "pending":
                todos = [t for t in todos if not t.get("completed")]
            
            # Filter by priority
            if priority:
                todos = [t for t in todos if t.get("priority") == priority]
            
            # Filter by tag
            if tag:
                todos = [t for t in todos if tag in t.get("tags", [])]
            
            # Sort by priority and due date
            priority_order = {"high": 0, "medium": 1, "low": 2}
            todos = sorted(todos, key=lambda x: (
                x.get("completed"),  # Incomplete first
                priority_order.get(x.get("priority", "medium"), 1),  # Priority
                x.get("due_date", "9999-12-31")  # Due date
            ))
            
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_list_completed", "count": len(todos[:limit])},
            )
            return {
                "success": True,
                "result": {
                    "count": len(todos[:limit]),
                    "todos": todos[:limit]
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class CompleteTodoTool(BaseTool):
    """Mark a todo as completed."""
    
    name = "complete_todo"
    description = "Mark a todo as completed"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Mark todo as completed.
        
        Args:
            todo_id: The ID of the todo to complete
        """
        try:
            todo_id = kwargs.get("todo_id", "")
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_complete_started", "todo_id": todo_id},
            )
            
            if not todo_id:
                return {
                    "success": False,
                    "error": "todo_id is required"
                }
            
            todos = _load_todos()
            
            updated = False
            for todo in todos:
                if todo["id"] == todo_id:
                    todo["completed"] = True
                    todo["completed_at"] = datetime.now().isoformat()
                    updated = True
                    break
            
            if not updated:
                return {
                    "success": False,
                    "error": f"Todo {todo_id} not found"
                }
            
            _save_todos(todos)
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_complete_completed", "todo_id": todo_id},
            )
            
            return {
                "success": True,
                "result": {
                    "id": todo_id,
                    "status": "completed"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class UpdateTodoTool(BaseTool):
    """Update a todo item."""
    
    name = "update_todo"
    description = "Update a todo item"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Update a todo.
        
        Args:
            todo_id: The ID of the todo to update
            title: Optional new title
            description: Optional new description
            priority: Optional new priority
            due_date: Optional new due date
            tags: Optional new tags
        """
        try:
            todo_id = kwargs.get("todo_id", "")
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_update_started", "todo_id": todo_id},
            )
            
            if not todo_id:
                return {
                    "success": False,
                    "error": "todo_id is required"
                }
            
            todos = _load_todos()
            
            updated = False
            for todo in todos:
                if todo["id"] == todo_id:
                    if "title" in kwargs:
                        todo["title"] = kwargs["title"]
                    if "description" in kwargs:
                        todo["description"] = kwargs["description"]
                    if "priority" in kwargs:
                        todo["priority"] = kwargs["priority"]
                    if "due_date" in kwargs:
                        todo["due_date"] = kwargs["due_date"]
                    if "tags" in kwargs:
                        tags = kwargs["tags"]
                        todo["tags"] = tags if isinstance(tags, list) else [tags]
                    updated = True
                    break
            
            if not updated:
                return {
                    "success": False,
                    "error": f"Todo {todo_id} not found"
                }
            
            _save_todos(todos)
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_update_completed", "todo_id": todo_id},
            )
            
            return {
                "success": True,
                "result": {
                    "id": todo_id,
                    "status": "updated"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class DeleteTodoTool(BaseTool):
    """Delete a todo item."""
    
    name = "delete_todo"
    description = "Delete a todo item"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Delete a todo.
        
        Args:
            todo_id: The ID of the todo to delete
        """
        try:
            todo_id = kwargs.get("todo_id", "")
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_delete_started", "todo_id": todo_id},
            )
            
            if not todo_id:
                return {
                    "success": False,
                    "error": "todo_id is required"
                }
            
            todos = _load_todos()
            initial_count = len(todos)
            todos = [t for t in todos if t["id"] != todo_id]
            
            if len(todos) == initial_count:
                return {
                    "success": False,
                    "error": f"Todo {todo_id} not found"
                }
            
            _save_todos(todos)
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_delete_completed", "todo_id": todo_id},
            )
            
            return {
                "success": True,
                "result": {
                    "id": todo_id,
                    "status": "deleted"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class GetTodoStatsTool(BaseTool):
    """Get todo statistics."""
    
    name = "get_todo_stats"
    description = "Get todo statistics (completed, pending, by priority)"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Get todo statistics.
        """
        try:
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_stats_started"},
            )
            todos = _load_todos()
            
            completed = len([t for t in todos if t.get("completed")])
            pending = len([t for t in todos if not t.get("completed")])
            
            by_priority = {
                "high": len([t for t in todos if t.get("priority") == "high"]),
                "medium": len([t for t in todos if t.get("priority") == "medium"]),
                "low": len([t for t in todos if t.get("priority") == "low"]),
            }
            
            overdue = 0
            today = datetime.now().date().isoformat()
            for todo in todos:
                if not todo.get("completed") and todo.get("due_date") and todo.get("due_date") < today:
                    overdue += 1
            
            event_stream.emit(
                "tool_progress",
                {"tool_name": self.name, "stage": "todo_stats_completed", "total": len(todos), "pending": pending},
            )
            return {
                "success": True,
                "result": {
                    "total": len(todos),
                    "completed": completed,
                    "pending": pending,
                    "overdue": overdue,
                    "by_priority": by_priority,
                    "completion_rate": f"{(completed / len(todos) * 100):.1f}%" if todos else "0%"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
