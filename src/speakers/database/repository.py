from typing import List, Optional
import numpy as np
from ..models.speaker import Speaker, SpeakerEmbedding, AudioSegment
from .connection import DatabaseConnection
import uuid
from datetime import datetime
import uuid
import psycopg2

class SpeakerRepository:
    def __init__(self):
        self.db = DatabaseConnection.get_instance()
    
    def create_speaker(self, external_id: str, name: Optional[str] = None) -> Speaker:
        """Create a new speaker in the database."""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                while True:
                    speaker_id = str(uuid.uuid4())
                    now = datetime.now()
                    try:
                        cur.execute("""
                            INSERT INTO speakers (id, external_id, name, created_at, updated_at)
                            VALUES (%s::uuid, %s, %s, %s, %s)
                            RETURNING id, created_at, updated_at
                        """, (speaker_id, external_id, name, now, now))
                        speaker_id, created_at, updated_at = cur.fetchone()
                        conn.commit()
                        return Speaker(
                            id=uuid.UUID(str(speaker_id)),
                            external_id=external_id,
                            name=name,
                            created_at=created_at,
                            updated_at=updated_at
                        )
                    except psycopg2.IntegrityError:
                        conn.rollback()
                        # Increment external_id number
                        num = int(external_id.split('_')[1]) + 1
                        external_id = f"SPEAKER_{num:02d}"
        finally:
            conn.close()
    
    def add_embedding(self, speaker_id: uuid.UUID, embedding: np.ndarray, 
                     audio_segment: AudioSegment) -> None:
        """Add a new embedding for a speaker."""
        # Ensure embedding is 512-dimensional
        if embedding.shape != (512,):
            if embedding.shape[0] == 256:
                # Pad with zeros to match 512
                embedding = np.pad(embedding, (0, 256))
            else:
                raise ValueError(f"Unexpected embedding shape: {embedding.shape}")
                
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                embedding_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO speaker_embeddings 
                    (id, speaker_id, embedding, audio_file, segment_start, segment_end)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
                """, (
                    embedding_id,
                    str(speaker_id),
                    embedding.tobytes(),
                    audio_segment.audio_file,
                    audio_segment.start,
                    audio_segment.end
                ))
                conn.commit()
        finally:
            conn.close()
    
    def get_all_speakers(self) -> List[Speaker]:
        """Get all speakers with their embeddings."""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM speakers")
                speaker_ids = [row[0] for row in cur.fetchall()]
                
            return [self.get_speaker(uuid.UUID(str(speaker_id))) for speaker_id in speaker_ids 
                    if self.get_speaker(uuid.UUID(str(speaker_id))) is not None]
        finally:
            conn.close()

    def get_speaker(self, speaker_id: uuid.UUID) -> Optional[Speaker]:
        """Get a speaker with embeddings."""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                # Get speaker info
                cur.execute("""
                    SELECT external_id, name, created_at, updated_at
                    FROM speakers WHERE id = %s::uuid
                """, (str(speaker_id),))
                
                row = cur.fetchone()
                if not row:
                    return None
                    
                external_id, name, created_at, updated_at = row
                
                # Get embeddings
                cur.execute("""
                    SELECT id, embedding, audio_file, segment_start, segment_end, created_at
                    FROM speaker_embeddings WHERE speaker_id = %s::uuid
                """, (str(speaker_id),))
                
                embeddings = []
                for row in cur.fetchall():
                    embedding_id, embedding_bytes, audio_file, start, end, emb_created_at = row
                    
                    embedding = np.frombuffer(embedding_bytes)
                    # Ensure 512-dimensional embedding
                    if embedding.shape[0] == 256:
                        embedding = np.pad(embedding, (0, 256))
                    
                    audio_segment = AudioSegment(start=start, end=end, audio_file=audio_file)
                    embeddings.append(SpeakerEmbedding(
                        id=uuid.UUID(str(embedding_id)),
                        embedding=embedding,
                        audio_segment=audio_segment,
                        created_at=emb_created_at
                    ))
                
                return Speaker(
                    id=uuid.UUID(str(speaker_id)),
                    external_id=external_id,
                    name=name,
                    embeddings=embeddings,
                    created_at=created_at,
                    updated_at=updated_at
                )
        finally:
            conn.close()
    
    def cleanup_unmapped_speakers(self):
        """Remove speakers without any embeddings."""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM speakers 
                    WHERE id NOT IN (
                        SELECT DISTINCT speaker_id 
                        FROM speaker_embeddings
                    )
                """)
                conn.commit()
        finally:
            conn.close()

    def get_speaker_by_external_id(self, external_id: str) -> Optional[Speaker]:
        """Get a speaker by external ID."""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM speakers WHERE external_id = %s
                """, (external_id,))
                row = cur.fetchone()
                if row:
                    return self.get_speaker(uuid.UUID(str(row[0])))
                return None
        finally:
            conn.close()

