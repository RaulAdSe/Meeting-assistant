from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime
import uuid
from src.batch_processing.processors.enhanced_batch_transcriber import EnhancedBatchTranscriber
from src.batch_processing.formatters.enhanced_formatter import EnhancedReportFormatter
from src.batch_processing.models.session import AudioSession, AudioFile

@pytest.fixture
def sample_timing_data():
    """Create sample timing analysis data"""
    return {
        'tasks': [
            {
                'name': 'Foundation',
                'duration': {'amount': 5, 'unit': 'days'},
                'dependencies': []
            },
            {
                'name': 'Walls',
                'duration': {'amount': 10, 'unit': 'days'},
                'dependencies': ['Foundation']
            }
        ]
    }

@pytest.fixture
def sample_analysis():
    """Create sample analysis data that matches the LLM output structure"""
    return {
        'executive_summary': 'Test summary',
        'vision_general': {
            'areas_visitadas': [{
                'area': 'Test Area',
                'observaciones_clave': ['Key observation'],
                'problemas_identificados': ['Problem 1']
            }]
        },
        'hallazgos_tecnicos': [{
            'ubicacion': 'Test Location',
            'hallazgo': 'Technical issue',
            'severidad': 'Alta',
            'accion_recomendada': 'Fix it'
        }],
        'tareas_pendientes': [{
            'ubicacion': 'Test Area',
            'tarea': 'Task 1',
            'asignado_a': 'John',
            'prioridad': 'Alta',
            'plazo': 'Tomorrow'
        }],
        'metadata': {
            'obra_principal': {
                'empresa': 'Test Company',
                'ubicacion': 'Test Site'
            }
        }
    }

@pytest.mark.asyncio
async def test_batch_to_report_integration(tmp_path, sample_analysis, sample_timing_data):
    """Test the integration between batch processing and report formatting"""
    # Initialize components
    formatter = EnhancedReportFormatter()

    # Mock dependencies
    formatter.location_processor = MagicMock()
    formatter.task_analyzer = MagicMock()
    formatter.history_service = MagicMock()
    formatter.llm_service = MagicMock()

    # Create sample data
    visit_id = uuid.uuid4()
    location_id = uuid.uuid4()
    
    # Set up mock returns
    formatter.location_processor.process_transcript.return_value = {
        'main_site': {
            'company': 'Test Company',
            'site': 'Test Site'
        },
        'location_changes': []
    }
    
    formatter.task_analyzer.analyze_transcript.return_value = sample_timing_data
    
    # Generate report
    report_files = await formatter.generate_comprehensive_report(
        transcript_text="Sample transcript",
        visit_id=visit_id,
        location_id=location_id,
        output_dir=tmp_path,
        analysis_data=sample_analysis,
        start_date=datetime.now()
    )
    
    # Read generated markdown
    markdown_content = (tmp_path / "report.md").read_text()
    print(f"Generated markdown content:\n{markdown_content}")  # Debug output
    
    # Verify executive summary
    assert "Resumen Ejecutivo" in markdown_content
    assert "Test summary" in markdown_content
    
    # Verify areas visited
    assert "Áreas Visitadas" in markdown_content
    assert "Test Area" in markdown_content
    assert "Key observation" in markdown_content
    assert "Problem 1" in markdown_content
    
    # Verify problems section
    assert "Problemas y Soluciones" in markdown_content
    assert "Technical issue" in markdown_content
    assert "Fix it" in markdown_content
    
    # Verify follow-up items
    assert "Tareas Pendientes" in markdown_content
    assert "Task 1" in markdown_content
    assert "John" in markdown_content
    assert "Tomorrow" in markdown_content
    
    # Verify all expected sections exist
    sections = [
        "Resumen Ejecutivo",
        "Áreas Visitadas",
        "Problemas y Soluciones",
        "Tareas Pendientes"
    ]
    for section in sections:
        assert section in markdown_content, f"Missing section: {section}"

    # Print sections if any assertions fail
    if any(section not in markdown_content for section in sections):
        print("\nSection content verification:")
        print(f"Executive Summary present: {'Resumen Ejecutivo' in markdown_content}")
        print(f"Areas Visited present: {'Áreas Visitadas' in markdown_content}")
        print(f"Problems present: {'Problemas y Soluciones' in markdown_content}")
        print(f"Tasks present: {'Tareas Pendientes' in markdown_content}")
        print("\nFull markdown content:")
        print(markdown_content)