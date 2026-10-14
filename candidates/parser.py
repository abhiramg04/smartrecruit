"""
Resume Parsing Engine for SmartRecruit.

Extraction Stack:
  - PyMuPDF (fitz) for PDF text extraction
  - python-docx for Word document extraction
  - spaCy for Named Entity Recognition (NER)
  - Regex for reliable Email, Phone, URL extraction
  - Keyword-based flexible section chunking for structured sections
"""

import re
import os
import logging

logger = logging.getLogger(__name__)


# ─── Keyword Definitions ─────────────────────────────────────────────────────

SECTION_HEADERS = {
    'summary': [
        'summary', 'professional summary', 'executive summary', 'profile', 'about me', 'career objective', 'objective', 'overview',
    ],
    'skills': [
        'skills', 'technical skills', 'core competencies', 'technologies',
        'tools', 'expertise', 'proficiencies', 'technical expertise', 'skills & expertise', 'technical proficiencies',
    ],
    'experience': [
        'experience', 'work experience', 'employment history',
        'professional experience', 'career history', 'work history', 'employment',
    ],
    'education': [
        'education', 'academic background', 'academic qualifications',
        'qualifications', 'educational background', 'academics', 'education & qualifications',
    ],
    'projects': [
        'projects', 'personal projects', 'key projects',
        'portfolio', 'academic projects', 'side projects', 'projects & portfolio',
    ],
    'certifications': [
        'certifications', 'certificates', 'licenses',
        'professional certifications', 'courses', 'certifications & licenses',
    ],
    'languages': [
        'languages', 'language proficiency', 'spoken languages',
    ],
}

COMMON_LANGUAGES = [
    'english', 'hindi', 'spanish', 'french', 'german', 'mandarin', 'chinese',
    'arabic', 'portuguese', 'japanese', 'russian', 'italian', 'korean',
    'dutch', 'turkish', 'telugu', 'tamil', 'kannada', 'bengali', 'marathi',
    'gujarati', 'urdu', 'punjabi', 'malayalam',
]

TECH_SKILLS = [
    'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'c', 'ruby',
    'php', 'swift', 'kotlin', 'go', 'rust', 'scala', 'r', 'matlab', 'sql',
    'html', 'css', 'react', 'angular', 'vue', 'node', 'django', 'flask',
    'fastapi', 'spring', 'laravel', 'rails', 'express', 'next.js', 'nuxt',
    'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'git', 'linux', 'bash',
    'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy', 'opencv',
    'mongodb', 'postgresql', 'mysql', 'redis', 'elasticsearch', 'kafka',
    'graphql', 'rest', 'api', 'ci/cd', 'jenkins', 'github actions', 'terraform',
    'ansible', 'machine learning', 'deep learning', 'nlp', 'computer vision',
    'data science', 'big data', 'hadoop', 'spark', 'tableau', 'power bi',
    'excel', 'figma', 'photoshop', 'illustrator', 'xd', 'unity', 'unreal',
    'blockchain', 'solidity', 'web3', 'cybersecurity', 'penetration testing',
    'agile', 'scrum', 'jira', 'confluence',
]


# ─── Text Extraction ──────────────────────────────────────────────────────────

def extract_text_from_pdf(file_path: str) -> str:
    """Extract raw text from a PDF file using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text("text") + "\n"
        return text.strip()
    except ImportError:
        raise RuntimeError("PyMuPDF (fitz) is not installed. Run: pip install PyMuPDF")
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise ValueError(f"Could not extract text from PDF: {e}")


def extract_text_from_docx(file_path: str) -> str:
    """Extract raw text from a DOCX file using python-docx."""
    try:
        # pyrefly: ignore [missing-import]
        from docx import Document
        doc = Document(file_path)
        paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        return "\n".join(paragraphs)
    except ImportError:
        raise RuntimeError("python-docx is not installed. Run: pip install python-docx")
    except Exception as e:
        logger.error(f"DOCX extraction failed: {e}")
        raise ValueError(f"Could not extract text from DOCX: {e}")


def extract_text(file_path: str, extension: str) -> str:
    """Route to the appropriate text extractor based on file extension."""
    ext = extension.lower().lstrip('.')
    if ext == 'pdf':
        return extract_text_from_pdf(file_path)
    elif ext in ('docx', 'doc'):
        return extract_text_from_docx(file_path)
    elif ext in ('txt', 'md'):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read().strip()
    else:
        raise ValueError(f"Unsupported file format: .{ext}. Allowed: PDF, DOCX, TXT.")


# ─── NLP Helpers ─────────────────────────────────────────────────────────────

def load_spacy():
    """Load and cache the spaCy NLP model."""
    try:
        # pyrefly: ignore [missing-import]
        import spacy
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
            nlp = spacy.load("en_core_web_sm")
        return nlp
    except ImportError:
        return None


# ─── Individual Extractors ────────────────────────────────────────────────────

def extract_email(text: str) -> str | None:
    pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    match = re.search(pattern, text)
    return match.group(0) if match else None


def extract_phone(text: str) -> str | None:
    pattern = r'(?:(?:\+?91)?[\-\s]?)?(?:\(?\d{3,5}\)?[\-\s]?)?\d{3,5}[\-\s]?\d{4,7}'
    match = re.search(pattern, text)
    return match.group(0).strip() if match else None


def extract_linkedin(text: str) -> str | None:
    match = re.search(r'linkedin\.com/in/[a-zA-Z0-9\-_%]+', text, re.IGNORECASE)
    return f"https://{match.group(0)}" if match else None


def extract_github(text: str) -> str | None:
    match = re.search(r'github\.com/[a-zA-Z0-9\-_%]+', text, re.IGNORECASE)
    return f"https://{match.group(0)}" if match else None


def extract_name(text: str, nlp=None) -> str | None:
    """Use spaCy NER or clean line fallback to find the candidate's name."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    cleaned_lines = []
    for line in lines[:8]:
        clean_l = re.sub(r'^[#*\-\s]+', '', line).strip()
        clean_l = re.sub(r'[*_~`]', '', clean_l).strip()
        if clean_l:
            cleaned_lines.append(clean_l)

    clean_text = '\n'.join(cleaned_lines)

    if nlp:
        try:
            doc = nlp(clean_text[:500])
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    name = ent.text.strip()
                    clean_name = re.sub(r'^[#*\-\s]+', '', name).strip()
                    if len(clean_name.split()) >= 1 and len(clean_name) < 50 and not re.search(r'[@|:/]', clean_name):
                        return clean_name
        except Exception as e:
            logger.warning(f"spaCy name extraction failed: {e}")

    for line in cleaned_lines:
        if re.search(r'[@|]|http|github|linkedin|phone|email|resume|cv|summary|skills|experience|education', line, re.I):
            continue
        if len(line.split()) >= 1 and len(line) < 50:
            return line
    return None


def extract_skills(text: str, skills_section_text: str = '') -> list:
    """Extract skills combining keyword matching and explicit skills section parsing."""
    found_skills = []
    text_lower = text.lower()

    # Keyword matching against TECH_SKILLS vocabulary
    for skill in TECH_SKILLS:
        if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
            found_skills.append(skill.title() if len(skill) > 2 else skill.upper())

    # Extract explicitly listed skills from section text if available
    if skills_section_text:
        for line in skills_section_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            line = re.sub(r'^[#*\-•\+\d\.\s]+', '', line).strip()
            if ':' in line:
                parts = line.split(':', 1)[1]
            else:
                parts = line

            items = re.split(r'[,;|\/]', parts)
            for item in items:
                cleaned = item.strip().strip('*_`')
                if cleaned and len(cleaned) < 40 and not cleaned.lower().startswith('http'):
                    found_skills.append(cleaned.title() if len(cleaned) > 2 else cleaned.upper())

    return list(dict.fromkeys(found_skills))


def extract_languages(text: str) -> list:
    """Detect natural languages mentioned in the resume."""
    text_lower = text.lower()
    return [lang.capitalize() for lang in COMMON_LANGUAGES if re.search(r'\b' + lang + r'\b', text_lower)]


# ─── Section Chunker ─────────────────────────────────────────────────────────

def chunk_sections(text: str) -> dict:
    """
    Divide full resume text into named sections using flexible header matching.
    Handles Markdown hashes (##), bullets, numbers, colons, upper/lower case.
    """
    lines = text.split('\n')
    sections = {}
    current_section = None
    current_lines = []

    for line in lines:
        raw_l = line.strip()
        if not raw_l:
            if current_section and current_lines:
                current_lines.append('')
            continue

        clean_header = re.sub(r'^[#*\-=_:\d\.\s]+', '', raw_l).strip().lower()
        clean_header = re.sub(r'[\s:]+$', '', clean_header).strip()

        matched_section = None
        if clean_header and len(clean_header) < 60:
            for section, keywords in SECTION_HEADERS.items():
                if any(clean_header == kw or clean_header.startswith(kw + ':') or clean_header == (kw + 's') for kw in keywords):
                    matched_section = section
                    break

        if matched_section:
            if current_section and current_lines:
                sections[current_section] = '\n'.join(current_lines).strip()
            current_section = matched_section
            current_lines = []
        elif current_section:
            current_lines.append(line)

    if current_section and current_lines:
        sections[current_section] = '\n'.join(current_lines).strip()

    return sections


def parse_section_to_list(section_text: str) -> list:
    """Convert section block into clean readable lines, stripping markdown noise."""
    if not section_text:
        return []
    lines = []
    for line in section_text.split('\n'):
        l = line.strip()
        if not l:
            continue
        if l.startswith('#'):
            continue
        clean_l = re.sub(r'^\s*[\-\*\•\+]\s*', '', l)
        clean_l = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_l)
        clean_l = re.sub(r'\*(.*?)\*', r'\1', clean_l)
        clean_l = clean_l.strip()
        if clean_l:
            lines.append(clean_l)
    return lines


# ─── Main Parser ─────────────────────────────────────────────────────────────

def parse_resume(file_path: str, extension: str) -> dict:
    """
    Full pipeline: extract text → chunk sections → run extractors.
    Returns a structured dict with all parsed fields.
    """
    result = {
        'full_name': None,
        'email': None,
        'phone': None,
        'summary': None,
        'linkedin_url': None,
        'github_url': None,
        'skills': [],
        'education': [],
        'experience': [],
        'projects': [],
        'certifications': [],
        'languages': [],
        'raw_text': '',
        'error': None,
    }

    try:
        # Step 1: Extract raw text
        raw_text = extract_text(file_path, extension)
        result['raw_text'] = raw_text

        if not raw_text.strip():
            result['error'] = "Could not extract any text from the uploaded file."
            return result

        # Step 2: Load spaCy model
        nlp = load_spacy()

        # Step 3: Extract atomic fields
        result['email'] = extract_email(raw_text)
        result['phone'] = extract_phone(raw_text)
        result['linkedin_url'] = extract_linkedin(raw_text)
        result['github_url'] = extract_github(raw_text)
        result['full_name'] = extract_name(raw_text, nlp)
        result['languages'] = extract_languages(raw_text)

        # Step 4: Chunk into sections and extract lists
        sections = chunk_sections(raw_text)
        summary_lines = parse_section_to_list(sections.get('summary', ''))
        result['summary'] = ' '.join(summary_lines) if summary_lines else None

        result['education'] = parse_section_to_list(sections.get('education', ''))
        result['experience'] = parse_section_to_list(sections.get('experience', ''))
        result['projects'] = parse_section_to_list(sections.get('projects', ''))
        result['certifications'] = parse_section_to_list(sections.get('certifications', ''))

        skills_sec = sections.get('skills', '')
        result['skills'] = extract_skills(raw_text, skills_sec)

    except Exception as e:
        logger.error(f"Resume parsing pipeline failed: {e}", exc_info=True)
        result['error'] = str(e)

    return result

