import pytest
from src.audio_processor import AudioProcessor
from pydub import AudioSegment
import os
import wave
import struct
import math

"""
This module contains tests for the AudioProcessor class.
Fixtures:
    audio_processor: Provides an instance of AudioProcessor.
    sample_audio: Creates a temporary test audio file with a simple sine wave.
Tests:
    test_audio_processor_mono_conversion: 
        Verifies that the AudioProcessor correctly converts stereo audio (2 channels) to mono (1 channel).
        Steps:
            - Takes a sample audio (sine wave).
            - Converts it to stereo.
            - Runs it through the AudioProcessor.
            - Verifies the output is mono (single channel).
    test_audio_processor_normalization: 
        Verifies that the AudioProcessor correctly normalizes the audio.
        Steps:
            - Processes the sample audio.
            - Verifies that the maximum dBFS of the processed audio is between -1.0 and 0.0.
"""

@pytest.fixture
def audio_processor():
    return AudioProcessor()

@pytest.fixture
def sample_audio(tmp_path):
    # Create a test audio file with a simple sine wave
    audio_path = tmp_path / "test_audio.wav"
    
    with wave.open(str(audio_path), 'w') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        
        # Generate one second of sine wave at 440Hz (A4 note)
        frequency = 440  # Hz
        amplitude = 32767 // 2  # Half of max amplitude for 16-bit audio
        samples = []
        
        for i in range(44100):  # One second of audio
            sample = amplitude * math.sin(2 * math.pi * frequency * i / 44100)
            packed_sample = struct.pack('<h', int(sample))
            samples.append(packed_sample)
        
        f.writeframes(b''.join(samples))
    
    return str(audio_path)

def test_audio_processor_mono_conversion(audio_processor, sample_audio):

    # Create stereo audio
    stereo = AudioSegment.from_wav(sample_audio)
    stereo = stereo.set_channels(2)
    stereo_path = sample_audio.replace(".wav", "_stereo.wav")
    stereo.export(stereo_path, format="wav")
    
    # Test conversion
    processed = audio_processor.preprocess(stereo_path)
    audio = AudioSegment.from_wav(processed)
    assert audio.channels == 1

def test_audio_processor_normalization(audio_processor, sample_audio):
    processed = audio_processor.preprocess(sample_audio)
    audio = AudioSegment.from_wav(processed)
    assert -1.0 <= audio.max_dBFS <= 0.0