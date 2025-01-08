import pytest
from datetime import datetime, timedelta
import uuid
from src.timing.chronogram import ChronogramVisualizer
from src.timing.models import Task, Duration, ScheduleGraph, TaskRelationship, TaskRelationType

@pytest.fixture
def sample_schedule():
    # Create tasks
    task1 = Task(
        name="Foundation Work",
        description="Complete foundation",
        duration=Duration(amount=14, unit="days"),
        responsible="John"
    )
    
    task2 = Task(
        name="Framing",
        description="Building frame",
        duration=Duration(amount=20, unit="days"),
        responsible="Mike"
    )
    
    # Create schedule
    schedule = ScheduleGraph(tasks={}, relationships=[])
    schedule.add_task(task1)
    schedule.add_task(task2)
    
    # Add sequential relationship
    relationship = TaskRelationship(
        from_task_id=task1.id,
        to_task_id=task2.id,
        relation_type=TaskRelationType.SEQUENTIAL
    )
    schedule.add_relationship(relationship)
    
    return schedule

def test_generate_mermaid_gantt():
    # Create visualizer
    visualizer = ChronogramVisualizer()
    
    # Create sample schedule
    schedule = sample_schedule()
    
    # Set start date
    start_date = datetime(2024, 1, 1)
    
    # Generate Mermaid diagram
    gantt = visualizer.generate_mermaid_gantt(schedule, start_date)
    
    # Basic assertions
    assert "gantt" in gantt
    assert "dateFormat" in gantt
    assert "Foundation Work" in gantt
    assert "Framing" in gantt
    assert "2024-01-01" in gantt  # Start date
    assert "John" in gantt  # Responsible person
    assert "Mike" in gantt  # Responsible person

def test_generate_html_visualization():
    visualizer = ChronogramVisualizer()
    schedule = sample_schedule()
    start_date = datetime(2024, 1, 1)
    
    html = visualizer.generate_html_visualization(schedule, start_date)
    
    # Basic assertions
    assert "<!DOCTYPE html>" in html
    assert "Foundation Work" in html
    assert "Framing" in html
    assert "John" in html
    assert "Mike" in html
    assert "vis-timeline" in html
