from unittest.mock import MagicMock, AsyncMock, patch
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


from pathlib import Path
from src.location.models.location import LocationChange
import numpy as np
import wave
import struct

@pytest.fixture
def sample_transcript_text():
    """Create a sample transcript with specific keywords and phrases to track"""
    return """
    Fecha: 2024-01-15
    Ubicación: Construcciones ABC - Sitio Principal
    
    10:15 AM - Área Principal
    Juan: Hemos identificado una grieta estructural importante en la pared norte del edificio A.
    María: La grieta parece tener unos 2 metros de largo y necesita atención inmediata.
    Carlos: Necesitaremos reforzar la estructura. Estimo unos 3 días para la reparación. Esto lo va a hacer Miguel.
    
    10:30 AM - Área de Instalaciones
    Sara: El sistema eléctrico está completo al 80%.
    Miguel: Podemos trabajar en paralelo con la fontanería para optimizar tiempos.
    
    11:00 AM - Pared Norte
    Juan: La inspección detallada muestra que es un problema estructural de severidad alta.
    María: Debemos programar la reparación lo antes posible para evitar complicaciones.
    
    Resumen de Acciones:
    1. Reparación estructural urgente en pared norte
    2. Coordinación de trabajos eléctricos y fontanería
    3. Seguimiento en 48 horas
    """

@pytest.mark.asyncio
async def test_transcript_processing_and_report_generation(sample_transcript_text, tmp_path):
    """Test complete pipeline processing from transcript to report, tracking keywords"""
    
    # Initialize transcriber
    transcriber = EnhancedBatchTranscriber()
    
    # Keywords to track through the process
    keywords = {
        'structural': ['grieta estructural', 'estructura', 'reforzar'],
        'location': ['pared norte', 'edificio A', 'área principal'],
        'timing': ['3 días', '48 horas', 'en paralelo'],
        'severity': ['urgente', 'inmediata', 'alta'],
        'personnel': ['Juan', 'María', 'Carlos', 'Sara', 'Miguel']
    }
    
    try:
        # Create test location
        location = transcriber.location_repo.create(
            name="Construcciones ABC - Sitio Principal",
            address="Sitio de Prueba",
            metadata={"type": "construction_site"}
        )
        
        # Generate analysis directly from transcript
        visit_id = uuid.uuid4()
        
        # Process location information
        location_data = transcriber.location_processor.process_transcript(sample_transcript_text)
        print("\nLocation data extracted:", location_data)
        
        # Process construction analysis
        construction_analysis = transcriber.construction_expert.analyze_visit(
            visit_id=visit_id,
            transcript_text=sample_transcript_text,
            location_id=location.id
        )
        print("\nConstruction analysis completed:", construction_analysis)
        
        # Process timing analysis
        timing_analysis = transcriber.task_analyzer.analyze_transcript(
            transcript_text=sample_transcript_text,
            location_id=location.id
        )
        print("\nTiming analysis completed:", timing_analysis)
        
        # Generate report
        report_files = await transcriber.report_formatter.generate_comprehensive_report(
            transcript_text=sample_transcript_text,
            visit_id=visit_id,
            location_id=location.id,
            output_dir=tmp_path,
            start_date=datetime.now()
        )
        
        # Verify report files
        assert Path(report_files['markdown']).exists()
        assert Path(report_files['pdf']).exists()
        
        # Read generated markdown report
        markdown_content = Path(report_files['markdown']).read_text()
        
        # Verify keyword preservation
        print("\nKeyword tracking results:")
        for category, terms in keywords.items():
            found_terms = [term for term in terms if term.lower() in markdown_content.lower()]
            print(f"\n{category} keywords found: {found_terms}")
            assert len(found_terms) > 0, f"No {category} keywords found in report"
        
        # Verify structural elements
        assert "# Construction Site Visit Report" in markdown_content
        assert "## Resumen Ejecutivo" in markdown_content
        assert "## Problemas y Soluciones" in markdown_content
        
    except Exception as e:
        print(f"\nTest failed with error: {str(e)}")
        raise