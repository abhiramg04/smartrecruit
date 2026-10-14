from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from companies.models import Company
from jobs.models import Job, Category
from applications.models import Application
from candidates.models import CandidateProfile
from skill_gap.models import AssessmentTest
from interviews.models import InterviewSchedule

User = get_user_model()

class RecruiterPortalWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.recruiter_user = User.objects.create_user(
            username="recruiter_mary",
            email="mary@company.com",
            password="Password123!",
            role="RECRUITER"
        )
        self.candidate_user = User.objects.create_user(
            username="candidate_bob",
            email="bob@candidate.com",
            password="Password123!",
            role="CANDIDATE"
        )
        self.company = Company.objects.create(
            owner=self.recruiter_user,
            name="Apex Tech Corp",
            industry="Software",
            location="San Francisco",
            is_approved=True
        )
        self.category = Category.objects.create(name="Engineering")
        self.job = Job.objects.create(
            company=self.company,
            title="Lead Backend Engineer",
            category=self.category,
            description="Build cloud services.",
            is_published=True,
            is_approved=True
        )
        self.candidate_profile = CandidateProfile.objects.create(user=self.candidate_user, is_parsed=True)
        self.application = Application.objects.create(
            candidate=self.candidate_profile,
            job=self.job,
            cover_letter="Interested in backend engineering."
        )

    def test_job_status_properties(self):
        job_draft = Job.objects.create(company=self.company, title="Draft Job", description="Draft")
        self.assertEqual(job_draft.status, 'DRAFT')

        job_pub = Job.objects.create(company=self.company, title="Pub Job", description="Pub", is_published=True)
        self.assertEqual(job_pub.status, 'PUBLISHED')

        job_closed = Job.objects.create(company=self.company, title="Closed Job", description="Closed", is_closed=True)
        self.assertEqual(job_closed.status, 'CLOSED')

    def test_recruiter_applicant_status_decision(self):
        self.client.login(username="recruiter_mary", password="Password123!")
        
        # Test Shortlist Decision
        response = self.client.post(reverse('workflow_update', kwargs={'pk': self.application.pk}), {
            'status': 'SHORTLISTED',
            'notes': 'Shortlisted based on strong resume'
        })
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'SHORTLISTED')

        # Test Reject Decision
        response_rej = self.client.post(reverse('workflow_update', kwargs={'pk': self.application.pk}), {
            'status': 'REJECTED',
            'notes': 'Not a fit for this position'
        })
        self.assertEqual(response_rej.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'REJECTED')

    def test_recruiter_assessment_creation(self):
        self.client.login(username="recruiter_mary", password="Password123!")
        
        response = self.client.post(reverse('assessment_create'), {
            'job_id': self.job.pk,
            'title': 'Backend Python Assessment',
            'description': 'Assess OOP & DB concepts',
            'duration_minutes': 45,
            'passing_score': 75.0
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AssessmentTest.objects.filter(job=self.job, title='Backend Python Assessment').exists())

    def test_recruiter_interview_status_update(self):
        self.client.login(username="recruiter_mary", password="Password123!")
        
        from django.utils import timezone
        interview = InterviewSchedule.objects.create(
            application=self.application,
            scheduled_time=timezone.now(),
            duration_minutes=45,
            status='SCHEDULED'
        )

        # Mark completed
        response = self.client.post(reverse('interview_status_update', kwargs={'pk': interview.pk}), {
            'status': 'COMPLETED'
        })
        self.assertEqual(response.status_code, 302)
        interview.refresh_from_db()
        self.assertEqual(interview.status, 'COMPLETED')
