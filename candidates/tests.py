from django.test import TestCase
from django.contrib.auth import get_user_model
from candidates.models import CandidateProfile

User = get_user_model()

class CandidateProfileNormalizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testcandidate",
            email="candidate@test.com",
            password="testpassword123",
            role="CANDIDATE"
        )
        self.profile = CandidateProfile.objects.create(user=self.user)

    def test_experience_normalization_string_list(self):
        # When experience contains a list of strings
        self.profile.experience = [
            "Senior Backend Developer | Tech Solutions Inc. | Jan 2021 - Present",
            "Junior Dev | Old Corp | Jan 2019 - Dec 2020"
        ]
        self.profile.save()

        structured = self.profile.experience_structured
        self.assertEqual(len(structured), 2)
        
        self.assertEqual(structured[0]['title'], "Senior Backend Developer | Tech Solutions Inc. | Jan 2021 - Present")
        self.assertEqual(structured[0]['role'], "Senior Backend Developer | Tech Solutions Inc. | Jan 2021 - Present")
        self.assertEqual(structured[0]['company'], "")
        
        self.assertEqual(structured[1]['title'], "Junior Dev | Old Corp | Jan 2019 - Dec 2020")
        self.assertEqual(structured[1]['role'], "Junior Dev | Old Corp | Jan 2019 - Dec 2020")

    def test_experience_normalization_dict_list(self):
        # When experience contains a list of dicts already
        self.profile.experience = [
            {
                "title": "Lead Dev",
                "role": "Lead Dev",
                "company": "Big Tech",
                "duration": "2 years",
                "description": "Led team"
            }
        ]
        self.profile.save()

        structured = self.profile.experience_structured
        self.assertEqual(len(structured), 1)
        self.assertEqual(structured[0]['title'], "Lead Dev")
        self.assertEqual(structured[0]['company'], "Big Tech")
        self.assertEqual(structured[0]['description'], "Led team")

    def test_education_normalization_string_list(self):
        # When education contains a list of strings
        self.profile.education = [
            "B.S. Computer Science | University | 2015-2019"
        ]
        self.profile.save()

        structured = self.profile.education_structured
        self.assertEqual(len(structured), 1)
        self.assertEqual(structured[0]['degree'], "B.S. Computer Science | University | 2015-2019")
        self.assertEqual(structured[0]['institution'], "")

    def test_education_normalization_dict_list(self):
        # When education contains a list of dicts
        self.profile.education = [
            {
                "degree": "M.S.",
                "institution": "Stanford",
                "year": "2021"
            }
        ]
        self.profile.save()

        structured = self.profile.education_structured
        self.assertEqual(len(structured), 1)
        self.assertEqual(structured[0]['degree'], "M.S.")
        self.assertEqual(structured[0]['institution'], "Stanford")

    def test_projects_normalization_string_list(self):
        # When projects contains a list of strings
        self.profile.projects = [
            "Project A: Cool app"
        ]
        self.profile.save()

        structured = self.profile.projects_structured
        self.assertEqual(len(structured), 1)
        self.assertEqual(structured[0]['name'], "Project A: Cool app")
        self.assertEqual(structured[0]['description'], "")

    def test_projects_normalization_dict_list(self):
        # When projects contains a list of dicts
        self.profile.projects = [
            {
                "name": "Project B",
                "description": "Awesome"
            }
        ]
        self.profile.save()

        structured = self.profile.projects_structured
        self.assertEqual(len(structured), 1)
        self.assertEqual(structured[0]['name'], "Project B")
        self.assertEqual(structured[0]['description'], "Awesome")


from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from jobs.models import Job, Company
from applications.models import Application

class CandidatePortalWorkflowTestCase(TestCase):
    def setUp(self):
        self.candidate_user = User.objects.create_user(
            username="candidate_john",
            email="john@candidate.com",
            password="Password123!",
            role="CANDIDATE"
        )
        self.recruiter_user = User.objects.create_user(
            username="recruiter_jane",
            email="jane@recruiter.com",
            password="Password123!",
            role="RECRUITER"
        )
        self.company = Company.objects.create(
            owner=self.recruiter_user,
            name="Innovate Tech",
            is_approved=True
        )
        self.job = Job.objects.create(
            company=self.company,
            title="Senior Python Developer",
            description="Build scalable APIs.",
            is_published=True,
            is_approved=True
        )

    def test_candidate_profile_and_resume_management(self):
        self.client.login(username="candidate_john", password="Password123!")
        
        # Test Upload Resume
        resume_file = SimpleUploadedFile("sample_resume.pdf", b"%PDF-1.4 sample resume text", content_type="application/pdf")
        response = self.client.post(reverse('resume_upload'), {'resume_file': resume_file})
        self.assertIn(response.status_code, (200, 302))

        profile = CandidateProfile.objects.get(user=self.candidate_user)
        self.assertIsNotNone(profile.resume_file)

        # Test Secure Resume Access
        secure_url = reverse('secure_resume_download', kwargs={'pk': profile.pk})
        res = self.client.get(secure_url)
        self.assertEqual(res.status_code, 200)
        res.close() # Close file handle

        # Test Delete Resume
        res_del = self.client.post(reverse('resume_delete'))
        self.assertEqual(res_del.status_code, 302)
        profile.refresh_from_db()
        self.assertFalse(profile.resume_file)

    def test_candidate_job_browse_and_apply(self):
        self.client.login(username="candidate_john", password="Password123!")
        CandidateProfile.objects.create(user=self.candidate_user, is_parsed=True)
        
        # Browse Jobs
        response = self.client.get(reverse('job_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Senior Python Developer")

        # Apply for Job
        app_response = self.client.post(reverse('apply_job', kwargs={'job_pk': self.job.pk}), {
            'cover_letter': 'I am excited to apply for this role.'
        })
        self.assertEqual(app_response.status_code, 302)
        self.assertTrue(Application.objects.filter(job=self.job, candidate__user=self.candidate_user).exists())

        # Application Tracking
        track_res = self.client.get(reverse('my_applications'))
        self.assertEqual(track_res.status_code, 200)
        self.assertContains(track_res, "Senior Python Developer")


