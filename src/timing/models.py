from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Set
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

class TaskRelationType(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DELAY = "delay"

@dataclass
class Duration:
    amount: float
    unit: str
    
    def to_days(self) -> float:
        """Convert duration to days, supporting both English and Spanish units"""
        unit = self.unit.lower()
        
        # English units
        if unit in ['day', 'days']:
            return self.amount
        elif unit in ['week', 'weeks']:
            return self.amount * 7
        elif unit in ['month', 'months']:
            return self.amount * 30
        
        # Spanish units
        elif unit in ['dia', 'dias', 'día', 'días']:
            return self.amount
        elif unit in ['semana', 'semanas']:
            return self.amount * 7
        elif unit in ['mes', 'meses']:
            return self.amount * 30
        else:
            supported_units = [
                'day/days', 'week/weeks', 'month/months',
                'dia/días', 'semana/semanas', 'mes/meses'
            ]
            raise ValueError(
                f"Unsupported duration unit: {self.unit}. "
                f"Supported units: {', '.join(supported_units)}"
            )

@dataclass
class Task:
    """Represents a task identified in the transcript"""
    name: str
    description: str
    duration: Duration
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    can_be_parallel: bool = False
    responsible: Optional[str] = None
    location: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TaskRelationship:
    """Represents a relationship between tasks"""
    from_task_id: uuid.UUID
    to_task_id: uuid.UUID
    relation_type: TaskRelationType
    delay: Optional[Duration] = None
    metadata: Dict[str, Any] = field(default_factory=dict)  # Add this line

@dataclass
class ScheduleGraph:
    """Represents the overall schedule as a graph of tasks"""
    tasks: Dict[uuid.UUID, Task]
    relationships: List[TaskRelationship]
    parallel_groups: List[Set[uuid.UUID]] = field(default_factory=list)

    def add_task(self, task: Task):
        self.tasks[task.id] = task

    def add_relationship(self, relationship: TaskRelationship):
        self.relationships.append(relationship)

    def add_parallel_group(self, task_ids: Set[uuid.UUID]):
        self.parallel_groups.append(task_ids)