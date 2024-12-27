import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.speakers.manager import SpeakerManager

def main():
    # Initialize speaker manager
    print("Initializing speaker manager...")
    speaker_manager = SpeakerManager()
    
    # Use project_root to create absolute paths to recordings
    recordings = [
        str(project_root / "data" / "raw" / "New_Recording_2.m4a"),
        str(project_root / "data" / "raw" / "New_Recording_3.m4a")
    ]
    
    # Verify files exist before processing
    for recording in recordings:
        if not Path(recording).exists():
            print(f"Warning: File not found: {recording}")
            continue
            
        print(f"\nProcessing {recording}...")
        try:
            result = speaker_manager.process_audio(recording)
            
            print("\nSpeaker segments:")
            for speaker_id, segments in result.items():
                print(f"\n{speaker_id}:")
                for segment in segments:
                    print(f"  {segment['start']:.2f}s - {segment['end']:.2f}s")
        except Exception as e:
            print(f"Error processing {recording}: {str(e)}")

if __name__ == "__main__":
    main()