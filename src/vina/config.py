import os
import json
import secrets
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

APP_NAME = "Vina"
LOCAL_APP_DATA = os.getenv("LOCALAPPDATA") if os.name == 'nt' else str(Path.home() / ".local" / "share")
APP_DIR = Path(LOCAL_APP_DATA) / APP_NAME
APP_DIR.mkdir(parents=True, exist_ok=True)

TOKEN_FILE = APP_DIR / "token"
CONFIG_FILE = APP_DIR / "config.json"
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR = APP_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "target_folder": str(Path.home() / "Documents"),
    "port": 8765,
    "host": "127.0.0.1"
}

def get_config() -> dict:
    """Loads config.json, creating it with defaults if it doesn't exist."""
    if not CONFIG_FILE.exists():
        # For your specific test, let's force D:\Course initially
        # but normally we'd let the user edit the config file.
        cfg = DEFAULT_CONFIG.copy()
        cfg["target_folder"] = r"D:\Course"
        CONFIG_FILE.write_text(json.dumps(cfg, indent=4))
        return cfg
    
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return DEFAULT_CONFIG

def get_or_create_token() -> str:
    """Reads the local auth token, or generates a secure one if it doesn't exist."""
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token)
    return token

def setup_logging():
    """Configures rotating file logs plus stdout streaming."""
    log_file = LOG_DIR / "vina.log"
    # 2MB max per file, keeps 3 history logs
    handler = RotatingFileHandler(log_file, maxBytes=2*1024*1024, backupCount=3) 
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if setup is called multiple times
    if not logger.handlers:
        logger.addHandler(handler)
        
        # Also log to console output stream
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger