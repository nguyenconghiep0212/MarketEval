import hashlib

def generate_content_hash(headline: str, raw_content: str) -> str:
    """
    Generates a unique SHA-256 hex digest for an article.
    Strips leading/trailing whitespace to prevent minor formatting differences
    from creating separate hashes.
    """
    # Ensure we are working with strings and handle potential None values
    safe_headline = str(headline or "").strip()
    safe_content = str(raw_content or "").strip()
    
    # Concatenate to form the raw payload
    raw_payload = f"{safe_headline}|{safe_content}"
    
    # Generate the SHA-256 hash
    return hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()