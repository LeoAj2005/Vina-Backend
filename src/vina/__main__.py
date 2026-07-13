from .indexer.runner import run_indexer
from .search.retrieve import search_files

def main():
    run_indexer()

    print("\n" + "="*50)
    print("[Vina] Phase 2: Search Engine Test")
    print("="*50)

    test_query = "algorithms"

    results = search_files(test_query, limit=3)

    if not results:
        print("No results found.")
        return

    for i, res in enumerate(results, 1):
        print(f"{i}. {res['filepath']}")
        print(f"Distance: {res['score']:.4f}")
        print(f"Excerpt: {res['text'][:150]}...")
        print()