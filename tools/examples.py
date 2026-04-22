# =========================
# TOOLS USAGE EXAMPLES
# =========================

from tools import ToolsManager


def example_file_operations():
    """Example: File operations"""
    manager = ToolsManager()
    
    # Write a file
    result = manager.execute("write_file", 
                            filepath="test.txt",
                            content="Hello, World!")
    print("Write result:", result)
    
    # Read the file
    result = manager.execute("read_file", filepath="test.txt")
    print("Read result:", result)
    
    # List directory
    result = manager.execute("list_dir", dirpath=".")
    print("List dir result:", result)


def example_code_execution():
    """Example: Execute Python code"""
    manager = ToolsManager()
    
    code = """
import math
result = math.sqrt(16)
print(f"Square root of 16: {result}")
"""
    
    result = manager.execute("execute_code", code=code)
    print("Code execution result:", result)


def example_memory():
    """Example: Save and load memory"""
    manager = ToolsManager()
    
    # Save memory
    data = {
        "user_id": 123,
        "preferences": {"theme": "dark", "lang": "en"}
    }
    result = manager.execute("save_memory", key="user_profile", data=data)
    print("Save memory result:", result)
    
    # Load memory
    result = manager.execute("load_memory", key="user_profile")
    print("Load memory result:", result)
    
    # List memory
    result = manager.execute("list_memory")
    print("List memory result:", result)


def example_data_processing():
    """Example: Process text and JSON"""
    manager = ToolsManager()
    
    # Process text
    text = "Hello World. This is a test. Amazing stuff!"
    result = manager.execute("process_text", text=text, operation="count")
    print("Text count result:", result)
    
    # Process JSON
    data = {"name": "John", "age": 30}
    result = manager.execute("process_json", data=data, operation="pretty")
    print("JSON pretty result:", result)


def show_available_tools():
    """Show all available tools"""
    manager = ToolsManager()
    
    print("\n=== AVAILABLE TOOLS ===\n")
    tools_info = manager.get_tool_info()
    
    for tool_name, info in tools_info.items():
        print(f"📌 {info['name']}")
        print(f"   {info['description']}\n")


if __name__ == "__main__":
    print("=== TOOLS LAYER EXAMPLES ===\n")
    
    # Show all tools
    show_available_tools()
    
    # Run examples
    print("\n=== RUNNING EXAMPLES ===\n")
    
    print("1. File Operations:")
    example_file_operations()
    
    print("\n2. Code Execution:")
    example_code_execution()
    
    print("\n3. Memory Operations:")
    example_memory()
    
    print("\n4. Data Processing:")
    example_data_processing()
