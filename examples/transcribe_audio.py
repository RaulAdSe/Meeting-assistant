import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.transcriber import EnhancedTranscriber

transcriber = EnhancedTranscriber()
result = transcriber.process_audio("../data/raw/New_Recording_3.m4a")