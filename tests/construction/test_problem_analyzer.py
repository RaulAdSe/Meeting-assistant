import pytest
from unittest.mock import MagicMock
import uuid
from datetime import datetime
from src.construction.solution_provider import SolutionProvider
from src.construction.models import (
    ConstructionProblem, ProposedSolution, AnalysisContext, ProblemCategory, AnalysisConfidence
)
from src.historical_data.models.models import Severity, ProblemStatus

@pytest.fixture
def solution_provider():
    # Create a SolutionProvider instance with a mocked LLMService
    llm_service_mock = MagicMock()
    return SolutionProvider(llm_service=llm_service_mock)

@pytest.fixture
def sample_problem():
    return ConstructionProblem(
        category=ProblemCategory.STRUCTURAL,
        description="Grieta en la pared",
        severity=Severity.HIGH,
        location_context=None,
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
    # Mock the LLM service to return a predefined solution
    solution_provider.llm_service.analyze_transcript.return_value = {
        'optimization_suggestions': ["Aplicar sellador estructural"]
    }
    
    # Call the method
    solutions = solution_provider.generate_solutions(sample_problem, sample_context)
    
    # Assertions
    assert len(solutions) >= 1
    assert any(sol.description == "Aplicar sellador estructural" for sol in solutions)

def test_find_historical_solutions(solution_provider, sample_problem, sample_context):
    # Mock the visit history service to return a predefined historical solution
    solution_provider.visit_history.solution_repo.get_by_problem.return_value = [
        ProposedSolution(
            problem_id=sample_problem.id,
            description="Usar inyección de epoxi",
            priority=2
        )
    ]
    
    # Call the method
    solutions = solution_provider._find_historical_solutions(sample_problem, sample_context)
    
    # Assertions
    assert len(solutions) == 1
    assert solutions[0].description == "Usar inyección de epoxi"

def test_generate_template_solutions(solution_provider, sample_problem):
    # Call the method
    solutions = solution_provider._generate_template_solutions(sample_problem)
    
    # Assertions
    assert len(solutions) > 0
    assert any("estructural" in sol.description.lower() for sol in solutions)