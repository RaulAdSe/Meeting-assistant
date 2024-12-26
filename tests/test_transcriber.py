import pytest
import os
from pathlib import Path
from src.transcriber import MeetingTranscriber
from src.config import OUTPUT_DIR

"""
# test_transcriber.py
This module contains unit tests for the MeetingTranscriber class, focusing on high-level functionality such as initialization, output format, and file creation.
Fixtures:
    transcriber: Provides an instance of MeetingTranscriber.
    sample_audio: Generates a temporary audio file for testing.
Tests:
    test_transcriber_initialization: Verifies that the MeetingTranscriber instance is initialized correctly.
    test_transcribe_output_format: Checks that the transcribe method returns a dictionary with a "text" key.
    test_output_file_creation: Ensures that the transcription output file is created and contains the correct text.
"""
@pytest.fixture
def transcriber():
    return MeetingTranscriber()

@pytest.fixture
def sample_audio(tmp_path):
    audio_path = tmp_path / "test_audio.wav"
    import wave
    import struct
    
    with wave.open(str(audio_path), 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        data = struct.pack('<h', 0) * 44100
        f.writeframes(data)
    
    return str(audio_path)

def test_transcriber_initialization(transcriber):
    assert isinstance(transcriber, MeetingTranscriber)

def test_transcribe_output_format(transcriber, sample_audio):
    result = transcriber.transcribe(sample_audio)
    assert isinstance(result, dict)
    assert "text" in result

def test_output_file_creation(transcriber, sample_audio):
    result = transcriber.transcribe(sample_audio)
    expected_output = Path(sample_audio).stem + "_transcript.txt"
    output_path = Path(OUTPUT_DIR) / expected_output
    assert output_path.exists()
    with open(output_path, "r", encoding="utf-8") as f:
        assert f.read() == result["text"]