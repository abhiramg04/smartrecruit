import os
from django.core.exceptions import ValidationError

def validate_resume_file(value):
    """
    Validates that a file is a PDF, DOC, DOCX, or TXT and is under 5MB.
    Prevents malicious uploads.
    """
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.doc', '.docx', '.txt']
    if not ext in valid_extensions:
        raise ValidationError('Unsupported file extension. Allowed extensions are: .pdf, .doc, .docx, .txt.')

    limit = 5 * 1024 * 1024 # 5 MB
    if value.size > limit:
        raise ValidationError('File size must not exceed 5 MB.')
