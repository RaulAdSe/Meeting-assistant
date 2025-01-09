import pytest
from unittest.mock import MagicMock
import uuid
from datetime import datetime
from src.construction.problem_analyzer import ProblemAnalyzer
from src.construction.models import (
    ConstructionProblem, AnalysisContext, ProblemCategory,
    AnalysisConfidence, LocationContext
)
from src.historical_data.models.models import Severity, ProblemStatus

@pytest.fixture
def problem_analyzer():
    llm_service_mock = MagicMock()
    return ProblemAnalyzer(llm_service=llm_service_mock)

@pytest.fixture
def sample_context():
    return AnalysisContext(
        visit_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        datetime=datetime.now(),
        previous_visit_findings=[],
        location_changes=[]
    )

def test_analyze_transcript(problem_analyzer, sample_context):
    transcript = "Se detectó una grieta estructural en la pared norte del edificio."
    
    # Mock LLM response
    problem_analyzer.llm_service.analyze_transcript.return_value = {
        'technical_findings': [{
            'hallazgo': 'grieta estructural',
            'severidad': 'Alta',  # Ensure this maps to Severity.HIGH
            'ubicacion': 'pared norte',
            'accion_recomendada': 'Reparar inmediatamente'
        }]
    }
    
    problems = problem_analyzer.analyze_transcript(transcript, sample_context)
    
    assert len(problems) == 1
    problem = problems[0]
    assert problem.category == ProblemCategory.STRUCTURAL
    assert problem.severity == Severity.HIGH  # Ensure mapping is correct
    assert problem.location_context.area == "pared norte"

def test_determine_category(problem_analyzer):
    descriptions = {
        "grieta en la estructura": ProblemCategory.STRUCTURAL,
        "falta de equipo de protección": ProblemCategory.SAFETY,
        "acabados de baja calidad": ProblemCategory.QUALITY,
        "retraso en el cronograma": ProblemCategory.SCHEDULE
    }
    
    for desc, expected_category in descriptions.items():
        assert problem_analyzer._determine_category(desc) == expected_category

def test_assess_severity(problem_analyzer):
    findings = {
        "crítico": Severity.CRITICAL,
        "riesgo alto": Severity.HIGH,  # Ensure this maps correctly
        "moderado": Severity.MEDIUM,
        "leve": Severity.LOW
    }
    
    for desc, expected_severity in findings.items():
        finding = {'hallazgo': desc}
        assert problem_analyzer._assess_severity(finding) == expected_severity

def test_assess_confidence(problem_analyzer):
    # High confidence case
    finding_high = {
        'severidad': 'Alta',
        'accion_recomendada': 'Reparar'
    }
    assert problem_analyzer._assess_confidence(finding_high) == AnalysisConfidence.HIGH
    
    # Medium confidence case
    finding_medium = {
        'severidad': 'Alta'
    }
    assert problem_analyzer._assess_confidence(finding_medium) == AnalysisConfidence.MEDIUM
    
    # Low confidence case
    finding_low = {}
    assert problem_analyzer._assess_confidence(finding_low) == AnalysisConfidence.LOW