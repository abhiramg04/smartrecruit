"""
Unified AI Manager Facade for SmartRecruit — Phase 07.

Connects:
  - GroqAIEngine         (LLM structured outputs & completions)
  - AISecurityManager    (prompt injection & secret redaction)
  - NLPProcessingService (text processing & NER)
  - VectorEmbeddingService (semantic embeddings & similarity)
  - DeterministicScoringEngine (5-dimension configurable weighted scoring)

Phase 07 key update:
  rank_candidate() now performs a two-layer evaluation:
    Layer 1  → DeterministicScoringEngine (skills, experience, education,
                semantic similarity — all computed locally without Groq)
    Layer 2  → Groq CandidateRankingEvalSchema (qualitative AI narrative
                score, strengths, missing skills, rationale)
  Final overall_score is computed by the deterministic engine using the
  Groq ai_evaluation_score as a weighted input.  Groq NEVER sets the final score.
"""

import logging
from typing import Dict, Any, List, Optional

from .service import GroqAIEngine
from .security import AISecurityManager
from .nlp_service import NLPProcessingService
from .vector_service import VectorEmbeddingService
from .scoring_engine import DeterministicScoringEngine

from .schemas import (
    ResumeScoreSchema, CandidateJobMatchSchema, SkillGapAnalysisSchema,
    InterviewQuestionSetSchema, InterviewSummarySchema, JobOptimizationSchema,
    CandidateRankingEvalSchema, InterviewIntelligenceSchema,
)
from .prompts import (
    RESUME_SCORING_PROMPT, CANDIDATE_JOB_MATCH_PROMPT, SKILL_GAP_ANALYSIS_PROMPT,
    INTERVIEW_QUESTION_GEN_PROMPT, INTERVIEW_SUMMARY_PROMPT, JOB_OPTIMIZATION_PROMPT,
    CANDIDATE_RANKING_EVAL_PROMPT, INTERVIEW_INTELLIGENCE_PROMPT,
)

logger = logging.getLogger(__name__)


class AIManager:
    """Centralized Facade providing AI/ML services to SmartRecruit applications."""

    def __init__(self):
        self.engine  = GroqAIEngine()
        self.security = AISecurityManager()
        self.nlp     = NLPProcessingService()
        self.vector  = VectorEmbeddingService()
        self.scoring = DeterministicScoringEngine()

    # ── Resume Screening (Part A) ─────────────────────────────────────────────

    def score_resume(self, job_description: str, resume_text: str) -> dict:
        """
        Structured AI resume screening score & feedback.
        Returns ResumeScoreSchema fields as a dict.
        """
        clean_jd     = self.security.sanitize_prompt_input(job_description)
        clean_resume = self.security.sanitize_prompt_input(resume_text)
        prompt  = RESUME_SCORING_PROMPT.format(job_description=clean_jd, resume_text=clean_resume)
        result  = self.engine.generate_structured_response(prompt, ResumeScoreSchema, model=self.engine.FAST_MODEL)
        return result.model_dump()

    # ── Candidate Ranking (Parts B–E) ────────────────────────────────────────

    def rank_candidate(
        self,
        job_title:       str,
        job_description: str,
        job_skills:      List[str],
        candidate_data:  Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Full Phase 07 two-layer candidate ranking pipeline.

        Layer 1 — Deterministic (no Groq):
          Computes skills / experience / education / semantic scores.

        Layer 2 — Groq narrative:
          Asks Groq for a qualitative 0-100 score, strengths, missing skills,
          and rationale.  This score feeds back into Layer 1 as the
          'ai_evaluation' dimension.

        Returns a dict ready for ApplicationAIScore.
        """
        raw_text        = candidate_data.get('raw_text', '')
        candidate_skills = candidate_data.get('skills', [])

        # ── Step 1: Groq AI narrative evaluation (Layer 2 input) ─────────────
        ai_eval_score  = 0.0
        ai_strengths   = []
        ai_missing     = []
        ai_rationale   = "Deterministic evaluation only (AI evaluation unavailable)."
        ai_concerns    = []

        try:
            clean_jd     = self.security.sanitize_prompt_input(job_description[:1200])
            clean_resume = self.security.sanitize_prompt_input(raw_text[:2000])
            clean_skills = ', '.join(candidate_skills[:30])
            req_skills   = ', '.join(job_skills[:30])

            prompt = CANDIDATE_RANKING_EVAL_PROMPT.format(
                job_title        = job_title,
                job_description  = clean_jd,
                required_skills  = req_skills,
                resume_text      = clean_resume,
                candidate_skills = clean_skills,
            )
            groq_eval     = self.engine.generate_structured_response(
                prompt, CandidateRankingEvalSchema, model=self.engine.FAST_MODEL
            )
            ai_eval_score = float(max(0, min(100, groq_eval.ai_score)))
            ai_strengths  = groq_eval.strengths
            ai_missing    = groq_eval.missing_skills
            ai_rationale  = groq_eval.rationale
            ai_concerns   = groq_eval.concerns
            logger.info(f"Groq evaluation completed: ai_score={ai_eval_score}")
        except Exception as e:
            logger.warning(f"Groq Layer 2 evaluation skipped (will use 0.0 for ai_eval weight): {e}")

        # ── Step 2: Deterministic scoring (Layer 1 + ai_eval feed-in) ────────
        eval_result = self.scoring.evaluate_candidate(
            job_title            = job_title,
            job_description      = job_description,
            job_skills           = job_skills,
            candidate_data       = candidate_data,
            ai_evaluation_score  = ai_eval_score,
        )

        # ── Step 3: Merge everything into one result dict ─────────────────────
        result = {
            # Dimension scores (0-100 scale each)
            'overall_score':       eval_result['overall_score'],
            'skill_score':         eval_result['skill_score'],
            'experience_score':    eval_result['experience_score'],
            'education_score':     eval_result['education_score'],
            'semantic_score':      eval_result['semantic_score'],
            'ai_evaluation_score': ai_eval_score,
            # Verdict & explanation
            'ai_recommendation':   eval_result['verdict'],
            'ai_strengths':        ai_strengths or eval_result.get('matched_skills', []),
            'ai_missing_skills':   ai_missing  or eval_result.get('missing_skills', []),
            'ai_rationale':        ai_rationale,
            'ai_concerns':         ai_concerns,
            # Matched/missing from deterministic pass
            'matched_skills':      eval_result['matched_skills'],
            'missing_skills':      eval_result['missing_skills'],
            # Config meta
            'weights':             eval_result['weights'],
        }
        return result

    # ── Generate resume embeddings & store on CandidateProfile ───────────────

    def generate_and_store_resume_embedding(self, profile) -> List[float]:
        """
        Generate a 384-dim embedding for the candidate's resume + skills and
        save it to profile.embedding_vector.  Returns the vector.
        """
        text_parts = []
        if profile.raw_text:
            text_parts.append(profile.raw_text[:3000])
        if profile.skills:
            text_parts.append(' '.join(profile.skills))
        text = ' '.join(text_parts).strip()
        if not text:
            return []
        vector = self.vector.generate_embedding(text)
        profile.embedding_vector = vector
        profile.save(update_fields=['embedding_vector'])
        logger.info(f"Stored {len(vector)}-dim embedding for profile {profile.pk}")
        return vector

    # ── Skill Gap Analysis ────────────────────────────────────────────────────

    def analyze_skill_gap(self, job_description: str, resume_text: str) -> dict:
        """Identifies missing skills and learning recommendations."""
        clean_jd     = self.security.sanitize_prompt_input(job_description)
        clean_resume = self.security.sanitize_prompt_input(resume_text)
        prompt  = SKILL_GAP_ANALYSIS_PROMPT.format(job_description=clean_jd, resume_text=clean_resume)
        result  = self.engine.generate_structured_response(prompt, SkillGapAnalysisSchema, model=self.engine.DEFAULT_MODEL)
        return result.model_dump()

    # ── Interview Services ────────────────────────────────────────────────────

    def generate_interview_questions(
        self,
        job_title: str,
        job_description: str,
        resume_text: str,
        required_skills: list = None,
        difficulty: str = 'MEDIUM',
        num_questions: int = 15,
        experience_level: str = 'MID',
        categories: list = None,
    ) -> dict:
        """Generates a structured, multi-category interview question bank via Groq."""
        if categories is None:
            categories = ['Technical', 'Behavioral', 'HR']
        if required_skills is None:
            required_skills = []

        clean_resume = self.security.sanitize_prompt_input(resume_text[:2000])
        clean_skills = ', '.join(required_skills[:20])
        category_str = ', '.join(categories)

        prompt = INTERVIEW_QUESTION_GEN_PROMPT.format(
            job_title        = job_title,
            experience_level = experience_level,
            difficulty       = difficulty,
            required_skills  = clean_skills,
            resume_text      = clean_resume,
            num_questions    = num_questions,
            categories       = category_str,
        )
        result = self.engine.generate_structured_response(
            prompt, InterviewQuestionSetSchema, model=self.engine.DEFAULT_MODEL
        )
        return result.model_dump()

    def summarize_interview(self, transcript: str) -> dict:
        """Analyzes raw interview transcript (legacy schema). Prefer analyze_interview_intelligence for new code."""
        clean_transcript = self.security.sanitize_prompt_input(transcript)
        prompt = INTERVIEW_SUMMARY_PROMPT.format(transcript=clean_transcript)
        result = self.engine.generate_structured_response(prompt, InterviewSummarySchema, model=self.engine.DEFAULT_MODEL)
        return result.model_dump()

    def analyze_interview_intelligence(
        self,
        transcript: str,
        job_title: str = '',
        job_description: str = '',
    ) -> dict:
        """
        Module 7: Full interview intelligence analysis using InterviewIntelligenceSchema.
        Separates the transcript-analysis LLM call from any STT step.
        Returns structured dict ready for InterviewSummary model.
        """
        clean_transcript = self.security.sanitize_prompt_input(transcript[:6000])
        job_context = f"Job: {job_title}\n{job_description[:400]}" if job_title else 'Not provided.'
        prompt = INTERVIEW_INTELLIGENCE_PROMPT.format(
            transcript  = clean_transcript,
            job_context = job_context,
        )
        result = self.engine.generate_structured_response(
            prompt, InterviewIntelligenceSchema, model=self.engine.DEFAULT_MODEL
        )
        return result.model_dump()

    # ── Job Description Optimization ──────────────────────────────────────────

    def optimize_job_description(self, draft_jd: str) -> dict:
        """Optimizes draft job description for engagement and skill keywords."""
        clean_jd = self.security.sanitize_prompt_input(draft_jd)
        prompt   = JOB_OPTIMIZATION_PROMPT.format(draft_jd=clean_jd)
        result   = self.engine.generate_structured_response(prompt, JobOptimizationSchema, model=self.engine.DEFAULT_MODEL)
        return result.model_dump()


# Centralized singleton instance
ai_manager = AIManager()
