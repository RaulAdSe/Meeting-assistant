import pytest
from datetime import datetime, timedelta
import uuid
from src.historical_data.services.visit_history import VisitHistoryService
from src.historical_data.models.models import (
    Severity, ProblemStatus, ChronogramStatus, ChecklistStatus
)

@pytest.fixture
def history_service():
    return VisitHistoryService()

@pytest.fixture
def sample_location(history_service):
    # Create a location first
    location = history_service.location_repo.create(
        name="Test Location",
        address="123 Test St",
        metadata={"type": "facility"}
    )
    return location

@pytest.fixture
def sample_location_id(sample_location):
    return sample_location.id

@pytest.fixture
def sample_visit(history_service, sample_location_id):
    return history_service.create_visit(
        location_id=sample_location_id,
        date=datetime.now(),
        metadata={"weather": "sunny"}
    )

@pytest.fixture
def sample_problem(history_service, sample_visit):
    return history_service.record_problem(
        visit_id=sample_visit.id,
        description="Test Problem",
        severity=Severity.HIGH,
        area="Test Area"
    )

@pytest.fixture
def sample_checklist_template(history_service):
    items = [
        {"text": "Safety check 1", "required": True},
        {"text": "Safety check 2", "required": True},
        {"text": "Optional check", "required": False}
    ]
    return history_service.create_checklist_template(
        name="Safety Checklist",
        items=items,
        description="Standard safety checklist"
    )

class TestVisitHistoryService:
    def test_create_visit(self, history_service, sample_location_id):
        visit = history_service.create_visit(
            location_id=sample_location_id,
            date=datetime.now(),
            metadata={"weather": "cloudy"}
        )
        assert visit.id is not None
        assert visit.location_id == sample_location_id
        assert visit.metadata["weather"] == "cloudy"

    def test_record_problem(self, history_service, sample_visit):
        problem = history_service.record_problem(
            visit_id=sample_visit.id,
            description="Safety issue",
            severity=Severity.HIGH,
            area="Main entrance"
        )
        assert problem.id is not None
        assert problem.visit_id == sample_visit.id
        assert problem.severity == Severity.HIGH
        assert problem.status == ProblemStatus.IDENTIFIED

    def test_add_solution(self, history_service, sample_problem):
        solution = history_service.add_solution(
            problem_id=sample_problem.id,
            description="Applied fix",
            implemented_at=datetime.now(),
            effectiveness_rating=4
        )
        assert solution.id is not None
        assert solution.problem_id == sample_problem.id
        assert solution.effectiveness_rating == 4

    def test_create_chronogram_entry(self, history_service, sample_visit):
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=2)
        
        entry = history_service.create_chronogram_entry(
            visit_id=sample_visit.id,
            task_name="Inspection Task",
            planned_start=start_time,
            planned_end=end_time
        )
        assert entry.id is not None
        assert entry.visit_id == sample_visit.id
        assert entry.status == ChronogramStatus.PLANNED

    def test_update_chronogram_progress(self, history_service, sample_visit):
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=2)
        
        entry = history_service.create_chronogram_entry(
            visit_id=sample_visit.id,
            task_name="Inspection Task",
            planned_start=start_time,
            planned_end=end_time
        )
        
        actual_start = datetime.now()
        updated_entry = history_service.update_chronogram_progress(
            entry_id=entry.id,
            actual_start=actual_start,
            status=ChronogramStatus.IN_PROGRESS
        )
        assert updated_entry.actual_start == actual_start
        assert updated_entry.status == ChronogramStatus.IN_PROGRESS

    def test_create_visit_checklist(self, history_service, sample_visit, sample_checklist_template):
        checklist = history_service.create_visit_checklist(
            visit_id=sample_visit.id,
            template_id=sample_checklist_template.id
        )
        assert checklist.id is not None
        assert checklist.visit_id == sample_visit.id
        assert checklist.template_id == sample_checklist_template.id
        assert checklist.completion_status == ChecklistStatus.PENDING

    def test_update_checklist_progress(self, history_service, sample_visit, sample_checklist_template):
        checklist = history_service.create_visit_checklist(
            visit_id=sample_visit.id,
            template_id=sample_checklist_template.id
        )
        
        completed_items = [
            {"item_id": 1, "completed": True, "notes": "Done"},
            {"item_id": 2, "completed": False, "notes": "In progress"}
        ]
        
        updated_checklist = history_service.update_checklist_progress(
            checklist_id=checklist.id,
            completed_items=completed_items,
            completion_status=ChecklistStatus.IN_PROGRESS
        )
        assert updated_checklist.completion_status == ChecklistStatus.IN_PROGRESS
        assert len(updated_checklist.completed_items) == 2

    def test_get_visit_history(self, history_service, sample_location_id):
        # Create visits on different dates
        date1 = datetime.now() - timedelta(days=2)
        date2 = datetime.now() - timedelta(days=1)
        
        visit1 = history_service.create_visit(location_id=sample_location_id, date=date1)
        visit2 = history_service.create_visit(location_id=sample_location_id, date=date2)
        
        # Add problems to visits
        problem1 = history_service.record_problem(
            visit_id=visit1.id,
            description="Problem 1",
            severity=Severity.HIGH,
            area="Area 1"
        )
        problem2 = history_service.record_problem(
            visit_id=visit2.id,
            description="Problem 2",
            severity=Severity.MEDIUM,
            area="Area 2"
        )
        
        # Get history
        history = history_service.get_visit_history(
            location_id=sample_location_id,
            start_date=date1,
            end_date=datetime.now()
        )
        
        assert len(history) == 2
        assert any(v['visit'].id == visit1.id for v in history)
        assert any(v['visit'].id == visit2.id for v in history)
        
        # Verify problem details
        for visit_data in history:
            if visit_data['visit'].id == visit1.id:
                assert len(visit_data['problems']) == 1
                assert visit_data['problems'][0]['problem'].severity == Severity.HIGH
            elif visit_data['visit'].id == visit2.id:
                assert len(visit_data['problems']) == 1
                assert visit_data['problems'][0]['problem'].severity == Severity.MEDIUM

    def test_get_problem_trends(self, history_service, sample_location_id):
        # Create visits and problems
        visit = history_service.create_visit(location_id=sample_location_id, date=datetime.now())
        
        # Create problems with different severities
        history_service.record_problem(
            visit_id=visit.id,
            description="Critical Problem",
            severity=Severity.CRITICAL,
            area="Area 1"
        )
        history_service.record_problem(
            visit_id=visit.id,
            description="High Problem",
            severity=Severity.HIGH,
            area="Area 1"
        )
        history_service.record_problem(
            visit_id=visit.id,
            description="Medium Problem",
            severity=Severity.MEDIUM,
            area="Area 2"
        )
        
        # Get trends
        trends = history_service.get_problem_trends(
            location_id=sample_location_id,
            area="Area 1"
        )
        
        assert trends['total_problems'] == 2
        assert trends['severity_distribution'][Severity.CRITICAL] == 1
        assert trends['severity_distribution'][Severity.HIGH] == 1
        assert trends['status_distribution'][ProblemStatus.IDENTIFIED] == 2