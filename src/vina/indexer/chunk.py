def chunk_text(text: str, max_words: int = 400, overlap: int = 50) -> list[str]:
    """Splits text into overlapping chunks by word count."""
    words = text.split()
    if not words:
        return []
        
    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i : i + max_words]
        chunks.append(" ".join(chunk_words))
        i += (max_words - overlap)
        
    return chunks