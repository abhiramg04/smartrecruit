"""
Skill Gap Analyzer for SmartRecruit.

Pipeline:
  1. Compare candidate skills vs job skills (keyword + semantic)
  2. Classify: matched, missing, extra skills
  3. Call Groq LLaMA3 to generate:
     - Recommended courses per missing skill
     - Recommended certifications
     - Ordered learning path with time estimates
     - AI summary narrative
"""

import re
import json
import os
import logging

logger = logging.getLogger(__name__)

# ── Curated course database (fallback when Groq unavailable) ──────────────────
FALLBACK_COURSES = {
    'python':          {'course': 'Python for Everybody – Coursera', 'hours': 30},
    'django':          {'course': 'Django for Beginners – Real Python', 'hours': 20},
    'react':           {'course': 'The Complete React Developer – Udemy', 'hours': 40},
    'javascript':      {'course': 'JavaScript – The Complete Guide – Udemy', 'hours': 52},
    'sql':             {'course': 'SQL for Data Science – Coursera', 'hours': 15},
    'docker':          {'course': 'Docker & Kubernetes: The Practical Guide – Udemy', 'hours': 23},
    'aws':             {'course': 'AWS Certified Solutions Architect – A Cloud Guru', 'hours': 50},
    'machine learning':{'course': 'Machine Learning Specialization – Coursera (Andrew Ng)', 'hours': 60},
    'deep learning':   {'course': 'Deep Learning Specialization – Coursera', 'hours': 80},
    'tensorflow':      {'course': 'TensorFlow Developer Certificate – Google', 'hours': 40},
    'pytorch':         {'course': 'PyTorch for Deep Learning – Udemy', 'hours': 35},
    'data science':    {'course': 'IBM Data Science Professional Certificate – Coursera', 'hours': 70},
    'git':             {'course': 'Git & GitHub Crash Course – FreeCodeCamp', 'hours': 5},
    'kubernetes':      {'course': 'Kubernetes for the Absolute Beginners – KodeKloud', 'hours': 18},
    'typescript':      {'course': 'Understanding TypeScript – Udemy', 'hours': 22},
    'flutter':         {'course': 'Flutter & Dart – The Complete Guide – Udemy', 'hours': 45},
    'nlp':             {'course': 'NLP with Python – DataCamp', 'hours': 30},
    'agile':           {'course': 'Agile Fundamentals – LinkedIn Learning', 'hours': 8},
}

FALLBACK_CERTS = {
    'aws':             'AWS Certified Solutions Architect – Associate',
    'python':          'PCEP – Certified Entry-Level Python Programmer',
    'data science':    'IBM Data Science Professional Certificate',
    'machine learning':'Google Professional Machine Learning Engineer',
    'docker':          'Docker Certified Associate (DCA)',
    'kubernetes':      'Certified Kubernetes Administrator (CKA)',
    'agile':           'PMI Agile Certified Practitioner (PMI-ACP)',
    'sql':             'Oracle Database SQL Certified Associate',
    'javascript':      'OpenJS Node.js Application Developer',
}


# ── Skill Comparison Engine ────────────────────────────────────────────────────

def normalize(skills: list) -> set:
    return {s.lower().strip() for s in skills if s}


def compute_gap(candidate_skills: list, job_skills: list) -> dict:
    """
    Compare candidate and job skills.
    Returns matched, missing, extra skills and match percentage.
    """
    cand_set = normalize(candidate_skills)
    job_set  = normalize(job_skills)

    matched = sorted(cand_set & job_set)
    missing = sorted(job_set - cand_set)
    extra   = sorted(cand_set - job_set)

    match_pct = round((len(matched) / len(job_set) * 100), 2) if job_set else 0.0

    return {
        'matched': matched,
        'missing': missing,
        'extra':   extra,
        'match_percentage': match_pct,
    }


# ── Fallback Course/Cert Generator ────────────────────────────────────────────

def get_fallback_recommendations(missing_skills: list) -> dict:
    courses = []
    certs   = set()
    total_hours = 0

    for skill in missing_skills:
        key = skill.lower()
        if key in FALLBACK_COURSES:
            entry = FALLBACK_COURSES[key]
            courses.append({
                'skill': skill,
                'course': entry['course'],
                'hours': entry['hours'],
                'url': f"https://www.google.com/search?q={entry['course'].replace(' ', '+')}",
            })
            total_hours += entry['hours']
        if key in FALLBACK_CERTS:
            certs.add(FALLBACK_CERTS[key])

    # Build basic learning path from missing skills order
    learning_path = []
    for i, skill in enumerate(missing_skills[:8], 1):
        key = skill.lower()
        hrs = FALLBACK_COURSES.get(key, {}).get('hours', 10)
        learning_path.append({
            'step': i,
            'skill': skill,
            'action': f"Learn {skill}",
            'resource': FALLBACK_COURSES.get(key, {}).get('course', f'Search for {skill} courses on Udemy/Coursera'),
            'estimated_hours': hrs,
        })

    return {
        'courses': courses,
        'certs': list(certs),
        'learning_path': learning_path,
        'estimated_hours': total_hours,
        'ai_summary': None,
    }


# ── Groq AI Generator ──────────────────────────────────────────────────────────

def build_groq_skill_gap_prompt(job_title: str, matched: list, missing: list, extra: list, match_pct: float) -> str:
    return f"""You are an expert career coach and technical recruiter at SmartRecruit.

A candidate is analyzing their skill gap for the role: **{job_title}**

Current Match: {match_pct:.1f}%
Matched Skills: {', '.join(matched) if matched else 'None'}
Missing Skills: {', '.join(missing) if missing else 'None'}
Extra Skills (candidate has, job doesn't require): {', '.join(extra) if extra else 'None'}

Generate a comprehensive skill gap learning plan in this EXACT JSON format:
{{
  "ai_summary": "2-3 sentence personalized coaching summary for the candidate",
  "recommended_courses": [
    {{"skill": "SkillName", "course": "Course Title – Platform", "hours": 20, "url": "https://coursera.org or udemy.com"}},
    ...
  ],
  "recommended_certs": [
    "Certification Name 1",
    "Certification Name 2"
  ],
  "learning_path": [
    {{"step": 1, "skill": "SkillName", "action": "Learn X", "resource": "Course/resource name", "estimated_hours": 20}},
    {{"step": 2, "skill": "SkillName", "action": "Practice Y", "resource": "Project idea or resource", "estimated_hours": 10}},
    ...
  ],
  "estimated_hours": 120
}}

Rules:
- Include max 6 courses (most impactful missing skills first)
- Include max 3 certifications relevant to the role
- Learning path should have max 8 ordered steps
- estimated_hours is total of all learning_path steps
- Use real course names from Coursera, Udemy, Pluralsight, or freeCodeCamp
- Respond ONLY with valid JSON, no markdown, no extra text"""


def call_groq_for_gap(prompt: str) -> dict | None:
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        logger.warning("GROQ_API_KEY not set — using fallback course database.")
        return None
    for model_name in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]:
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=1000,
            )
            raw = response.choices[0].message.content.strip()
            clean = re.sub(r'```(?:json)?', '', raw).strip().rstrip('`').strip()
            return json.loads(clean)
        except Exception as e:
            logger.warning(f"Groq skill gap call failed with model {model_name}: {e}")
            continue
    return None


# ── Main Analyzer ──────────────────────────────────────────────────────────────

def analyze_gap(candidate_profile, job) -> dict:
    """
    Full skill gap analysis pipeline.
    Returns structured dict ready for SkillGapReport storage.
    """
    result = {
        'matched_skills': [],
        'missing_skills': [],
        'extra_skills': [],
        'match_percentage': 0.0,
        'recommended_courses': [],
        'recommended_certs': [],
        'learning_path': [],
        'estimated_hours': 0,
        'ai_summary': None,
        'error': None,
    }

    try:
        # Gather skills
        candidate_skills = candidate_profile.skills or []
        job_skills = [s.name for s in job.skills.all()] if job.skills.exists() else []

        # If job has no explicit skills, try extracting from description
        if not job_skills and job.description:
            from ranking.engine import extract_skills_from_text
            # Simple fallback: use tech skill vocab matching
            from candidates.parser import extract_skills as parse_skills
            job_skills = parse_skills(job.description)

        gap_data = compute_gap(candidate_skills, job_skills)
        result.update({
            'matched_skills': gap_data['matched'],
            'missing_skills': gap_data['missing'],
            'extra_skills': gap_data['extra'],
            'match_percentage': gap_data['match_percentage'],
        })

        if not gap_data['missing']:
            result['ai_summary'] = "Great news! Your skill set fully matches the requirements for this role."
            result['learning_path'] = []
            result['estimated_hours'] = 0
            return result

        # Try Groq first
        prompt = build_groq_skill_gap_prompt(
            job_title=job.title,
            matched=gap_data['matched'],
            missing=gap_data['missing'],
            extra=gap_data['extra'],
            match_pct=gap_data['match_percentage'],
        )
        groq_data = call_groq_for_gap(prompt)

        if groq_data:
            result['recommended_courses'] = groq_data.get('recommended_courses', [])
            result['recommended_certs']   = groq_data.get('recommended_certs', [])
            result['learning_path']       = groq_data.get('learning_path', [])
            result['estimated_hours']     = groq_data.get('estimated_hours', 0)
            result['ai_summary']          = groq_data.get('ai_summary', '')
        else:
            # Fallback to curated database
            fb = get_fallback_recommendations(gap_data['missing'])
            result['recommended_courses'] = fb['courses']
            result['recommended_certs']   = fb['certs']
            result['learning_path']       = fb['learning_path']
            result['estimated_hours']     = fb['estimated_hours']
            result['ai_summary']          = (
                f"You are {gap_data['match_percentage']:.1f}% ready for the {job.title} role. "
                f"Focus on acquiring {', '.join(gap_data['missing'][:3])} to significantly "
                f"boost your candidacy. The estimated time to bridge this gap is approximately "
                f"{fb['estimated_hours']} hours of focused learning."
            )

    except Exception as e:
        logger.error(f"Skill gap analysis failed: {e}", exc_info=True)
        result['error'] = str(e)

    return result
