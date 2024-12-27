# src/batch_processing/utils/time_utils.py

from datetime import datetime
from typing import Dict, Any

def calculate_relative_timestamps(base_time: float, 
                                segments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert absolute timestamps to relative timestamps based on session start time
    
    Args:
        base_time: Session start time as Unix timestamp
        segments: Dictionary containing transcript segments with timestamps
        
    Returns:
        Updated segments with relative timestamps added
    """
    updated_segments = segments.copy()
    
    for segment in updated_segments.get('aligned_transcript', []):
        if isinstance(segment, dict) and 'start_time' in segment:
            segment['relative_start'] = segment['start_time'] - base_time
            segment['absolute_time'] = datetime.fromtimestamp(
                base_time + segment['relative_start']
            )
            
    return updated_segments

def format_duration(seconds: float) -> str:
    """Convert duration in seconds to human readable format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"