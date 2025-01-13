import pytest
from pathlib import Path
import wave
import numpy as np
from datetime import datetime
import uuid
import os
import logging


from src.batch_processing.processors.enhanced_batch_transcriber import EnhancedBatchTranscriber
from src.timing.models import Task, Duration, ScheduleGraph

class TestEnhancedBatchTranscriber:
    @pytest.fixture
    def audio_file(self):
        """Use a real audio file from the data/raw directory"""
        raw_data_dir = Path("data/raw")
        
        # Log the directory being accessed
        logging.info(f"Looking for audio files in: {raw_data_dir.resolve()}")
        
        audio_files = list(raw_data_dir.glob("*.m4a"))
        
        # Log the files found
        logging.info(f"Audio files found: {[str(file) for file in audio_files]}")
        
        if not audio_files:
            raise FileNotFoundError("No audio files found in data/raw directory")
        
        # Return the first audio file found
        return str(audio_files[0])
    
    @pytest.fixture
    def transcriber(self):
        """Create an EnhancedBatchTranscriber instance"""
        return EnhancedBatchTranscriber()
    
    def test_create_session(self, transcriber, audio_file):
        """Test creating a session with real audio file"""
        session = transcriber.create_session(
            audio_paths=[audio_file],
            location="Test Construction Site"
        )
        
        assert session is not None
        assert len(session.files) == 1
        assert session.location == "Test Construction Site"
        assert session.files[0].duration > 0
        assert session.files[0].processed is False

    def test_analyze_transcript(self, transcriber):
        """Test analyzing a transcript with realistic construction text"""
        transcript_text = """
        Estamos en el ala norte del Edificio A. Hay una grieta importante en el muro de carga.
        que necesita atención inmediata. Los trabajos de cimentación deben estar terminados en un plazo de 2 semanas.
        Tendremos que coordinarnos con el equipo eléctrico, ya que necesitan instalar el cableado antes.
        cerramos las paredes. Juan se encargará del trabajo de cimentación mientras el equipo de María trabaja en 
        la instalación eléctrica.
        """
        
        analysis = transcriber.analyze_transcript(
            transcript_text=transcript_text,
            visit_id=uuid.uuid4()
        )
        
        # Check location data
        assert 'location_data' in analysis
        assert 'main_site' in analysis['location_data']
        
        # Check construction analysis
        assert 'construction_analysis' in analysis
        construction = analysis['construction_analysis']
        assert 'problems' in construction
        assert 'solutions' in construction
        assert 'confidence_scores' in construction
        
        # Check timing analysis
        assert 'timing_analysis' in analysis
        timing = analysis['timing_analysis']
        assert 'tasks' in timing
        assert 'relationships' in timing
        
        # Verify metadata
        assert 'metadata' in analysis
        assert 'visit_id' in analysis['metadata']
        assert 'analyzed_at' in analysis['metadata']

    def test_process_session(self, transcriber, audio_file):
        """Test processing a complete session"""
        # Create session
        session = transcriber.create_session(
            audio_paths=[audio_file],
            location="Test Site",
            notes="Initial inspection of Building A"
        )
        
        # Process session
        results = transcriber.process_session(session)
        
        # Check results structure
        assert results is not None
        assert 'session_id' in results
        assert 'transcripts' in results
        assert 'metadata' in results
        
        # Check that files were processed
        assert all(file.processed for file in session.files)
        
        # Verify analysis results
        assert 'construction_analysis' in results
        assert 'timing_analysis' in results
        assert 'location_data' in results
        
        # Check output files were created
        output_dir = Path(results['output_dir'])
        assert output_dir.exists()
        assert (output_dir / 'session_transcript.txt').exists()
        assert (output_dir / 'session_analysis.json').exists()

    def test_error_handling(self, transcriber):
        """Test error handling with invalid inputs"""
        # Test empty audio paths
        with pytest.raises(ValueError) as e:
            transcriber.create_session(audio_paths=[])
        assert "No audio files provided" in str(e.value)
        
        # Test invalid audio file
        with pytest.raises(FileNotFoundError):
            transcriber.create_session(audio_paths=['nonexistent.wav'])
        
        # Test invalid transcript text
        with pytest.raises(ValueError) as e:
            transcriber.analyze_transcript(transcript_text="", visit_id=uuid.uuid4())
        assert "Empty transcript text" in str(e.value)

    def test_comprehensive_analysis(self, transcriber, audio_file):
        """Test complete analysis pipeline with real data"""
        # Create and process session
        session = transcriber.create_session(
            audio_paths=[audio_file],
            location="Construction Site A",
            notes="Foundation and electrical work inspection"
        )
        
        results = transcriber.process_session(session)
        
        # Verify transcript generation
        assert results['transcripts']
        assert isinstance(results['transcripts'][0], dict)
        assert 'text' in results['transcripts'][0]
        
        # Verify construction analysis
        construction = results['construction_analysis']
        assert construction['problems']
        assert construction['solutions']
        assert 0 <= construction['confidence_scores']['overall'] <= 1
        
        # Verify timing analysis
        timing = results['timing_analysis']
        assert isinstance(timing['tasks'], dict)
        assert isinstance(timing['relationships'], list)
        
        # Verify output files
        transcript_file = Path(results['output_dir']) / 'session_transcript.txt'
        analysis_file = Path(results['output_dir']) / 'session_analysis.json'
        
        assert transcript_file.exists()
        assert analysis_file.exists()
        
        # Check content of output files
        transcript_content = transcript_file.read_text()
        assert transcript_content.strip()  # Not empty
        
        # Clean up
        for file in [transcript_file, analysis_file]:
            if file.exists():
                file.unlink()