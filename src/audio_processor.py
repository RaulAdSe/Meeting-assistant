from pydub import AudioSegment
import os
import tempfile
from pathlib import Path

class AudioProcessor:
    def preprocess(self, audio_path: str) -> str:
        audio = AudioSegment.from_file(audio_path)
        
        if audio.channels > 1:
            audio = audio.set_channels(1)
            
        normalized_audio = audio.normalize()
        
        # Create temp file with a proper suffix
        temp_dir = tempfile.gettempdir()
        temp_path = Path(temp_dir) / f"temp_{Path(audio_path).stem}_processed.wav"
        normalized_audio.export(str(temp_path), format="wav")
        
        return str(temp_path)