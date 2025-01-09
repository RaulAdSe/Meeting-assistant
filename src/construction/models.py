from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid
from src.historical_data.models.models import Severity, ProblemStatus
from src.location.models.location import LocationChange

class ProblemCategory(str, Enum):
    STRUCTURAL = "structural"
    SAFETY = "safety"
    QUALITY = "quality"
    SCHEDULE = "schedule"
    RESOURCE = "resource"
    ENVIRONMENTAL = "environmental"
    OTHER = "other"

class AnalysisConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class LocationContext:
    """Context information about the location where a problem was identified"""
    area: str
    sub_location: Optional[str] = None
    coordinates: Optional[tuple[float, float]] = None
    floor_level: Optional[int] = None
    change_history: List[LocationChange] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ConstructionProblem:
    """Represents a construction problem identified during analysis"""
    category: ProblemCategory
    description: str
    severity: Severity  # Using historical_data Severity enum
    location_context: LocationContext
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    identified_at: datetime = field(default_factory=datetime.now)
    status: ProblemStatus = ProblemStatus.IDENTIFIED  # Using historical_data ProblemStatus
    confidence: AnalysisConfidence = AnalysisConfidence.MEDIUM
    historical_pattern: Optional[bool] = None
    related_problems: List[uuid.UUID] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProposedSolution:
    """Represents a proposed solution to a construction problem"""
    problem_id: uuid.UUID
    description: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    estimated_time: Optional[int] = None  # in minutes
    estimated_cost: Optional[float] = None
    required_resources: List[str] = field(default_factory=list)
    priority: int = 1  # 1 (highest) to 5 (lowest)
    effectiveness_rating: Optional[float] = None
    prerequisites: List[str] = field(default_factory=list)
    historical_success_rate: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AnalysisContext:
    """Context information for construction analysis"""
    visit_id: uuid.UUID
    location_id: uuid.UUID
    datetime: datetime
    weather_conditions: Optional[Dict[str, Any]] = None
    site_conditions: Optional[Dict[str, Any]] = None
    previous_visit_findings: List[Dict] = field(default_factory=list)
    location_changes: List[LocationChange] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AnalysisResult:
    """Results of a construction site analysis"""
    context: AnalysisContext
    problems: List[ConstructionProblem]
    solutions: Dict[uuid.UUID, List[ProposedSolution]]  # problem_id -> solutions
    confidence_scores: Dict[str, float]
    execution_time: float  # in seconds
    metadata: Dict[str, Any] = field(default_factory=dict)