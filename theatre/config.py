import os
from pathlib import Path

APP_DATA_DIR = os.getenv("THEATRE_DATA_DIR", "~/.local/share/theatre")
RESOURCES_DIR = Path(__file__).parent / "resources"
TEMPLATES_DIR = RESOURCES_DIR / "templates"

SCENE_EXTENSION = ".theatre"
SCENE_FILE_TYPE = f"Scene (*{SCENE_EXTENSION});;All files (*)"
PYTHON_SOURCE_TYPE = "Python source (*.py);;All files (*)"
