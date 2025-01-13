from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging
import json
from pydub import AudioSegment

from src.transcriber import EnhancedTranscriber
from src.construction.expert import ConstructionExpert
from src.timing.analyser import TaskAnalyzer
from src.location.location_processor import LocationProcessor
from src.batch_processing.models.session import AudioSession, AudioFile
from src.batch_processing.exceptions import BatchProcessingError, FileProcessingError
from src.historical_data.services.visit_history import VisitHistoryService
from src.historical_data.database.location_repository import LocationRepository

from enum import Enum

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        return super().default(obj)
    
def convert_uuid_keys_to_str(d):
    """Recursively convert UUID keys in a dictionary to strings."""
    if isinstance(d, dict):
        return {str(k) if isinstance(k, uuid.UUID) else k: convert_uuid_keys_to_str(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [convert_uuid_keys_to_str(i) for i in d]
    else:
        return d
    
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
        
        # Initialize repositories
        self.location_repo = LocationRepository()
        self.history_service = VisitHistoryService()

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
            
            # Create or get location
            location_data = self.location_processor.process_transcript(transcript_result['transcript']['text'])
            location = self._get_or_create_location(location_data)
            
            # Access location ID correctly
            location_id = location.get('id')  # Use .get() for dictionary
            
            # Perform comprehensive analysis
            analysis = self.analyze_transcript(
                transcript_text=transcript_result['transcript']['text'],
                visit_id=visit_id,
                location_id=location_id
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
        if not transcript_text.strip():
            raise ValueError("Empty transcript text")
            
        try:
            # Process location information
            location_data = self.location_processor.process_transcript(transcript_text)
            
            if not location_id:
                # Create or get location if not provided
                location = self._get_or_create_location(location_data)
                location_id = location['id'] if isinstance(location, dict) else location.id
            
            # Get construction analysis
            construction_analysis = self.construction_expert.analyze_visit(
                visit_id=visit_id,
                transcript_text=transcript_text,
                location_id=location_id
            )
            
            # Get timing analysis
            timing_analysis = self.task_analyzer.analyze_transcript(
                transcript_text=transcript_text,
                location_id=location_id
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
                    'location_id': str(location_id),
                    'analyzed_at': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing transcript: {str(e)}")
            raise

    def process_session(self, session: AudioSession) -> Dict[str, Any]:
            """Process all files in a session with comprehensive analysis."""
            try:
                # Create output directory for session
                output_dir = Path("reports") / session.session_id
                output_dir.mkdir(parents=True, exist_ok=True)

                session_results = {
                    'session_id': session.session_id,
                    'location': session.location,
                    'start_time': session.start_time.isoformat(),
                    'analyses': [],
                    'transcripts': [],
                    'metadata': {
                        'total_files': len(session.files),
                        'total_duration': session.total_duration,
                        'notes': session.notes
                    },
                    'output_dir': str(output_dir)
                }
                combined_analysis = {}
                latest_location_data = None
                
                # Process each file sequentially
                for audio_file in session.files:
                    self.logger.info(f"Processing file: {audio_file.path}")
                    try:
                        # Process audio and get analysis
                        result = self.process_audio(str(audio_file.path))
                        session_results['analyses'].append(result)
                        
                        # Combine analyses for root level access
                        if 'construction_analysis' in result:
                            combined_analysis['construction_analysis'] = result['construction_analysis']
                        if 'timing_analysis' in result:
                            combined_analysis['timing_analysis'] = result['timing_analysis']
                        if 'location_data' in result:
                            latest_location_data = result['location_data']
                            combined_analysis['location_data'] = result['location_data']
                        
                        # Add transcript to transcripts list and save to file
                        if 'transcript' in result:
                            transcript_data = {
                                'text': result['transcript']['text'],
                                'file': str(audio_file.path),
                                'duration': audio_file.duration
                            }
                            session_results['transcripts'].append(transcript_data)
                            
                            # Save individual transcript
                            transcript_path = Path(output_dir) / f"{Path(audio_file.path).stem}_transcript.txt"
                            with open(transcript_path, "w", encoding="utf-8") as f:
                                f.write(result['transcript']['text'])
                            
                        audio_file.processed = True
                        
                    except Exception as e:
                        self.logger.error(f"Error processing {audio_file.path}: {str(e)}")
                        continue

                combined_analysis = convert_uuid_keys_to_str(combined_analysis)
                # Save combined session transcript
                session_transcript_path = Path(output_dir) / "session_transcript.txt"
                with open(session_transcript_path, "w", encoding="utf-8") as f:
                    f.write(f"Session ID: {session.session_id}\n")
                    f.write(f"Location: {session.location}\n")
                    f.write(f"Date: {session.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Total Duration: {session.total_duration:.2f} seconds\n")
                    if session.notes:
                        f.write(f"Notes: {session.notes}\n")
                    f.write("\n=== Transcripts ===\n\n")
                    
                    for idx, transcript in enumerate(session_results['transcripts'], 1):
                        f.write(f"File {idx}: {Path(transcript['file']).name}\n")
                        f.write(f"Duration: {transcript['duration']:.2f} seconds\n")
                        f.write("-" * 40 + "\n")
                        f.write(transcript['text'])
                        f.write("\n\n")

                # Save session analysis
                analysis_path = Path(output_dir) / "session_analysis.json"
                with open(analysis_path, "w", encoding="utf-8") as f:
                    json.dump({
                        'session_id': session.session_id,
                        'location': session.location,
                        'total_files': len(session.files),
                        'total_duration': session.total_duration,
                        'notes': session.notes,
                        'analysis_timestamp': datetime.now().isoformat(),
                        'construction_analysis': combined_analysis.get('construction_analysis', {}),
                        'timing_analysis': combined_analysis.get('timing_analysis', {}),
                        'location_data': latest_location_data
                }, f, indent=2, cls=CustomJSONEncoder)
                # Merge combined analysis into results
                session_results.update(combined_analysis)
                return session_results
                
            except Exception as e:
                self.logger.error(f"Session processing error: {str(e)}")
                raise BatchProcessingError(f"Error processing session: {str(e)}")

    def _get_or_create_location(self, location_data: Dict[str, Any]):
        try:
            main_site = location_data.get('main_site', {})
            company = getattr(main_site, 'company', None) or 'Unknown Company'
            site = getattr(main_site, 'site', None) or 'Unknown Site'
            
            # Try to find existing location
            locations = self.location_repo._execute_query(
                "SELECT id, name, address, metadata FROM locations WHERE name = %s",
                (f"{company} - {site}",)
            )
            
            if locations:
                # Access as dictionary
                return {
                    'id': locations[0]['id'],
                    'name': locations[0]['name'],
                    'address': locations[0]['address'],
                    'metadata': locations[0]['metadata']
                }
            
            # Create new location
            location = self.location_repo.create(
                name=f"{company} - {site}",
                address=site,
                metadata={'company': company}
            )
            
            # Ensure dictionary format
            if not isinstance(location, dict):
                location = {
                    'id': location.id,
                    'name': location.name,
                    'address': location.address,
                    'metadata': location.metadata
                }
            return location
            
        except Exception as e:
            self.logger.error(f"Error creating location: {str(e)}")
            return {
                'id': uuid.uuid4(),
                'name': "Unknown Location",
                'address': "Unknown",
                'metadata': {}
            }

    def _get_or_create_location_by_name(self, location_name: str):
        """Get existing location or create new one by name."""
        try:
            # Try to find existing location
            locations = self.location_repo._execute_query(
                "SELECT id, name, address, metadata FROM locations WHERE name = %s",
                (location_name,)
            )
            
            if locations:
                return locations[0]
            
            # Create new location
            location = self.location_repo.create(
                name=location_name,
                address=location_name,
                metadata={}
            )
            
            # Convert to dict if not already
            if not isinstance(location, dict):
                location = {
                    'id': location.id,
                    'name': location.name,
                    'address': location.address,
                    'metadata': location.metadata
                }
            
        except Exception as e:
            self.logger.error(f"Error creating location: {str(e)}")
            # Return a default location
            return self.location_repo.create(
                name="Unknown Location",
                address="Unknown",
                metadata={}
            )