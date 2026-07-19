import logging
import sys
from pathlib import Path

import uvicorn

from .config import APP_DIR, get_config, get_or_create_token, setup_logging
from .indexer.runner import run_indexer
# Leveraging the context manager architecture built in step 1
from .indexer.watcher import file_watcher_scope
from .server import app  # Static import ensures PyInstaller traces & bundles this module directly

### Today is World cup  2026 Final.. What a Day to be a Barca Fan. I don't know who to Support...
def main() -> None:
    """
    Application entrypoint orchestrating initialization, synchronous baseline indexing,
    asynchronous file-system monitoring, and the core HTTP network layer.
    """
    # 1. Setup Structured Framework Logging
    logger = setup_logging()
    logger.info("Initializing Vina Engine Core Services")
    logger.info("Local App Configuration Repository Location: %s", APP_DIR)
    
    try:
        # 2. Extract and Validate Configuration Parameters
        config = get_config()
        
        # Defensive validation for configuration keys
        try:
            target_folder = str(config["target_folder"])
            host = str(config["host"])
            port = int(config["port"])
        except KeyError as err:
            logger.critical("Missing critical configuration parameter key: %s", err)
            sys.exit(1)
        except ValueError as err:
            logger.critical("Invalid datatype detected within configuration properties: %s", err)
            sys.exit(1)
            
        # Ensure security token initialization takes place early
        _ = get_or_create_token()
        
        # 3. Execute Synchronous Directory Baseline Sync
        # Catches changes that occurred while the app was shut down
        logger.info("Executing initial directory indexing baseline sync for: %s", target_folder)
        run_indexer(target_folder)
        
        # 4. Bind Live File Watcher and Hand Control to Uvicorn
        # The context manager controls the lifecycle of the background watchdog thread.
        # When uvicorn.run blocks, the watcher runs smoothly. When uvicorn exits,
        # the context manager guarantees the background threads are cleanly drained and closed.
        with file_watcher_scope(target_folder):
            logger.info("Starting REST API infrastructure server on http://%s:%d", host, port)
            
            uvicorn.run(
                app, 
                host=host, 
                port=port, 
                log_level="info",
                interface="asgi"
            )
            
    except SystemExit:
        # Pass-through for deliberate runtime termination exits
        pass
    except Exception:
        logger.exception("Fatal crash encountered during Vina Core engine startup runtime loop")
        sys.exit(1)


if __name__ == "__main__":
    main()