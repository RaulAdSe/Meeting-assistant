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

from enum import Enum

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        elif isinstance(obj, Path):  # Handle PosixPath and other Path objects
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
            if not transcript_result or 'transcript' not in transcript_result:
                raise FileProcessingError("Transcription failed")
                
            # Get location data first
            location_data = self.location_processor.process_transcript(
                transcript_result['transcript']['text']
            )
            
            # Create or get location - this will return a Location object
            location = self._get_or_create_location(location_data)
            location_id = location.id if location else uuid.uuid4()
            
            # Create visit ID for tracking
            visit_id = uuid.uuid4()
            
            # Get construction analysis
            construction_analysis = self.construction_expert.analyze_visit(
                visit_id=visit_id,
                transcript_text=transcript_result['transcript']['text'],
                location_id=location_id
            )
            
            # Get timing analysis
            timing_analysis = self.task_analyzer.analyze_transcript(
                transcript_text=transcript_result['transcript']['text'],
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

    async def process_session(self, session: AudioSession) -> Dict[str, Any]:
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
            
            # Get or create location for session
            location = self.location_repo.get_by_name(session.location)
            if not location:
                location = self.location_repo.create(
                    name=session.location, 
                    address=session.location
                )
            location_id = location.id

            # Process each file sequentially
            all_transcripts = []
            for audio_file in session.files:
                self.logger.info(f"Processing file: {audio_file.path}")
                try:
                    # Process audio and get analysis
                    result = self.process_audio(str(audio_file.path))
                    session_results['analyses'].append(result)
                    
                    # Add transcript
                    if 'transcript' in result:
                        transcript_data = {
                            'text': result['transcript']['text'],
                            'file': str(audio_file.path),
                            'duration': audio_file.duration
                        }
                        session_results['transcripts'].append(transcript_data)
                        all_transcripts.append(result['transcript']['text'])
                        
                        # Save individual transcript
                        transcript_path = output_dir / f"{Path(audio_file.path).stem}_transcript.txt"
                        with open(transcript_path, "w", encoding="utf-8") as f:
                            f.write(result['transcript']['text'])
                    
                    audio_file.processed = True
                    
                except Exception as e:
                    self.logger.error(f"Error processing {audio_file.path}: {str(e)}")
                    continue
            
            if not session_results['transcripts']:
                raise BatchProcessingError("No transcripts were successfully processed")

            # Generate report using all transcripts
            if location_id:
                combined_transcript = "\n".join(all_transcripts)
                analysis_result = self.construction_expert.analyze_visit(
                    visit_id=uuid.uuid4(),
                    transcript_text=combined_transcript,
                    location_id=location_id
                )

                # Convert AnalysisResult to dictionary format for report formatter
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

                report_files = await self.report_formatter.generate_comprehensive_report(
                    transcript_text=combined_transcript,
                    visit_id=uuid.uuid4(),
                    location_id=location_id,
                    output_dir=output_dir,
                    analysis_data=analysis_dict
                )
                session_results.update(report_files)

            session_results = convert_uuid_keys_to_str(session_results)

            # Save session transcript
            session_transcript_path = output_dir / "session_transcript.txt"
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

            # Save session analysis to JSON
            session_analysis_path = output_dir / "session_analysis.json"
            with open(session_analysis_path, "w", encoding="utf-8") as f:
                json.dump(session_results, f, cls=CustomJSONEncoder, indent=4)

            return session_results

        except Exception as e:
            self.logger.error(f"Session processing error: {str(e)}")
            raise BatchProcessingError(f"Error processing session: {str(e)}")

    def _get_or_create_location(self, location_data: Dict[str, Any]):
        """Get existing location or create new one from location data."""
        try:
            main_site = location_data.get('main_site', {})
            
            # Extract company and site names safely
            company = getattr(main_site, 'company', None) or main_site.get('company', 'Unknown Company')
            site = getattr(main_site, 'site', None) or main_site.get('site', 'Unknown Site')
            
            location_name = f"{company} - {site}"
            
            # Try to find existing location
            location = self.location_repo.get_by_name(location_name)
            
            if location:
                return location
            
            # Create new location
            return self.location_repo.create(
                name=location_name,
                address=site,
                metadata={'company': company}
            )
            
        except Exception as e:
            self.logger.error(f"Error in _get_or_create_location: {str(e)}")
            # Return a default location
            return self.location_repo.create(
                name="Unknown Location",
                address="Unknown",
                metadata={}
            )

    def _get_or_create_location_by_name(self, location_name: str):
        """Get existing location or create new one by name."""
        try:
            # Try to find existing location
            existing_locations = list(filter(
                lambda x: x.name == location_name,
                self.location_repo.get_all()
            ))
            
            if existing_locations:
                return existing_locations[0]
            
            # Create new location if not found
            return self.location_repo.create(
                name=location_name,
                address=location_name,
                metadata={}
            )
            
        except Exception as e:
            self.logger.error(f"Error handling location: {str(e)}")
            # Create a default location as fallback
            return self.location_repo.create(
                name="Unknown Location",
                address="Unknown",
                metadata={}
            )
        
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