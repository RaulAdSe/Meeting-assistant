from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging
import json
from pydub import AudioSegment
# The import statement for pytest-asyncio seems incorrect. It should be imported as a regular module.
import pytest_asyncio

from src.transcriber import EnhancedTranscriber
from src.construction.expert import ConstructionExpert
from src.timing.analyser import TaskAnalyzer
from src.location.location_processor import LocationProcessor
from src.batch_processing.models.session import AudioSession, AudioFile
from src.batch_processing.exceptions import BatchProcessingError, FileProcessingError
from src.historical_data.services.visit_history import VisitHistoryService
from src.historical_data.database.location_repository import LocationRepository
from src.batch_processing.formatters.enhanced_formatter import EnhancedReportFormatter
from src.historical_data.models.models import Location

from enum import Enum

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, Path):  
            return str(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)
    
def convert_uuid_keys_to_str(d):
    """Recursively convert UUID keys in a dictionary to strings."""
    if isinstance(d, dict):
        return {str(k) if isinstance(k, uuid.UUID) else k: convert_uuid_keys_to_str(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [convert_uuid_keys_to_str(i) for i in d]
    else:
        return d
    
def process_timestamp(timestamp):
    """Process a timestamp, handling None values and float timestamps."""
    if timestamp is None:
        logging.warning("Timestamp is None, using default value.")
        return datetime.now()  # or another default value
    try:
        # Check if the timestamp is a float (Unix timestamp)
        if isinstance(timestamp, float):
            return datetime.fromtimestamp(timestamp)
        # If it's a string, parse it
        return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logging.error(f"Error processing timestamp {timestamp}: {str(e)}")
        return None

def convert_sets_to_lists(data):
    """Recursively convert all sets in a data structure to lists."""
    if isinstance(data, dict):
        return {k: convert_sets_to_lists(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_sets_to_lists(i) for i in data]
    elif isinstance(data, set):
        return list(data)
    else:
        return data
    

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

        # Initialize report formatter
        self.report_formatter = EnhancedReportFormatter()

    def _validate_uuid_or_str(self, value: Any) -> str:
        """Safely convert UUID or string to string."""
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value) if value is not None else None

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
                    creation_time=process_timestamp(path.stat().st_ctime),
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
        
        # Ensure location is a string
        location_str = self._validate_uuid_or_str(location) or "Default Construction Site"

        return AudioSession(
            session_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            start_time=audio_files[0].creation_time,
            files=audio_files,
            location=location_str,
            notes=notes
        )


    async def process_session(self, session: AudioSession) -> Dict[str, Any]:
        try:
            # Create output directory for session
            output_dir = Path("reports") / session.session_id
            output_dir.mkdir(parents=True, exist_ok=True)

            # Get location using unified handler
            location_name = self._validate_uuid_or_str(session.location)
            location = self._handle_location(location_name=location_name)
            
            if not location:
                raise ValueError("Failed to create or retrieve location")
                    
            location_id = location.id

            session_results = {
                'session_id': session.session_id,
                'location': location.name,  # Use the location name from the location object
                'start_time': session.start_time.isoformat(),
                'analyses': [],
                'transcripts': [],
                'metadata': {
                    'total_files': len(session.files),
                    'total_duration': session.total_duration,
                    'notes': session.notes,
                    'location_id': str(location_id)  # Convert UUID to string
                },
                'output_dir': str(output_dir)
            }

            # Process each file sequentially
            all_transcripts = []
            for audio_file in session.files:
                self.logger.info(f"Processing file: {audio_file.path}")
                try:
                    # Process audio and get analysis
                    result = self.process_audio(str(audio_file.path))
                    session_results['analyses'].append(result)
                    
                    if 'transcript' in result:
                        transcript_data = {
                            'text': result['transcript']['text'],
                            'file': str(audio_file.path),
                            'duration': audio_file.duration
                        }
                        session_results['transcripts'].append(transcript_data)
                        all_transcripts.append(result['transcript']['text'])
                        
                        transcript_path = output_dir / f"{Path(audio_file.path).stem}_transcript.txt"
                        with open(transcript_path, "w", encoding="utf-8") as f:
                            f.write(result['transcript']['text'])
                    
                    audio_file.processed = True
                    
                except Exception as e:
                    self.logger.error(f"Error processing {audio_file.path}: {str(e)}")
                    continue

            if not session_results['transcripts']:
                raise ValueError("No transcripts were successfully processed")

            # Generate report
            if location_id:
                combined_transcript = "\n".join(all_transcripts)
                analysis_result = self.construction_expert.analyze_visit(
                    visit_id=uuid.uuid4(),
                    transcript_text=combined_transcript,
                    location_id=location_id
                )

                # Convert AnalysisResult to dictionary format
                analysis_dict = {
                    'executive_summary': "Visit analysis completed successfully",
                    'problems': [self._problem_to_dict(p) for p in analysis_result.problems],
                    'solutions': {
                        str(pid): [self._solution_to_dict(s) for s in solutions]
                        for pid, solutions in analysis_result.solutions.items()
                    },
                    'confidence_scores': analysis_result.confidence_scores,
                    'metadata': analysis_result.metadata
                }

                # Generate report
                report_files = await self.report_formatter.generate_comprehensive_report(
                    transcript_text=combined_transcript,
                    visit_id=uuid.uuid4(),
                    location_id=location_id,
                    output_dir=output_dir,
                    analysis_data=analysis_dict
                )
                
                session_results.update(report_files)

            return session_results

        except Exception as e:
            self.logger.error(f"Session processing error: {str(e)}")
            raise

    def get_transcript_data(self, transcription_result):
        """
        Extracts structured transcript data from Whisper transcription output.
        """
        transcript_data = []
        
        for chunk in transcription_result.get("chunks", []):
            transcript_data.append({
                "text": chunk["text"],
                "timestamp": chunk["timestamp"][0]  
            })
        
        return transcript_data

    def process_audio(self, audio_path: str) -> Dict[str, Any]:
        """Process audio file with transcription and speaker diarization"""
        try:
            # Get basic transcription first
            transcript_result = self.transcriber.process_audio(audio_path)
            if not transcript_result or 'transcript' not in transcript_result:
                raise FileProcessingError("Transcription failed")
                
            # Get location data first
            transcript_text = transcript_result['transcript'].get('text')
            if not transcript_text:
                raise FileProcessingError("No transcript text available")
            
            print(transcript_result)
            
            transcript_data = self.get_transcript_data(transcript_result)
            
            # Process location with timing data
            location_data = self.location_processor.process_transcript(
                transcript_text=transcript_text,
                transcript_data=transcript_data
            )
                
            # Create or get location - this will return a Location object
            location = self._handle_location(location_data=location_data)
            if not location:
                raise ValueError("Failed to create or retrieve location")

            location_id = location.id
                
            # Create visit ID for tracking
            visit_id = uuid.uuid4()
                
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
                'transcript': transcript_result['transcript'],
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
                'location_data': location_data,
                'metadata': {
                    **transcript_result['metadata'],
                    'visit_id': str(visit_id),
                    'location_id': str(location_id),
                    'analyzed_at': datetime.now().isoformat()
                }
            }
                
        except Exception as e:
            self.logger.error(f"Error processing audio {audio_path}: {str(e)}")
            raise FileProcessingError(f"Failed to process {audio_path}: {str(e)}")
            
    def _handle_location(self, 
                            location_name: Optional[str] = None, 
                            location_data: Optional[Dict] = None) -> Any:
        """
        Unified method to handle location creation/retrieval.
        """
        try:
            # Case 1: Try to convert location_name to UUID and look up by ID first
            if location_name is not None:
                try:
                    location_id = uuid.UUID(str(location_name))
                    existing = self.location_repo.get(location_id)
                    if existing:
                        return existing
                except ValueError:
                    # Not a UUID, continue with normal flow
                    pass

            # Case 2: We have location data from processor
            if location_data and location_data.get('main_site'):
                main_site = location_data['main_site']
                company = getattr(main_site, 'company', None) or main_site.get('company', 'Unknown Company')
                site = getattr(main_site, 'site', None) or main_site.get('site', 'Unknown Site')
                
                full_name = f"{company} - {site}"
                existing = self.location_repo.get_by_name(full_name)
                if existing:
                    return existing
                
                return self.location_repo.create(
                    name=full_name,
                    address=site,
                    metadata={'company': company}
                )
            
            # Case 3: We have an explicit location name
            if location_name is not None:
                # Convert to string and clean
                clean_name = str(location_name).strip()
                if clean_name == "Unknown Location" or not clean_name:
                    clean_name = "Default Construction Site"
                    
                self.logger.debug(f"Looking up location with clean name: {clean_name}")
                existing = self.location_repo.get_by_name(clean_name)
                if existing:
                    return existing
                
                return self.location_repo.create(
                    name=clean_name,
                    address=clean_name,
                    metadata={'created_at': datetime.now().isoformat()}
                )
            
            # Case 4: Fallback - create default location
            default_name = "Default Construction Site"
            self.logger.debug("Using fallback location")
            existing = self.location_repo.get_by_name(default_name)
            if existing:
                return existing
            
            return self.location_repo.create(
                name=default_name,
                address="Unknown Address",
                metadata={'is_fallback': True}
            )
            
        except Exception as e:
            self.logger.error(f"Error handling location with name '{location_name}': {str(e)}")
            # Add additional debug information
            self.logger.error(f"Location name type: {type(location_name)}")
            if location_data:
                self.logger.error(f"Location data: {location_data}")
            raise
        
    def _problem_to_dict(self, problem) -> Dict[str, Any]:
        """Convert a ConstructionProblem to dictionary format."""
        return {
            'id': str(problem.id),
            'category': problem.category,
            'description': problem.description,
            'severity': problem.severity,
            'location_context': {
                'area': problem.location_context.area,
                'sub_location': problem.location_context.sub_location
            } if problem.location_context else {},
            'status': problem.status
        }

    def _solution_to_dict(self, solution) -> Dict[str, Any]:
        """Convert a ProposedSolution to dictionary format."""
        return {
            'description': solution.description,
            'estimated_time': solution.estimated_time,
            'priority': solution.priority,
            'effectiveness_rating': solution.effectiveness_rating
        }