# src/vina/llm/manager.py
import os
import time
import logging
import threading
from pathlib import Path
from llama_cpp import Llama
from ..config import MODELS_DIR

logger = logging.getLogger(__name__)

# Look for any .gguf file in the models/llm directory
LLM_DIR = MODELS_DIR / "llm"
IDLE_TIMEOUT = 600  # 10 minutes in seconds

class LLMManager:
    _instance = None
    _lock = threading.Lock()
    _last_used = 0.0
    _llm = None

    @classmethod
    def get_instance(cls) -> Llama:
        """Lazy-loads the LLM on first request."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                # Start the idle watcher thread
                watcher = threading.Thread(target=cls._idle_watcher, daemon=True)
                watcher.start()
            cls._last_used = time.time()
            return cls._instance._get_llm()

    def _get_llm(self) -> Llama:
        if self._llm is None:
            logger.info("Loading Local LLM into RAM...")
            if not LLM_DIR.exists() or not any(LLM_DIR.glob("*.gguf")):
                raise FileNotFoundError(f"No .gguf model found in {LLM_DIR}")
            
            model_path = next(LLM_DIR.glob("*.gguf"))
            
            self._llm = Llama(
                model_path=str(model_path),
                n_ctx=2048,          # Keep context small for CPU speed
                n_threads=os.cpu_count(),
                n_gpu_layers=0,       # Explicit CPU-only
                verbose=False
            )
            logger.info("LLM loaded successfully.")
        return self._llm

    @classmethod
    def _idle_watcher(cls):
        """Background thread that unloads the LLM if idle for too long."""
        while True:
            time.sleep(60) # Check every minute
            with cls._lock:
                if cls._instance and cls._instance._llm:
                    idle_time = time.time() - cls._last_used
                    if idle_time > IDLE_TIMEOUT:
                        logger.info("LLM idle for 10 minutes. Unloading from RAM to save memory.")
                        cls._instance._llm = None