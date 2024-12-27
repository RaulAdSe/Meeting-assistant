# src/batch_processing/models/session.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

@dataclass
class AudioFile:
    """Represents a single audio file in a session"""
    path: Path
    creation_time: datetime
    size: int
    duration: Optional[float] = None
    processed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AudioSession:
    """Represents a collection of related audio files from a site visit"""
    session_id: str
    start_time: datetime
    files: List[AudioFile]
    location: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_duration(self) -> float:
        """Calculate total duration of all processed files"""
        return sum(f.duration or 0 for f in self.files if f.processed)

    @property
    def total_size(self) -> int:
        """Calculate total size of all files"""
        return sum(f.size for f in self.files)

    @property
    def processed_count(self) -> int:
        """Count number of processed files"""
        return sum(1 for f in self.files if f.processed)