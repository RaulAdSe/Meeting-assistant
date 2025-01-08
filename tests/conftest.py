import pytest
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Common fixtures that can be used across all tests
@pytest.fixture(scope="session")
def project_root():
    return Path(__file__).parent.parent 