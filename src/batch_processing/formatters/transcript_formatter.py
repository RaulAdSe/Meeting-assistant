from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import json
from ..models.session import AudioSession
from ..speakers.speaker_tracker import TrackedSpeaker, SpeakerSegment
from ..utils.time_utils import format_duration

class TranscriptFormatter:
    """Formats transcripts and speaker information into various output formats."""
    
    @staticmethod
    def format_session_transcript(
        session: AudioSession,
        transcripts: List[Dict[str, Any]],
        speaker_stats: List[Dict],
        output_dir: Path
    ):
        """Format and save session transcript with enhanced speaker information."""
        # Create session output directory
        session_dir = output_dir / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save main transcript
        transcript_path = session_dir / "session_transcript.txt"
        
        with open(transcript_path, "w", encoding="utf-8") as f:
            # Write session metadata
            f.write(f"Session ID: {session.session_id}\n")
            f.write(f"Location: {session.location or 'Not specified'}\n")
            f.write(f"Start Time: {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Files: {len(session.files)}\n")
            f.write(f"Total Duration: {format_duration(session.total_duration)}\n")
            
            if session.notes:
                f.write(f"\nNotes: {session.notes}\n")
            
            # Write speaker statistics
            f.write("\nSpeaker Statistics:\n")
            f.write("-" * 50 + "\n")
            for stats in speaker_stats:
                f.write(f"\nSpeaker: {stats['name']}\n")
                f.write(f"Total Speaking Time: {format_duration(stats['total_duration'])}\n")
                f.write(f"First Appearance: {stats['first_seen'].strftime('%H:%M:%S')}\n")
                f.write(f"Last Appearance: {stats['last_seen'].strftime('%H:%M:%S')}\n")
                f.write(f"Number of Segments: {stats['segment_count']}\n")
            
            # Write chronological transcript
            f.write("\nTranscript:\n")
            f.write("-" * 50 + "\n\n")
            
            current_time = None
            for segment in transcripts:
                timestamp = segment["absolute_time"]
                
                # Add visual separator for different times
                if current_time != timestamp:
                    if current_time is not None:
                        f.write("\n")
                    current_time = timestamp
                    f.write(f"[{timestamp.strftime('%H:%M:%S')}]\n")
                
                f.write(f"{segment['speaker']}: {segment['text']}\n")
        
        # Save detailed speaker data in JSON format
        speaker_data_path = session_dir / "speaker_data.json"
        with open(speaker_data_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "session_id": session.session_id,
                    "speakers": speaker_stats
                },
                f,
                indent=2,
                default=str
            )
        
        return transcript_path