from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

PASSWORD = "SecurePass123!"
USERNAME = "newuser"
EMAIL = "newuser@example.com"


def get_registration_data() -> dict:
    """Return valid data for the registration form."""
    return {
        "username": USERNAME,
        "email": EMAIL,
        "password": PASSWORD,
        "confirmed_password": PASSWORD,
    }


class RegistrationTests(APITestCase):
    """Tests for the registration endpoint."""

    def test_register_creates_user(self) -> None:
        """A valid registration creates the user."""
        data = get_registration_data()
        response = self.client.post(reverse("register"), data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_register_fails_if_passwords_differ(self) -> None:
        """Two different passwords are rejected."""
        data = get_registration_data()
        data["confirmed_password"] = "Different123!"
        response = self.client.post(reverse("register"), data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_register_fails_if_email_is_taken(self) -> None:
        """An email address can only be used once."""
        User.objects.create_user("existing", EMAIL, PASSWORD)
        data = get_registration_data()
        response = self.client.post(reverse("register"), data, format="json")
        self.assertEqual(response.status_code, 400)


class LoginTests(APITestCase):
    """Tests for the login endpoint."""

    def setUp(self) -> None:
        """Create a user before every test."""
        User.objects.create_user("tester", "tester@example.com", PASSWORD)

    def test_login_sets_cookies(self) -> None:
        """A correct login sets both token cookies as HttpOnly."""
        data = {"username": "tester", "password": PASSWORD}
        response = self.client.post(reverse("login"), data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertTrue(response.cookies["refresh_token"]["httponly"])

    def test_login_fails_with_wrong_password(self) -> None:
        """A wrong password returns 401 and no cookies."""
        data = {"username": "tester", "password": "wrong"}
        response = self.client.post(reverse("login"), data, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access_token", response.cookies)


class TokenAndLogoutTests(APITestCase):
    """Tests for token refresh and logout."""

    def setUp(self) -> None:
        """Create a user and log in before every test."""
        User.objects.create_user("tester", "tester@example.com", PASSWORD)
        data = {"username": "tester", "password": PASSWORD}
        self.client.post(reverse("login"), data, format="json")

    def test_refresh_sets_new_access_token(self) -> None:
        """A valid refresh cookie gives a new access token cookie."""
        response = self.client.post(reverse("token_refresh"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.cookies)

    def test_refresh_fails_without_cookie(self) -> None:
        """Without a refresh cookie there is no new token."""
        self.client.cookies.clear()
        response = self.client.post(reverse("token_refresh"))
        self.assertEqual(response.status_code, 401)

    def test_logout_deletes_cookies(self) -> None:
        """Logout empties both cookies."""
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies["access_token"].value, "")
        self.assertEqual(response.cookies["refresh_token"].value, "")

    def test_old_refresh_token_is_blacklisted(self) -> None:
        """After logout the old refresh token does not work anymore."""
        old_refresh_token = self.client.cookies["refresh_token"].value
        self.client.post(reverse("logout"))
        self.client.cookies["refresh_token"] = old_refresh_token
        response = self.client.post(reverse("token_refresh"))
        self.assertEqual(response.status_code, 401)

    def test_logout_requires_login(self) -> None:
        """Logout is not possible without being logged in."""
        self.client.cookies.clear()
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 401)
