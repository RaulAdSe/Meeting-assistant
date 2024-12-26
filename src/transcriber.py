from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "data" / "processed"

class MeetingTranscriber:
    def __init__(self, api_key=None):
        load_dotenv()
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment or .env file")
        self.client = OpenAI(api_key=self.api_key)
        
    def transcribe(self, audio_path: str) -> dict:
        with open(audio_path, "rb") as audio_file:
            response = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            
        output_path = Path(OUTPUT_DIR) / f"{Path(audio_path).stem}_transcript.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)
            
        return {"text": response.text}