"""
Machine Learning & Deterministic Scoring Layer for SmartRecruit — Phase 07.

5-Dimension weighted candidate scoring (configurable via AIConfiguration):
  1. Skills Match:           default 40%  (hybrid keyword + vector)
  2. Experience Match:       default 20%  (vector semantic similarity)
  3. Education Match:        default 10%  (vector semantic similarity)
  4. Semantic Similarity:    default 20%  (full resume ↔ full JD similarity)
  5. AI Evaluation:          default 10%  (Groq 0-100 rating, normalized)

Verdict Thresholds:
  - SUITABLE : overall_score >= 70.0
  - MAYBE    : 45.0 <= overall_score < 70.0
  - REJECT   : overall_score < 45.0
"""

import logging
from typing import Dict, List, Any

from .vector_service import VectorEmbeddingService
from .nlp_service import NLPProcessingService

logger = logging.getLogger(__name__)

# ── Default fallback weights ──────────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    'skill':              0.40,
    'experience':         0.20,
    'education':          0.10,
    'semantic_similarity': 0.20,
    'ai_evaluation':      0.10,
}

VERDICT_THRESHOLDS = {
    'SUITABLE': 70.0,
    'MAYBE':    45.0,
}


def _get_weights() -> Dict[str, float]:
    """Load scoring weights from AIConfiguration; fall back to defaults."""
    try:
        from dashboard.models import AIConfiguration
        cfg = AIConfiguration.get_solo()
        weights = {
            'skill':               cfg.weight_skill_match,
            'experience':          cfg.weight_experience_match,
            'education':           cfg.weight_education_match,
            'semantic_similarity': cfg.weight_semantic_similarity,
            'ai_evaluation':       cfg.weight_ai_evaluation,
        }
        total = sum(weights.values())
        if abs(total - 1.0) > 0.05:
            logger.warning(
                f"AIConfiguration weights sum to {total:.2f} (expected ~1.0). "
                "Falling back to defaults."
            )
            return DEFAULT_WEIGHTS
        return weights
    except Exception as e:
        logger.warning(f"Could not load AIConfiguration weights: {e}. Using defaults.")
        return DEFAULT_WEIGHTS


class DeterministicScoringEngine:
    """Deterministic Multi-Dimensional Candidate Scoring Engine (Phase 07)."""

    # ── Verdict ───────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_verdict(overall_score: float) -> str:
        """Return SUITABLE / MAYBE / REJECT based on overall score."""
        if overall_score >= VERDICT_THRESHOLDS['SUITABLE']:
            return 'SUITABLE'
        elif overall_score >= VERDICT_THRESHOLDS['MAYBE']:
            return 'MAYBE'
        return 'REJECT'

    # ── Dimension scorers ─────────────────────────────────────────────────────

    @staticmethod
    def score_skills(
        job_skills: List[str],
        candidate_skills: List[str],
        job_description: str,
    ) -> Dict[str, Any]:
        """
        Hybrid skill score:
          60% exact keyword match ratio  +  40% vector semantic similarity.
        Returns skill_score (0-100), matched list, missing list.
        """
        if not job_skills and not job_description:
            return {'score': 0.0, 'matched': [], 'missing': []}

        job_set  = {s.lower().strip() for s in job_skills}
        cand_set = {s.lower().strip() for s in candidate_skills}

        matched = [s for s in candidate_skills if s.lower().strip() in job_set]
        missing = [s for s in job_skills     if s.lower().strip() not in cand_set]

        keyword_score = (len(matched) / len(job_set) * 100.0) if job_set else 0.0

        job_text  = ' '.join(job_skills) if job_skills else job_description[:600]
        cand_text = ' '.join(candidate_skills) if candidate_skills else ''
        semantic_score = VectorEmbeddingService.compute_similarity(job_text, cand_text)

        final_score = round(keyword_score * 0.6 + semantic_score * 0.4, 2)
        return {
            'score':          min(final_score, 100.0),
            'matched':        matched,
            'missing':        missing,
            'keyword_score':  keyword_score,
            'semantic_score': semantic_score,
        }

    # ── Full evaluation ───────────────────────────────────────────────────────

    @classmethod
    def evaluate_candidate(
        cls,
        job_title:       str,
        job_description: str,
        job_skills:      List[str],
        candidate_data:  Dict[str, Any],
        ai_evaluation_score: float = 0.0,   # 0-100 from Groq; 0 if unavailable
    ) -> Dict[str, Any]:
        """
        Evaluate a candidate across 5 dimensions and produce an overall score.

        Parameters
        ----------
        ai_evaluation_score : float
            A 0-100 score produced by Groq (normalized by this method to 0-100
            so it blends cleanly with the other dimensions). Pass 0.0 when Groq
            is unavailable; the remaining weights are preserved as-is.
        """
        weights = _get_weights()

        candidate_skills = candidate_data.get('skills', [])
        raw_text         = candidate_data.get('raw_text', '')
        exp_lines        = candidate_data.get('experience', [])
        edu_lines        = candidate_data.get('education', [])

        full_jd = f"{job_title}\n{job_description}"

        # ── 1. Skills ─────────────────────────────────────────────────────────
        skill_res   = cls.score_skills(job_skills, candidate_skills, full_jd)
        skill_score = skill_res['score']

        # ── 2. Experience (vector) ────────────────────────────────────────────
        exp_text        = '\n'.join(exp_lines) if isinstance(exp_lines, list) else str(exp_lines)
        experience_score = VectorEmbeddingService.compute_similarity(full_jd, exp_text)

        # ── 3. Education (vector) ─────────────────────────────────────────────
        edu_text       = '\n'.join(edu_lines) if isinstance(edu_lines, list) else str(edu_lines)
        education_score = VectorEmbeddingService.compute_similarity(full_jd, edu_text)

        # ── 4. Semantic Similarity (full resume ↔ full JD) ───────────────────
        resume_text       = raw_text or ' '.join(candidate_skills)
        semantic_score    = VectorEmbeddingService.compute_similarity(full_jd, resume_text)

        # ── 5. AI Evaluation (Groq, 0-100 already) ───────────────────────────
        ai_eval_norm = float(ai_evaluation_score)  # already 0-100

        # ── Weighted overall ──────────────────────────────────────────────────
        overall_score = round(
            skill_score           * weights['skill']               +
            experience_score      * weights['experience']          +
            education_score       * weights['education']           +
            semantic_score        * weights['semantic_similarity']  +
            ai_eval_norm          * weights['ai_evaluation'],
            2,
        )

        verdict = cls.calculate_verdict(overall_score)

        return {
            # Scores
            'skill_score':          skill_score,
            'experience_score':     experience_score,
            'education_score':      education_score,
            'semantic_score':       semantic_score,
            'ai_evaluation_score':  ai_eval_norm,
            'overall_score':        overall_score,
            # Verdict
            'verdict':              verdict,
            # Skill details
            'matched_skills':       skill_res['matched'],
            'missing_skills':       skill_res['missing'],
            # Config meta
            'weights':              weights,
            'thresholds':           VERDICT_THRESHOLDS,
        }
