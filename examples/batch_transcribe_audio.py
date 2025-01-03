# examples/batch_transcribe_audio.py

import sys
from pathlib import Path

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Now we can import from src
from src.transcriber import EnhancedTranscriber
from src.batch_processing.processors.batch_transcriber import BatchTranscriber
from src.config import RAW_DIR, OUTPUT_DIR

def main():
    # Initialize transcriber
    enhanced_transcriber = EnhancedTranscriber()
    
    # Initialize batch transcriber with output directory from config
    batch_transcriber = BatchTranscriber(
        transcriber=enhanced_transcriber,
        output_dir=OUTPUT_DIR
    )
    
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
        session = batch_transcriber.create_session(
            audio_paths=audio_files
        )
        
        # Display temporal order
        print("\nFiles in chronological order:")
        for audio_file in session.files:
            print(f"\nFile: {audio_file.path.name}")
            print(f"Created: {audio_file.creation_time}")
            print(f"Duration: {audio_file.duration:.2f} seconds")
            print(f"Format: {audio_file.metadata.get('format', 'unknown')}")
            print(f"Sample Rate: {audio_file.metadata.get('sample_rate', 'unknown')} Hz")
            
        # Process all files
        print("\nProcessing files...")
        results = batch_transcriber.process_session(session)
        
        # Show results
        print("\nTranscript excerpts in temporal order:")
        for segment in results["transcripts"][:5]:  # First 5 segments
            print(f"[{segment['absolute_time']}] {segment['speaker']}: {segment['text']}")
            
        print(f"\nFull transcript saved to: {OUTPUT_DIR / session.session_id / 'session_transcript.txt'}")
        
    except Exception as e:
        print(f"Error processing batch: {str(e)}")

if __name__ == "__main__":
    main()