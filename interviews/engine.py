"""
Interview Engine — Phase 08.

Provides:
  generate_interview_questions()   — parameterized Groq generation → InterviewQuestion rows
  transcribe_audio_with_groq()     — Groq Whisper STT (separate from LLM analysis)
  generate_interview_intelligence() — Full interview intelligence pipeline
"""

import os
import logging
from typing import Optional

from core.ai.manager import ai_manager

logger = logging.getLogger(__name__)

# ── Module 5: Interview Question Generator ────────────────────────────────────

CATEGORY_CODE_TO_DISPLAY = {
    'TECHNICAL':  'Technical',
    'RESUME':     'Resume-Based',
    'SCENARIO':   'Scenario',
    'PROBLEM':    'Problem-Solving',
    'BEHAVIORAL': 'Behavioral',
    'HR':         'HR',
}

DISPLAY_TO_CODE = {v: k for k, v in CATEGORY_CODE_TO_DISPLAY.items()}


def generate_interview_questions(
    application,
    difficulty: str = 'MEDIUM',
    num_questions: int = 15,
    experience_level: str = 'MID',
    selected_categories: list = None,
):
    """
    Generate a structured interview question bank for an application.
    Saves individual InterviewQuestion rows into the InterviewQuestionSet.

    Returns the InterviewQuestionSet instance on success, None on failure.
    """
    from .models import InterviewQuestionSet, InterviewQuestion

    if selected_categories is None:
        selected_categories = ['TECHNICAL', 'BEHAVIORAL', 'HR']

    candidate_profile = application.candidate
    job               = application.job

    skills    = candidate_profile.skills or []
    exp_lines = candidate_profile.experience_structured or []
    raw_text  = candidate_profile.raw_text or ''
    resume_text = (raw_text or ' '.join(skills))[:2000]

    job_skills    = [s.name for s in job.skills.all()] if job.skills.exists() else []
    category_labels = [CATEGORY_CODE_TO_DISPLAY.get(c, c) for c in selected_categories]

    try:
        data = ai_manager.generate_interview_questions(
            job_title        = job.title,
            job_description  = job.description or '',
            resume_text      = resume_text,
            required_skills  = job_skills,
            difficulty       = difficulty,
            num_questions    = num_questions,
            experience_level = experience_level,
            categories       = category_labels,
        )

        # Persist config + legacy JSON
        q_set, _ = InterviewQuestionSet.objects.update_or_create(
            application=application,
            defaults={
                'difficulty':            difficulty,
                'num_questions':         num_questions,
                'experience_level':      experience_level,
                'selected_categories':   ','.join(selected_categories),
                'questions_data':        data,
            }
        )

        # Persist individual InterviewQuestion rows
        InterviewQuestion.objects.filter(question_set=q_set).delete()
        order = 0
        for category in data.get('categories', []):
            cat_name    = category.get('name', 'Technical')
            cat_code    = DISPLAY_TO_CODE.get(cat_name, 'TECHNICAL')
            for q in category.get('questions', []):
                diff_raw = q.get('difficulty', 'Medium').upper()
                diff     = diff_raw if diff_raw in ('EASY', 'MEDIUM', 'HARD') else 'MEDIUM'
                InterviewQuestion.objects.create(
                    question_set  = q_set,
                    category      = cat_code,
                    difficulty    = diff,
                    question_text = q.get('question', ''),
                    model_answer  = q.get('model_answer', ''),
                    order         = order,
                )
                order += 1

        logger.info(f"Generated {order} questions for application {application.pk}")
        return q_set

    except Exception as e:
        logger.error(f"Failed to generate interview questions: {e}", exc_info=True)
        return None


# ── Module 7: Interview Intelligence ─────────────────────────────────────────

def transcribe_audio_with_groq(audio_file_path: str) -> Optional[str]:
    """
    Transcribe an audio/video file using Groq Whisper.
    Returns the transcript string, or None on failure.
    Kept SEPARATE from the LLM analysis step.
    """
    import os
    try:
        from groq import Groq
        client = Groq(api_key=os.environ.get('GROQ_API_KEY', ''))

        with open(audio_file_path, 'rb') as audio_file:
            transcription = client.audio.transcriptions.create(
                file   = audio_file,
                model  = 'whisper-large-v3',
                response_format = 'text',
            )
        transcript = transcription if isinstance(transcription, str) else getattr(transcription, 'text', str(transcription))
        logger.info(f"Groq STT transcription complete: {len(transcript)} chars from {audio_file_path}")
        return transcript

    except Exception as e:
        logger.error(f"Groq STT transcription failed: {e}", exc_info=True)
        return None


def generate_interview_intelligence(application, transcript: str, source: str = 'MANUAL') -> Optional[object]:
    """
    Run the Module 7 interview intelligence pipeline:
      transcript → AIManager.analyze_interview_intelligence → InterviewSummary

    Args:
        application:  Application object
        transcript:   Raw transcript text
        source:       'MANUAL' or 'AUDIO_STT'

    Returns:
        InterviewSummary instance, or None on failure.
    """
    from .models import InterviewSummary

    if not transcript.strip():
        logger.warning("Empty transcript; skipping intelligence analysis.")
        return None

    try:
        job = application.job
        result = ai_manager.analyze_interview_intelligence(
            transcript      = transcript,
            job_title       = job.title,
            job_description = (job.description or '')[:600],
        )

        # Map problem_solving_score (new) — may be missing in legacy InterviewSummarySchema results
        problem_solving_score = result.get('problem_solving_score', 0)

        summary_obj, _ = InterviewSummary.objects.update_or_create(
            application=application,
            defaults={
                'transcript':            transcript,
                'transcript_source':     source,
                'summary':               result.get('summary', ''),
                'strengths':             result.get('strengths', []),
                'weaknesses':            result.get('weaknesses', []),
                'relevant_answers':      result.get('relevant_answers', []),
                'areas_of_concern':      result.get('areas_of_concern', []),
                'overall_evaluation':    result.get('overall_evaluation', ''),
                'communication_score':   result.get('communication_score', 0),
                'technical_score':       result.get('technical_score', 0),
                'confidence_score':      result.get('confidence_score', 0),
                'problem_solving_score': problem_solving_score,
                'hiring_recommendation': result.get('hiring_recommendation', ''),
                'next_round_suggestion': result.get('next_round_suggestion', ''),
            }
        )
        logger.info(f"InterviewSummary saved for application {application.pk}")
        return summary_obj

    except Exception as e:
        logger.error(f"Interview intelligence failed for application {application.pk}: {e}", exc_info=True)
        return None
