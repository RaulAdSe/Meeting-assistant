from pathlib import Path

WHISPER_MODEL = "base"
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = DATA_DIR / "processed"

for dir_path in [RAW_DIR, OUTPUT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)