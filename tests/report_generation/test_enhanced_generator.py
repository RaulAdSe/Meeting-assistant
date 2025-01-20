import pytest
from datetime import datetime
import uuid
from unittest.mock import MagicMock
from src.batch_processing.formatters.enhanced_formatter import EnhancedReportFormatter, ReportSection
from src.location.models.location import Location, LocationChange
from src.timing.models import Task, Duration, ScheduleGraph, TaskRelationship, TaskRelationType
import logging


@pytest.fixture
def formatter():
    return EnhancedReportFormatter()

@pytest.fixture
def sample_location_data():
    """Create sample location data"""
    return {
        'main_site': {
            'company': 'Test Company',
            'site': 'Test Site'
        },
        'location_changes': [
            LocationChange(
                timestamp=datetime.now(),
                area='Test Area',
                sublocation='Sub Area',
                notes='Test note'
            )
        ]
    }

@pytest.fixture
def sample_construction_analysis():
    """Create sample construction analysis data"""
    return {
        'executive_summary': 'Test summary of the visit',
        'vision_general': {
            'areas_visitadas': [
                {
                    'area': 'Test Area',
                    'observaciones_clave': ['Key observation 1', 'Key observation 2'],
                    'problemas_identificados': ['Problem 1']
                }
            ]
        },
        'hallazgos_tecnicos': [
            {
                'ubicacion': 'Test Location',
                'hallazgo': 'Technical issue found',
                'severidad': 'Alta',
                'accion_recomendada': 'Fix immediately'
            }
        ],
        'preocupaciones_seguridad': [
            {
                'ubicacion': 'Test Area',
                'preocupacion': 'Safety concern',
                'prioridad': 'Alta',
                'mitigacion': 'Safety measure needed'
            }
        ],
        'tareas_pendientes': [
            {
                'tarea': 'Pending task',
                'ubicacion': 'Test Location',
                'asignado_a': 'John Doe',
                'prioridad': 'Alta',
                'plazo': 'Tomorrow'
            }
        ],
        'observaciones_generales': ['General observation 1'],
        'confidence_scores': {'overall': 0.85}
    }

@pytest.fixture
def sample_schedule(self):
    """Create a sample schedule for testing"""
    schedule = ScheduleGraph(tasks={}, relationships=[])
    
    # Create a few sample tasks
    task1 = Task(
        name="Foundation Work",
        description="Complete foundation",
        estimated_duration=14 * 60,
        duration=Duration(amount=14, unit="days"),
        responsible="Engineer A",  # Add assigned user
        location="Main Site"  # Add location
    )

    task2 = Task(
        name="Framing",
        description="Building frame",
        estimated_duration=20 * 60,
        duration=Duration(amount=20, unit="days"),
        responsible="Worker B",  # Add assigned user
        location="Construction Zone"  # Add location
    )

    task1.add_dependency(task2)
        
    # Add tasks to schedule
    schedule.add_task(task1)
    schedule.add_task(task2)
    
    # Create a relationship
    rel = TaskRelationship(
        from_task_id=task1.id,
        to_task_id=task2.id,
        relation_type=TaskRelationType.SEQUENTIAL
    )
    schedule.add_relationship(rel)
    
    return schedule

class TestEnhancedReportFormatter:
    @pytest.fixture
    def sample_schedule(self):
        """Create a sample schedule for testing"""
        schedule = ScheduleGraph(tasks={}, relationships=[])
        
        # Create a few sample tasks
        task1 = Task(
            name="Foundation Work",
            description="Complete foundation",
            estimated_duration=14 * 60,  # 14 days in minutes
            duration=Duration(amount=14, unit="days")
        )
        
        task2 = Task(
            name="Framing",
            description="Building frame",
            estimated_duration=20 * 60,  # 20 days in minutes
            duration=Duration(amount=20, unit="days")
        )
        
        # Add tasks to schedule
        schedule.add_task(task1)
        schedule.add_task(task2)
        
        # Create a relationship
        rel = TaskRelationship(
            from_task_id=task1.id,
            to_task_id=task2.id,
            relation_type=TaskRelationType.SEQUENTIAL
        )
        schedule.add_relationship(rel)
        
        return schedule

    def test_format_header(self, formatter, sample_location_data):
        """Test header formatting"""
        header = formatter._format_header(sample_location_data)
        
        assert '# Construction Site Visit Report' in header
        assert 'Test Company' in header
        assert 'Test Site' in header
        assert datetime.now().strftime('%Y-%m-%d') in header

    def test_format_executive_summary(self, formatter, sample_construction_analysis):
        """Test executive summary formatting"""
        summary = formatter._format_executive_summary(sample_construction_analysis)
        
        assert 'Test summary of the visit' in summary
        assert 'Test Area' in summary
        assert 'Key observation 1' in summary
        assert 'Problem 1' in summary
        assert '85.0%' in summary

    def test_format_problems_section(self, formatter, sample_construction_analysis):
        """Test problems section formatting"""
        problems = formatter._format_problems_section(sample_construction_analysis)
        
        # Check technical findings
        assert 'Problema en Test Location' in problems  # Adjust to match the actual output
        assert 'Alta' in problems
        assert 'Solucionar inmediatamente' in problems  # "Fix immediately"

        # Check safety concerns
        assert 'Riesgos de Seguridad' in problems  # "Safety Concerns"
        assert 'Medida de seguridad necesaria' in problems  # "Safety measure needed"

    def test_format_follow_up_section(self, formatter, sample_construction_analysis):
        """Test follow-up section formatting"""
        data = {'construction_analysis': sample_construction_analysis}
        follow_up = formatter._format_follow_up_section(data)
        
        assert 'Pending task' in follow_up
        assert 'John Doe' in follow_up
        assert 'Alta' in follow_up
        assert 'Tomorrow' in follow_up
        assert 'General observation 1' in follow_up

    def test_format_location_analysis(self, formatter, sample_location_data):
        """Test location analysis formatting"""
        location = formatter._format_location_analysis(sample_location_data)
        
        assert '## Location Analysis' in location
        assert 'Test Area' in location
        assert 'Sub Area' in location
        assert 'Test note' in location

    def test_create_report_sections(self, formatter, sample_location_data, sample_construction_analysis):
        """Test complete report section creation"""
        sections = formatter._create_report_sections(
            location_data=sample_location_data,
            construction_analysis=sample_construction_analysis,
            timing_analysis={'tasks': []},
            chronogram="gantt\n  title Test"
        )
        
        # Check all sections are present
        section_titles = [s.title for s in sections]
        assert "Información de la Obra" in section_titles
        assert "Resumen Ejecutivo" in section_titles
        assert "Análisis de Ubicación" in section_titles
        assert "Problemas y Soluciones" in section_titles
        assert "Cronograma del Proyecto" in section_titles
        assert "Tareas Pendientes" in section_titles
        
        # Check section order
        section_order = {s.title: s.order for s in sections}
        assert section_order["Información de la Obra"] < section_order["Resumen Ejecutivo"]
        assert section_order["Resumen Ejecutivo"] < section_order["Análisis de Ubicación"]
        assert section_order["Problemas y Soluciones"] < section_order["Tareas Pendientes"]


    @pytest.mark.asyncio
    async def test_generation_with_real_data(self, formatter, sample_location_data, 
                                        sample_construction_analysis, sample_schedule, tmp_path):
        """Test actual report generation with sample data"""
        test_id = uuid.uuid4()
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
        logger = logging.getLogger(__name__)
        
        # Mock the location processor to return our sample data
        formatter.location_processor.process_transcript = MagicMock(
            return_value=sample_location_data
        )
        
        # Mock the construction expert to return our sample analysis
        formatter.construction_expert.analyze_visit = MagicMock(
            return_value=sample_construction_analysis
        )
        
        # Mock the task analyzer to return a proper ScheduleGraph
        formatter.task_analyzer.analyze_transcript = MagicMock(
            return_value=sample_schedule
        )
        
        # Mock chronogram visualizer to return a simple Mermaid diagram
        formatter.chronogram_visualizer.generate_mermaid_gantt = MagicMock(
            return_value="""gantt
    dateFormat YYYY-MM-DD
    title Project Timeline
    Foundation Work :2025-01-01, 2025-01-14
    Framing :2025-01-15, 2025-02-04"""
        )
        
        result = await formatter.generate_comprehensive_report(
            transcript_text="Test transcript",
            visit_id=test_id,
            location_id=test_id,
            output_dir=tmp_path,
            analysis_data=sample_construction_analysis
        )
        
        # Check output files exist
        assert (tmp_path / "report.md").exists()
        assert (tmp_path / "report.pdf").exists()
        assert (tmp_path / "report_metadata.json").exists()
        
        # Check markdown content
        markdown_content = (tmp_path / "report.md").read_text()

        # Log the markdown content to see what is actually being generated
        logger.debug("\nGenerated Markdown Content:\n" + markdown_content)

        assert 'Test Company' in markdown_content
        assert 'Test Site' in markdown_content
        assert 'Test summary of the visit' in markdown_content
        assert 'Technical issue found' in markdown_content
        assert 'Test Location' in markdown_content
        assert 'John Doe' in markdown_content
