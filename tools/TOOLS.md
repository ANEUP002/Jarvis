# Tools Layer Documentation

## Overview

The **Tools Layer** provides a unified interface for agents to execute actions beyond text generation. It includes file I/O, code execution, web operations, memory management, and data processing.

## Architecture

```
tools/
├── __init__.py           # Package entry point
├── base_tool.py          # Base tool interface
├── manager.py            # Central tools manager
├── file_tools.py         # File operations
├── code_tools.py         # Code execution
├── web_tools.py          # Web search & fetch
├── memory_tools.py       # Memory/knowledge base
├── data_tools.py         # Data processing
└── examples.py           # Usage examples
```

## Quick Start

### Import and Initialize

```python
from tools import ToolsManager

manager = ToolsManager()
```

### Execute a Tool

```python
# Method 1: Using execute()
result = manager.execute("read_file", filepath="path/to/file.txt")

# Method 2: Using dict-like access
result = manager["read_file"](filepath="path/to/file.txt")
```

### Check Results

All tools return a consistent result format:

```python
{
    "success": True/False,
    "result": <data>,           # The actual result
    "error": None/<error_msg>   # Error message if failed
    # Additional tool-specific fields
}
```

## Available Tools

### File Tools

#### `read_file`
Read file contents
```python
result = manager.execute("read_file", filepath="file.txt")
# result["result"] = file contents
```

#### `write_file`
Write content to file (creates or overwrites)
```python
result = manager.execute("write_file", 
                        filepath="file.txt",
                        content="Hello, World!")
```

#### `append_file`
Append content to file
```python
result = manager.execute("append_file",
                        filepath="file.txt",
                        content="\nNew line")
```

#### `list_dir`
List directory contents
```python
result = manager.execute("list_dir", dirpath=".")
# result["result"] = list of {name, is_dir, size}
```

#### `delete_file`
Delete a file
```python
result = manager.execute("delete_file", filepath="file.txt")
```

#### `file_search`
Search for files matching a pattern (glob)
```python
result = manager.execute("file_search", 
                        pattern="*.py",
                        start_dir=".")
```

### Code Tools

#### `execute_code`
Execute Python code
```python
result = manager.execute("execute_code",
                        code="print('Hello')",
                        timeout=30)
# result["result"] = stdout
# result["error"] = stderr (if failed)
```

#### `execute_shell`
Execute shell commands
```python
result = manager.execute("execute_shell",
                        command="ls -la",
                        timeout=30)
```

### Web Tools

#### `web_search`
Search the web (requires API integration)
```python
result = manager.execute("web_search",
                        query="Python best practices",
                        max_results=5)
```

#### `fetch_webpage`
Fetch content from URL
```python
result = manager.execute("fetch_webpage",
                        url="https://example.com",
                        timeout=10)
```

#### `parse_json`
Parse and validate JSON data
```python
result = manager.execute("parse_json",
                        data='{"name": "John"}')
```

### Memory Tools

#### `save_memory`
Save information to memory
```python
result = manager.execute("save_memory",
                        key="user_config",
                        data={"theme": "dark"},
                        memory_dir="memory")
```

#### `load_memory`
Load information from memory
```python
result = manager.execute("load_memory",
                        key="user_config",
                        memory_dir="memory")
```

#### `list_memory`
List all saved memory keys
```python
result = manager.execute("list_memory", memory_dir="memory")
```

### Data Tools

#### `process_json`
Process and format JSON
```python
result = manager.execute("process_json",
                        data={"key": "value"},
                        operation="pretty")  # or "minify"
```

#### `process_csv`
Read/write CSV files
```python
# Read
result = manager.execute("process_csv",
                        filepath="data.csv",
                        operation="read")

# Write
result = manager.execute("process_csv",
                        filepath="data.csv",
                        operation="write",
                        data=[{"col1": "val1"}, {"col1": "val2"}])
```

#### `process_text`
Process text data
```python
result = manager.execute("process_text",
                        text="Hello. World.",
                        operation="count")  # "count", "lines", "sentences"
```

## Using Tools in Agents

### Example: Code Agent with Tools

```python
from tools import ToolsManager
from providers.llm_provider import generate

def run(task: dict, model: str = "groq/llama3-8b") -> dict:
    manager = ToolsManager()
    input_text = task.get("input", "")
    
    # Generate code
    prompt = f"""Write Python code for: {input_text}"""
    code = generate(prompt, model=model)
    
    # Execute the generated code
    result = manager.execute("execute_code", code=code)
    
    return {
        "response": result["result"],
        "code": code,
        "success": result["success"]
    }
```

### Example: Research Agent with Tools

```python
def run(task: dict, model: str = "groq/mixtral") -> dict:
    manager = ToolsManager()
    
    # Search for information
    search_result = manager.execute("web_search", query=task["input"])
    
    # Save findings to memory
    manager.execute("save_memory", 
                   key=f"research_{task['id']}",
                   data=search_result["result"])
    
    # Generate research summary
    prompt = f"""Summarize findings from search"""
    response = generate(prompt, model=model)
    
    return {"response": response}
```

## Tool Registry

List all tools:
```python
manager.list_tools()
# Returns: ['read_file', 'write_file', 'list_dir', ...]

# Get info about a specific tool
info = manager.get_tool_info("read_file")
# Returns: {"name": "read_file", "description": "..."}

# Get info about all tools
all_info = manager.get_tool_info()
```

## Error Handling

All tools follow a consistent error format:

```python
result = manager.execute("read_file", filepath="nonexistent.txt")

if not result["success"]:
    print(f"Error: {result['error']}")
else:
    print(f"Success: {result['result']}")
```

## Adding New Tools

1. Create a new tool class inheriting from `BaseTool`:

```python
from tools.base_tool import BaseTool
from typing import Any, Dict

class MyCustomTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        try:
            # Your implementation
            return {
                "success": True,
                "result": <your_result>,
                "error": None
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}
```

2. Register in `manager.py`:

```python
from tools.custom_tools import MyCustomTool

# Add to __init__
self.tools["my_tool"] = MyCustomTool()
```

## Best Practices

1. **Always check success**: Always verify `result["success"]` before using `result["result"]`
2. **Handle timeouts**: Set reasonable timeouts for code/shell execution
3. **Validate input**: Validate file paths and user input before execution
4. **Use memory**: Cache results using the memory tools to avoid redundant operations
5. **Error messages**: Provide clear error messages and context

## Examples

Run the examples:
```bash
python tools/examples.py
```

This will demonstrate all available tools and their usage patterns.
