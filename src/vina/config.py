import os
import secrets
from pathlib import Path

# Windows local app data, with a fallback for non-Windows dev
APP_NAME = "Vina"
LOCAL_APP_DATA = os.getenv("LOCALAPPDATA") if os.name == 'nt' else str(Path.home() / ".local" / "share")
APP_DIR = Path(LOCAL_APP_DATA) / APP_NAME
APP_DIR.mkdir(parents=True, exist_ok=True)

TOKEN_FILE = APP_DIR / "token"
MODELS_DIR = APP_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# For Phase 0 smoke test, we hardcode your test folder.
# In Phase 1+, this will be configurable via UI/CLI.
TARGET_FOLDER = r"D:\Course"

def get_or_create_token() -> str:
    """Reads the local auth token, or generates a secure one if it doesn't exist."""
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token)
    return token

def warm_up_model():
    """Downloads and loads the embedding model into the cache directory."""
    from fastembed import TextEmbedding
    print(f"[Vina] Checking/downloading embedding model to {MODELS_DIR}...")
    # This triggers the download if not already cached
    model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2", cache_dir=str(MODELS_DIR))
    # Run a dummy embed to ensure ONNX runtime initializes correctly
    list(model.embed(["warmup"]))
    print("[Vina] Model ready.")
    return model