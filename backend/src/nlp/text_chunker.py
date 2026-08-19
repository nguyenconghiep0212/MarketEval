# src/intelligence/text_chunker.py
from typing import List

def chunk_text(text: str, max_words: int = 250, overlap_words: int = 50) -> List[str]:
    """
    Splits long narrative/PDF text into overlapping chunks based on word boundaries.
    Default (~250 words) comfortably stays within PhoBERT's 512-token limit.
    """
    if not text or not text.strip():
        return []

    words = text.split()
    if len(words) <= max_words:
        return [text.strip()]

    chunks = []
    start = 0
    stride = max(1, max_words - overlap_words)

    while start < len(words):
        chunk_words = words[start : start + max_words]
        chunk_str = " ".join(chunk_words).strip()
        if chunk_str:
            chunks.append(chunk_str)
        start += stride

    return chunks