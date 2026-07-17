from __future__ import annotations

import logging
import re
from collections import deque
from typing import Iterator

logger = logging.getLogger("vina.chunker")

# High-efficiency compiled regex pattern capturing non-whitespace word sequences
_WORD_REGEX = re.compile(r"\S+")


def chunk_text(text: str, max_words: int = 400, overlap: int = 50) -> Iterator[str]:
    """
    Streams overlapping text chunks based on word boundaries using a lazy generator.
    
    Maintains a true fixed-size sliding memory window using a double-ended queue,
    ensuring O(max_words) auxiliary memory overhead regardless of total document size.
    """
    # 1. Fail-Fast Configuration Guardrails
    if max_words <= 0:
        raise ValueError(f"max_words must be greater than 0, got {max_words}")
    if overlap < 0:
        raise ValueError(f"overlap cannot be negative, got {overlap}")
    if overlap >= max_words:
        raise ValueError(f"overlap ({overlap}) must be strictly less than max_words ({max_words})")

    step_size = max_words - overlap
    window: deque[re.Match[str]] = deque()
    yielded_at_least_once = False

    # 2. True Streaming Sliding Window Engine
    for match in _WORD_REGEX.finditer(text):
        window.append(match)
        
        if len(window) == max_words:
            # Extract slice directly out of original string using match positions
            # This preserves native formatting layout like newlines (\n\n)
            yield text[window[0].start() : window[-1].end()]
            yielded_at_least_once = True
            
            # Slide the window forward by dropping the oldest unneeded step matches
            for _ in range(step_size):
                window.popleft()

    # 3. Handle the remaining tail elements cleanly
    # Only yield a trailing chunk if new words were added after the last popleft,
    # or if the document was too short to ever trigger a full window max_words yield.
    if (yielded_at_least_once and len(window) > overlap) or (not yielded_at_least_once and window):
        yield text[window[0].start() : window[-1].end()]