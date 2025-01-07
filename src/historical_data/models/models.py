# src/historical_data/models/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ProblemStatus(str, Enum):
    IDENTIFIED = "identified"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    MONITORING = "monitoring"

class ChronogramStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    CANCELLED = "cancelled"

class ChecklistStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

@dataclass
class Visit:
    id: uuid.UUID
    date: datetime
    location_id: uuid.UUID
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class Problem:
    id: uuid.UUID
    visit_id: uuid.UUID
    description: str
    severity: Severity
    area: str
    status: ProblemStatus = ProblemStatus.IDENTIFIED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class Solution:
    id: uuid.UUID
    problem_id: uuid.UUID
    description: str
    implemented_at: Optional[datetime] = None
    effectiveness_rating: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.effectiveness_rating is not None and not (1 <= self.effectiveness_rating <= 5):
            raise ValueError("Effectiveness rating must be between 1 and 5")

@dataclass
class ChronogramEntry:
    id: uuid.UUID
    visit_id: uuid.UUID
    task_name: str
    planned_start: datetime
    planned_end: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: ChronogramStatus = ChronogramStatus.PLANNED
    dependencies: List[uuid.UUID] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class ChecklistTemplate:
    id: uuid.UUID
    name: str
    items: List[Dict[str, Any]]
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class VisitChecklist:
    id: uuid.UUID
    visit_id: uuid.UUID
    template_id: uuid.UUID
    completed_items: List[Dict[str, Any]] = field(default_factory=list)
    completion_status: ChecklistStatus = ChecklistStatus.PENDING
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)