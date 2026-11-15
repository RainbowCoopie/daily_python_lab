from .cluster import dedupe, near_duplicates
from .fingerprint import hamming, minhash_signature, minhash_similarity, simhash, simhash_similarity
from .shingle import jaccard, normalize_text, shingles

__all__ = [
    "normalize_text",
    "shingles",
    "jaccard",
    "simhash",
    "hamming",
    "simhash_similarity",
    "minhash_signature",
    "minhash_similarity",
    "near_duplicates",
    "dedupe",
]
