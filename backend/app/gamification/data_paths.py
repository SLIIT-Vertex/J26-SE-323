import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GAMIFICATION_DATA_DIRECTORY = Path(
    os.environ.get("MINDBRIDGE_GAMIFICATION_DATA_DIR", PROJECT_ROOT / "data" / "gamification")
).expanduser().resolve()
