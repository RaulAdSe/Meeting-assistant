import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.transcriber import EnhancedTranscriber
from src.config import RAW_DIR

transcriber = EnhancedTranscriber()
result = transcriber.process_audio(str(RAW_DIR / "New_Recording_2.m4a"))