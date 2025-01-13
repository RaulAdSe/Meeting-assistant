import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch
import uuid
from datetime import datetime
from pathlib import Path
import json
from src.report_generation.enhanced_formatter import EnhancedReportFormatter, ReportSection

@pytest.fixture
def report_formatter():
    """Create a report formatter with mocked dependencies"""
    formatter = EnhancedReportFormatter()
    
    # Mock all dependencies
    formatter.location_processor = MagicMock()
    formatter.construction_expert = MagicMock()
    formatter.task_analyzer = MagicMock()
    formatter.llm_service = MagicMock()
    formatter.chronogram_visualizer = MagicMock()
    
    return formatter

@pytest.fixture
def sample_location_data():
    """Sample location analysis data"""
    return {
        'main_site': {
            'company': 'Test Construction Corp',
            'site': 'Test Site Location'
        },
        'location_changes': [
            {
                'timestamp': datetime.now(),
                'area': 'Main Building',
                'sublocation': 'Ground Floor'
            }
        ]
    }

@pytest.fixture
def sample_construction_analysis():
    """Sample construction analysis data"""
    problem_id = str(uuid.uuid4())
    return {
        'executive_summary': 'Test executive summary',
        'confidence_scores': {'overall': 0.85},
        'problems': [
            {
                'id': problem_id,
                'severity': 'HIGH',
                'description': 'Test problem',
                'location_context': {'area': 'Test Area'}
            }
        ],
        'solutions': {
            problem_id: [  # Ensure this matches the problem's ID
                {
                    'description': 'Test solution',
                    'estimated_time': 120
                }
            ]
        },
        'follow_up_required': [
            {
                'item': 'Follow up task',
                'priority': 'High',
                'assigned_to': 'John Doe'
            }
        ]
    }

@pytest.fixture
def sample_timing_analysis():
    """Sample timing analysis data"""
    return {
        'tasks': [
            {
                'name': 'Test Task',
                'duration': {'amount': 5, 'unit': 'days'}
            }
        ],
        'relationships': []
    }

class TestEnhancedReportFormatter:
    @pytest.mark.asyncio
    async def test_generate_comprehensive_report(self, report_formatter, tmp_path, 
                                              sample_location_data, sample_construction_analysis,
                                              sample_timing_analysis):
        # Set up mocks
        report_formatter.location_processor.process_transcript.return_value = sample_location_data
        report_formatter.construction_expert.analyze_visit.return_value = sample_construction_analysis
        report_formatter.task_analyzer.analyze_transcript.return_value = sample_timing_analysis
        report_formatter.chronogram_visualizer.generate_mermaid_gantt.return_value = "graph TD;"
        
        # Generate report
        result = await report_formatter.generate_comprehensive_report(
            transcript_text="Test transcript",
            visit_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            output_dir=tmp_path
        )
        
        # Verify all expected files were created
        assert (tmp_path / "report.md").exists()
        assert (tmp_path / "report.pdf").exists()
        assert (tmp_path / "report_metadata.json").exists()
        
        # Verify markdown content
        markdown_content = (tmp_path / "report.md").read_text()
        assert "Test Construction Corp" in markdown_content
        assert "Test executive summary" in markdown_content
        assert "Test problem" in markdown_content
        assert "Follow up task" in markdown_content
        
        # Verify metadata
        metadata = json.loads((tmp_path / "report_metadata.json").read_text())
        assert len(metadata['sections']) > 0
        assert any(section['title'] == "Executive Summary" for section in metadata['sections'])

    def test_create_report_sections(self, report_formatter, sample_location_data,
                                  sample_construction_analysis, sample_timing_analysis):
        sections = report_formatter._create_report_sections(
            location_data=sample_location_data,
            construction_analysis=sample_construction_analysis,
            timing_analysis=sample_timing_analysis,
            chronogram="graph TD;"
        )
        
        # Verify all expected sections are present
        section_titles = {section.title for section in sections}
        expected_titles = {
            "Site Information",
            "Executive Summary",
            "Location Analysis",
            "Problems and Solutions",
            "Project Timeline",
            "Follow-up Items"
        }
        assert section_titles == expected_titles
        
        # Verify section ordering
        assert all(hasattr(section, 'order') for section in sections)
        assert sections == sorted(sections, key=lambda s: s.order)

    def test_format_header(self, report_formatter, sample_location_data):
        header = report_formatter._format_header(sample_location_data)
        
        assert "# Construction Site Visit Report" in header
        assert "Test Construction Corp" in header
        assert "Test Site Location" in header
        assert datetime.now().strftime('%Y-%m-%d') in header

    def test_format_problems_section(self, report_formatter, sample_construction_analysis):
        problems_section = report_formatter._format_problems_section(sample_construction_analysis)
        
        assert "## Problems and Solutions" in problems_section
        assert "Test problem" in problems_section
        assert "Test solution" in problems_section
        assert "HIGH" in problems_section
        assert "Test Area" in problems_section

    def test_format_follow_up_section(self, report_formatter, sample_construction_analysis):
        follow_up_section = report_formatter._format_follow_up_section({
            'construction_analysis': sample_construction_analysis
        })
        
        assert "## Follow-up Items" in follow_up_section
        assert "Follow up task" in follow_up_section
        assert "High" in follow_up_section
        assert "John Doe" in follow_up_section

    def test_generate_markdown(self, report_formatter):
        sections = [
            ReportSection(title="Test Section 1", content="# Test Content 1", order=1),
            ReportSection(title="Test Section 2", content="graph TD;", type="mermaid", order=2)
        ]
        
        markdown = report_formatter._generate_markdown(sections)
        
        assert "# Test Content 1" in markdown
        assert "```mermaid" in markdown
        assert "graph TD;" in markdown
        assert "```" in markdown

    @pytest.mark.asyncio
    async def test_error_handling(self, report_formatter, tmp_path):
        # Simulate an error in location processing
        report_formatter.location_processor.process_transcript.side_effect = Exception("Test error")
        
        with pytest.raises(Exception) as exc_info:
            await report_formatter.generate_comprehensive_report(
                transcript_text="Test transcript",
                visit_id=uuid.uuid4(),
                location_id=uuid.uuid4(),
                output_dir=tmp_path
            )
        
        assert "Test error" in str(exc_info.value)

    def test_section_metadata(self, report_formatter):
        section = ReportSection(
            title="Test Section",
            content="Test content",
            order=1,
            type="markdown",
            metadata={"key": "value"}
        )
        
        assert section.title == "Test Section"
        assert section.content == "Test content"
        assert section.order == 1
        assert section.type == "markdown"
        assert section.metadata == {"key": "value"}

# Chronogram testing
from src.timing.models import Task, Duration, ScheduleGraph
from src.historical_data.models.models import Location, Visit

@pytest.fixture
def mock_location():
    return Location(
        id=uuid.uuid4(),
        name="Test Site",
        address="123 Test St"
    )

@pytest.fixture
def mock_visit(mock_location):
    return Visit(
        id=uuid.uuid4(),
        date=datetime.now(),
        location_id=mock_location.id
    )

@pytest.fixture
def mock_formatter():
    formatter = EnhancedReportFormatter()
    
    # Mock all dependencies
    formatter.location_processor = MagicMock()
    formatter.construction_expert = MagicMock()
    formatter.task_analyzer = MagicMock()
    formatter.llm_service = MagicMock()
    formatter.chronogram_visualizer = MagicMock()
    
    return formatter

@pytest.fixture
def sample_timing_analysis():
    schedule = ScheduleGraph(tasks={}, relationships=[])
    
    # Add sample tasks
    foundation = Task(
        name="Foundation Work",
        description="Complete foundation",
        duration=Duration(amount=14, unit="days")
    )
    framing = Task(
        name="Framing",
        description="Building frame",
        duration=Duration(amount=20, unit="days")
    )
    
    schedule.add_task(foundation)
    schedule.add_task(framing)
    
    return schedule

@pytest.mark.asyncio
class TestEnhancedFormatter:
    async def test_chronogram_integration(
        self, 
        mock_formatter: EnhancedReportFormatter,
        mock_location: Location,
        mock_visit: Visit,
        sample_timing_analysis: ScheduleGraph,
        tmp_path: Path
    ):
        mock_formatter.construction_expert.visit_history.location_repo.get.return_value = mock_location
        mock_formatter.location_processor.process_transcript.return_value = {"location_changes": []}
        mock_formatter.construction_expert.analyze_visit.return_value = {
            "problems": [],
            "solutions": {},
            "confidence_scores": {"overall": 0.9}
        }
        mock_formatter.task_analyzer.analyze_transcript.return_value = sample_timing_analysis
        mock_formatter.chronogram_visualizer.generate_mermaid_gantt.return_value = """gantt
            dateFormat YYYY-MM-DD
            title Project Timeline
            Foundation Work :2024-01-01, 2024-01-14
            Framing :2024-01-15, 2024-02-04"""

        output_dir = tmp_path / "test_output"
        output_dir.mkdir(exist_ok=True)

        report = await mock_formatter.generate_comprehensive_report(
            transcript_text="Foundation takes 14 days. Then framing for 20 days.",
            visit_id=mock_visit.id,
            location_id=mock_location.id,
            output_dir=output_dir,
            start_date=datetime.now()
        )

        assert report["markdown"].exists()
        content = report["markdown"].read_text(encoding="utf-8")
        assert "```mermaid" in content
        assert "gantt" in content
        assert "Foundation" in content
        assert "Framing" in content