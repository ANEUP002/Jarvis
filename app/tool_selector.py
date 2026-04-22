from typing import Dict, List, Any


class ToolSelector:
    """
    Selects appropriate tools for agents based on task characteristics.
    """
    
    # Tool recommendations by task type
    TOOL_RECOMMENDATIONS = {
        "code": {
            "primary": ["execute_code", "file_search"],
            "secondary": ["write_file", "read_file", "vector_search"],
            "memory": ["save_memory", "load_memory"],
        },
        "research": {
            "primary": ["duckduckgo_search", "serpapi_search", "semantic_search"],
            "secondary": ["vector_search", "fetch_webpage", "parse_json"],
            "memory": ["save_memory", "load_memory", "list_memory"],
        },
        "writer": {
            "primary": ["write_file", "read_file"],
            "secondary": ["vector_search", "process_text"],
            "memory": ["save_memory", "load_memory"],
        },
    }
    
    # Tool recommendations by complexity
    COMPLEXITY_TOOLS = {
        "simple": {
            "search": ["duckduckgo_search"],  # Free, no API key
            "memory": ["save_memory", "load_memory"],
            "execution": ["execute_code"],
        },
        "complex": {
            "search": ["serpapi_search", "google_search", "semantic_search"],
            "memory": ["save_memory", "load_memory", "vector_search"],
            "execution": ["execute_code", "execute_shell"],
        },
    }

    SPECIAL_TOOL_KEYWORDS = {
        "email": ["send_email", "list_emails", "search_emails"],
        "todo": ["create_todo", "list_todos", "get_todo_stats"],
        "schedule": ["create_todo", "list_todos", "get_todo_stats"],
        "weather": ["get_weather"],
        "forecast": ["get_weather"],
        "temperature": ["get_weather"],
    }
    
    @staticmethod
    def select_tools(task_type: str, complexity: str = "simple", custom_tools: List[str] = None, task_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Select tools for a given task.
        
        Args:
            task_type: "code", "research", or "writer"
            complexity: "simple" or "complex"
            custom_tools: Override with specific tool names
            
        Returns:
            Dict with selected tools and configuration
        """
        if custom_tools:
            return {
                "task_type": task_type,
                "complexity": complexity,
                "primary_tools": custom_tools,
                "secondary_tools": [],
                "memory_tools": [],
                "custom": True
            }
        
        # Get task-based recommendations
        task_tools = ToolSelector.TOOL_RECOMMENDATIONS.get(task_type, {})
        complexity_tools = ToolSelector.COMPLEXITY_TOOLS.get(complexity, {})
        
        # Build tool selection
        selection = {
            "task_type": task_type,
            "complexity": complexity,
            "primary_tools": list(task_tools.get("primary", [])),
            "secondary_tools": list(task_tools.get("secondary", [])),
            "memory_tools": list(task_tools.get("memory", [])),
            "custom": False
        }
        
        # Add keyword-driven tools from task_context
        text = "" if not task_context else str(task_context.get("input", "")).lower()
        for keyword, tools in ToolSelector.SPECIAL_TOOL_KEYWORDS.items():
            if keyword in text:
                for tool in tools:
                    if tool not in selection["primary_tools"] and tool not in selection["secondary_tools"]:
                        selection["secondary_tools"].append(tool)

        # Promote email and todo tools for writer tasks when the input indicates action
        if task_type == "writer" and "email" in text:
            if "send_email" not in selection["primary_tools"]:
                selection["primary_tools"].append("send_email")
        if "todo" in text or "follow up" in text or "schedule" in text:
            if "create_todo" not in selection["secondary_tools"]:
                selection["secondary_tools"].append("create_todo")

        # Adjust for complexity (replace simple search tools with more powerful ones if complex)
        if complexity == "complex":
            if "duckduckgo_search" in selection["primary_tools"]:
                selection["primary_tools"].remove("duckduckgo_search")
                if "serpapi_search" not in selection["secondary_tools"]:
                    selection["secondary_tools"].insert(0, "serpapi_search")

        # Deduplicate tool lists while preserving order
        selection["primary_tools"] = list(dict.fromkeys(selection["primary_tools"]))
        selection["secondary_tools"] = list(dict.fromkeys(selection["secondary_tools"]))
        selection["memory_tools"] = list(dict.fromkeys(selection["memory_tools"]))

        return selection
    

class ToolUsageTracker:
    """
    Track tool usage for analytics and optimization.
    """
    
    def __init__(self):
        self.usage_stats = {
            "total_calls": 0,
            "by_tool": {},
            "by_task": {},
            "by_agent": {},
        }
    
    def track_usage(self, tool_name: str, task_type: str, agent_name: str, success: bool, duration: float = 0):
        """Track a tool usage"""
        self.usage_stats["total_calls"] += 1
        
        # By tool
        if tool_name not in self.usage_stats["by_tool"]:
            self.usage_stats["by_tool"][tool_name] = {
                "calls": 0,
                "successes": 0,
                "total_duration": 0
            }
        self.usage_stats["by_tool"][tool_name]["calls"] += 1
        if success:
            self.usage_stats["by_tool"][tool_name]["successes"] += 1
        self.usage_stats["by_tool"][tool_name]["total_duration"] += duration
        
        # By task
        if task_type not in self.usage_stats["by_task"]:
            self.usage_stats["by_task"][task_type] = {"calls": 0, "successes": 0}
        self.usage_stats["by_task"][task_type]["calls"] += 1
        if success:
            self.usage_stats["by_task"][task_type]["successes"] += 1
        
        # By agent
        if agent_name not in self.usage_stats["by_agent"]:
            self.usage_stats["by_agent"][agent_name] = {"calls": 0, "successes": 0}
        self.usage_stats["by_agent"][agent_name]["calls"] += 1
        if success:
            self.usage_stats["by_agent"][agent_name]["successes"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return self.usage_stats
    
    def get_tool_stats(self, tool_name: str) -> Dict[str, Any]:
        """Get stats for a specific tool"""
        if tool_name not in self.usage_stats["by_tool"]:
            return None
        
        stats = self.usage_stats["by_tool"][tool_name]
        success_rate = stats["successes"] / stats["calls"] if stats["calls"] > 0 else 0
        avg_duration = stats["total_duration"] / stats["calls"] if stats["calls"] > 0 else 0
        
        return {
            "tool": tool_name,
            "calls": stats["calls"],
            "success_rate": round(success_rate, 2),
            "avg_duration": round(avg_duration, 3),
        }
    
    def print_summary(self):
        """Print usage summary"""
        print("\n" + "="*60)
        print("TOOL USAGE SUMMARY")
        print("="*60)
        
        print(f"\nTotal Calls: {self.usage_stats['total_calls']}")
        
        print("\nBy Tool:")
        for tool in sorted(self.usage_stats["by_tool"].keys()):
            stats = self.get_tool_stats(tool)
            if stats:
                print(f"  {tool}: {stats['calls']} calls, {stats['success_rate']*100:.0f}% success, {stats['avg_duration']}s avg")
        
        print("\nBy Task Type:")
        for task_type, stats in self.usage_stats["by_task"].items():
            success_rate = stats["successes"] / stats["calls"] if stats["calls"] > 0 else 0
            print(f"  {task_type}: {stats['calls']} calls, {success_rate*100:.0f}% success")
        
        print("\nBy Agent:")
        for agent, stats in self.usage_stats["by_agent"].items():
            success_rate = stats["successes"] / stats["calls"] if stats["calls"] > 0 else 0
            print(f"  {agent}: {stats['calls']} calls, {success_rate*100:.0f}% success")
        
        print("="*60 + "\n")
