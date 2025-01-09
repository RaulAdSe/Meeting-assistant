import pytest
from datetime import datetime, timedelta
import uuid
from src.timing.analyser import TaskAnalyzer
from src.timing.models import ScheduleGraph, Task, Duration, TaskRelationship, TaskRelationType
from unittest.mock import MagicMock
from src.historical_data.models.models import ChronogramStatus

@pytest.fixture
def task_analyzer():
    analyzer = TaskAnalyzer()
    analyzer.history_service = MagicMock()
    analyzer.history_service.create_visit.return_value = MagicMock(id=uuid.uuid4())
    
    # Mock the chronogram_repo and its methods
    analyzer.history_service.chronogram_repo = MagicMock()
    analyzer.history_service.chronogram_repo.create_visit.return_value = MagicMock(id=uuid.uuid4())
    
    return analyzer

@pytest.fixture
def sample_transcript():
    return """
    Necesitamos completar el trabajo de cimentación en 2 semanas. Después, podemos comenzar 
    con la estructura que tomará unos 20 días. El trabajo eléctrico y de fontanería puede 
    hacerse en paralelo, cada uno tomando unos 10 días. Las inspecciones finales tomarán 3 días.
    Juan se encargará de la cimentación, Miguel de la estructura, y Sara del trabajo eléctrico.
    """

@pytest.fixture
def sample_location_id():
    return uuid.uuid4()

class TestTaskAnalyzer:
    def test_analyzer_initialization(self, task_analyzer):
        assert task_analyzer.logger is not None
        assert task_analyzer.history_service is not None

    def test_analyze_transcript_basic(self, task_analyzer, sample_transcript, sample_location_id):
        schedule = task_analyzer.analyze_transcript(
            transcript_text=sample_transcript,
            location_id=sample_location_id
        )
        
        # Verify basic schedule structure
        assert schedule is not None
        assert len(schedule.tasks) > 0
        
        # Check for expected tasks
        task_names = {task.name.lower() for task in schedule.tasks.values()}
        
        # Check for Spanish or English task names
        foundation_terms = {'foundation', 'cimentación', 'cimentacion'}
        framing_terms = {'framing', 'estructura'}
        electrical_terms = {'electrical', 'eléctrico', 'electrico'}
        
        assert any(any(term in name for term in foundation_terms) for name in task_names), \
            f"No foundation-related task found in {task_names}"
        assert any(any(term in name for term in framing_terms) for name in task_names), \
            f"No framing-related task found in {task_names}"
        assert any(any(term in name for term in electrical_terms) for name in task_names), \
            f"No electrical-related task found in {task_names}"
        
        # Verify task assignments
        tasks = schedule.tasks.values()
        assignees = {task.responsible.lower() if task.responsible else '' for task in tasks}
        expected_assignees = {'juan', 'miguel', 'sara'}
        
        assert any(name in assignees for name in expected_assignees), \
            f"Expected assignees {expected_assignees} not found in {assignees}"

    def test_parallel_task_detection(self, task_analyzer, sample_location_id):
        transcript = """
        The electrical and plumbing work must be done in parallel, starting after framing.
        Both electrical and plumbing will take 10 days each.
        """
        
        schedule = task_analyzer.analyze_transcript(
            transcript_text=transcript,
            location_id=sample_location_id
        )
        
        # Check for parallel task groups
        assert len(schedule.parallel_groups) > 0
        
        # Find electrical and plumbing tasks
        electrical_task = None
        plumbing_task = None
        for task in schedule.tasks.values():
            if 'electrical' in task.name.lower():
                electrical_task = task
            elif 'plumbing' in task.name.lower():
                plumbing_task = task
        
        assert electrical_task is not None
        assert plumbing_task is not None
        
        # Verify they're in the same parallel group
        for group in schedule.parallel_groups:
            if electrical_task.id in group and plumbing_task.id in group:
                break
        else:
            pytest.fail("Electrical and plumbing tasks not found in the same parallel group")

    def test_duration_parsing(self, task_analyzer, sample_location_id):
        transcript = "Foundation work will take 14 days. Inspection needs 3 days."
        
        schedule = task_analyzer.analyze_transcript(
            transcript_text=transcript,
            location_id=sample_location_id
        )
        
        tasks = list(schedule.tasks.values())
        foundation_task = next((t for t in tasks if 'foundation' in t.name.lower()), None)
        inspection_task = next((t for t in tasks if 'inspection' in t.name.lower()), None)
        
        assert foundation_task is not None
        assert inspection_task is not None
        assert foundation_task.duration.to_days() == 14  # Using duration.to_days()
        assert inspection_task.duration.to_days() == 3   # Using duration.to_days()


    def test_historical_enhancement(self, task_analyzer, sample_location_id):
        """Test enhancement of schedule with historical data"""
        # Create a mock visit
        mock_visit = MagicMock()
        mock_visit.id = uuid.uuid4()
        mock_visit.date = datetime.now() - timedelta(days=30)
        task_analyzer.history_service.create_visit.return_value = mock_visit

        # Create mock chronogram entry
        mock_foundation_entry = MagicMock()
        mock_foundation_entry.id = uuid.uuid4()
        mock_foundation_entry.task_name = "Foundation"
        mock_foundation_entry.planned_start = mock_visit.date
        mock_foundation_entry.planned_end = mock_visit.date + timedelta(days=14)
        mock_foundation_entry.actual_start = mock_visit.date
        mock_foundation_entry.actual_end = mock_visit.date + timedelta(days=18)
        mock_foundation_entry.status = ChronogramStatus.COMPLETED

        # Set up the mock chronogram repo to return our test data
        task_analyzer.history_service.get_visit_history.return_value = [mock_visit]
        task_analyzer.history_service.chronogram_repo.get_by_visit.return_value = [mock_foundation_entry]

        # Create current schedule
        schedule = ScheduleGraph(tasks={}, relationships=[])
        foundation_task = Task(
            name="Foundation",
            description="Foundation work",
            duration=Duration(amount=14, unit="days")
        )
        schedule.add_task(foundation_task)

        # Get historical context and enhance
        historical_context = task_analyzer._get_historical_context(sample_location_id)
        enhanced_schedule = task_analyzer._enhance_with_historical_data(schedule, historical_context)

        # Check enhancements
        enhanced_task = enhanced_schedule.tasks[foundation_task.id]
        assert 'historical_count' in enhanced_task.metadata
        assert enhanced_task.metadata['historical_count'] == 1
        assert enhanced_task.metadata['avg_historical_duration'] == 18.0
        assert enhanced_task.metadata['typical_deviation'] == 4.0

    def test_relationship_enhancement(self, task_analyzer, sample_location_id):
        """Test enhancement of task relationships with historical data"""
        # Create mock visit
        mock_visit = MagicMock()
        mock_visit.id = uuid.uuid4()
        mock_visit.date = datetime.now() - timedelta(days=30)
        
        # Create mock foundation entry
        mock_foundation = MagicMock()
        mock_foundation.id = uuid.uuid4()
        mock_foundation.task_name = "Foundation"
        mock_foundation.planned_start = mock_visit.date
        mock_foundation.planned_end = mock_visit.date + timedelta(days=14)
        mock_foundation.actual_start = mock_visit.date
        mock_foundation.actual_end = mock_visit.date + timedelta(days=14)
        mock_foundation.status = ChronogramStatus.COMPLETED
        mock_foundation.dependencies = []

        # Create mock framing entry
        mock_framing = MagicMock()
        mock_framing.id = uuid.uuid4()
        mock_framing.task_name = "Framing"
        mock_framing.planned_start = mock_visit.date + timedelta(days=17)
        mock_framing.planned_end = mock_visit.date + timedelta(days=37)
        mock_framing.actual_start = mock_visit.date + timedelta(days=17)
        mock_framing.actual_end = mock_visit.date + timedelta(days=37)
        mock_framing.status = ChronogramStatus.COMPLETED
        mock_framing.dependencies = [mock_foundation.id]

        # Set up mock returns
        task_analyzer.history_service.get_visit_history.return_value = [mock_visit]
        task_analyzer.history_service.chronogram_repo.get_by_visit.return_value = [
            mock_foundation, mock_framing
        ]

        # Create current schedule
        schedule = ScheduleGraph(tasks={}, relationships=[])
        foundation_task = Task(
            name="Foundation",
            description="Foundation work",
            duration=Duration(amount=14, unit="days")
        )
        framing_task = Task(
            name="Framing",
            description="Framing work",
            duration=Duration(amount=20, unit="days")
        )

        schedule.add_task(foundation_task)
        schedule.add_task(framing_task)

        relationship = TaskRelationship(
            from_task_id=foundation_task.id,
            to_task_id=framing_task.id,
            relation_type=TaskRelationType.SEQUENTIAL
        )
        schedule.add_relationship(relationship)

        # Get historical context and enhance
        historical_context = task_analyzer._get_historical_context(sample_location_id)
        enhanced_schedule = task_analyzer._enhance_with_historical_data(schedule, historical_context)

        # Check relationship enhancement
        enhanced_rel = enhanced_schedule.relationships[0]
        assert 'historical_avg_gap' in enhanced_rel.metadata
        assert enhanced_rel.metadata['historical_avg_gap'] == 3.0