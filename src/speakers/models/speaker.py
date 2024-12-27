from dataclasses import dataclass
from typing import List, Optional
import numpy as np
import uuid
from datetime import datetime

@dataclass
class AudioSegment:
    start: float
    end: float
    audio_file: str

@dataclass
class SpeakerEmbedding:
    id: uuid.UUID
    embedding: np.ndarray
    audio_segment: AudioSegment
    created_at: datetime = datetime.now()

@dataclass
class Speaker:
    id: uuid.UUID
    external_id: str  # e.g. "SPEAKER_1"
    name: Optional[str] = None
    embeddings: List[SpeakerEmbedding] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    
    def __post_init__(self):
        if self.embeddings is None:
            self.embeddings = []
            
    def add_embedding(self, embedding: np.ndarray, audio_segment: AudioSegment) -> None:
        """Add a new embedding for this speaker."""
        self.embeddings.append(
            SpeakerEmbedding(
                id=uuid.uuid4(),
                embedding=embedding,
                audio_segment=audio_segment
            )
        )
        self.updated_at = datetime.now()
        
    def get_average_embedding(self) -> np.ndarray:
        """Calculate the average embedding for this speaker."""
        if not self.embeddings:
            raise ValueError("No embeddings available for this speaker")
        return np.mean([e.embedding for e in self.embeddings], axis=0)