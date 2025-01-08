import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import pytest
from datetime import datetime, timedelta
import uuid
from src.timing.analyser import TaskAnalyzer
from src.timing.models import Task, TaskStatus, TaskPriority

@pytest.fixture
def task_analyzer():
    return TaskAnalyzer()

@pytest.fixture
def sample_transcript():
    return """
    We need to complete the foundation work within 2 weeks. After that, we can start 
    the framing which will take about 20 days. The electrical and plumbing work can 
    be done in parallel, each taking about 10 days. Final inspections should take 3 days.
    John will handle the foundation, Mike the framing, and Sarah the electrical work.
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
        assert any('foundation' in name for name in task_names)
        assert any('framing' in name for name in task_names)
        assert any('electrical' in name for name in task_names)
        
        # Verify task assignments
        tasks = schedule.tasks.values()
        assert any(task.assignee == 'John' for task in tasks)
        assert any(task.assignee == 'Mike' for task in tasks)
        assert any(task.assignee == 'Sarah' for task in tasks)

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
        parallel_tasks = {task.id for group in schedule.parallel_groups for task in group}
        assert electrical_task.id in parallel_tasks
        assert plumbing_task.id in parallel_tasks

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
        assert foundation_task.estimated_duration == 14 * 24 * 60  # 14 days in minutes
        assert inspection_task.estimated_duration == 3 * 24 * 60   # 3 days in minutes
