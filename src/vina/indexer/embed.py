from fastembed import TextEmbedding
from ..config import MODELS_DIR

class Embedder:
    _instance = None

    @classmethod
    def get_instance(cls) -> TextEmbedding:
        if cls._instance is None:
            print(f"[Vina] Loading embedding model from {MODELS_DIR}...")
            cls._instance = TextEmbedding(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                cache_dir=str(MODELS_DIR)
            )
        return cls._instance

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generates embeddings for a list of text chunks."""
    if not texts:
        return []
    model = Embedder.get_instance()
    # list() is required because fastembed returns a generator
    return [list(map(float, vec)) for vec in model.embed(texts)]