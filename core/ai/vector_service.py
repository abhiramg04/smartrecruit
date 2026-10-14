"""
Vector Search & Embeddings Infrastructure Service for SmartRecruit.

Provides:
- Embedding generation using SentenceTransformers ('all-MiniLM-L6-v2')
- Cosine similarity computation
- Batch similarity scoring for candidate resumes, job descriptions, and profiles
"""

import logging
from typing import List, Union, Dict, Any

logger = logging.getLogger(__name__)

_transformer_model = None


def get_embedding_model():
    """Lazy-load and cache the SentenceTransformer model singleton."""
    global _transformer_model
    if _transformer_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading SentenceTransformer model ('all-MiniLM-L6-v2')...")
            _transformer_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("SentenceTransformer model loaded successfully.")
        except ImportError:
            logger.error("sentence-transformers package is not installed.")
            raise RuntimeError("sentence-transformers package missing. Install via pip install sentence-transformers.")
    return _transformer_model


class VectorEmbeddingService:
    """Reusable Vector Embedding and Semantic Similarity Infrastructure."""

    @staticmethod
    def generate_embedding(text: str) -> List[float]:
        """
        Generates a 384-dimensional vector embedding for a given text.
        """
        if not text or not text.strip():
            return [0.0] * 384

        try:
            model = get_embedding_model()
            tensor = model.encode(text.strip(), convert_to_numpy=True)
            return tensor.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return [0.0] * 384

    @staticmethod
    def compute_similarity(text_a: str, text_b: str) -> float:
        """
        Computes cosine similarity between two text strings.
        Returns a float score in [0.0, 100.0].
        """
        if not text_a or not text_b or not text_a.strip() or not text_b.strip():
            return 0.0

        try:
            from sentence_transformers import util
            model = get_embedding_model()
            emb_a = model.encode(text_a, convert_to_tensor=True)
            emb_b = model.encode(text_b, convert_to_tensor=True)
            score = util.cos_sim(emb_a, emb_b).item()
            # Clamp to [0, 1] and scale to 100
            return round(max(0.0, min(score, 1.0)) * 100, 2)
        except Exception as e:
            logger.error(f"Cosine similarity computation failed: {e}")
            return 0.0

    @staticmethod
    def batch_rank_candidates(job_description: str, candidate_texts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Vector similarity ranking of multiple candidate texts against a single job description.
        Returns candidate list sorted by semantic match score descending.
        """
        if not job_description or not candidate_texts:
            return []

        ranked = []
        for cand in candidate_texts:
            text = cand.get('text', '')
            score = VectorEmbeddingService.compute_similarity(job_description, text)
            cand_copy = dict(cand)
            cand_copy['similarity_score'] = score
            ranked.append(cand_copy)

        return sorted(ranked, key=lambda x: x['similarity_score'], reverse=True)
