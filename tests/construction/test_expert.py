import pytest
from unittest.mock import MagicMock, patch
import uuid
from src.construction.expert import ConstructionExpert
from src.construction.models import AnalysisResult, ConstructionProblem
from src.historical_data.models.models import Severity, ProblemStatus

@pytest.fixture
def expert():
    # Create a ConstructionExpert instance
    expert = ConstructionExpert()

    # Mock dependencies
    expert.visit_history = MagicMock()
    expert.location_processor = MagicMock()
    expert.llm_service = MagicMock()

    return expert

def test_analyze_visit_success(expert):
    # Sample data
    visit_id = uuid.uuid4()
    transcript_text = "Sample transcript text"
    location_id = uuid.uuid4()
    metadata = {"key": "value"}

    # Mock the methods used in analyze_visit
    expert.location_processor.process_transcript.return_value = {"location_changes": []}
    expert.llm_service.analyze_transcript.return_value = {
        "technical_findings": [
            {"hallazgo": "structural issue", "severidad": "Alta", "ubicacion": "Area 1"}
        ]
    }
    expert._identify_problems = MagicMock(return_value=[
        ConstructionProblem(
            category="structural",
            description="structural issue",
            severity=Severity.HIGH,
            location_context=None,
            status=ProblemStatus.IDENTIFIED
        )
    ])
    expert._generate_solutions = MagicMock(return_value={})
    expert._calculate_confidence_scores = MagicMock(return_value={"overall": 0.9})

    # Call the method
    result = expert.analyze_visit(
        visit_id=visit_id,
        transcript_text=transcript_text,
        location_id=location_id,
        metadata=metadata
    )

    # Assertions
    expert.location_processor.process_transcript.assert_called_once_with(transcript_text)
    expert.llm_service.analyze_transcript.assert_called_once()
    expert._identify_problems.assert_called_once()
    expert._generate_solutions.assert_called_once()
    expert._calculate_confidence_scores.assert_called_once()
    assert isinstance(result, AnalysisResult)

def test_analyze_visit_exception(expert):
    # Sample data
    visit_id = uuid.uuid4()
    transcript_text = "Sample transcript text"
    location_id = uuid.uuid4()
    metadata = {"key": "value"}

    # Simulate an exception in the process
    expert.location_processor.process_transcript.side_effect = Exception("Processing error")

    with pytest.raises(Exception) as excinfo:
        expert.analyze_visit(
            visit_id=visit_id,
            transcript_text=transcript_text,
            location_id=location_id,
            metadata=metadata
        )

    assert "Processing error" in str(excinfo.value)