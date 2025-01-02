#!/usr/bin/env python3
# examples/analyze_transcripts.py

import sys
from pathlib import Path
import json
import shutil
from datetime import datetime
import logging
from typing import Dict, Any

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.transcriber import EnhancedTranscriber
from src.batch_processing.processors.batch_transcriber import BatchTranscriber
from src.config import RAW_DIR, OUTPUT_DIR
from src.batch_processing.formatters.transcript_formatter import TranscriptFormatter
from src.report_generation.llm_service import LLMService
from src.batch_processing.formatters.markdown_report_generator import MarkdownReportGenerator

class TranscriptAnalyzer:
    def __init__(self):
        self.setup_directories()
        self.setup_logging()
        self.llm_service = LLMService()
        self.markdown_generator = MarkdownReportGenerator()
        
    def setup_directories(self):
        """Set up reports directory"""
        self.base_dir = Path(__file__).parent.parent
        self.reports_dir = self.base_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
    def setup_logging(self):
        """Configure logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self.reports_dir / "analysis.log")
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_session_directory(self, session_id: str) -> Path:
        """Create and return a directory for a specific session"""
        session_dir = self.reports_dir / session_id
        session_dir.mkdir(exist_ok=True)
        return session_dir

    def analyze_transcript(self, transcript_path: Path):
        """Analyze a transcript and generate organized outputs"""
        try:
            # Read the transcript
            transcript_text = transcript_path.read_text(encoding='utf-8')
            
            # Parse session info from transcript
            session_info = self.parse_session_info(transcript_text)
            
            # Create session directory
            session_dir = self.create_session_directory(session_info['session_id'])
            
            # Copy original transcript
            shutil.copy2(transcript_path, session_dir / "original_transcript.txt")
            
            # Generate AI analysis
            analysis = self.llm_service.analyze_transcript(
                transcript_text=transcript_text,
                session_info=session_info
            )
            
            # Save analysis as JSON
            analysis_path = session_dir / "analysis.json"
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            
            # Generate reports in different formats
            # 1. Legacy text report
            text_report_path = self.generate_text_report(session_info, analysis, session_dir)
            
            # 2. Markdown/PDF report
            markdown_path, pdf_path = self.markdown_generator.generate_report(
                session_info=session_info,
                analysis=analysis,
                output_dir=session_dir
            )
            
            # Log completion
            self.logger.info(f"Analysis completed for session {session_info['session_id']}")
            self.logger.info(f"Reports saved in: {session_dir}")
            
            # Print locations of generated files
            print("\nGenerated Files:")
            print(f"- Original Transcript: {session_dir / 'original_transcript.txt'}")
            print(f"- Analysis JSON: {analysis_path}")
            print(f"- Text Report: {text_report_path}")
            print(f"- PDF Report: {pdf_path}")
            print(f"- Markdown Report: {pdf_path.with_suffix('.md')}")
            
            # Print summary
            self.print_analysis_summary(analysis)
            
        except Exception as e:
            self.logger.error(f"Error analyzing transcript: {str(e)}")
            raise

    def parse_session_info(self, transcript_text: str) -> Dict[str, Any]:
        """Parse session information from transcript text"""
        lines = transcript_text.split('\n')
        session_info = {}
        
        for line in lines:
            if line.startswith('Session ID: '):
                session_info['session_id'] = line.split(': ')[1]
            elif line.startswith('Location: '):
                session_info['location'] = line.split(': ')[1]
            elif line.startswith('Start Time: '):
                session_info['start_time'] = datetime.strptime(
                    line.split(': ')[1], 
                    '%Y-%m-%d %H:%M:%S'
                )
            elif line.startswith('Total Duration: '):
                duration_str = line.split(': ')[1]
                h, m = map(int, duration_str.split(':'))
                session_info['total_duration'] = h * 3600 + m * 60  # Convert to seconds
            elif line.startswith('Notes: '):
                session_info['notes'] = line.split(': ')[1]
                
        return session_info

    def generate_text_report(self, session_info: Dict, analysis: Dict, output_dir: Path) -> Path:
        """Generate a plain text formatted report (legacy format)"""
        report_path = output_dir / "session_report.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write(f"Session Analysis Report\n")
            f.write("=" * 50 + "\n\n")
            
            # Session Information
            f.write("Session Information\n")
            f.write("-" * 20 + "\n")
            f.write(f"Session ID: {session_info['session_id']}\n")
            f.write(f"Location: {session_info['location']}\n")
            f.write(f"Date: {session_info['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if 'total_duration' in session_info:
                duration_mins = session_info['total_duration'] // 60
                f.write(f"Duration: {duration_mins // 60:02d}:{duration_mins % 60:02d}\n")
                
            if 'notes' in session_info:
                f.write(f"Notes: {session_info['notes']}\n")
            f.write("\n")
            
            # Executive Summary
            f.write("Executive Summary\n")
            f.write("-" * 20 + "\n")
            f.write(analysis['executive_summary'])
            f.write("\n\n")
            
            # Key Points
            f.write("Key Points\n")
            f.write("-" * 20 + "\n")
            for point in analysis['key_points']:
                f.write(f"\nTopic: {point['topic']}\n")
                f.write(f"Details: {point['details']}\n")
                if point.get('decisions'):
                    f.write("Decisions:\n")
                    for decision in point['decisions']:
                        f.write(f"- {decision}\n")
                if point.get('action_items'):
                    f.write("Action Items:\n")
                    for item in point['action_items']:
                        f.write(f"- {item}\n")
            f.write("\n")
            
            # Language Analysis
            if 'language_analysis' in analysis:
                f.write("Language Analysis\n")
                f.write("-" * 20 + "\n")
                f.write(f"Languages Used: {', '.join(analysis['language_analysis'].get('languages_used', []))}\n")
                f.write(f"Distribution: {analysis['language_analysis'].get('language_distribution', '')}\n\n")
            
            # Follow-up Items
            f.write("Follow-up Required\n")
            f.write("-" * 20 + "\n")
            for item in analysis['follow_up_required']:
                f.write(f"- {item['item']}\n")
                f.write(f"  Priority: {item['priority']}\n")
                f.write(f"  Assigned to: {item['assigned_to']}\n")
            
        return report_path

    def print_analysis_summary(self, analysis: Dict):
        """Print a summary of the analysis to console"""
        print("\nAnalysis Summary")
        print("=" * 50)
        print("\nExecutive Summary:")
        print(analysis['executive_summary'])
        
        print("\nKey Action Items:")
        for item in analysis['follow_up_required']:
            print(f"- {item['item']} (Priority: {item['priority']})")

def main():
    analyzer = TranscriptAnalyzer()
    
    # Get all transcript files from processed directory
    transcript_files = list(OUTPUT_DIR.glob("*/session_transcript.txt"))
    
    if not transcript_files:
        print(f"No transcript files found in {OUTPUT_DIR}")
        return
        
    print(f"Found {len(transcript_files)} transcript files:")
    for idx, file in enumerate(transcript_files, 1):
        print(f"{idx}. {file.parent.name} - {file.name}")
    
    try:
        while True:
            selection = input("\nSelect a transcript to analyze (number) or 'q' to quit: ")
            
            if selection.lower() == 'q':
                break
                
            try:
                idx = int(selection) - 1
                if 0 <= idx < len(transcript_files):
                    selected_file = transcript_files[idx]
                    print(f"\nAnalyzing: {selected_file}")
                    analyzer.analyze_transcript(selected_file)
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number or 'q' to quit.")
                
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()