import pytest
from unittest.mock import MagicMock
import uuid
from datetime import datetime
from src.construction.solution_provider import SolutionProvider
from src.construction.models import (
    ConstructionProblem, ProposedSolution, AnalysisContext, 
    ProblemCategory, LocationContext
)
from src.historical_data.models.models import Severity, ProblemStatus

@pytest.fixture
def solution_provider():
    # Create a SolutionProvider instance with mocked dependencies
    llm_service_mock = MagicMock()
    provider = SolutionProvider(llm_service=llm_service_mock)
    provider.visit_history = MagicMock()
    return provider

@pytest.fixture
def sample_problem():
    return ConstructionProblem(
        category=ProblemCategory.STRUCTURAL,
        description="Grieta en la pared",
        severity=Severity.HIGH,
        location_context=LocationContext(area="Test Area"),
        status=ProblemStatus.IDENTIFIED
    )

@pytest.fixture
def sample_context():
    return AnalysisContext(
        visit_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        datetime=datetime.now(),
        previous_visit_findings=[],
        location_changes=[]
    )

def test_generate_solutions(solution_provider, sample_problem, sample_context):
    # Mock the LLM service response
    solution_provider.llm_service.analyze_transcript.return_value = {
        'optimization_suggestions': ["Aplicar sellador estructural"]
    }
    
    solutions = solution_provider.generate_solutions(sample_problem, sample_context)
    
    assert len(solutions) >= 1
    assert isinstance(solutions[0], ProposedSolution)
    assert "sellador estructural" in solutions[0].description.lower()

def test_find_historical_solutions(solution_provider, sample_problem, sample_context):
    # Mock historical solution with all required attributes
    historical_solution = ProposedSolution(
        problem_id=sample_problem.id,
        description="Usar inyección de epoxi",
        effectiveness_rating=4
        )
    
    solution_provider.visit_history.solution_repo.get_by_problem.return_value = [
        historical_solution
    ]
    
    sample_problem.historical_pattern = True
    sample_problem.related_problems = [uuid.uuid4()]
    
    solutions = solution_provider._find_historical_solutions(sample_problem, sample_context)
    
    assert len(solutions) == 1
    assert solutions[0].description == "Usar inyección de epoxi"
    assert solutions[0].effectiveness_rating == 4

def test_generate_template_solutions(solution_provider, sample_problem):
    solutions = solution_provider._generate_template_solutions(sample_problem)
    
    assert len(solutions) > 0
    assert all(isinstance(s, ProposedSolution) for s in solutions)
    assert any("estructural" in s.description.lower() for s in solutions)