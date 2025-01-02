# src/report_generation/formatter.py

from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import json
import logging

def format_duration(seconds: float) -> str:
    """Format duration in seconds to HH:MM:SS format"""
    if isinstance(seconds, str):
        return seconds  # Already formatted
        
    from datetime import timedelta
    duration = timedelta(seconds=int(seconds))
    hours = duration.seconds // 3600
    minutes = (duration.seconds % 3600) // 60
    remaining_seconds = duration.seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
    else:
        return f"{minutes:02d}:{remaining_seconds:02d}"

class ReportFormatter:
    """Formats AI analysis into readable reports"""
    
    @staticmethod
    def format_session_report(
        session_info: Dict[str, Any],
        analysis: Dict[str, Any],
        output_dir: Path
    ) -> Path:
        """Format and save AI analysis as a readable report"""
        
        # Create session output directory
        session_dir = output_dir / session_info['session_id']
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Create report paths
        report_path = session_dir / "meeting_report.txt"
        analysis_path = session_dir / "meeting_analysis.json"
        
        # Save raw analysis
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        # Create formatted report
        with open(report_path, "w", encoding="utf-8") as f:
            # Write header
            f.write("Meeting Analysis Report\n")
            f.write("=" * 50 + "\n\n")
            
            # Session Information
            f.write("Session Information:\n")
            f.write("-" * 20 + "\n")
            f.write(f"Session ID: {session_info['session_id']}\n")
            f.write(f"Location: {session_info['location']}\n")
            f.write(f"Date: {session_info['start_time']}\n")
            f.write(f"Duration: {format_duration(float(session_info['total_duration']))}\n")
            if session_info.get('notes'):
                f.write(f"Notes: {session_info['notes']}\n")
            f.write("\n")
            
            # Executive Summary
            f.write("Executive Summary:\n")
            f.write("-" * 20 + "\n")
            f.write(f"{analysis['executive_summary']}\n\n")
            
            # Key Points
            f.write("Key Discussion Points:\n")
            f.write("-" * 20 + "\n")
            for point in analysis['key_points']:
                f.write(f"\nTopic: {point['topic']}\n")
                f.write(f"Details: {point['details']}\n")
                if point['decisions']:
                    f.write("Decisions:\n")
                    for decision in point['decisions']:
                        f.write(f"- {decision}\n")
                if point['action_items']:
                    f.write("Action Items:\n")
                    for item in point['action_items']:
                        f.write(f"- {item}\n")
            f.write("\n")
            
            # Site Specific Details
            f.write("Site Specific Details:\n")
            f.write("-" * 20 + "\n")
            details = analysis['site_specific_details']
            if details['safety_concerns']:
                f.write("\nSafety Concerns:\n")
                for concern in details['safety_concerns']:
                    f.write(f"- {concern}\n")
            if details['progress_updates']:
                f.write("\nProgress Updates:\n")
                for update in details['progress_updates']:
                    f.write(f"- {update}\n")
            if details['technical_issues']:
                f.write("\nTechnical Issues:\n")
                for issue in details['technical_issues']:
                    f.write(f"- {issue}\n")
            f.write("\n")
            
            # Follow-up Items
            f.write("Follow-up Required:\n")
            f.write("-" * 20 + "\n")
            for item in analysis['follow_up_required']:
                f.write(f"\nItem: {item['item']}\n")
                f.write(f"Assigned to: {item['assigned_to']}\n")
                f.write(f"Priority: {item['priority']}\n")
            f.write("\n")
            
            # Meeting Metrics
            f.write("Meeting Metrics:\n")
            f.write("-" * 20 + "\n")
            metrics = analysis['meeting_metrics']
            f.write(f"\nLanguage Distribution: {metrics['language_distribution']}\n")
            f.write(f"Interaction Quality: {metrics['interaction_quality']}\n")
            if metrics['unresolved_items']:
                f.write("\nUnresolved Items:\n")
                for item in metrics['unresolved_items']:
                    f.write(f"- {item}\n")
            
        return report_path