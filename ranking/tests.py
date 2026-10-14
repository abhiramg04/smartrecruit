from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from jobs.models import Job, Category, Skill
from candidates.models import CandidateProfile
from applications.models import Application, ApplicationAIScore
from applications.views import ManageApplicationsView
from core.ai.scoring_engine import DeterministicScoringEngine, DEFAULT_WEIGHTS
from core.ai.manager import AIManager
from core.ai.vector_service import VectorEmbeddingService
from core.ai.prompts import CANDIDATE_RANKING_EVAL_PROMPT

User = get_user_model()


class DeterministicScoringEngineTests(TestCase):
    """Tests for Phase 07 Part D: Deterministic Scoring Engine."""

    def test_scoring_weights_defaults(self):
        self.assertEqual(DEFAULT_WEIGHTS['skill'], 0.40)
        self.assertEqual(DEFAULT_WEIGHTS['experience'], 0.20)
        self.assertEqual(DEFAULT_WEIGHTS['education'], 0.10)
        self.assertEqual(DEFAULT_WEIGHTS['semantic_similarity'], 0.20)
        self.assertEqual(DEFAULT_WEIGHTS['ai_evaluation'], 0.10)
        self.assertAlmostEqual(sum(DEFAULT_WEIGHTS.values()), 1.0)

    def test_verdict_thresholds(self):
        self.assertEqual(DeterministicScoringEngine.calculate_verdict(85.0), 'SUITABLE')
        self.assertEqual(DeterministicScoringEngine.calculate_verdict(70.0), 'SUITABLE')
        self.assertEqual(DeterministicScoringEngine.calculate_verdict(65.0), 'MAYBE')
        self.assertEqual(DeterministicScoringEngine.calculate_verdict(45.0), 'MAYBE')
        self.assertEqual(DeterministicScoringEngine.calculate_verdict(30.0), 'REJECT')

    def test_score_skills_exact_match(self):
        job_skills = ['Python', 'Django', 'PostgreSQL']
        cand_skills = ['Python', 'Django', 'Docker']

        res = DeterministicScoringEngine.score_skills(job_skills, cand_skills, "Job JD")
        self.assertIn('Python', res['matched'])
        self.assertIn('Django', res['matched'])
        self.assertIn('PostgreSQL', res['missing'])
        self.assertGreater(res['score'], 50.0)

    def test_evaluate_candidate_deterministic(self):
        candidate_data = {
            'skills': ['Python', 'Django', 'REST API'],
            'experience': ['Senior Python Developer at Tech Corp (3 years)'],
            'education': ['BS Computer Science, Stanford University'],
            'raw_text': 'Experienced Python Developer proficient in Django and REST APIs.',
        }

        result = DeterministicScoringEngine.evaluate_candidate(
            job_title='Senior Python Engineer',
            job_description='Looking for Senior Python Engineer with Django experience.',
            job_skills=['Python', 'Django', 'PostgreSQL'],
            candidate_data=candidate_data,
            ai_evaluation_score=80.0,
        )

        self.assertIn('overall_score', result)
        self.assertIn('verdict', result)
        self.assertGreaterEqual(result['overall_score'], 0.0)
        self.assertLessEqual(result['overall_score'], 100.0)


class AIManagerRankingPipelineTests(TestCase):
    """Tests for Phase 07 Parts B, C, E, & IMPORTANT rules."""

    @patch('core.ai.service.GroqAIEngine.generate_structured_response')
    def test_rank_candidate_two_layer(self, mock_groq):
        # Mock Groq qualitative evaluation
        mock_eval = MagicMock()
        mock_eval.ai_score = 85
        mock_eval.strengths = ['Strong Django expertise', 'Solid backend architecture']
        mock_eval.missing_skills = ['Kubernetes']
        mock_eval.rationale = 'Candidate fits senior backend developer role well.'
        mock_eval.concerns = []
        mock_groq.return_value = mock_eval

        manager = AIManager()
        candidate_data = {
            'skills': ['Python', 'Django', 'PostgreSQL'],
            'experience': ['Backend Engineer at Acme (4 years)'],
            'education': ['B.Tech Computer Science'],
            'raw_text': 'Python Django developer with 4 years experience building web apps.',
        }

        ranking = manager.rank_candidate(
            job_title='Python Backend Developer',
            job_description='Develop RESTful APIs using Python and Django.',
            job_skills=['Python', 'Django', 'PostgreSQL', 'Kubernetes'],
            candidate_data=candidate_data,
        )

        self.assertIn('overall_score', ranking)
        self.assertEqual(ranking['ai_evaluation_score'], 85.0)
        self.assertIn('Strong Django expertise', ranking['ai_strengths'])
        self.assertIn('Kubernetes', ranking['ai_missing_skills'])
        self.assertEqual(ranking['ai_rationale'], 'Candidate fits senior backend developer role well.')

    def test_prompt_excludes_sensitive_attributes(self):
        """Verify prompt enforces non-discrimination guidelines (Phase 07 IMPORTANT)."""
        prompt_lower = CANDIDATE_RANKING_EVAL_PROMPT.lower()
        self.assertIn('protected attribute', prompt_lower)
        self.assertIn('age', prompt_lower)
        self.assertIn('gender', prompt_lower)
        self.assertIn('race', prompt_lower)
        self.assertIn('religion', prompt_lower)
        self.assertIn('decision support only', prompt_lower)

    def test_vector_embedding_generation(self):
        """Test vector generation and similarity computation (Part C)."""
        vec = VectorEmbeddingService.generate_embedding("Python Django Senior Backend Developer")
        self.assertEqual(len(vec), 384)

        sim = VectorEmbeddingService.compute_similarity("Python Django Developer", "Python Django Software Engineer")
        self.assertGreater(sim, 50.0)


class MultiCandidateRankingViewTests(TestCase):
    """Tests for Phase 07 Part F: Multi-Candidate Ranking in Recruiter Dashboard."""

    def setUp(self):
        self.company_owner = User.objects.create_user(
            username='company_owner',
            email='owner@corp.com',
            password='password123',
            role='COMPANY',
        )
        from companies.models import Company
        self.company = Company.objects.create(owner=self.company_owner, name='TechCorp', is_approved=True)

        self.recruiter_user = User.objects.create_user(
            username='recruiter_jane',
            email='recruiter@corp.com',
            password='password123',
            role='RECRUITER',
            company=self.company,
        )
        self.category = Category.objects.create(name='Engineering')
        self.job = Job.objects.create(
            title='Senior Fullstack Engineer',
            company=self.company,
            category=self.category,
            description='Build fullstack web applications with Python and React.',
            is_published=True,
            is_approved=True,
        )

        # Candidate 1: High Match (Score 90.0)
        self.cand_user_1 = User.objects.create_user(username='cand_1', email='cand1@test.com', password='pass')
        self.profile_1 = CandidateProfile.objects.create(user=self.cand_user_1, is_parsed=True, skills=['Python', 'React', 'Django'])
        self.app_1 = Application.objects.create(candidate=self.profile_1, job=self.job)
        ApplicationAIScore.objects.create(
            application=self.app_1,
            overall_score=90.0,
            skill_score=95.0,
            experience_score=85.0,
            semantic_score=88.0,
            ai_recommendation='SUITABLE',
        )

        # Candidate 2: Medium Match (Score 60.0)
        self.cand_user_2 = User.objects.create_user(username='cand_2', email='cand2@test.com', password='pass')
        self.profile_2 = CandidateProfile.objects.create(user=self.cand_user_2, is_parsed=True, skills=['Python'])
        self.app_2 = Application.objects.create(candidate=self.profile_2, job=self.job)
        ApplicationAIScore.objects.create(
            application=self.app_2,
            overall_score=60.0,
            skill_score=50.0,
            experience_score=65.0,
            semantic_score=60.0,
            ai_recommendation='MAYBE',
        )

    def test_ranking_sort_order(self):
        """Verify recruiter view orders applications by overall AI score descending."""
        factory = RequestFactory()
        request = factory.get(f'/applications/manage/?job_id={self.job.pk}')
        request.user = self.recruiter_user

        view = ManageApplicationsView()
        view.request = request

        qs = view.get_queryset()
        self.assertEqual(len(qs), 2)
        # First ranked candidate must be Candidate 1 (Score 90.0)
        self.assertEqual(qs[0].pk, self.app_1.pk)
        self.assertEqual(qs[1].pk, self.app_2.pk)
