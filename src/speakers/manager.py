from pathlib import Path
import torch
from pyannote.audio import Pipeline
from pyannote.audio.pipelines.speaker_verification import PretrainedSpeakerEmbedding
import numpy as np
from typing import Dict, List, Optional, Tuple
from .models.speaker import Speaker, AudioSegment, SpeakerEmbedding
from .database.repository import SpeakerRepository
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
        self.logger = logging.getLogger(__name__)
        
        # Initialize database repository
        try:
            self.repository = SpeakerRepository()
            self.logger.info("Successfully connected to database")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {str(e)}")
            raise
        
        # Load environment variables from project root
        env_path = Path(__file__).parent.parent.parent / '.env'
        load_dotenv(env_path)
        
        self.hf_token = os.getenv('HF_TOKEN')
        if not self.hf_token:
            raise ValueError("HF_TOKEN not found in .env file")
            
        # Set up device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.logger.info(f"Using device: {self.device}")
        
        self.similarity_threshold = 0.75
        
        # Initialize speaker embedding model
        try:
            self.logger.info("Initializing speaker embedding model...")
            self.embedding_model = PretrainedSpeakerEmbedding(
                "pyannote/embedding",
                use_auth_token=self.hf_token
            ).to(self.device)
            self.logger.info("Speaker embedding model initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize embedding model: {str(e)}")
            raise
            
        # Initialize diarization pipeline
        try:
            self.logger.info("Initializing diarization pipeline...")
            self.diarization = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            ).to(self.device)
            self.logger.info("Diarization pipeline initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize diarization pipeline: {str(e)}")
            raise

    def process_audio(self, audio_file: str) -> Dict[str, List[Dict[str, float]]]:
        """Process audio file and store speaker data in database."""
        self.logger.info(f"Processing audio file: {audio_file}")
        
        # Convert audio to WAV if needed
        if not audio_file.lower().endswith('.wav'):
            wav_file = self._convert_to_wav(audio_file)
        else:
            wav_file = audio_file
            
        try:
            # Run diarization
            diarization = self.diarization(wav_file)
            
            # Create speakers dict to store results
            speakers_segments = {}
            
            # Process each speech turn
            for turn, _, speaker_id in diarization.itertracks(yield_label=True):
                if speaker_id not in speakers_segments:
                    # Try to find existing speaker or create new one
                    speaker = self._get_or_create_speaker(speaker_id)
                    speakers_segments[speaker_id] = []
                
                # Create audio segment
                segment = AudioSegment(
                    start=float(turn.start),
                    end=float(turn.end),
                    audio_file=audio_file
                )
                
                # Extract embedding
                embedding = self._extract_embedding(wav_file, turn.start, turn.end)
                
                # Store embedding in database
                self.repository.add_embedding(
                    speaker_id=uuid.UUID(speakers_segments[speaker_id][0]['speaker_id']) 
                        if speakers_segments[speaker_id] else speaker.id,
                    embedding=embedding,
                    audio_segment=segment
                )
                
                # Add segment information
                speakers_segments[speaker_id].append({
                    'start': float(turn.start),
                    'end': float(turn.end),
                    'speaker_id': str(speaker.id)
                })
            
            return speakers_segments
            
        finally:
            # Cleanup temporary WAV file if we created one
            if wav_file != audio_file and os.path.exists(wav_file):
                os.remove(wav_file)

    def _get_or_create_speaker(self, external_id: str) -> Speaker:
        """Find existing speaker or create new one."""
        try:
            # Get all existing speakers with this external_id
            with self.repository.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, name FROM speakers 
                    WHERE external_id = %s AND name IS NOT NULL 
                    ORDER BY created_at ASC LIMIT 1
                """, (external_id,))
                row = cur.fetchone()
                
                if row:
                    return self.repository.get_speaker(uuid.UUID(str(row[0])))
                
                # Create new speaker with proper name
                speaker_number = external_id.split('_')[-1]
                return self.repository.create_speaker(
                    external_id=external_id,
                    name=f"Speaker {speaker_number}"
                )
        except Exception as e:
            self.logger.error(f"Error in _get_or_create_speaker: {str(e)}")
            raise

    def _convert_to_wav(self, audio_file: str) -> str:
        """Convert audio file to WAV format and ensure mono."""
        audio = PydubSegment.from_file(audio_file)
        # Convert to mono
        audio = audio.set_channels(1)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            wav_path = temp_wav.name
            
        audio.export(wav_path, format='wav')
        return wav_path

    def _extract_embedding(self, wav_file: str, start: float, end: float) -> np.ndarray:
        """Extract speaker embedding from an audio segment."""
        waveform, sample_rate = torchaudio.load(wav_file)
        
        # Ensure mono audio
        if waveform.size(0) > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        start_sample = int(start * sample_rate)
        end_sample = int(end * sample_rate)
        segment = waveform[:, start_sample:end_sample].to(self.device)
        
        with torch.no_grad():
            embedding = self.embedding_model(segment)
            if isinstance(embedding, torch.Tensor):
                embedding = embedding.cpu().numpy()
        
        return embedding
    
    def create_speaker(self, external_id: str, name: Optional[str] = None) -> Speaker:
        """Create a new speaker using the repository."""
        return self.repository.create_speaker(external_id, name)

    def compare_speakers(self, speaker1_id: uuid.UUID, speaker2_id: uuid.UUID) -> float:
        """Compare two speakers using their average embeddings."""
        try:
            speaker1 = self.repository.get_speaker(speaker1_id)
            speaker2 = self.repository.get_speaker(speaker2_id)
            
            if not speaker1 or not speaker2:
                raise ValueError("One or both speakers not found")
            
            emb1 = speaker1.get_average_embedding()
            emb2 = speaker2.get_average_embedding()
            
            # Compute cosine similarity
            similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            return float(similarity)
        except Exception as e:
            self.logger.error(f"Error comparing speakers: {str(e)}")
            return 0.0