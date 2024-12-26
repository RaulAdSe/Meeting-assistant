from pydub import AudioSegment
import os

class AudioProcessor:
    def preprocess(self, audio_path: str) -> str:
        audio = AudioSegment.from_file(audio_path)
        
        if audio.channels > 1:
            audio = audio.set_channels(1)
            
        normalized_audio = audio.normalize()
        
        temp_path = os.path.join(os.path.dirname(audio_path), f"{os.path.basename(audio_path)}_processed.wav")
        normalized_audio.export(temp_path, format="wav")
        
        return temp_path