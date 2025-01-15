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
    SECUENCIAL = "secuencial"  # Add Spanish variant
    PARALLEL = "parallel"
    PARALELO = "paralelo"     # Add Spanish variant
    DELAY = "delay"
    ESPERA = "espera"        # Add Spanish variant

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
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_duration: int = 0  # Duration in minutes
    assignee: Optional[str] = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    can_be_parallel: bool = False
    responsible: Optional[str] = None
    location: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[Duration] = None

@dataclass
class Timeline:
    """Represents a timeline of tasks for a visit"""
    visit_id: uuid.UUID
    planned_start: datetime
    planned_end: datetime
    tasks: List[Task]
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TaskRelationship:
    """Represents a relationship between tasks"""
    from_task_id: uuid.UUID
    to_task_id: uuid.UUID
    relation_type: TaskRelationType
    delay: Optional[Duration] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ScheduleGraph:
    """Represents the overall schedule as a graph of tasks"""
    tasks: Dict[uuid.UUID, Task]
    relationships: List[TaskRelationship]
    parallel_groups: List[Set[uuid.UUID]] = field(default_factory=list)

    def add_task(self, task: Task):
        """Add a task to the schedule"""
        self.tasks[task.id] = task

    def add_relationship(self, relationship: TaskRelationship):
        """Add a relationship to the schedule"""
        self.relationships.append(relationship)

    def add_parallel_group(self, task_ids: Set[uuid.UUID]):
        """Add a group of tasks that can be executed in parallel"""
        self.parallel_groups.append(task_ids)