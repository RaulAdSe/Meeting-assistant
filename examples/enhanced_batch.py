import sys
from pathlib import Path
import logging
import asyncio

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import necessary modules
from src.batch_processing.processors.enhanced_batch_transcriber import EnhancedBatchTranscriber
from src.config import RAW_DIR, OUTPUT_DIR

async def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize transcriber
    transcriber = EnhancedBatchTranscriber()
    
    # Get all audio files from RAW_DIR
    audio_files = []
    for ext in ['.wav', '.m4a']:
        audio_files.extend([str(p) for p in RAW_DIR.glob(f'*{ext}')])
    
    if not audio_files:
        print(f"No audio files found in {RAW_DIR}")
        return
        
    print(f"Found {len(audio_files)} audio files:")
    for file in audio_files:
        print(f"  - {Path(file).name}")
    
    try:
        # Create a session
        session = transcriber.create_session(
            audio_paths=audio_files,
            location="Default Location",
            notes="Batch processing of audio files"
        )
        
        # Process all files
        print("\nProcessing files...")
        results = await transcriber.process_session(session)
        
        # Generate comprehensive report using the formatter within the transcriber
        print("\nGenerating report...")
        report_files = await transcriber.report_formatter.generate_comprehensive_report(
            transcript_text="\n".join([t['text'] for t in results['transcripts']]),
            visit_id=session.session_id,
            location_id=session.location,
            output_dir=OUTPUT_DIR / session.session_id
        )
        
        print(f"\nReports generated in: {OUTPUT_DIR / session.session_id}")
        
    except Exception as e:
        print(f"Error processing batch: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())