# src/vina/__main__.py
from .indexer.runner import run_indexer

def main():
    # For Phase 1 & 2, we run the indexer. 
    # Later, we'll use argparse here to switch between 'vina index' and 'vina serve'
    run_indexer()

if __name__ == "__main__":
    main()