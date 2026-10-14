from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser

class AuthenticationAndRBACTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create Candidate User
        self.candidate_password = "CandidatePassword123!"
        self.candidate = CustomUser.objects.create_user(
            username="candidate_user",
            email="candidate@test.com",
            password=self.candidate_password,
            role="CANDIDATE"
        )
        
        # Create Recruiter User
        self.recruiter_password = "RecruiterPassword123!"
        self.recruiter = CustomUser.objects.create_user(
            username="recruiter_user",
            email="recruiter@test.com",
            password=self.recruiter_password,
            role="RECRUITER"
        )
        
        # Create Admin User
        self.admin_password = "AdminPassword123!"
        self.admin = CustomUser.objects.create_superuser(
            username="admin_user",
            email="admin@test.com",
            password=self.admin_password,
            role="ADMIN"
        )

    def test_candidate_registration_and_login(self):
        """Test candidate registration and successful login."""
        response = self.client.post(reverse('register'), {
            'username': 'new_candidate',
            'email': 'new_candidate@test.com',
            'password1': 'NewPass123!',
            'password2': 'NewPass123!',
            'role': 'CANDIDATE'
        })
        self.assertEqual(response.status_code, 302) # Redirects to login
        self.assertTrue(CustomUser.objects.filter(username='new_candidate').exists())

        login_success = self.client.login(username='new_candidate', password='NewPass123!')
        self.assertTrue(login_success)

    def test_recruiter_login(self):
        """Test recruiter login and redirection."""
        login_success = self.client.login(username='recruiter_user', password=self.recruiter_password)
        self.assertTrue(login_success)
        response = self.client.get(reverse('recruiter_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_admin_login(self):
        """Test admin login and redirection."""
        login_success = self.client.login(username='admin_user', password=self.admin_password)
        self.assertTrue(login_success)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_invalid_credentials(self):
        """Test invalid credentials login failure."""
        login_success = self.client.login(username='candidate_user', password='WrongPassword!')
        self.assertFalse(login_success)

    def test_candidate_accessing_recruiter_endpoint(self):
        """Test candidate accessing recruiter-only endpoint is rejected server-side (403)."""
        self.client.login(username='candidate_user', password=self.candidate_password)
        response = self.client.get(reverse('recruiter_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_candidate_accessing_admin_endpoint(self):
        """Test candidate accessing admin-only endpoint is rejected server-side (403)."""
        self.client.login(username='candidate_user', password=self.candidate_password)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_recruiter_accessing_admin_endpoint(self):
        """Test recruiter accessing admin-only endpoint is rejected server-side (403)."""
        self.client.login(username='recruiter_user', password=self.recruiter_password)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_role_change_prevention(self):
        """Test that a user cannot elevate or change their own role through profile update."""
        self.client.login(username='candidate_user', password=self.candidate_password)
        response = self.client.post(reverse('profile'), {
            'first_name': 'Candidate',
            'last_name': 'Updated',
            'email': 'candidate@test.com',
            'role': 'ADMIN' # Malicious attempt to elevate role
        })
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.role, 'CANDIDATE') # Role must remain CANDIDATE
