import json
from django.test import TestCase
from pydantic import ValidationError
from core.ai.schemas import ResumeScoreSchema
from core.ai.service import GroqAIEngine
from unittest.mock import patch, MagicMock

class MockMessage:
    def __init__(self, content):
        self.content = content

class MockChoice:
    def __init__(self, message):
        self.message = message

class MockResponse:
    def __init__(self, choices):
        self.choices = choices

class AISchemaValidationTests(TestCase):

    @patch('core.ai.service.Groq')
    def test_successful_schema_validation(self, MockGroq):
        """Test that a perfectly formatted JSON string parses into the Pydantic schema."""
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        
        valid_json_response = json.dumps({
            "score": 95,
            "matching_skills": ["Python", "Django"],
            "missing_skills": ["Docker"],
            "strengths": ["Backend engineering"],
            "weaknesses": ["Deployment experience"],
            "summary": "Great backend candidate."
        })
        
        mock_client.chat.completions.create.return_value = MockResponse(
            choices=[MockChoice(message=MockMessage(content=valid_json_response))]
        )
        
        engine = GroqAIEngine()
        # Mocking the env var to avoid warning in test
        engine._client = mock_client 
        
        result = engine.generate_structured_response("Test prompt", ResumeScoreSchema)
        
        self.assertEqual(result.score, 95)
        self.assertIn("Python", result.matching_skills)

    @patch('core.ai.service.Groq')
    def test_failed_schema_validation(self, MockGroq):
        """Test that an invalid JSON response raises a ValidationError."""
        mock_client = MagicMock()
        MockGroq.return_value = mock_client
        
        # Missing the 'summary' and 'weaknesses' fields
        invalid_json_response = json.dumps({
            "score": "ninety-five", # Should be int
            "matching_skills": ["Python", "Django"],
            "missing_skills": ["Docker"],
            "strengths": ["Backend engineering"]
        })
        
        mock_client.chat.completions.create.return_value = MockResponse(
            choices=[MockChoice(message=MockMessage(content=invalid_json_response))]
        )
        
        engine = GroqAIEngine()
        engine._client = mock_client 
        
        with self.assertRaises(ValidationError):
            engine.generate_structured_response("Test prompt", ResumeScoreSchema)

