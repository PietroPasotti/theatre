import os
from pathlib import Path

APP_DATA_DIR = os.getenv("THEATRE_DATA_DIR", "~/.local/share/theatre")
RESOURCES_DIR = Path(__file__).parent / "resources"
