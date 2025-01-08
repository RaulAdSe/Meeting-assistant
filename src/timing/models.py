from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    BLOCKED = "blocked"

class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class Task:
    """Represents a task identified in the transcript"""
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str
    description: str
    priority: TaskPriority
    estimated_duration: int  # in minutes
    dependencies: List[uuid.UUID] = field(default_factory=list)
    assignee: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Timeline:
    """Represents the overall timeline of tasks"""
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    visit_id: uuid.UUID
    tasks: List[Task] = field(default_factory=list)
    planned_start: datetime
    planned_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    location: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)