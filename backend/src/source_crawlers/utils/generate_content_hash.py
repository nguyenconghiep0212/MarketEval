import hashlib

def generate_content_hash(headline: str, body: str) -> str:
    """Generates a SHA-256 fingerprint for article deduplication."""
    combined = f"{headline.strip().lower()}{body.strip().lower()}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()