import pytest
from pathlib import Path
import os
import logging
from datetime import datetime
import uuid
from typing import Optional

from src.batch_processing.processors.enhanced_batch_transcriber import EnhancedBatchTranscriber
from src.batch_processing.models.session import AudioSession, AudioFile
from src.historical_data.database.init_db import init_historical_database

import traceback
import sys
sys.excepthook = lambda t, v, tb: print(''.join(traceback.format_exception(t, v, tb)))

class TestEnhancedBatchTranscriber:
    @pytest.fixture(scope="session", autouse=True)
    def setup_database(self):
        """Initialize the database before running tests"""
        try:
            init_historical_database()
        except Exception as e:
            logging.warning(f"Database initialization error: {e}")

    @pytest.fixture
    def audio_file(self) -> Optional[str]:
        """Get a real audio file from the data/raw directory"""
        raw_dir = Path("data/raw")
        
        # Log directory contents
        logging.info(f"Looking for audio files in: {raw_dir.resolve()}")
        if not raw_dir.exists():
            logging.error(f"Directory not found: {raw_dir}")
            raw_dir.mkdir(parents=True, exist_ok=True)
            return None
            
        # Look for both .m4a and .wav files
        audio_files = []
        for ext in ['.m4a', '.wav']:
            audio_files.extend(list(raw_dir.glob(f"*{ext}")))
        
        # Log found files
        logging.info(f"Audio files found: {[f.name for f in audio_files]}")
        
        if not audio_files:
            logging.warning("No audio files found in data/raw directory")
            return None
            
        # Return the path to the first audio file
        return str(audio_files[0])

    @pytest.fixture
    def transcriber(self):
        """Create a real EnhancedBatchTranscriber instance"""
        return EnhancedBatchTranscriber()

    def test_create_session(self, transcriber, audio_file):
        """Test creating a session with real audio file"""
        if not audio_file:
            pytest.skip("No audio file available for testing")
            
        session = transcriber.create_session(
            audio_paths=[audio_file],
            location="Test Construction Site",
            notes="Real file test"
        )
        
        assert session is not None
        assert len(session.files) == 1
        assert session.location == "Test Construction Site"
        assert session.files[0].duration > 0
        assert session.files[0].processed is False
        assert session.files[0].metadata.get('format') in ['m4a', 'wav']

    def test_analyze_transcript(self, transcriber):
        """Test analyzing a transcript with realistic construction text"""
        transcript_text = """
        Estamos en el ala norte del Edificio A. Hay una grieta importante en el muro de carga
        que necesita atención inmediata. Los trabajos de cimentación deben estar terminados 
        en un plazo de 2 semanas. Tendremos que coordinarnos con el equipo eléctrico, ya que 
        necesitan instalar el cableado antes de que cerramos las paredes.
        """
        
        # Create a test location first
        location = transcriber.location_repo.create(
            name="Test Building A",
            address="North Wing",
            metadata={"company": "Construction Corp"}
        )
        
        analysis = transcriber.analyze_transcript(
            transcript_text=transcript_text,
            visit_id=uuid.uuid4(),
            location_id=location.id  # Use the created location's ID
        )
        
        # Verify analysis structure
        assert 'location_data' in analysis
        assert 'construction_analysis' in analysis
        assert 'timing_analysis' in analysis
        assert 'metadata' in analysis

    @pytest.mark.asyncio
    async def test_process_session(self, transcriber, audio_file):
        """Test full session processing with real audio"""
        if not audio_file:
            pytest.skip("No audio file available for testing")
            
        # Create test location first
        location = transcriber.location_repo.create(
            name="Test Site",
            address="Test Location",
            metadata={"company": "Test Company"}
        )
        
        # Create and process session
        session = transcriber.create_session(
            audio_paths=[audio_file],
            location=location.name,  # Use the created location's name
            notes="Integration test with real audio"
        )
        
        results = await transcriber.process_session(session)
        
        # Verify results
        assert results is not None
        assert 'transcripts' in results
        assert len(results['transcripts']) > 0
        assert 'analyses' in results
        
        # Check output files
        assert Path(results['output_dir']).exists()
        assert (Path(results['output_dir']) / 'session_transcript.txt').exists()
        assert (Path(results['output_dir']) / 'session_analysis.json').exists()

    @pytest.mark.asyncio
    async def test_comprehensive_analysis(self, transcriber, audio_file):
        """Test complete analysis pipeline with real audio"""
        if not audio_file:
            pytest.skip("No audio file available for testing")

        # Create and verify test location
        location_name = "Construction Site A"
        try:
            # Try to find existing location first
            location = next(
                (loc for loc in transcriber.location_repo.get_all()
                if loc.name == location_name),
                None
            )

            if not location:
                # Create new location if needed
                location = transcriber.location_repo.create(
                    name=location_name,
                    address="Main Building",
                    metadata={"company": "Construction Corp A"}
                )

            # Verify location exists
            assert location is not None
            assert location.id is not None

            # Create session with verified location
            session = transcriber.create_session(
                audio_paths=[audio_file],
                location=location.name,
                notes="Full pipeline test"
            )

            # Process and validate
            results = await transcriber.process_session(session)

            # Basic result validation
            assert results is not None
            assert 'transcripts' in results
            assert isinstance(results['transcripts'], list)
            assert len(results['transcripts']) > 0

            # Analysis validation
            assert 'analyses' in results
            assert isinstance(results['analyses'], list)
            assert len(results['analyses']) > 0

            # Check for construction_analysis within analyses
            construction_analysis = results['analyses'][0].get('construction_analysis')
            assert construction_analysis is not None

            # File validation
            output_dir = Path(results['output_dir'])
            assert output_dir.exists()
            assert (output_dir / 'session_transcript.txt').exists()
            assert (output_dir / 'session_analysis.json').exists()
            assert (output_dir / 'report.md').exists()
            assert (output_dir / 'report.pdf').exists()

        except Exception as e:
            pytest.fail(f"Test failed: {str(e)}")

    def test_error_handling(self, transcriber):
        """Test error handling with invalid inputs"""
        # Test empty audio paths
        with pytest.raises(ValueError) as e:
            transcriber.create_session(audio_paths=[])
        assert "No audio files provided" in str(e.value)
        
        # Test nonexistent audio file
        with pytest.raises(FileNotFoundError):
            transcriber.create_session(audio_paths=['nonexistent.wav'])
        
        # Test empty transcript
        with pytest.raises(ValueError) as e:
            transcriber.analyze_transcript(transcript_text="", visit_id=uuid.uuid4())
        assert "Empty transcript text" in str(e.value)

    @pytest.fixture
    def cleanup_output(self):
        """Cleanup fixture to remove test outputs after each test"""
        yield
        reports_dir = Path("reports")
        if reports_dir.exists():
            for path in reports_dir.glob("**/session_*.txt"):
                path.unlink()
            for path in reports_dir.glob("**/analysis.json"):
                path.unlink()
            for path in reports_dir.glob("**/report.*"):
                path.unlink()