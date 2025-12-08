import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from the project root .env file if present.
# Also try loading from 'env' file (without dot) for compatibility
load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(BASE_DIR / "env", override=False)


def get_env(name: str, *, required: bool = True, default: Optional[str] = None) -> str:
    """
    Helper to read environment variables and enforce required secrets.
    """
    value = os.environ.get(name, default)
    if required and (value is None or str(value).strip() == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
