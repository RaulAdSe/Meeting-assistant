import sys
from pathlib import Path
import logging
import asyncio
import uuid
from datetime import datetime

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.batch_processing.processors.enhanced_batch_transcriber import EnhancedBatchTranscriber
from src.batch_processing.formatters.enhanced_formatter import EnhancedReportFormatter
from src.config import RAW_DIR, OUTPUT_DIR

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # 1) Initialize transcriber (analysis) & formatter
    transcriber = EnhancedBatchTranscriber()
    formatter = EnhancedReportFormatter()
    
    # 2) Gather audio files
    audio_files = []
    for ext in ('.wav','.m4a'):
        audio_files.extend(str(p) for p in RAW_DIR.glob(f'*{ext}'))
    
    if not audio_files:
        print(f"No audio files found in {RAW_DIR}")
        return
    
    print(f"Found {len(audio_files)} audio files:\n")
    for file in audio_files:
        print(f"  - {Path(file).name}")
    
    try:
        # 3) Create the analysis session
        session = transcriber.create_session(
            audio_paths=audio_files,
            location="Default Location",  # user-defined or from CLI
            notes="Batch processing of audio files"
        )
        
        # 4) Run the analysis pipeline (but do NOT create PDF/MD yet)
        print("\nProcessing files...")
        analysis_data = await transcriber.process_session(session)
        # analysis_data now has:
        # {
        #   "session_id": "...",
        #   "location_name": "...",
        #   "visit_id": <uuid>,
        #   "location_id": <uuid>,
        #   "combined_transcript": "...",
        #   "analysis": {
        #       "location_data": {...},
        #       "construction_analysis": {...},
        #       "timing_analysis": ...
        #   },
        #   "metadata": {...}
        # }

        # 5) Optionally generate a chronogram (Mermaid Gantt) from timing data
        #    if you want it in the final report
        chronogram = formatter.chronogram_visualizer.generate_mermaid_gantt(
            analysis_data["analysis"]["timing_analysis"],
            start_date=datetime.now()
        )

        # 6) Now create the final report. Provide the pre-analyzed data:
        output_dir = OUTPUT_DIR / analysis_data["session_id"]
        report_files = await formatter.generate_comprehensive_report(
            output_dir=output_dir,
            visit_id=analysis_data["visit_id"],
            location_id=analysis_data["location_id"],
            location_data=analysis_data["analysis"]["location_data"],
            construction_analysis=analysis_data["analysis"]["construction_analysis"],
            timing_analysis=analysis_data["analysis"]["timing_analysis"],
            chronogram=chronogram
        )

        # 7) Done! We can see where the final PDF/MD are stored:
        print(f"\nMarkdown report saved to: {report_files['markdown']}")
        print(f"PDF report saved to: {report_files['pdf']}")
        print(f"Metadata: {report_files['metadata']}")

    except Exception as e:
        print(f"Error processing batch: {e}")


if __name__ == "__main__":
    asyncio.run(main())
