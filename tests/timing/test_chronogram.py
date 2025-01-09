import pytest
from datetime import datetime, timedelta
import uuid
from src.timing.chronogram import ChronogramVisualizer
from src.timing.models import (
    Task, Duration, ScheduleGraph, 
    TaskRelationship, TaskRelationType
)

@pytest.fixture
def visualizer():
    return ChronogramVisualizer()

@pytest.fixture
def sample_tasks():
    """Create a set of sample tasks for testing"""
    foundation = Task(
        name="Foundation Work",
        description="Complete foundation",
        duration=Duration(amount=14, unit="days"),
        responsible="John",
        can_be_parallel=False
    )
    
    electrical = Task(
        name="Electrical Installation",
        description="Install electrical systems",
        duration=Duration(amount=10, unit="days"),
        responsible="Sarah",
        can_be_parallel=True
    )
    
    plumbing = Task(
        name="Plumbing Installation",
        description="Install plumbing systems",
        duration=Duration(amount=10, unit="days"),
        responsible="Mike",
        can_be_parallel=True
    )
    
    return [foundation, electrical, plumbing]

@pytest.fixture
def sample_schedule(sample_tasks):
    """Create a sample schedule with relationships"""
    schedule = ScheduleGraph(tasks={}, relationships=[])
    
    # Add tasks to schedule and store their IDs
    foundation, electrical, plumbing = sample_tasks
    task_ids = {}
    
    # Add each task and store its ID
    for task in [foundation, electrical, plumbing]:
        schedule.add_task(task)
        task_ids[task.name] = task.id
    
    # Create relationships using stored IDs
    schedule.add_relationship(TaskRelationship(
        from_task_id=task_ids["Foundation Work"],
        to_task_id=task_ids["Electrical Installation"],
        relation_type=TaskRelationType.SEQUENTIAL
    ))
    
    schedule.add_relationship(TaskRelationship(
        from_task_id=task_ids["Foundation Work"],
        to_task_id=task_ids["Plumbing Installation"],
        relation_type=TaskRelationType.SEQUENTIAL
    ))
    
    # Add parallel group using stored IDs
    schedule.add_parallel_group({
        task_ids["Electrical Installation"],
        task_ids["Plumbing Installation"]
    })
    
    return schedule

class TestChronogramVisualizer:
    def test_mermaid_generation(self, visualizer, sample_schedule):
        """Test Mermaid.js Gantt diagram generation"""
        # Debug print
        print("Available task IDs:", list(sample_schedule.tasks.keys()))
        for task in sample_schedule.tasks.values():
            print(f"Task: {task.name}, ID: {task.id}")
        
        start_date = datetime(2024, 1, 1)
        gantt = visualizer.generate_mermaid_gantt(sample_schedule, start_date)
            
        # Check basic structure
        assert "gantt" in gantt
        assert "dateFormat" in gantt
        assert "title Cronograma de Construcción" in gantt
        
        # Check all tasks are included
        for task in sample_schedule.tasks.values():
            assert task.name in gantt
            if task.responsible:
                assert task.responsible in gantt
        
        # Check dates
        assert "2024-01-01" in gantt  # Start date
        
        # Check parallel task section
        assert "Tareas Paralelas" in gantt
        assert "Electrical Installation" in gantt
        assert "Plumbing Installation" in gantt

    def test_html_visualization(self, visualizer, sample_schedule):
        """Test HTML timeline visualization generation"""
        start_date = datetime(2024, 1, 1)
        html = visualizer.generate_html_visualization(sample_schedule, start_date)
        
        # Check HTML structure
        assert "<!DOCTYPE html>" in html
        assert '<div id="timeline">' in html
        
        # Check if all tasks are included
        for task in sample_schedule.tasks.values():
            assert task.name in html
            if task.responsible:
                assert task.responsible in html
        
        # Check for visualization library inclusion
        assert "vis-timeline" in html
        assert "https://cdnjs.cloudflare.com" in html

    def test_task_date_calculation(self, visualizer, sample_schedule):
        """Test internal task date calculation"""
        start_date = datetime(2024, 1, 1)
        task_dates = visualizer._calculate_task_dates(sample_schedule, start_date)
        
        # Check all tasks have dates
        assert len(task_dates) == len(sample_schedule.tasks)
        
        # Get tasks by name for testing
        tasks = list(sample_schedule.tasks.values())
        foundation = next(t for t in tasks if t.name == "Foundation Work")
        electrical = next(t for t in tasks if t.name == "Electrical Installation")
        plumbing = next(t for t in tasks if t.name == "Plumbing Installation")
        
        # Check foundation dates
        foundation_dates = task_dates[foundation.id]
        assert foundation_dates['start'] == start_date
        assert foundation_dates['end'] == start_date + timedelta(days=14)
        
        # Check parallel tasks start after foundation
        electrical_dates = task_dates[electrical.id]
        plumbing_dates = task_dates[plumbing.id]
        
        # Both should start after foundation
        assert electrical_dates['start'] > foundation_dates['end']
        assert plumbing_dates['start'] > foundation_dates['end']
        
        # Both should start at the same time (parallel)
        assert electrical_dates['start'] == plumbing_dates['start']

    def test_parallel_task_grouping(self, visualizer, sample_schedule):
        """Test grouping of parallel tasks"""
        groups = visualizer._group_tasks(sample_schedule)
        
        # Should have at least two groups (sequential + parallel)
        assert len(groups) >= 2
        
        # Find parallel group
        parallel_group = None
        for group in groups:
            if len(group) > 1:
                parallel_group = group
                break
        
        assert parallel_group is not None
        
        # Get task names in parallel group
        task_names = {
            sample_schedule.tasks[task_id].name 
            for task_id in parallel_group
        }
        
        # Check parallel tasks are grouped together
        assert "Electrical Installation" in task_names
        assert "Plumbing Installation" in task_names
        assert "Foundation Work" not in task_names

    @pytest.mark.parametrize("unit,amount,expected_days", [
        ("days", 5, 5),
        ("weeks", 2, 14),
        ("months", 1, 30),
        ("días", 5, 5),
        ("semanas", 2, 14),
        ("meses", 1, 30)
    ])
    def test_duration_conversion(self, unit, amount, expected_days):
        """Test duration conversion to days"""
        duration = Duration(amount=amount, unit=unit)
        assert duration.to_days() == expected_days

    def test_invalid_duration_unit(self):
        """Test handling of invalid duration units"""
        with pytest.raises(ValueError):
            Duration(amount=5, unit="invalid").to_days()

    def test_empty_schedule(self, visualizer):
        """Test handling of empty schedule"""
        schedule = ScheduleGraph(tasks={}, relationships=[])
        start_date = datetime(2024, 1, 1)
        
        # Should handle empty schedule without errors
        gantt = visualizer.generate_mermaid_gantt(schedule, start_date)
        html = visualizer.generate_html_visualization(schedule, start_date)
        
        assert gantt is not None
        assert html is not None
        assert "gantt" in gantt
        assert "<!DOCTYPE html>" in html

    def test_schedule_with_delays(self, visualizer, sample_schedule):
        """Test handling of schedule with explicit delays"""
        tasks = list(sample_schedule.tasks.values())
        foundation = next(t for t in tasks if t.name == "Foundation Work")
        electrical = next(t for t in tasks if t.name == "Electrical Installation")
        
        # Add a delay relationship
        delay_rel = TaskRelationship(
            from_task_id=foundation.id,
            to_task_id=electrical.id,
            relation_type=TaskRelationType.DELAY,
            delay=Duration(amount=2, unit="days")
        )
        sample_schedule.add_relationship(delay_rel)
        
        start_date = datetime(2024, 1, 1)
        gantt = visualizer.generate_mermaid_gantt(sample_schedule, start_date)
        
        # Check if delay is represented
        task_dates = visualizer._calculate_task_dates(sample_schedule, start_date)
        delayed_task = task_dates[electrical.id]
        
        # Should include 2-day delay after foundation
        expected_start = task_dates[foundation.id]['end'] + timedelta(days=2)
        assert delayed_task['start'] == expected_start