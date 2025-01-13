from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging
from pydub import AudioSegment

from src.transcriber import EnhancedTranscriber
from src.construction.expert import ConstructionExpert
from src.timing.analyser import TaskAnalyzer
from src.location.location_processor import LocationProcessor
from src.batch_processing.models.session import AudioSession, AudioFile
from src.batch_processing.exceptions import BatchProcessingError, FileProcessingError

class EnhancedBatchTranscriber:
    """Enhanced batch transcriber that integrates construction and timing analysis."""
    
    def __init__(self):
        """Initialize transcriber with all specialized analysis agents."""
        self.logger = logging.getLogger(__name__)
        
        # Initialize core transcription
        self.transcriber = EnhancedTranscriber()
        
        # Initialize specialized analysis agents
        self.construction_expert = ConstructionExpert()
        self.task_analyzer = TaskAnalyzer()
        self.location_processor = LocationProcessor()

    def create_session(
        self, 
        audio_paths: List[str],
        location: Optional[str] = None,
        notes: Optional[str] = None
    ) -> AudioSession:
        """Create a new analysis session from audio files."""
        if not audio_paths:
            raise ValueError("No audio files provided")
            
        audio_files = []
        
        for path_str in audio_paths:
            path = Path(path_str)
            if not path.exists():
                raise FileNotFoundError(f"Audio file not found: {path}")
                
            try:
                # Get audio metadata using pydub
                audio = AudioSegment.from_file(str(path))
                
                audio_file = AudioFile(
                    path=path,
                    creation_time=datetime.fromtimestamp(path.stat().st_ctime),
                    size=path.stat().st_size,
                    duration=len(audio) / 1000.0,  # Convert to seconds
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
            notes=notes
        )

    def process_audio(self, audio_path: str) -> Dict[str, Any]:
        """Process a single audio file with full analysis."""
        try:
            # Get basic transcription
            transcript_result = self.transcriber.process_audio(audio_path)
            
            # Create visit ID for tracking
            visit_id = uuid.uuid4()
            
            # Perform comprehensive analysis
            analysis = self.analyze_transcript(
                transcript_text=transcript_result['transcript']['text'],
                visit_id=visit_id
            )
            
            return {
                'transcript': transcript_result['transcript'],
                'construction_analysis': analysis['construction_analysis'],
                'timing_analysis': analysis['timing_analysis'],
                'location_data': analysis['location_data'],
                'metadata': {
                    **transcript_result['metadata'],
                    'visit_id': str(visit_id),
                    'analyzed_at': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error processing audio {audio_path}: {str(e)}")
            raise FileProcessingError(f"Failed to process {audio_path}: {str(e)}")

    def analyze_transcript(
        self,
        transcript_text: str,
        visit_id: uuid.UUID,
        location_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Perform comprehensive transcript analysis using all agents."""
        try:
            # Process location information
            location_data = self.location_processor.process_transcript(transcript_text)
            
            # Get construction analysis
            construction_analysis = self.construction_expert.analyze_visit(
                visit_id=visit_id,
                transcript_text=transcript_text,
                location_id=location_id or uuid.uuid4()
            )
            
            # Get timing analysis
            timing_analysis = self.task_analyzer.analyze_transcript(
                transcript_text=transcript_text,
                location_id=location_id or uuid.uuid4()
            )
            
            return {
                'location_data': location_data,
                'construction_analysis': {
                    'problems': construction_analysis.problems,
                    'solutions': construction_analysis.solutions,
                    'confidence_scores': construction_analysis.confidence_scores
                },
                'timing_analysis': {
                    'tasks': timing_analysis.tasks,
                    'relationships': timing_analysis.relationships,
                    'parallel_groups': timing_analysis.parallel_groups
                },
                'metadata': {
                    'visit_id': str(visit_id),
                    'location_id': str(location_id) if location_id else None,
                    'analyzed_at': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing transcript: {str(e)}")
            raise

    def process_session(self, session: AudioSession) -> Dict[str, Any]:
        """Process all files in a session with comprehensive analysis."""
        try:
            session_results = {
                'session_id': session.session_id,
                'location': session.location,
                'start_time': session.start_time.isoformat(),
                'analyses': [],
                'metadata': {
                    'total_files': len(session.files),
                    'total_duration': session.total_duration,
                    'notes': session.notes
                }
            }
            
            # Process each file sequentially
            for audio_file in session.files:
                self.logger.info(f"Processing file: {audio_file.path}")
                try:
                    # Process audio and get analysis
                    result = self.process_audio(str(audio_file.path))
                    session_results['analyses'].append(result)
                    audio_file.processed = True
                    
                except Exception as e:
                    self.logger.error(f"Error processing {audio_file.path}: {str(e)}")
                    continue
            
            return session_results
            
        except Exception as e:
            self.logger.error(f"Session processing error: {str(e)}")
            raise BatchProcessingError(f"Error processing session: {str(e)}")