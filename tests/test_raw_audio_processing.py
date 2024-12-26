import pytest
import numpy as np
from pathlib import Path
import wave
import struct
import math
from pydub import AudioSegment
from src.audio_processor import AudioProcessor

"""
Comprehensive test suite for audio preprocessing functionality.
Tests cover:
- Audio file loading and basic properties
- Mono conversion from stereo
- Audio normalization
- Sample rate handling
- File output generation
- Error handling for invalid files
"""

@pytest.fixture
def audio_processor():
    """Create an AudioProcessor instance for testing"""
    return AudioProcessor()

@pytest.fixture
def sample_audio_path(tmp_path):
    """Generate a sample audio file with a simple sine wave"""
    audio_path = tmp_path / "test_audio.wav"
    duration_ms = 1000  # 1 second
    sample_rate = 44100
    
    # Generate sine wave
    frequency = 440  # Hz (A4 note)
    samples = []
    for i in range(int(sample_rate * duration_ms / 1000)):
        sample = math.sin(2 * math.pi * frequency * i / sample_rate)
        samples.append(sample)
    
    # Convert to 16-bit PCM
    samples = np.array(samples) * 32767
    samples = samples.astype(np.int16)
    
    # Write WAV file
    with wave.open(str(audio_path), 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())
    
    return str(audio_path)

@pytest.fixture
def stereo_audio_path(tmp_path, sample_audio_path):
    """Create a stereo version of the sample audio"""
    stereo_path = tmp_path / "stereo_audio.wav"
    
    # Load mono audio and convert to stereo
    audio = AudioSegment.from_wav(sample_audio_path)
    stereo = audio.set_channels(2)
    stereo.export(str(stereo_path), format="wav")
    
    return str(stereo_path)

def test_audio_processor_initialization(audio_processor):
    """Test AudioProcessor initialization"""
    assert isinstance(audio_processor, AudioProcessor)

def test_preprocess_mono_input(audio_processor, sample_audio_path):
    """Test preprocessing of mono audio file"""
    processed_path = audio_processor.preprocess(sample_audio_path)
    
    # Check if output file exists
    assert Path(processed_path).exists()
    
    # Verify audio properties
    processed_audio = AudioSegment.from_wav(processed_path)
    assert processed_audio.channels == 1
    assert processed_audio.frame_rate == 44100
    assert processed_audio.sample_width == 2  # 16-bit

def test_stereo_to_mono_conversion(audio_processor, stereo_audio_path):
    """Test conversion of stereo audio to mono"""
    processed_path = audio_processor.preprocess(stereo_audio_path)
    processed_audio = AudioSegment.from_wav(processed_path)
    
    # Verify mono conversion
    assert processed_audio.channels == 1
    
    # Original should be stereo
    original_audio = AudioSegment.from_wav(stereo_audio_path)
    assert original_audio.channels == 2

def test_audio_normalization(audio_processor, sample_audio_path):
    """Test audio normalization"""
    processed_path = audio_processor.preprocess(sample_audio_path)
    processed_audio = AudioSegment.from_wav(processed_path)
    
    # Check if normalized audio's peak amplitude is within expected range
    assert -1.0 <= processed_audio.max_dBFS <= 0.0

def test_output_file_naming(audio_processor, sample_audio_path):
    """Test output file naming convention"""
    processed_path = audio_processor.preprocess(sample_audio_path)
    original_name = Path(sample_audio_path).stem
    
    expected_stem = f"{original_name}_processed"
    assert Path(processed_path).stem == expected_stem
    assert processed_path.endswith(".wav")

@pytest.mark.parametrize("invalid_path", [
    "nonexistent.wav",
    "",
    None
])
def test_invalid_input_handling(audio_processor, invalid_path):
    """Test handling of invalid input files"""
    with pytest.raises((FileNotFoundError, ValueError)):
        audio_processor.preprocess(invalid_path)

def test_empty_audio_handling(audio_processor, tmp_path):
    """Test handling of empty audio files"""
    empty_path = tmp_path / "empty.wav"
    
    # Create empty WAV file
    with wave.open(str(empty_path), 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(44100)
        wav_file.writeframes(b'')
    
    # Should handle empty file without crashing
    processed_path = audio_processor.preprocess(str(empty_path))
    assert Path(processed_path).exists()

def test_large_file_handling(audio_processor, tmp_path):
    """Test handling of larger audio files"""
    large_path = tmp_path / "large_audio.wav"
    duration_ms = 5000  # 5 seconds
    sample_rate = 44100
    
    # Generate larger audio file
    samples = np.zeros(int(sample_rate * duration_ms / 1000), dtype=np.int16)
    with wave.open(str(large_path), 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())
    
    # Process larger file
    processed_path = audio_processor.preprocess(str(large_path))
    assert Path(processed_path).exists()