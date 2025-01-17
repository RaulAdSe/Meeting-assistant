from transformers import pipeline
import torch
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dotenv import load_dotenv
import os
from pyannote.audio import Pipeline
from .config import ROOT_DIR, OUTPUT_DIR
from .audio_processor import AudioProcessor
import logging
from .speakers.manager import SpeakerManager  # Import SpeakerManager

class EnhancedTranscriber:
    def __init__(self, model_name: str = "openai/whisper-base", verbose: bool = False):
        """Initialize transcription and diarization models"""
        if not verbose:
            # Suppress non-error logging
            logging.getLogger("transformers").setLevel(logging.ERROR)
            logging.getLogger("speechbrain.utils.quirks").setLevel(logging.ERROR)
        
        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Initialize audio processor
        self.audio_processor = AudioProcessor()
        
        # Load environment variables
        env_path = ROOT_DIR / '.env'
        load_dotenv(env_path)
        self.hf_token = os.getenv('HF_TOKEN')
        if not self.hf_token:
            raise ValueError("HF_TOKEN not found in .env file")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if verbose:
            print(f"Device set to use {self.device}")
        
        # Initialize transcription model
        self.model_name = model_name
        self.transcriber = pipeline(
            "automatic-speech-recognition", 
            model=model_name,
            device=self.device,
            model_kwargs={"forced_decoder_ids": self._get_language_codes()}
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
            if verbose:
                print(f"Error initializing diarization: {str(e)}")
            self.diarization_pipeline = None

        self.speaker_manager = SpeakerManager()  # Initialize SpeakerManager

    def _get_language_codes(self):
        """Get forced decoder IDs for Spanish and Catalan"""
        # Map to force Spanish/Catalan detection
        language_codes = {
            "es": 2979,  # Spanish
            "ca": 2422   # Catalan
        }
        return {"language": "es", "task": "transcribe"}

    def align_transcript_with_speakers(self, transcript_chunks: List[Dict], speaker_segments: List[Dict]) -> List[Tuple[str, str]]:
        """Align transcript chunks with speaker segments"""
        aligned_transcript = []
        
        for chunk in transcript_chunks:
            if 'timestamp' not in chunk or not chunk.get('text'):
                continue
                
            start_time = chunk['timestamp'][0]
            end_time = chunk['timestamp'][1]
            text = chunk['text'].strip()
            
            # Find the speaker who was talking during this chunk
            speaker = None
            max_overlap = 0
            
            for segment in speaker_segments:
                # Calculate overlap between chunk and speaker segment
                overlap_start = max(start_time, segment['start'])
                overlap_end = min(end_time, segment['end'])
                
                if overlap_end > overlap_start:
                    overlap_duration = overlap_end - overlap_start
                    if overlap_duration > max_overlap:
                        max_overlap = overlap_duration
                        speaker = segment['speaker']
            
            if speaker and text:
                # Add to aligned transcript, combining consecutive chunks from same speaker
                if aligned_transcript and aligned_transcript[-1][0] == speaker:
                    aligned_transcript[-1] = (speaker, aligned_transcript[-1][1] + " " + text)
                else:
                    aligned_transcript.append((speaker, text))
        
        return aligned_transcript

    def process_audio(self, audio_path: str) -> Dict[str, Any]:
        """Process audio file with transcription and speaker diarization"""
        try:
            temp_path = self.audio_processor.preprocess(audio_path)
            
            result = {
                "transcript": None,
                "diarization": None,
                "aligned_transcript": None,
                "metadata": {
                    "model": self.model_name,
                    "audio_path": audio_path
                }
            }

            # Perform transcription
            transcription = self.transcriber(
                temp_path,
                return_timestamps="word"
                )
            
            result["transcript"] = {"text": transcription["text"]}
            
            # Store chunks for alignment
            chunks = transcription.get('chunks', [])
            if not chunks and transcription.get('text'):
                # If no chunks, create a single chunk
                chunks = [{'text': transcription['text'], 'timestamp': [0, -1]}]

            # Perform diarization
            if self.diarization_pipeline:
                try:
                    diarization = self.diarization_pipeline(temp_path)
                    segments = []
                    for turn, _, speaker in diarization.itertracks(yield_label=True):
                        speaker_id = self.speaker_manager.get_or_create_speaker_id(f"SPEAKER_{speaker.split('_')[-1]}")
                        segments.append({
                            "start": turn.start,
                            "end": turn.end,
                            "speaker": speaker_id
                        })
                    result["diarization"] = segments
                    
                    # Align transcript with speakers
                    if chunks:
                        result["aligned_transcript"] = self.align_transcript_with_speakers(chunks, segments)
                except Exception as e:
                    print(f"Error during diarization: {str(e)}")

            # Save transcript
            transcript_path = OUTPUT_DIR / f"{Path(audio_path).stem}_transcript.txt"
            self.save_transcript(result, transcript_path)

            return result
            
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)

    def save_transcript(self, result: Dict[str, Any], output_path: Path):
        """Save transcription and diarization results to file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            # Write metadata
            f.write(f"Transcription using {result['metadata']['model']}\n")
            f.write(f"Audio file: {result['metadata']['audio_path']}\n\n")
            
            # Write aligned transcript if available
            if result.get("aligned_transcript"):
                f.write("Conversation:\n\n")
                current_speaker = None
                current_text = []
                
                for speaker, text in result["aligned_transcript"]:
                    if speaker != current_speaker:
                        # Write accumulated text for previous speaker
                        if current_speaker and current_text:
                            f.write(f"{current_speaker}: {' '.join(current_text)}\n\n")
                        current_speaker = speaker
                        current_text = [text]
                    else:
                        current_text.append(text)
                
                # Write final speaker's text
                if current_speaker and current_text:
                    f.write(f"{current_speaker}: {' '.join(current_text)}\n\n")
            
            else:
                # Fall back to raw transcript if no alignment
                f.write("Transcript:\n\n")
                if result["transcript"]:
                    f.write(result["transcript"]["text"])
                    f.write("\n\n")

    def get_transcript_data(transcription_result):
        """
        Extracts structured transcript data from Whisper transcription output.
        """
        transcript_data = []
        
        for chunk in transcription_result.get("chunks", []):
            transcript_data.append({
                "text": chunk["text"],
                "timestamp": chunk["timestamp"][0]  # Use start timestamp
            })
        
        return transcript_data
