import pytest
import os
from pathlib import Path
from src.transcriber import EnhancedTranscriber
from src.config import OUTPUT_DIR
import wave
import struct

"""
# test_transcriber.py
This module contains unit tests for the EnhancedTranscriber class, focusing on high-level 
functionality such as initialization, output format, and file creation.

Fixtures:
    transcriber: Provides an instance of EnhancedTranscriber.
    sample_audio: Generates a temporary audio file for testing.

Tests:
    test_transcriber_initialization: Verifies that the EnhancedTranscriber instance is initialized correctly.
    test_process_audio_output_format: Checks that the process_audio method returns a dictionary with expected keys.
    test_output_file_creation: Ensures that the transcription output file is created and contains the correct content.
"""

@pytest.fixture
def transcriber():
    """Provides a transcriber instance with minimal model for testing"""
    return EnhancedTranscriber(model_name="openai/whisper-tiny")

@pytest.fixture
def sample_audio(tmp_path):
    """Creates a test audio file"""
    audio_path = tmp_path / "test_audio.wav"
    
    with wave.open(str(audio_path), 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)  # 16kHz is standard for speech
        # Generate 1 second of silence
        data = struct.pack('<h', 0) * 16000
        f.writeframes(data)
    
    return str(audio_path)

def test_transcriber_initialization(transcriber):
    """Test that transcriber initializes with required attributes"""
    assert isinstance(transcriber, EnhancedTranscriber)
    assert hasattr(transcriber, 'transcriber')
    assert hasattr(transcriber, 'hf_token')
    assert hasattr(transcriber, 'model_name')

def test_process_audio_output_format(transcriber, sample_audio):
    """Test that process_audio returns correctly structured output"""
    result = transcriber.process_audio(sample_audio)
    
    # Check basic structure
    assert isinstance(result, dict)
    assert "transcript" in result
    assert "metadata" in result
    
    # Check metadata
    assert "model" in result["metadata"]
    assert "language" in result["metadata"]
    assert "audio_path" in result["metadata"]
    
    # Check transcript
    assert result["transcript"] is not None
    assert "text" in result["transcript"]

def test_output_file_creation(transcriber, sample_audio, tmp_path):
    """Test that save_transcript creates a properly formatted output file"""
    # Process audio and save transcript
    result = transcriber.process_audio(sample_audio)
    output_path = tmp_path / "test_transcript.txt"
    transcriber.save_transcript(result, output_path)
    
    # Verify file exists and contains expected content
    assert output_path.exists()
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "Transcription using" in content
        assert "Language:" in content
        assert "Audio file:" in content
        assert "Transcript:" in content

def test_output_directory_creation(transcriber, sample_audio):
    """Test that transcription output is saved in the correct directory"""
    # Process the audio
    result = transcriber.process_audio(sample_audio)
    
    # Define expected output path
    expected_output = Path(OUTPUT_DIR) / f"{Path(sample_audio).stem}_transcript.txt"
    
    # Save the transcript
    transcriber.save_transcript(result, expected_output)
    
    # Check output file exists in the configured output directory
    assert expected_output.exists()
    
    # Verify content
    with open(expected_output, "r", encoding="utf-8") as f:
        content = f.read()
        # Check that the transcript text is in the saved file
        assert result["transcript"]["text"] in content

def test_diarization_output(transcriber, sample_audio):
    """Test diarization output format when available"""
    result = transcriber.process_audio(sample_audio)
    
    # Check if diarization is available
    if "diarization" in result and result["diarization"] is not None:
        for segment in result["diarization"]:
            assert "start" in segment
            assert "end" in segment
            assert "speaker" in segment
            assert isinstance(segment["start"], float)
            assert isinstance(segment["end"], float)
            assert isinstance(segment["speaker"], str)

