import pytest
from datetime import datetime, timedelta
import uuid
from src.timing.models import Task, Timeline, TaskStatus, TaskPriority

class TestTimingModels:
    def test_task_creation(self):
        task = Task(
            name="Test Task",
            description="Test Description",
            priority=TaskPriority.HIGH,
            estimated_duration=60,  # 1 hour in minutes
            assignee="John"
        )
        
        assert task.id is not None
        assert isinstance(task.id, uuid.UUID)
        assert task.name == "Test Task"
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.PENDING
        assert task.assignee == "John"

    def test_timeline_creation(self):
        visit_id = uuid.uuid4()
        start_date = datetime.now()
        end_date = start_date + timedelta(days=30)
        
        timeline = Timeline(
            visit_id=visit_id,
            planned_start=start_date,
            planned_end=end_date,
            tasks=[]
        )
        
        assert timeline.id is not None
        assert isinstance(timeline.id, uuid.UUID)
        assert timeline.visit_id == visit_id
        assert timeline.planned_start == start_date
        assert timeline.planned_end == end_date
        assert len(timeline.tasks) == 0

    def test_task_duration_calculation(self):
        start_time = datetime.now()
        task = Task(
            name="Test Task",
            description="Test Description",
            priority=TaskPriority.MEDIUM,
            estimated_duration=480,  # 8 hours in minutes
            assignee="John"
        )
        
        # Start the task
        task.status = TaskStatus.IN_PROGRESS
        task.actual_start = start_time
        
        # Complete the task after 6 hours
        task.status = TaskStatus.COMPLETED
        task.actual_end = start_time + timedelta(hours=6)
        
        # Calculate actual duration in minutes
        actual_duration = (task.actual_end - task.actual_start).total_seconds() / 60
        assert actual_duration == 360  # 6 hours in minutes
        
        # Verify it took less time than estimated
        assert actual_duration < task.estimated_duration

    def test_timeline_task_management(self):
        timeline = Timeline(
            visit_id=uuid.uuid4(),
            planned_start=datetime.now(),
            planned_end=datetime.now() + timedelta(days=30),
            tasks=[]
        )
        
        # Create tasks
        task1 = Task(
            name="Task 1",
            description="First task",
            priority=TaskPriority.HIGH,
            estimated_duration=480
        )
        task2 = Task(
            name="Task 2",
            description="Second task",
            priority=TaskPriority.MEDIUM,
            estimated_duration=240
        )
        
        # Add tasks to timeline
        timeline.tasks.append(task1)
        timeline.tasks.append(task2)
        
        assert len(timeline.tasks) == 2
        assert timeline.tasks[0].name == "Task 1"
        assert timeline.tasks[1].name == "Task 2"
        
        # Verify task properties
        high_priority_tasks = [t for t in timeline.tasks if t.priority == TaskPriority.HIGH]
        medium_priority_tasks = [t for t in timeline.tasks if t.priority == TaskPriority.MEDIUM]
        assert len(high_priority_tasks) == 1
        assert len(medium_priority_tasks) == 1
