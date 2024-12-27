from pathlib import Path
import torch
from pyannote.audio import Pipeline
from pyannote.audio.pipelines.speaker_verification import PretrainedSpeakerEmbedding
import numpy as np
from typing import Dict, List, Optional, Tuple
from .models.speaker import Speaker, AudioSegment, SpeakerEmbedding
import logging
import os
from dotenv import load_dotenv
import uuid
import torchaudio
from pydub import AudioSegment as PydubSegment
import tempfile

class SpeakerManager:
    def __init__(self, debug: bool = False):
        """Initialize speaker management with models and database."""
        # Configure logging
        logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
        
        # Load environment variables from project root
        env_path = Path(__file__).parent.parent.parent / '.env'
        load_dotenv(env_path)
        
        self.hf_token = os.getenv('HF_TOKEN')
        if not self.hf_token:
            raise ValueError("HF_TOKEN not found in .env file")
        
        # Set up device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logging.info(f"Using device: {self.device}")
        
        self.similarity_threshold = 0.75
        
        # Initialize speaker embedding model
        try:
            logging.info("Initializing speaker embedding model...")
            self.embedding_model = PretrainedSpeakerEmbedding(
                "pyannote/embedding",
                use_auth_token=self.hf_token
            ).to(self.device)
            logging.info("Speaker embedding model initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize embedding model: {str(e)}")
            raise
            
        # Initialize diarization pipeline
        try:
            logging.info("Initializing diarization pipeline...")
            self.diarization = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            ).to(self.device)
            logging.info("Diarization pipeline initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize diarization pipeline: {str(e)}")
            raise

    def process_audio(self, audio_file: str) -> Dict[str, List[Dict[str, float]]]:
        """
        Process an audio file to identify and extract embeddings for all speakers.
        
        Args:
            audio_file: Path to the audio file
            
        Returns:
            Dictionary mapping speaker IDs to lists of segments
        """
        logging.info(f"Processing audio file: {audio_file}")
        
        # Convert audio to WAV if needed
        if not audio_file.lower().endswith('.wav'):
            wav_file = self._convert_to_wav(audio_file)
        else:
            wav_file = audio_file
            
        try:
            # Run diarization
            diarization = self.diarization(wav_file)
            
            # Create speakers dict to store results
            speakers = {}
            
            # Process each speech turn
            for turn, _, speaker_id in diarization.itertracks(yield_label=True):
                if speaker_id not in speakers:
                    speakers[speaker_id] = []
                
                # Add segment information
                speakers[speaker_id].append({
                    'start': float(turn.start),
                    'end': float(turn.end)
                })
            
            return speakers
            
        finally:
            # Cleanup temporary WAV file if we created one
            if wav_file != audio_file and os.path.exists(wav_file):
                os.remove(wav_file)

    def _convert_to_wav(self, audio_file: str) -> str:
        """Convert audio file to WAV format."""
        audio = PydubSegment.from_file(audio_file)
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            wav_path = temp_wav.name
            
        # Export to WAV
        audio.export(wav_path, format='wav')
        return wav_path

    def _extract_embedding(self, wav_file: str, start: float, end: float) -> np.ndarray:
        """Extract speaker embedding from an audio segment."""
        # Load audio
        waveform, sample_rate = torchaudio.load(wav_file)
        
        # Convert time to samples
        start_sample = int(start * sample_rate)
        end_sample = int(end * sample_rate)
        
        # Extract segment
        segment = waveform[:, start_sample:end_sample]
        
        # Ensure segment is on the correct device
        segment = segment.to(self.device)
        
        # Get embedding
        with torch.no_grad():
            embedding = self.embedding_model(segment)
            embedding = embedding.cpu().numpy()  # Convert to numpy array after moving to CPU
            
        return embedding

    def compare_speakers(self, speaker1: Speaker, speaker2: Speaker) -> float:
        """Compare two speakers using their average embeddings."""
        try:
            emb1 = speaker1.get_average_embedding()
            emb2 = speaker2.get_average_embedding()
            
            # Compute cosine similarity
            similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            return float(similarity)
        except ValueError as e:
            logging.error(f"Error comparing speakers: {str(e)}")
            return 0.0

    def create_speaker(self, external_id: str, name: Optional[str] = None) -> Speaker:
        """Create a new speaker instance."""
        return Speaker(
            id=uuid.uuid4(),
            external_id=external_id,
            name=name or f"Speaker {external_id.split('_')[-1]}"
        )