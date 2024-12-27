# src/batch_processing/processors/batch_transcriber.py
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from pydub import AudioSegment

from ...transcriber import EnhancedTranscriber
from ..models.session import AudioSession, AudioFile
from ..utils.time_utils import calculate_relative_timestamps, format_duration
from ..exceptions import BatchProcessingError, FileProcessingError

class BatchTranscriber:
    """Manages the processing of multiple audio files in a session context"""
    
    def __init__(self, transcriber: EnhancedTranscriber, output_dir: Path):
        self.transcriber = transcriber
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def create_session(self, 
                      audio_paths: List[str], 
                      session_id: Optional[str] = None,
                      location: Optional[str] = None,
                      notes: Optional[str] = None) -> AudioSession:
        """Create a new session from a list of audio files"""
        try:
            audio_files = []
            
            for path_str in audio_paths:
                path = Path(path_str)
                if not path.exists():
                    raise FileNotFoundError(f"Audio file not found: {path}")
                
                # Get file metadata
                stats = path.stat()
                audio = AudioSegment.from_file(str(path))
                
                audio_file = AudioFile(
                    path=path,
                    creation_time=datetime.fromtimestamp(stats.st_ctime),
                    size=stats.st_size,
                    duration=len(audio) / 1000.0,  # Convert to seconds
                    metadata={
                        'sample_rate': audio.frame_rate,
                        'channels': audio.channels,
                        'format': path.suffix[1:]  # Remove dot from extension
                    }
                )
                audio_files.append(audio_file)
            
            # Sort files by creation time
            audio_files.sort(key=lambda x: x.creation_time)
            
            return AudioSession(
                session_id=session_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
                start_time=audio_files[0].creation_time,
                files=audio_files,
                location=location,
                notes=notes
            )
            
        except Exception as e:
            raise BatchProcessingError(f"Error creating session: {str(e)}")
    
    def process_session(self, session: AudioSession, max_workers: int = 3) -> Dict[str, Any]:
        """Process all files in a session maintaining chronological order"""
        try:
            session_output_dir = self.output_dir / session.session_id
            session_output_dir.mkdir(exist_ok=True)
            
            session_results = {
                "session_id": session.session_id,
                "start_time": session.start_time,
                "location": session.location,
                "transcripts": [],
                "metadata": {
                    "total_files": len(session.files),
                    "total_duration": session.total_duration,
                    "notes": session.notes
                }
            }
            
            # Process files in parallel while maintaining order
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_file = {
                    executor.submit(
                        self._process_file,
                        audio_file,
                        session.start_time.timestamp(),
                        session_output_dir
                    ): audio_file
                    for audio_file in session.files
                }
                
                # Collect results in chronological order
                for audio_file in session.files:
                    future = next(f for f, af in future_to_file.items() if af == audio_file)
                    try:
                        result = future.result()
                        self._merge_result_into_session(session_results, result)
                        audio_file.processed = True
                    except Exception as e:
                        self.logger.error(f"Error processing {audio_file.path}: {str(e)}")
                        continue
            
            # Save consolidated transcript
            self._save_session_transcript(session_results, session_output_dir)
            
            return session_results
            
        except Exception as e:
            raise BatchProcessingError(f"Error processing session: {str(e)}")
    
    def _process_file(self, 
                     audio_file: AudioFile, 
                     base_time: float,
                     output_dir: Path) -> Dict[str, Any]:
        """Process a single file with enhanced timing information"""
        try:
            result = self.transcriber.process_audio(str(audio_file.path))
            
            # Convert tuple transcripts to dictionaries with timing
            if result.get("aligned_transcript"):
                processed_transcript = []
                file_start_time = audio_file.creation_time
                
                for transcript in result["aligned_transcript"]:
                    if isinstance(transcript, tuple):
                        speaker, text = transcript
                        processed_transcript.append({
                            "speaker": speaker,
                            "text": text,
                            "absolute_time": file_start_time
                        })
                
                result["aligned_transcript"] = processed_transcript
            
            # Add file metadata
            result["metadata"].update({
                "file_info": {
                    "name": audio_file.path.name,
                    "size": audio_file.size,
                    "duration": audio_file.duration,
                    **audio_file.metadata
                }
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing file {audio_file.path}: {str(e)}")
            raise FileProcessingError(f"Failed to process {audio_file.path.name}: {str(e)}")
    
    def _merge_result_into_session(self, 
                                 session_results: Dict[str, Any], 
                                 file_result: Dict[str, Any]):
        """Merge a single file's results into the session results"""
        if file_result.get("aligned_transcript"):
            # Convert tuples to dictionaries if needed
            for transcript in file_result["aligned_transcript"]:
                if isinstance(transcript, tuple):
                    speaker, text = transcript
                    session_results["transcripts"].append({
                        "speaker": speaker,
                        "text": text,
                        "absolute_time": datetime.now()  # You might want to adjust this based on file metadata
                    })
                else:
                    session_results["transcripts"].append(transcript)

    
    def _save_session_transcript(self, 
                               session_results: Dict[str, Any], 
                               output_dir: Path):
        """Save consolidated session transcript with timing information"""
        output_path = output_dir / "session_transcript.txt"
        
        with open(output_path, "w", encoding="utf-8") as f:
            # Write session metadata
            f.write(f"Session ID: {session_results['session_id']}\n")
            f.write(f"Location: {session_results.get('location', 'Not specified')}\n")
            f.write(f"Start Time: {session_results['start_time']}\n")
            f.write(f"Total Files: {session_results['metadata']['total_files']}\n")
            f.write(
                f"Total Duration: {format_duration(session_results['metadata']['total_duration'])}\n"
            )
            if session_results['metadata'].get('notes'):
                f.write(f"\nNotes: {session_results['metadata']['notes']}\n")
            
            # Write chronological transcript
            f.write("\nTranscript:\n\n")
            for segment in session_results["transcripts"]:
                timestamp = segment.get("absolute_time", "").strftime("%H:%M:%S")
                f.write(f"[{timestamp}] {segment['speaker']}: {segment['text']}\n")