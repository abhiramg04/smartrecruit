"""
Reusable NLP & Text Processing Service for SmartRecruit.

Provides text extraction, cleaning, section chunking, Named Entity Recognition (NER),
and keyphrase extraction across:
- Candidate Resumes
- Job Descriptions
- Candidate Profiles
- Interview Transcripts
- Technical Assessment Content
"""

import re
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Standard section header vocabularies
SECTION_HEADERS = {
    'skills': ['skills', 'technical skills', 'core competencies', 'technologies', 'tools', 'expertise', 'proficiencies'],
    'experience': ['experience', 'work experience', 'employment history', 'professional experience', 'career history'],
    'education': ['education', 'academic background', 'qualifications', 'educational background', 'academics'],
    'projects': ['projects', 'personal projects', 'key projects', 'portfolio', 'academic projects'],
    'certifications': ['certifications', 'certificates', 'licenses', 'professional certifications'],
    'languages': ['languages', 'spoken languages', 'language proficiency'],
}

TECH_KEYWORDS = [
    'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'c', 'ruby', 'php', 'swift', 'kotlin',
    'go', 'rust', 'scala', 'sql', 'html', 'css', 'react', 'angular', 'vue', 'node', 'django', 'flask',
    'fastapi', 'spring', 'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'git', 'linux', 'bash',
    'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy', 'mongodb', 'postgresql', 'mysql',
    'redis', 'elasticsearch', 'kafka', 'graphql', 'rest', 'api', 'ci/cd', 'jenkins', 'terraform',
    'machine learning', 'deep learning', 'nlp', 'computer vision', 'data science', 'agile', 'scrum'
]


class NLPProcessingService:
    """Reusable NLP and text pre-processing service."""

    _spacy_nlp = None

    @classmethod
    def get_spacy(cls):
        """Lazy-load spaCy model singleton."""
        if cls._spacy_nlp is None:
            try:
                import spacy
                try:
                    cls._spacy_nlp = spacy.load("en_core_web_sm")
                except OSError:
                    import subprocess, sys
                    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
                    cls._spacy_nlp = spacy.load("en_core_web_sm")
            except Exception as e:
                logger.warning(f"spaCy model loading failed: {e}")
                cls._spacy_nlp = None
        return cls._spacy_nlp

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize whitespace, remove unprintable chars."""
        if not text:
            return ""
        # Remove null bytes and non-printable control chars
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        # Normalize whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Extract technical skills and keywords from text using regex boundary matching."""
        if not text:
            return []
        text_lower = text.lower()
        found = []
        for kw in TECH_KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                found.append(kw.title() if len(kw) > 2 else kw.upper())
        return list(dict.fromkeys(found))

    @staticmethod
    def chunk_sections(text: str) -> Dict[str, str]:
        """
        Segment text into logical headers (Skills, Experience, Education, Projects, Certifications).
        """
        cleaned = NLPProcessingService.clean_text(text)
        lines = cleaned.split('\n')
        sections = {}
        current_section = 'general'
        current_lines = []

        for line in lines:
            stripped = line.strip().lower()
            matched_section = None

            for sec, keywords in SECTION_HEADERS.items():
                if any(stripped == kw or stripped.startswith(kw + ':') for kw in keywords):
                    matched_section = sec
                    break

            if matched_section:
                if current_lines:
                    sections[current_section] = '\n'.join(current_lines).strip()
                current_section = matched_section
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            sections[current_section] = '\n'.join(current_lines).strip()

        return sections

    @classmethod
    def extract_entities(cls, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities (PERSON, ORG, GPE, DATE) using spaCy NER.
        """
        cleaned = cls.clean_text(text)[:2000]
        nlp = cls.get_spacy()
        entities = {'persons': [], 'organizations': [], 'locations': []}

        if nlp and cleaned:
            doc = nlp(cleaned)
            for ent in doc.ents:
                if ent.label_ == "PERSON" and ent.text not in entities['persons']:
                    entities['persons'].append(ent.text)
                elif ent.label_ == "ORG" and ent.text not in entities['organizations']:
                    entities['organizations'].append(ent.text)
                elif ent.label_ in ("GPE", "LOC") and ent.text not in entities['locations']:
                    entities['locations'].append(ent.text)

        return entities
