"""
Sandboxed code execution via Judge0 CE — Module 6, Phase 08.

Coding questions NEVER execute code on the main application server.
This module delegates execution to the Judge0 CE public API.

Judge0 CE Language IDs (subset):
  71 = Python 3
  62 = Java
  54 = C++ (GCC 9.2)
  63 = JavaScript (Node.js 12)
  74 = TypeScript (3.7)
  51 = C# (Mono 6)

Configure in .env:
  JUDGE0_API_KEY=<your RapidAPI key>
  JUDGE0_BASE_URL=https://judge0-ce.p.rapidapi.com  (default)

If JUDGE0_API_KEY is not set, the sandbox falls back to a safe mock response.
"""

import os
import time
import logging
import base64
import requests

logger = logging.getLogger(__name__)

JUDGE0_BASE_URL = os.environ.get('JUDGE0_BASE_URL', 'https://judge0-ce.p.rapidapi.com')
JUDGE0_API_KEY  = os.environ.get('JUDGE0_API_KEY', '')

# Map human-friendly language names to Judge0 language IDs
LANGUAGE_ID_MAP = {
    'python':     71,
    'python3':    71,
    'java':       62,
    'cpp':        54,
    'c++':        54,
    'javascript': 63,
    'js':         63,
    'typescript': 74,
    'ts':         74,
    'csharp':     51,
    'c#':         51,
}

DEFAULT_TIMEOUT_SECONDS = 10


def get_language_id(language: str) -> int:
    """Resolve a language string to a Judge0 language ID. Defaults to Python 3."""
    return LANGUAGE_ID_MAP.get(language.lower(), 71)


def _mock_response(code: str) -> dict:
    """Safe fallback when Judge0 API key is not configured."""
    return {
        'stdout':          '(Sandbox not configured — set JUDGE0_API_KEY in .env to enable code execution)',
        'stderr':          '',
        'compile_output':  '',
        'status':          {'description': 'Not configured'},
        'time':            '0',
        'memory':          0,
        'mock':            True,
    }


def execute_code_in_sandbox(
    code: str,
    language: str = 'python',
    stdin: str = '',
    expected_output: str = '',
) -> dict:
    """
    Submit code to Judge0 CE and poll for result.

    Returns a dict with:
      stdout, stderr, compile_output, status, time, memory, is_correct
    """
    if not JUDGE0_API_KEY:
        logger.warning("JUDGE0_API_KEY not set — returning mock sandbox response")
        return _mock_response(code)

    language_id = get_language_id(language)

    headers = {
        'X-RapidAPI-Key':  JUDGE0_API_KEY,
        'X-RapidAPI-Host': 'judge0-ce.p.rapidapi.com',
        'Content-Type':    'application/json',
    }

    payload = {
        'source_code':       base64.b64encode(code.encode()).decode(),
        'language_id':       language_id,
        'stdin':             base64.b64encode(stdin.encode()).decode() if stdin else '',
        'expected_output':   base64.b64encode(expected_output.encode()).decode() if expected_output else '',
        'base64_encoded':    True,
        'wait':              False,
    }

    try:
        # Step 1: Submit
        submit_url = f"{JUDGE0_BASE_URL}/submissions"
        resp = requests.post(submit_url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        token = resp.json().get('token')

        if not token:
            return {'stdout': '', 'stderr': 'Submission failed — no token returned', 'status': {'description': 'Error'}}

        # Step 2: Poll (max 10 attempts, 1s apart)
        result_url = f"{JUDGE0_BASE_URL}/submissions/{token}?base64_encoded=true&fields=stdout,stderr,status,time,memory,compile_output"
        for _ in range(DEFAULT_TIMEOUT_SECONDS):
            time.sleep(1)
            result_resp = requests.get(result_url, headers=headers, timeout=10)
            result_resp.raise_for_status()
            result = result_resp.json()
            status_id = result.get('status', {}).get('id', 0)
            if status_id not in (1, 2):  # 1=In Queue, 2=Processing
                break

        def _decode(val):
            if val:
                try:
                    return base64.b64decode(val).decode(errors='replace')
                except Exception:
                    return val
            return ''

        stdout  = _decode(result.get('stdout', ''))
        stderr  = _decode(result.get('stderr', ''))
        compile = _decode(result.get('compile_output', ''))

        is_correct = False
        if expected_output:
            is_correct = stdout.strip() == expected_output.strip()

        return {
            'stdout':          stdout,
            'stderr':          stderr,
            'compile_output':  compile,
            'status':          result.get('status', {}),
            'time':            result.get('time', ''),
            'memory':          result.get('memory', 0),
            'is_correct':      is_correct,
            'mock':            False,
        }

    except requests.RequestException as e:
        logger.error(f"Judge0 CE API error: {e}")
        return {
            'stdout':         '',
            'stderr':         f'Sandbox API error: {e}',
            'compile_output': '',
            'status':         {'description': 'Network Error'},
            'time':           '',
            'memory':         0,
            'is_correct':     False,
            'mock':           False,
        }
