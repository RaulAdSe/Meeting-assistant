import pytest
from datetime import datetime, timedelta
import uuid
from src.historical_data.database.connection import DatabaseConnection
from src.historical_data.models.models import (
    Severity, ProblemStatus, ChronogramStatus, ChecklistStatus
)
from src.historical_data.database.repositories import (
    VisitRepository, ProblemRepository, SolutionRepository,
    ChronogramRepository, ChecklistTemplateRepository,
    VisitChecklistRepository
)
from src.historical_data.database.location_repository import LocationRepository

@pytest.fixture(scope="session")
def db_connection():
    """Create a shared database connection for all tests"""
    conn = DatabaseConnection.get_instance().get_connection()
    yield conn
    conn.close()

@pytest.fixture(autouse=True)
def transaction(db_connection):
    """Create a transaction for each test"""
    try:
        # Start a transaction
        db_connection.autocommit = False
        yield
        # Rollback at the end of each test
        db_connection.rollback()
    finally:
        # Reset autocommit mode
        db_connection.autocommit = True

@pytest.fixture
def location_repo(db_connection):
    return LocationRepository()

@pytest.fixture
def sample_location(location_repo, db_connection):
    location = location_repo.create(
        name="Test Location",
        address="123 Test St",
        metadata={"type": "facility"}
    )
    return location  # No need to commit explicitly

@pytest.fixture
def sample_location_id(sample_location):
    return sample_location.id

@pytest.fixture
def visit_repo(db_connection):
    return VisitRepository()

@pytest.fixture
def sample_visit(visit_repo, sample_location_id, db_connection):
    visit = visit_repo.create(
        date=datetime.now(),
        location_id=sample_location_id,
        metadata={"weather": "sunny"}
    )
    return visit  # No need to commit explicitly

@pytest.fixture
def problem_repo(db_connection):
    return ProblemRepository()

@pytest.fixture
def sample_problem(problem_repo, sample_visit):
    return problem_repo.create(
        visit_id=sample_visit.id,
        description="Test Problem",
        severity=Severity.HIGH,
        area="Test Area"
    )

@pytest.fixture
def template_repo(db_connection):
    return ChecklistTemplateRepository()

@pytest.fixture
def sample_template(template_repo):
    items = [{"text": "Test item", "required": True}]
    return template_repo.create(
        name="Test Template",
        items=items,
        description="Test description"
    )

@pytest.fixture
def checklist_repo(db_connection):
    return VisitChecklistRepository()

@pytest.fixture
def solution_repo(db_connection):
    return SolutionRepository()

@pytest.fixture
def chronogram_repo(db_connection):
    return ChronogramRepository()

class TestVisitRepository:
    def test_create_visit(self, visit_repo, sample_location_id):
        visit = visit_repo.create(
            date=datetime.now(),
            location_id=sample_location_id,
            metadata={"weather": "sunny"}
        )
        assert visit.id is not None
        assert visit.location_id == sample_location_id
        assert visit.metadata["weather"] == "sunny"

    def test_get_visit(self, visit_repo, sample_visit):
        retrieved_visit = visit_repo.get(sample_visit.id)
        assert retrieved_visit is not None
        assert retrieved_visit.id == sample_visit.id
        assert retrieved_visit.location_id == sample_visit.location_id

    def test_get_by_location(self, visit_repo, sample_location_id):
        # Create multiple visits using the same location
        date1 = datetime.now()
        date2 = date1 + timedelta(days=1)
        visit1 = visit_repo.create(date=date1, location_id=sample_location_id)
        visit2 = visit_repo.create(date=date2, location_id=sample_location_id)

        visits = visit_repo.get_by_location(sample_location_id)
        assert len(visits) >= 2
        assert any(v.id == visit1.id for v in visits)
        assert any(v.id == visit2.id for v in visits)

    def test_get_by_date_range(self, visit_repo, sample_location_id):
        # Create visits on different dates
        date1 = datetime.now() - timedelta(days=2)
        date2 = datetime.now() - timedelta(days=1)
        date3 = datetime.now()
        
        visit1 = visit_repo.create(date=date1, location_id=sample_location_id)
        visit2 = visit_repo.create(date=date2, location_id=sample_location_id)
        visit3 = visit_repo.create(date=date3, location_id=sample_location_id)

        # Test date range filtering
        visits = visit_repo.get_by_location(
            sample_location_id,
            start_date=date2,
            end_date=date3
        )
        
        assert len(visits) == 2
        visit_ids = {v.id for v in visits}
        assert visit2.id in visit_ids
        assert visit3.id in visit_ids
        assert visit1.id not in visit_ids

class TestProblemRepository:
    def test_create_problem(self, problem_repo, sample_visit):
        problem = problem_repo.create(
            visit_id=sample_visit.id,
            description="Test problem",
            severity=Severity.HIGH,
            area="Test Area"
        )
        assert problem.id is not None
        assert problem.visit_id == sample_visit.id
        assert problem.severity == Severity.HIGH
        assert problem.status == ProblemStatus.IDENTIFIED

    def test_get_by_visit(self, problem_repo, sample_visit):
        problem1 = problem_repo.create(
            visit_id=sample_visit.id,
            description="Problem 1",
            severity=Severity.LOW,
            area="Area 1"
        )
        problem2 = problem_repo.create(
            visit_id=sample_visit.id,
            description="Problem 2",
            severity=Severity.MEDIUM,
            area="Area 2"
        )

        problems = problem_repo.get_by_visit(sample_visit.id)
        assert len(problems) >= 2
        assert any(p.id == problem1.id for p in problems)
        assert any(p.id == problem2.id for p in problems)

    def test_update_status(self, problem_repo, sample_visit):
        problem = problem_repo.create(
            visit_id=sample_visit.id,
            description="Test problem",
            severity=Severity.HIGH,
            area="Test Area"
        )
        
        updated_problem = problem_repo.update_status(
            problem.id,
            ProblemStatus.IN_PROGRESS
        )
        
        assert updated_problem.status == ProblemStatus.IN_PROGRESS
        assert updated_problem.id == problem.id

    def test_get_history_by_location(self, problem_repo, visit_repo, sample_location_id):
        # Create visits using the sample location
        visit1 = visit_repo.create(date=datetime.now(), location_id=sample_location_id)
        visit2 = visit_repo.create(date=datetime.now(), location_id=sample_location_id)
        
        problem1 = problem_repo.create(
            visit_id=visit1.id,
            description="Problem in Area 1",
            severity=Severity.HIGH,
            area="Area 1"
        )
        problem2 = problem_repo.create(
            visit_id=visit2.id,
            description="Problem in Area 1",
            severity=Severity.MEDIUM,
            area="Area 1"
        )
        problem3 = problem_repo.create(
            visit_id=visit2.id,
            description="Problem in Area 2",
            severity=Severity.LOW,
            area="Area 2"
        )

        # Test getting all problems
        problems = problem_repo.get_history_by_location(sample_location_id)
        assert len(problems) == 3
        assert any(p.severity == Severity.HIGH for p in problems)
        assert any(p.severity == Severity.MEDIUM for p in problems)
        assert any(p.severity == Severity.LOW for p in problems)
        
        # Test filtering by area
        area1_problems = problem_repo.get_history_by_location(
            sample_location_id,
            area="Area 1"
        )
        assert len(area1_problems) == 2
        assert all(p.area == "Area 1" for p in area1_problems)
        assert any(p.severity == Severity.HIGH for p in area1_problems)
        assert any(p.severity == Severity.MEDIUM for p in area1_problems)

    def test_get_problem_trends(self, problem_repo, visit_repo, sample_location_id):
        # Create visits and problems
        visit = visit_repo.create(date=datetime.now(), location_id=sample_location_id)
        
        problem1 = problem_repo.create(
            visit_id=visit.id,
            description="Problem in Area 1",
            severity=Severity.HIGH,
            area="Area 1"
        )
        problem2 = problem_repo.create(
            visit_id=visit.id,
            description="Problem in Area 1",
            severity=Severity.MEDIUM,
            area="Area 1"
        )

        trends = problem_repo.get_problem_trends(sample_location_id, area="Area 1")
        assert trends['total_problems'] == 2
        assert trends['severity_distribution'][Severity.HIGH] == 1
        assert trends['severity_distribution'][Severity.MEDIUM] == 1
        assert trends['status_distribution'][ProblemStatus.IDENTIFIED] == 2

class TestSolutionRepository:
    def test_create_solution(self, problem_repo, solution_repo, sample_visit):
        # Create a problem first
        problem = problem_repo.create(
            visit_id=sample_visit.id,
            description="Test problem",
            severity=Severity.HIGH,
            area="Test Area"
        )
        
        # Create solution
        solution = solution_repo.create(
            problem_id=problem.id,
            description="Test solution",
            implemented_at=datetime.now(),
            effectiveness_rating=4
        )
        
        assert solution.id is not None
        assert solution.problem_id == problem.id
        assert solution.effectiveness_rating == 4

    def test_get_by_problem(self, problem_repo, solution_repo, sample_visit):
        problem = problem_repo.create(
            visit_id=sample_visit.id,
            description="Test problem",
            severity=Severity.HIGH,
            area="Test Area"
        )
        
        solution1 = solution_repo.create(
            problem_id=problem.id,
            description="Solution 1",
            effectiveness_rating=3
        )
        solution2 = solution_repo.create(
            problem_id=problem.id,
            description="Solution 2",
            effectiveness_rating=5
        )
        
        solutions = solution_repo.get_by_problem(problem.id)
        assert len(solutions) == 2
        assert any(s.id == solution1.id for s in solutions)
        assert any(s.id == solution2.id for s in solutions)

class TestChronogramRepository:
    def test_create_chronogram_entry(self, chronogram_repo, sample_visit):
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=2)
        
        entry = chronogram_repo.create(
            visit_id=sample_visit.id,
            task_name="Test Task",
            planned_start=start_time,
            planned_end=end_time
        )
        
        assert entry.id is not None
        assert entry.visit_id == sample_visit.id
        assert entry.task_name == "Test Task"
        assert entry.status == ChronogramStatus.PLANNED

    def test_update_progress(self, chronogram_repo, sample_visit):
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=2)
        
        entry = chronogram_repo.create(
            visit_id=sample_visit.id,
            task_name="Test Task",
            planned_start=start_time,
            planned_end=end_time
        )
        
        actual_start = datetime.now()
        updated_entry = chronogram_repo.update_progress(
            entry_id=entry.id,
            actual_start=actual_start,
            status=ChronogramStatus.IN_PROGRESS
        )
        
        assert updated_entry.actual_start == actual_start
        assert updated_entry.status == ChronogramStatus.IN_PROGRESS

    def test_get_by_visit(self, chronogram_repo, sample_visit):
        start_time = datetime.now()
        
        entry1 = chronogram_repo.create(
            visit_id=sample_visit.id,
            task_name="Task 1",
            planned_start=start_time,
            planned_end=start_time + timedelta(hours=1)
        )
        entry2 = chronogram_repo.create(
            visit_id=sample_visit.id,
            task_name="Task 2",
            planned_start=start_time + timedelta(hours=1),
            planned_end=start_time + timedelta(hours=2)
        )
        
        entries = chronogram_repo.get_by_visit(sample_visit.id)
        assert len(entries) == 2
        assert any(e.id == entry1.id for e in entries)
        assert any(e.id == entry2.id for e in entries)

class TestChecklistTemplateRepository:
    def test_create_template(self, template_repo):
        items = [
            {"text": "Check item 1", "required": True},
            {"text": "Check item 2", "required": False}
        ]
        
        template = template_repo.create(
            name="Test Template",
            items=items,
            description="Test description"
        )
        
        assert template.id is not None
        assert template.name == "Test Template"
        assert len(template.items) == 2

    def test_get_template(self, template_repo):
        items = [{"text": "Test item", "required": True}]
        template = template_repo.create(
            name="Test Template",
            items=items,
            description="Test description"
        )
        
        retrieved = template_repo.get(template.id)
        assert retrieved is not None
        assert retrieved.id == template.id
        assert retrieved.name == template.name
        assert retrieved.items == template.items

class TestVisitChecklistRepository:
    def test_create_checklist(self, checklist_repo, sample_visit, sample_template):
        checklist = checklist_repo.create(
            visit_id=sample_visit.id,
            template_id=sample_template.id
        )
        
        assert checklist.id is not None
        assert checklist.visit_id == sample_visit.id
        assert checklist.template_id == sample_template.id
        assert checklist.completion_status == ChecklistStatus.PENDING

    def test_update_progress(self, checklist_repo, sample_visit, sample_template):
        checklist = checklist_repo.create(
            visit_id=sample_visit.id,
            template_id=sample_template.id
        )
        
        completed_items = [
            {"item_id": 1, "completed": True, "notes": "Done"},
            {"item_id": 2, "completed": False, "notes": None}
        ]
        
        updated_checklist = checklist_repo.update_progress(
            checklist_id=checklist.id,
            completed_items=completed_items,
            completion_status=ChecklistStatus.IN_PROGRESS
        )
        
        assert updated_checklist.completion_status == ChecklistStatus.IN_PROGRESS
        assert len(updated_checklist.completed_items) == 2
        assert updated_checklist.completed_at is None

        # Test completing the checklist
        all_completed = [
            {"item_id": 1, "completed": True, "notes": "Done"},
            {"item_id": 2, "completed": True, "notes": "Also done"}
        ]
        
        completed_checklist = checklist_repo.update_progress(
            checklist_id=checklist.id,
            completed_items=all_completed,
            completion_status=ChecklistStatus.COMPLETED
        )
        
        assert completed_checklist.completion_status == ChecklistStatus.COMPLETED
        assert completed_checklist.completed_at is not None