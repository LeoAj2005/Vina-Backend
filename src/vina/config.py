from __future__ import annotations

import json
import logging
import os
import secrets
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

APP_NAME = "Vina"

# 1. Deterministic Cross-Platform Path Initialization
def _resolve_app_directory() -> Path:
    """Computes a secure, write-accessible base directory for application data."""
    if os.name == "nt":
        local_app_data = os.getenv("LOCALAPPDATA")
        base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    else:
        base_dir = Path.home() / ".local" / "share"
    
    target_dir = base_dir / APP_NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


APP_DIR = _resolve_app_directory()
TOKEN_FILE = APP_DIR / "token"
CONFIG_FILE = APP_DIR / "config.json"

LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

MODELS_DIR = APP_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG: dict[str, Any] = {
    "target_folder": str(Path.home() / "Documents"),
    "port": 8765,
    "host": "127.0.0.1"
}

# Module-level internal logger instance
logger = logging.getLogger(APP_NAME.lower())

# Explicit state guard to strictly prevent duplicate handler registrations
_logging_initialized = False


def _atomic_write_text(file_path: Path, content: str) -> None:
    """
    Writes content to a temporary file before renaming it to the target location.
    Guarantees file integrity and prevents data corruption during unexpected shutdowns.
    """
    temp_file = file_path.with_suffix(".tmp")
    try:
        temp_file.write_text(content, encoding="utf-8")
        # Atomic replacement operation at the OS kernel level
        temp_file.replace(file_path)
    except Exception as err:
        # missing_ok=True prevents cleanup failures from masking the underlying write exception
        temp_file.unlink(missing_ok=True)
        logger.error("Failed atomic write operation to %s: %s", file_path, err)
        raise


def get_config() -> dict[str, Any]:
    """
    Loads config.json from disk. Automatically repairs itself and falls back 
    to robust defaults if data corruption is encountered.
    """
    if not CONFIG_FILE.exists():
        cfg = DEFAULT_CONFIG.copy()
        # Retained explicitly for your 1-week test path requirement
        cfg["target_folder"] = r"D:\Course"
        try:
            _atomic_write_text(CONFIG_FILE, json.dumps(cfg, indent=4))
        except Exception:
            pass
        return cfg

    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError, OSError) as err:
        logger.error("Configuration file corruption encountered at %s. Error: %s", CONFIG_FILE, err)
        
        # Self-Healing Routine: Isolate the broken config for inspection and regenerate healthy states
        try:
            corrupted_backup = CONFIG_FILE.with_suffix(".corrupted")
            CONFIG_FILE.replace(corrupted_backup)
            logger.warning("Corrupted configuration file rotated out to: %s", corrupted_backup)
        except Exception:
            pass
            
        return DEFAULT_CONFIG.copy()


def get_or_create_token() -> str:
    """Reads the secure local authorization token, or atomically generates one if missing."""
    if TOKEN_FILE.exists():
        try:
            return TOKEN_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            logger.exception("Failed reading security credential token from filesystem layer.")

    token = secrets.token_urlsafe(32)
    try:
        _atomic_write_text(TOKEN_FILE, token)
    except Exception:
        logger.error("Failed to commit security authorization token atomically to storage media.")
    return token


def setup_logging() -> logging.Logger:
    """Configures high-availability rotating file logs alongside diagnostic stdout streaming."""
    global _logging_initialized
    
    # Short-circuit immediately if logging handles have already been bound to this lifecycle
    if _logging_initialized:
        return logger

    log_file = LOG_DIR / "vina.log"
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

    # Guard explicitly against duplicate handler stacking in multiple entry-points
    has_file_handler = any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers)
    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) 
        for h in root_logger.handlers
    )

    if not has_file_handler:
        file_handler = RotatingFileHandler(log_file, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    if not has_stream_handler:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    _logging_initialized = True
    return logger