from pydub import AudioSegment
import os
import tempfile
from pathlib import Path

class AudioProcessor:
    def preprocess(self, audio_path: str) -> str:
        """
        Preprocess audio file: convert to mono and normalize
        
        Args:
            audio_path: Path to input audio file
            
        Returns:
            Path to processed audio file
            
        Raises:
            ValueError: If audio_path is None or empty
            FileNotFoundError: If audio file does not exist
        """
        if audio_path is None or not audio_path:
            raise ValueError("Audio path cannot be None or empty")
            
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
        audio = AudioSegment.from_file(audio_path)
        
        # Convert to mono if stereo
        if audio.channels > 1:
            audio = audio.set_channels(1)
            
        # Normalize audio
        normalized_audio = audio.normalize()
        
        # Generate output path preserving original filename
        input_path = Path(audio_path)
        output_path = input_path.parent / f"{input_path.stem}_processed{input_path.suffix}"
        
        # Export processed audio
        normalized_audio.export(str(output_path), format="wav")
        
        return str(output_path)
