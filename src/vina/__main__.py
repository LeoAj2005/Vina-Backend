import threading
import uvicorn
import logging
from .config import get_config, get_or_create_token, APP_DIR, setup_logging
from .indexer.runner import run_indexer
from .indexer.watcher import start_watcher
from .server import app  # Static import ensures PyInstaller traces & bundles this module directly

def main():
    # 1. Setup Framework Logging
    logger = setup_logging()
    logger.info(f"Initializing Vina Engine Core Services")
    logger.info(f"Local App Configuration Repository Location: {APP_DIR}")
    
    try:
        # 2. Extract Configuration Values
        config = get_config()
        target_folder = config["target_folder"]
        port = config["port"]
        host = config["host"]
        
        # Ensure security key is generated
        _ = get_or_create_token()
        
        # 3. Execute Directory Baseline Sync
        run_indexer(target_folder)
        
        # 4. Bind Live Background Watchdog Instance
        logger.info(f"Spawning live background file tracking daemon thread targeting: {target_folder}")
        watcher_thread = threading.Thread(
            target=start_watcher, 
            args=(target_folder,), 
            daemon=True
        )
        watcher_thread.start()
        
        # 5. Hand control off to FastAPI/Uvicorn HTTP Engine Layer
        logger.info(f"Starting REST API infrastructure server on http://{host}:{port}")
        
        # Passing the pre-imported 'app' instance protects the frozen executable build
        uvicorn.run(
            app, 
            host=host, 
            port=port, 
            log_level="info"
        )
        
    except Exception as e:
        # Captures the full traceback automatically and dumps it straight into your vina.log file
        logger.exception("Fatal error encountered during Vina Core engine startup runtime loop")
        raise

if __name__ == "__main__":
    main()