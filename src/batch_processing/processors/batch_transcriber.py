from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

from ...transcriber import EnhancedTranscriber
from ..models.session import AudioSession, AudioFile
from ..speakers.speaker_tracker import SessionSpeakerTracker
from ..formatters.transcript_formatter import TranscriptFormatter
from ..utils.time_utils import calculate_relative_timestamps, format_duration
from ..exceptions import BatchProcessingError, FileProcessingError
from pydub import AudioSegment

class BatchTranscriber:
    """Manages the processing of multiple audio files with speaker tracking."""
    
    def __init__(self, transcriber: EnhancedTranscriber, output_dir: Path):
        self.transcriber = transcriber
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_session(self, 
                      audio_paths: List[str], 
                      location: Optional[str] = None,
                      notes: Optional[str] = None) -> AudioSession:
        """Create a new session from a list of audio files."""
        try:
            audio_files = []
            
            for path_str in audio_paths:
                path = Path(path_str)
                if not path.exists():
                    self.logger.warning(f"Audio file not found: {path}")
                    continue
                
                try:
                    # Get file stats
                    stats = path.stat()
                    
                    # Get audio duration using pydub
                    audio = AudioSegment.from_file(str(path))
                    duration = len(audio) / 1000.0  # Convert to seconds
                    
                    audio_file = AudioFile(
                        path=path,
                        creation_time=datetime.fromtimestamp(stats.st_ctime),
                        size=stats.st_size,
                        duration=duration,
                        processed=False,
                        metadata={
                            'format': path.suffix[1:],
                            'sample_rate': audio.frame_rate,
                            'channels': audio.channels
                        }
                    )
                    audio_files.append(audio_file)
                    
                except Exception as e:
                    self.logger.error(f"Error processing file {path}: {str(e)}")
                    continue
            
            if not audio_files:
                raise BatchProcessingError("No valid audio files found")
            
            # Sort files by creation time
            audio_files.sort(key=lambda x: x.creation_time)
            
            return AudioSession(
                session_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
                start_time=audio_files[0].creation_time,
                files=audio_files,
                location=location or "Unknown Location",
                notes=notes or ""
            )
            
        except Exception as e:
            raise BatchProcessingError(f"Error creating session: {str(e)}")
    
    def process_session(self, session: AudioSession, max_workers: int = 3) -> Dict[str, Any]:
        """Process all files in a session with speaker tracking."""
        try:
            # Initialize speaker tracker
            speaker_tracker = SessionSpeakerTracker()
            
            session_results = {
                "session_id": session.session_id,
                "start_time": session.start_time.isoformat() if session.start_time else None,
                "location": session.location,
                "transcripts": [],
                "metadata": {
                    "total_files": len(session.files),
                    "total_duration": session.total_duration,
                    "notes": session.notes
                }
            }
            
            # Process files sequentially to maintain speaker tracking
            for audio_file in session.files:
                self.logger.info(f"Processing file: {audio_file.path}")
                try:
                    # Get transcription first
                    transcript = self.transcriber.process_audio(str(audio_file.path))
                    
                    # Get speaker segments
                    speaker_segments = speaker_tracker.process_file(audio_file)
                    
                    # Align transcripts with speaker segments
                    if transcript and transcript.get("aligned_transcript"):
                        self._align_and_add_transcripts(
                            session_results["transcripts"],
                            transcript["aligned_transcript"],
                            speaker_segments,
                            audio_file
                        )
                        
                    audio_file.processed = True
                    
                except Exception as e:
                    self.logger.error(f"Error processing {audio_file.path}: {str(e)}")
                    continue
            
            # Get speaker statistics
            speaker_stats = speaker_tracker.get_speaker_stats()
            
            # Format and save results
            formatter = TranscriptFormatter()
            transcript_path = formatter.format_session_transcript(
                session=session,
                transcripts=session_results["transcripts"],
                speaker_stats=speaker_stats,
                output_dir=self.output_dir
            )
            
            session_results["output_path"] = str(transcript_path)
            session_results["speaker_stats"] = speaker_stats
            
            return session_results
            
        except Exception as e:
            self.logger.error(f"Session processing error: {str(e)}")
            raise BatchProcessingError(f"Error processing session: {str(e)}")
    
    def _align_and_add_transcripts(self,
                                 result_transcripts: List[Dict],
                                 aligned_transcript: List,
                                 speaker_segments: Dict,
                                 audio_file: AudioFile):
        """Align transcripts with speaker segments and add to results."""
        if not aligned_transcript:
            return
            
        base_time = audio_file.creation_time
        
        for transcript_item in aligned_transcript:
            try:
                # Handle both tuple and dict formats
                if isinstance(transcript_item, tuple):
                    speaker_id, text = transcript_item
                else:
                    speaker_id = transcript_item.get('speaker')
                    text = transcript_item.get('text')
                    
                if not speaker_id or not text:
                    continue
                
                # Find matching speaker segment
                speaker = None
                for seg_speaker_id, segments in speaker_segments.items():
                    for segment in segments:
                        if segment.speaker.external_id == speaker_id:
                            speaker = segment.speaker
                            break
                    if speaker:
                        break
                
                result_transcripts.append({
                    "absolute_time": base_time,
                    "speaker": speaker.name if speaker else f"Speaker {speaker_id}",
                    "text": text.strip(),
                    "file": audio_file.path.name
                })
                
            except Exception as e:
                self.logger.error(f"Error aligning transcript: {str(e)}")
                continue