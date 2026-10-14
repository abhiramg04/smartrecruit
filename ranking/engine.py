"""
AI Resume Ranking Engine for SmartRecruit.

Architecture:
  Layer 1 - Sentence Transformers: Fast semantic similarity scoring
             across 5 weighted dimensions.
  Layer 2 - Groq API (LLaMA3): Generates human-readable verdict,
             missing skills, and XAI narrative explanation.
"""

import re
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Weighted scoring dimensions ────────────────────────────────────────────────
WEIGHTS = {
    'skill':        0.40,
    'experience':   0.20,
    'education':    0.15,
    'project':      0.15,
    'certification': 0.10,
}

VERDICT_THRESHOLDS = {
    'SUITABLE': 70.0,
    'MAYBE':    45.0,
    # Below 45 → REJECT
}


# ── Sentence Transformer Loader (singleton) ────────────────────────────────────

from core.ai.vector_service import VectorEmbeddingService

def semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Compute cosine similarity between two texts using centralized VectorEmbeddingService.
    Returns a float in [0.0, 100.0].
    """
    return VectorEmbeddingService.compute_similarity(text_a, text_b)


# ── Individual Component Scorers ───────────────────────────────────────────────

def score_skills(job_skills: list, candidate_skills: list, job_description: str) -> dict:
    """
    Hybrid skill scoring:
      - Direct keyword intersection (exact match bonus)
      - Semantic similarity of skill strings
    """
    if not job_skills and not job_description:
        return {'score': 0.0, 'matched': [], 'missing': []}

    job_skill_set = {s.lower().strip() for s in job_skills}
    cand_skill_set = {s.lower().strip() for s in candidate_skills}

    # Exact matches
    matched = [s for s in candidate_skills if s.lower().strip() in job_skill_set]
    missing = [s for s in job_skills if s.lower().strip() not in cand_skill_set]

    # Keyword match ratio
    keyword_score = (len(matched) / len(job_skill_set) * 100) if job_skill_set else 0.0

    # Semantic similarity on joined skill lists
    job_text = ' '.join(job_skills) if job_skills else job_description[:500]
    cand_text = ' '.join(candidate_skills) if candidate_skills else ''
    semantic_score = semantic_similarity(job_text, cand_text)

    # Blend 60% keyword + 40% semantic
    final_score = round(keyword_score * 0.6 + semantic_score * 0.4, 2)
    return {'score': min(final_score, 100.0), 'matched': matched, 'missing': missing}


def score_experience(job_description: str, experience_lines: list) -> float:
    """Semantic similarity between job requirements and candidate experience."""
    experience_text = ' '.join(experience_lines)
    return semantic_similarity(job_description, experience_text)


def score_education(job_description: str, education_lines: list) -> float:
    """Semantic similarity between job posting and candidate education section."""
    education_text = ' '.join(education_lines)
    return semantic_similarity(job_description, education_text)


def score_projects(job_description: str, project_lines: list) -> float:
    """Semantic similarity between job description and candidate projects."""
    project_text = ' '.join(project_lines)
    return semantic_similarity(job_description, project_text)


def score_certifications(job_description: str, cert_lines: list) -> float:
    """Semantic similarity between job posting and candidate certifications."""
    cert_text = ' '.join(cert_lines)
    return semantic_similarity(job_description, cert_text)


# ── Groq API Integration ───────────────────────────────────────────────────────

def call_groq(prompt: str, model: str = "llama-3.3-70b-versatile") -> Optional[str]:
    """Call the Groq API and return the text response."""
    api_key = os.environ.get('GROQ_API_KEY') or ''
    if not api_key:
        try:
            from dashboard.models import AIConfiguration
            cfg = AIConfiguration.get_solo()
            if cfg and cfg.groq_api_key:
                api_key = cfg.groq_api_key
        except Exception:
            pass

    if not api_key:
        logger.warning("GROQ_API_KEY not set. Skipping Groq recommendation.")
        return None

    models_to_try = [model, "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    for m in models_to_try:
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=600,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Groq API call failed with model {m}: {e}")
            continue

    return None


def build_groq_prompt(job_title: str, job_description: str, scores: dict,
                      matched_skills: list, missing_skills: list,
                      candidate_name: str) -> str:
    return f"""You are an expert AI recruitment assistant for SmartRecruit.

Candidate: {candidate_name}
Job Title: {job_title}

Scoring Results:
- Skill Match:         {scores['skill']:.1f}%
- Experience Match:    {scores['experience']:.1f}%
- Education Match:     {scores['education']:.1f}%
- Project Match:       {scores['project']:.1f}%
- Certification Match: {scores['certification']:.1f}%
- Overall Score:       {scores['overall']:.1f}%

Matched Skills: {', '.join(matched_skills) if matched_skills else 'None identified'}
Missing Skills: {', '.join(missing_skills) if missing_skills else 'None'}

Job Description (first 500 chars):
{job_description[:500]}

Based on this data, provide a professional recruitment recommendation in this exact JSON format:
{{
  "verdict": "SUITABLE" | "MAYBE" | "REJECT",
  "summary": "2-3 sentence professional summary of the candidate's fit",
  "strengths": ["strength 1", "strength 2", "strength 3"],
  "concerns": ["concern 1", "concern 2"],
  "recommendation": "One clear actionable recommendation for the recruiter"
}}

Respond ONLY with valid JSON, no markdown, no extra text."""


def parse_groq_response(response_text: str) -> dict:
    """Parse and validate the Groq JSON response."""
    try:
        # Strip any markdown code fences if present
        clean = re.sub(r'```(?:json)?', '', response_text).strip().rstrip('`').strip()
        data = json.loads(clean)
        return {
            'verdict': data.get('verdict', 'MAYBE'),
            'summary': data.get('summary', ''),
            'strengths': data.get('strengths', []),
            'concerns': data.get('concerns', []),
            'recommendation': data.get('recommendation', ''),
        }
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to parse Groq response: {e}\nRaw: {response_text}")
        return {
            'verdict': 'MAYBE',
            'summary': response_text[:300] if response_text else 'Analysis unavailable.',
            'strengths': [],
            'concerns': [],
            'recommendation': 'Manual review recommended.',
        }


def determine_verdict(overall_score: float) -> str:
    """Determine verdict from numeric overall score."""
    if overall_score >= VERDICT_THRESHOLDS['SUITABLE']:
        return 'SUITABLE'
    elif overall_score >= VERDICT_THRESHOLDS['MAYBE']:
        return 'MAYBE'
    return 'REJECT'


# ── Main Ranking Orchestrator ──────────────────────────────────────────────────

def rank_resume(job, candidate_profile) -> dict:
    """
    Full AI ranking pipeline.

    Args:
        job: jobs.Job model instance
        candidate_profile: candidates.CandidateProfile model instance

    Returns:
        dict with all scores, verdict, missing skills, and AI recommendation
    """
    result = {
        'skill_score': 0.0,
        'experience_score': 0.0,
        'education_score': 0.0,
        'project_score': 0.0,
        'cert_score': 0.0,
        'overall_score': 0.0,
        'verdict': 'REJECT',
        'matched_skills': [],
        'missing_skills': [],
        'ai_recommendation': None,
        'explainability': {},
        'error': None,
    }

    try:
        # Gather inputs
        job_description = f"{job.title}\n{job.description}"
        job_skills = [s.name for s in job.skills.all()] if job.skills.exists() else []
        candidate_skills = candidate_profile.skills or []
        candidate_name = candidate_profile.full_name or candidate_profile.user.get_full_name() or 'Candidate'

        # ── Layer 1: Score all dimensions ────────────────────────────────────
        skill_data = score_skills(job_skills, candidate_skills, job_description)
        skill_score = skill_data['score']
        matched_skills = skill_data['matched']
        missing_skills = skill_data['missing']

        experience_score = score_experience(job_description, candidate_profile.experience or [])
        education_score  = score_education(job_description, candidate_profile.education or [])
        project_score    = score_projects(job_description, candidate_profile.projects or [])
        cert_score       = score_certifications(job_description, candidate_profile.certifications or [])

        # ── Weighted Overall Score ────────────────────────────────────────────
        overall_score = round(
            skill_score       * WEIGHTS['skill'] +
            experience_score  * WEIGHTS['experience'] +
            education_score   * WEIGHTS['education'] +
            project_score     * WEIGHTS['project'] +
            cert_score        * WEIGHTS['certification'],
            2
        )

        scores = {
            'skill': skill_score,
            'experience': experience_score,
            'education': education_score,
            'project': project_score,
            'certification': cert_score,
            'overall': overall_score,
        }

        # ── Fallback verdict from score thresholds ────────────────────────────
        verdict = determine_verdict(overall_score)

        # ── Layer 2: Groq AI Recommendation ──────────────────────────────────
        groq_data = {}
        groq_prompt = build_groq_prompt(
            job_title=job.title,
            job_description=job_description,
            scores=scores,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            candidate_name=candidate_name,
        )
        groq_response_text = call_groq(groq_prompt)

        if groq_response_text:
            groq_data = parse_groq_response(groq_response_text)
            if groq_data.get('verdict') in ('SUITABLE', 'MAYBE', 'REJECT'):
                verdict = groq_data['verdict']

        # Rule-based fallback for strengths/concerns if AI call yielded none
        if not groq_data.get('strengths'):
            fallback_strengths = []
            if matched_skills:
                fallback_strengths.append(f"Matched key required skills: {', '.join(matched_skills[:4])}.")
            if skill_score >= 70:
                fallback_strengths.append(f"Strong technical skill alignment ({skill_score:.1f}% match).")
            if experience_score >= 60:
                fallback_strengths.append(f"Relevant background and experience ({experience_score:.1f}% match).")
            if education_score >= 60:
                fallback_strengths.append("Education matches required qualifications.")
            if project_score >= 60:
                fallback_strengths.append("Project background aligns with domain needs.")
            if not fallback_strengths:
                fallback_strengths.append(f"Achieved overall match score of {overall_score:.1f}%.")
            groq_data['strengths'] = fallback_strengths

        if not groq_data.get('concerns'):
            fallback_concerns = []
            if missing_skills:
                fallback_concerns.append(f"Missing required skills: {', '.join(missing_skills[:4])}.")
            if experience_score < 50:
                fallback_concerns.append("Experience alignment is below target threshold.")
            groq_data['concerns'] = fallback_concerns

        if not groq_data.get('summary'):
            groq_data['summary'] = f"Candidate achieved {overall_score:.1f}% overall match with {skill_score:.1f}% skill alignment."

        if not groq_data.get('recommendation'):
            if verdict == 'SUITABLE':
                groq_data['recommendation'] = "Strong candidate: Proceed to technical interview."
            elif verdict == 'MAYBE':
                groq_data['recommendation'] = "Potential fit: Further screening recommended."
            else:
                groq_data['recommendation'] = "Candidate does not meet core requirements."

        # ── Build explainability dict ─────────────────────────────────────────
        explainability = {
            'weights': WEIGHTS,
            'component_scores': scores,
            'thresholds': VERDICT_THRESHOLDS,
            'groq_strengths': groq_data.get('strengths', []),
            'groq_concerns': groq_data.get('concerns', []),
            'groq_summary': groq_data.get('summary', ''),
            'groq_recommendation': groq_data.get('recommendation', ''),
        }

        result.update({
            'skill_score': skill_score,
            'experience_score': experience_score,
            'education_score': education_score,
            'project_score': project_score,
            'cert_score': cert_score,
            'overall_score': overall_score,
            'verdict': verdict,
            'matched_skills': matched_skills,
            'missing_skills': missing_skills,
            'ai_recommendation': groq_data.get('summary', ''),
            'explainability': explainability,
        })

    except Exception as e:
        logger.error(f"Ranking engine failed: {e}", exc_info=True)
        result['error'] = str(e)

    return result
