import os
import json
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def generate_questions_with_groq(topic: str, job_title: str = "", num_questions: int = 5, difficulty: str = "Medium") -> List[Dict[str, Any]]:
    """
    Generate structured technical assessment questions via Groq LLM API.
    """
    api_key = os.environ.get('GROQ_API_KEY') or ''
    if not api_key:
        try:
            from dashboard.models import AIConfiguration
            cfg = AIConfiguration.get_solo()
            if cfg and cfg.groq_api_key:
                api_key = cfg.groq_api_key
        except Exception:
            pass

    prompt = f"""You are a senior technical recruiter and assessment expert for SmartRecruit platform.
Generate {num_questions} high-quality assessment questions for:
Topic / Technical Domain: {topic}
Target Job Title: {job_title or 'Software Engineer'}
Difficulty Level: {difficulty}

Include a balanced mix of Multiple Choice Questions (MCQ), Technical Conceptual Questions, and Coding Challenges.

For each question, return a JSON object with:
- "question_type": "MCQ" | "TECHNICAL" | "APTITUDE" | "CODING"
- "text": "Clear and detailed question text"
- "marks": integer marks (e.g. 5, 10, 15)
- "options": array of 4 distinct choices for MCQ (for non-MCQ, set to empty array [])
- "correct_answer": For MCQ: string index "0", "1", "2", or "3". For TECHNICAL/CODING: brief correct answer / solution code.
- "code_snippet": starter template code string (for CODING questions, else empty string "")
- "expected_output": expected output or test case description (for CODING questions, else empty string "")

Return ONLY a valid JSON array of objects. Do not include markdown code fences or conversational text."""

    if api_key:
        models_to_try = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
        for m in models_to_try:
            try:
                from groq import Groq
                client = Groq(api_key=api_key)
                response = client.chat.completions.create(
                    model=m,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=2500,
                )
                raw = response.choices[0].message.content.strip()
                clean = re.sub(r'```(?:json)?', '', raw).strip().rstrip('`').strip()
                questions_data = json.loads(clean)
                if isinstance(questions_data, list) and len(questions_data) > 0:
                    logger.info(f"Groq API model {m} successfully generated {len(questions_data)} questions.")
                    return questions_data
            except Exception as e:
                logger.warning(f"Groq question generation failed with model {m}: {e}")
                continue

    logger.warning("Groq API fallback triggered: returning rule-based question set.")
    return [
        {
            "question_type": "MCQ",
            "text": f"Which of the following principles is key to maintaining clean code architecture in {topic or 'Software Engineering'}?",
            "options": [
                "Single Responsibility Principle (SRP) and modularity",
                "Hardcoding dynamic parameters directly into business logic",
                "Suppressing exceptions silently without logging",
                "Global state mutation across threads"
            ],
            "correct_answer": "0",
            "marks": 5,
            "code_snippet": "",
            "expected_output": ""
        },
        {
            "question_type": "MCQ",
            "text": "What is the primary advantage of utilizing database indexes on frequently queried columns?",
            "options": [
                "Increases disk storage efficiency",
                "Significantly reduces query search time from O(N) to O(log N)",
                "Removes foreign key constraints",
                "Disables write locks during transactions"
            ],
            "correct_answer": "1",
            "marks": 5,
            "code_snippet": "",
            "expected_output": ""
        },
        {
            "question_type": "TECHNICAL",
            "text": f"Describe the core workflow and error handling strategies for RESTful APIs or services building with {topic or 'modern tech stacks'}.",
            "options": [],
            "correct_answer": "Use HTTP status codes (2xx, 4xx, 5xx), return structured error JSON, implement rate limiting, and validate incoming payload schemas.",
            "marks": 10,
            "code_snippet": "",
            "expected_output": ""
        },
        {
            "question_type": "CODING",
            "text": "Write a Python function `find_duplicates(arr: list) -> list` that identifies and returns all duplicate numbers from an integer array.",
            "options": [],
            "correct_answer": "def find_duplicates(arr):\n    seen = set()\n    dupes = set()\n    for x in arr:\n        if x in seen:\n            dupes.add(x)\n        else:\n            seen.add(x)\n    return list(dupes)",
            "code_snippet": "def find_duplicates(arr: list) -> list:\n    # Write your solution here\n    pass",
            "expected_output": "find_duplicates([1, 2, 3, 2, 4, 1]) -> [1, 2]",
            "marks": 15
        }
    ]
