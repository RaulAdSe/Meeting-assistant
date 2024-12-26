from transformers import pipeline
import torch
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
import os
from pyannote.audio import Pipeline
from .config import ROOT_DIR, OUTPUT_DIR
from .audio_processor import AudioProcessor

class EnhancedTranscriber:
    def __init__(self, model_name: str = "openai/whisper-base"):
        """Initialize transcription and diarization models"""
        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Initialize audio processor
        self.audio_processor = AudioProcessor()
        
        # Load environment variables
        env_path = ROOT_DIR / '.env'
        if env_path.exists():
            print(f".env file found at: {env_path}")
        else:
            print(".env file not found")
            
        load_dotenv(env_path)
        self.hf_token = os.getenv('HF_TOKEN')
        if not self.hf_token:
            raise ValueError("HF_TOKEN not found in .env file")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Device set to use {self.device}")
        
        # Initialize transcription model
        self.model_name = model_name
        self.transcriber = pipeline(
            "automatic-speech-recognition", 
            model=model_name,
            device=self.device
        )
        
        # Initialize diarization pipeline
        try:
            self.diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            )
            if self.device == "cuda":
                self.diarization_pipeline.to(torch.device("cuda"))
        except Exception as e:
            print(f"Error initializing diarization: {str(e)}")
            print("Continuing with transcription only...")
            self.diarization_pipeline = None

    def process_audio(self, audio_path: str, language: str = "en") -> Dict[str, Any]:
        """
        Process audio file with transcription and speaker diarization
        
        Args:
            audio_path: Path to audio file
            language: Language code for transcription
            
        Returns:
            Dictionary containing transcription and metadata
        """
        try:
            # Process audio to temp file
            temp_path = self.audio_processor.preprocess(audio_path)
            
            result = {
                "transcript": None,
                "diarization": None,
                "metadata": {
                    "model": self.model_name,
                    "language": language,
                    "audio_path": audio_path
                }
            }

            # Perform transcription on processed audio
            transcription = self.transcriber(temp_path)
            result["transcript"] = {"text": transcription["text"]}

            # Perform diarization if available
            if self.diarization_pipeline:
                try:
                    diarization = self.diarization_pipeline(temp_path)
                    segments = []
                    for turn, _, speaker in diarization.itertracks(yield_label=True):
                        segments.append({
                            "start": turn.start,
                            "end": turn.end,
                            "speaker": speaker
                        })
                    result["diarization"] = segments
                except Exception as e:
                    print(f"Error during diarization: {str(e)}")

            # Save transcript to output directory
            transcript_path = OUTPUT_DIR / f"{Path(audio_path).stem}_transcript.txt"
            self.save_transcript(result, transcript_path)

            return result
            
        finally:
            # Clean up temp file
            try:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as e:
                print(f"Warning: Could not remove temporary file: {e}")

    def save_transcript(self, result: Dict[str, Any], output_path: Path):
        """Save transcription and diarization results to file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            # Write metadata
            f.write(f"Transcription using {result['metadata']['model']}\n")
            f.write(f"Language: {result['metadata']['language']}\n")
            f.write(f"Audio file: {result['metadata']['audio_path']}\n\n")
            
            # Write transcript
            f.write("Transcript:\n")
            if result["transcript"]:
                f.write(result["transcript"]["text"])
            
            # Write diarization results if available
            if result["diarization"]:
                f.write("\n\nSpeaker Segments:\n")
                for segment in result["diarization"]:
                    f.write(f"[{segment['start']:.2f}s -> {segment['end']:.2f}s] {segment['speaker']}\n")