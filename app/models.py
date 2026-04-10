from pydantic import BaseModel, Field   ##This file define what is a task?
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    input: str

    task_type: Optional[str] = None
    agent: Optional[str] = None
    model: Optional[str] = None

    status: str = "pending"

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None