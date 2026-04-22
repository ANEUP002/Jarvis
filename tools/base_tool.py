# =========================
# BASE TOOL INTERFACE
# =========================

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseTool(ABC):
    """Base class for all tools"""
    
    name: str = ""
    description: str = ""
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool with given arguments.
        
        Returns:
            {"success": bool, "result": any, "error": str (if failed)}
        """
        pass
    
    def __call__(self, **kwargs):
        return self.execute(**kwargs)
