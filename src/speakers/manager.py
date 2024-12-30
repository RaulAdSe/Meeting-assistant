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

        self.similarity_threshold = 0.85
        self.max_segments_per_speaker = 10
        self._known_diarization_mappings = {}  # Maps diarization IDs to database speakers
        
        
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
        
        # Initialize speaker embedding model
        try:
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
        wav_file = self._convert_to_wav(audio_file)
        try:
            diarization = self.diarization(wav_file)
            speakers_segments = {}
            existing_speakers = self.repository.get_all_speakers()
            speaker_embeddings = {
                speaker.id: speaker.get_average_embedding() 
                for speaker in existing_speakers 
                if speaker.embeddings
            }
            
            # Get existing external IDs
            used_external_ids = {speaker.external_id for speaker in existing_speakers}
            
            # Process diarization segments
            diarization_embeddings = {}
            for turn, _, speaker_id in diarization.itertracks(yield_label=True):
                diar_id = f"SPEAKER_{speaker_id.split('_')[-1]}"
                embedding = self._extract_embedding(wav_file, turn.start, turn.end)
                
                if diar_id not in diarization_embeddings:
                    diarization_embeddings[diar_id] = []
                diarization_embeddings[diar_id].append(embedding)
            
            # Match speakers
            for diar_id, embeddings in diarization_embeddings.items():
                avg_embedding = np.mean(embeddings, axis=0)
                
                # Find best matching existing speaker
                best_match = None
                highest_similarity = -1
                
                for speaker in existing_speakers:
                    if speaker.id not in speaker_embeddings:
                        continue
                    
                    similarity = self._compare_embedding_with_speaker(
                        avg_embedding,
                        speaker
                    )
                    
                    if similarity > self.similarity_threshold and similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = speaker
      
                if not best_match:
                    new_external_id = self._generate_unique_speaker_id()
                    best_match = self.repository.create_speaker(external_id=new_external_id)
                    existing_speakers.append(best_match)
                    used_external_ids.add(new_external_id)
                    speaker_embeddings[best_match.id] = avg_embedding
                                
                # Process segments for this speaker
                for turn, _, spk_id in diarization.itertracks(yield_label=True):
                    if f"SPEAKER_{spk_id.split('_')[-1]}" == diar_id:
                        embedding = self._extract_embedding(wav_file, turn.start, turn.end)
                        self._update_speaker_embeddings(best_match, embedding, audio_file, turn)
                        
                        if best_match.external_id not in speakers_segments:
                            speakers_segments[best_match.external_id] = []
                        speakers_segments[best_match.external_id].append({
                            'start': float(turn.start),
                            'end': float(turn.end),
                            'speaker_id': str(best_match.id)
                        })
            
            return speakers_segments
            
        finally:
            if wav_file != audio_file and os.path.exists(wav_file):
                os.remove(wav_file)


    def _update_speaker_embeddings(self, speaker: Speaker, embedding: np.ndarray, 
                                    audio_file: str, turn) -> None:
        """Update speaker embeddings, maintaining maximum number of segments."""
        if len(speaker.embeddings) >= self.max_segments_per_speaker:
            oldest = min(speaker.embeddings, key=lambda x: x.created_at)
            self.repository.remove_embedding(oldest.id)
            
        self.repository.add_embedding(
            speaker_id=speaker.id,
            embedding=embedding,
            audio_segment=AudioSegment(
                start=float(turn.start),
                end=float(turn.end),
                audio_file=audio_file
            )
        )

    def _compare_embedding_with_speaker(self, embedding: np.ndarray, speaker: Speaker) -> float:
        """Compare embedding with speaker's average embedding."""
        speaker_embedding = speaker.get_average_embedding()
        
        # Ensure embeddings are 1-dimensional and same size
        if embedding.ndim > 1:
            embedding = embedding.squeeze()
        if speaker_embedding.ndim > 1:
            speaker_embedding = speaker_embedding.squeeze()
            
        # Verify shapes match
        if embedding.shape != speaker_embedding.shape:
            raise ValueError(f"Embedding shapes don't match: {embedding.shape} vs {speaker_embedding.shape}")
        
        # Calculate cosine similarity
        similarity = np.dot(embedding, speaker_embedding) / (
            np.linalg.norm(embedding) * np.linalg.norm(speaker_embedding)
        )
        return float(similarity)
    
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
                
            # Ensure consistent shape
            if embedding.ndim > 1:
                embedding = embedding.squeeze()
                
            # Verify embedding dimension
            if embedding.shape != (512,):  # pyannote/embedding model outputs 512-dim vectors
                raise ValueError(f"Unexpected embedding dimension: {embedding.shape}")
                
        return embedding

    def _convert_to_wav(self, audio_file: str) -> str:
        """Convert audio file to WAV format and ensure mono."""
        audio = PydubSegment.from_file(audio_file)
        audio = audio.set_channels(1)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            wav_path = temp_wav.name
            
        audio.export(wav_path, format='wav')
        return wav_path

    def _generate_unique_speaker_id(self) -> str:
        with self.repository.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("BEGIN")
                try:
                    next_id = 0
                    while True:
                        candidate_id = f"SPEAKER_{next_id:02d}"
                        cur.execute("SELECT id FROM speakers WHERE external_id = %s FOR UPDATE", (candidate_id,))
                        if not cur.fetchone():
                            self.logger.debug(f"Found unique ID: {candidate_id}")
                            cur.execute("COMMIT")
                            return candidate_id
                        next_id += 1
                        self.logger.debug(f"ID {candidate_id} already exists, trying next")
                except Exception as e:
                    cur.execute("ROLLBACK")
                    raise