import pytest
import uuid
from datetime import datetime
from src.construction.models import (
    ProblemCategory, AnalysisConfidence, LocationContext,
    ConstructionProblem, ProposedSolution, AnalysisContext, AnalysisResult
)
from src.historical_data.models.models import Severity, ProblemStatus
from src.location.models.location import LocationChange

def test_problem_category_enum():
    assert ProblemCategory.STRUCTURAL == "structural"
    assert ProblemCategory.SAFETY == "safety"
    assert ProblemCategory.QUALITY == "quality"
    assert ProblemCategory.SCHEDULE == "schedule"
    assert ProblemCategory.RESOURCE == "resource"
    assert ProblemCategory.ENVIRONMENTAL == "environmental"
    assert ProblemCategory.OTHER == "other"

def test_analysis_confidence_enum():
    assert AnalysisConfidence.HIGH == "high"
    assert AnalysisConfidence.MEDIUM == "medium"
    assert AnalysisConfidence.LOW == "low"

def test_location_context():
    # Create a LocationChange instance with required arguments
    location_change = LocationChange(
        timestamp=datetime.now(),
        area="Main Hall"
    )
    
    context = LocationContext(
        area="Main Hall",
        sub_location="North Wing",
        coordinates=(40.7128, -74.0060),
        floor_level=2,
        change_history=[location_change],  # Use the properly initialized LocationChange
        additional_info={"note": "Check for leaks"}
    )
    assert context.area == "Main Hall"
    assert context.sub_location == "North Wing"
    assert context.coordinates == (40.7128, -74.0060)
    assert context.floor_level == 2
    assert len(context.change_history) == 1
    assert context.additional_info["note"] == "Check for leaks"

def test_construction_problem():
    problem_id = uuid.uuid4()
    location_context = LocationContext(area="Area 51")
    problem = ConstructionProblem(
        id=problem_id,
        category=ProblemCategory.STRUCTURAL,
        description="Crack in the wall",
        severity=Severity.HIGH,
        location_context=location_context,
        status=ProblemStatus.IDENTIFIED
    )
    assert problem.id == problem_id
    assert problem.category == ProblemCategory.STRUCTURAL
    assert problem.description == "Crack in the wall"
    assert problem.severity == Severity.HIGH
    assert problem.location_context.area == "Area 51"
    assert problem.status == ProblemStatus.IDENTIFIED
    assert problem.confidence == AnalysisConfidence.MEDIUM

def test_proposed_solution():
    solution_id = uuid.uuid4()
    problem_id = uuid.uuid4()
    solution = ProposedSolution(
        id=solution_id,
        problem_id=problem_id,
        description="Apply sealant",
        estimated_time=120,
        estimated_cost=500.0,
        required_resources=["sealant", "brush"],
        priority=1,
        effectiveness_rating=0.9,
        prerequisites=["Clean surface"],
        historical_success_rate=0.85
    )
    assert solution.id == solution_id
    assert solution.problem_id == problem_id
    assert solution.description == "Apply sealant"
    assert solution.estimated_time == 120
    assert solution.estimated_cost == 500.0
    assert solution.required_resources == ["sealant", "brush"]
    assert solution.priority == 1
    assert solution.effectiveness_rating == 0.9
    assert solution.prerequisites == ["Clean surface"]
    assert solution.historical_success_rate == 0.85

def test_analysis_context():
    visit_id = uuid.uuid4()
    location_id = uuid.uuid4()
    context = AnalysisContext(
        visit_id=visit_id,
        location_id=location_id,
        datetime=datetime.now(),
        weather_conditions={"temperature": 22},
        site_conditions={"dust_level": "high"},
        previous_visit_findings=[],
        location_changes=[]
    )
    assert context.visit_id == visit_id
    assert context.location_id == location_id
    assert isinstance(context.datetime, datetime)
    assert context.weather_conditions["temperature"] == 22
    assert context.site_conditions["dust_level"] == "high"

def test_analysis_result():
    context = AnalysisContext(
        visit_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        datetime=datetime.now()
    )
    problems = [ConstructionProblem(
        category=ProblemCategory.STRUCTURAL,
        description="Crack in the wall",
        severity=Severity.HIGH,
        location_context=LocationContext(area="Area 51")
    )]
    solutions = {problems[0].id: [ProposedSolution(
        problem_id=problems[0].id,
        description="Apply sealant"
    )]}
    confidence_scores = {"overall": 0.9}
    result = AnalysisResult(
        context=context,
        problems=problems,
        solutions=solutions,
        confidence_scores=confidence_scores,
        execution_time=1.23
    )
    assert result.context == context
    assert result.problems == problems
    assert result.solutions == solutions
    assert result.confidence_scores == confidence_scores
    assert result.execution_time == 1.23