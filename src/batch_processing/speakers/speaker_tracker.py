from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging
from ...speakers.manager import SpeakerManager
from ...speakers.models.speaker import Speaker
from ..models.session import AudioFile, AudioSession
from ..exceptions import BatchProcessingError

@dataclass
class SpeakerSegment:
    speaker: Speaker
    start_time: float
    end_time: float
    confidence: float = 1.0

@dataclass
class TrackedSpeaker:
    speaker: Speaker
    first_seen: datetime
    last_seen: datetime
    total_duration: float = 0.0
    segments: List[SpeakerSegment] = field(default_factory=list)

class SessionSpeakerTracker:
    """Tracks speakers across multiple audio files in a session."""
    
    def __init__(self):
        """Initialize speaker tracking for a session."""
        self.speaker_manager = SpeakerManager()
        self.tracked_speakers: Dict[str, TrackedSpeaker] = {}
        self.logger = logging.getLogger(__name__)
    
    def process_file(self, audio_file: AudioFile) -> Dict[str, List[SpeakerSegment]]:
        """Process a single audio file and track speakers."""
        try:
            # Get speaker segments from manager
            speaker_segments = self.speaker_manager.process_audio(str(audio_file.path))
            
            file_tracked_speakers = {}
            file_creation_time = audio_file.creation_time
            
            # Process each speaker segment
            for speaker_id, segments in speaker_segments.items():
                tracked_speaker = self._get_or_create_speaker(speaker_id, file_creation_time)
                
                file_segments = []
                for segment in segments:
                    speaker_segment = SpeakerSegment(
                        speaker=tracked_speaker.speaker,
                        start_time=segment['start'],
                        end_time=segment['end']
                    )
                    
                    # Update speaker tracking info
                    tracked_speaker.last_seen = file_creation_time
                    tracked_speaker.total_duration += (segment['end'] - segment['start'])
                    tracked_speaker.segments.append(speaker_segment)
                    
                    file_segments.append(speaker_segment)
                
                file_tracked_speakers[speaker_id] = file_segments
            
            return file_tracked_speakers
            
        except Exception as e:
            self.logger.error(f"Error processing file {audio_file.path}: {str(e)}")
            raise BatchProcessingError(f"Speaker tracking failed for {audio_file.path.name}: {str(e)}")
    
    def _get_or_create_speaker(self, speaker_id: str, timestamp: datetime) -> TrackedSpeaker:
        """Get existing tracked speaker or create a new one."""
        if speaker_id in self.tracked_speakers:
            return self.tracked_speakers[speaker_id]
        
        # Create new speaker and tracker
        new_speaker = self.speaker_manager.create_speaker(speaker_id)
        tracked_speaker = TrackedSpeaker(
            speaker=new_speaker,
            first_seen=timestamp,
            last_seen=timestamp
        )
        self.tracked_speakers[speaker_id] = tracked_speaker
        
        return tracked_speaker
    
    def get_speaker_stats(self) -> List[Dict]:
        """Get statistics for all tracked speakers."""
        return [
            {
                "speaker_id": tracked.speaker.external_id,
                "name": tracked.speaker.name,
                "first_seen": tracked.first_seen,
                "last_seen": tracked.last_seen,
                "total_duration": tracked.total_duration,
                "segment_count": len(tracked.segments)
            }
            for tracked in self.tracked_speakers.values()
        ]