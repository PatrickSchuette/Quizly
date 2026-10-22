from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

PASSWORD = "SecurePass123!"
USERNAME = "newuser"
EMAIL = "newuser@example.com"


def get_registration_data() -> dict:
    """Return valid data for the registration endpoint.

    A new dictionary is created on every call, so a test can change single
    values without affecting other tests.

    Returns:
        A dictionary with username, email and two matching passwords.
    """
    return {
        "username": USERNAME,
        "email": EMAIL,
        "password": PASSWORD,
        "confirmed_password": PASSWORD,
    }


class RegistrationTests(APITestCase):
    """Tests for the registration endpoint ``POST /api/register/``.

    They cover a successful registration and the two validation errors:
    different passwords and an email address that is already taken.
    """

    def test_register_creates_user(self) -> None:
        """Check that valid data creates a new user.

        Expected: status ``201`` and the user exists in the database.
        """
        data = get_registration_data()
        response = self.client.post(reverse("register"), data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_register_fails_if_passwords_differ(self) -> None:
        """Check that two different passwords are rejected.

        Expected: status ``400`` and no user is created.
        """
        data = get_registration_data()
        data["confirmed_password"] = "Different123!"
        response = self.client.post(reverse("register"), data, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_register_fails_if_email_is_taken(self) -> None:
        """Check that an email address can only be registered once.

        A user with the same email address is created before the request.
        Expected: status ``400``.
        """
        User.objects.create_user("existing", EMAIL, PASSWORD)
        data = get_registration_data()
        response = self.client.post(reverse("register"), data, format="json")
        self.assertEqual(response.status_code, 400)


class LoginTests(APITestCase):
    """Tests for the login endpoint ``POST /api/login/``.

    They cover a successful login with both token cookies and a login with
    a wrong password.
    """

    def setUp(self) -> None:
        """Create a test user before every test.

        Django runs ``setUp`` before every single test and resets the database
        after it, so every test starts with the same data.
        """
        User.objects.create_user("tester", "tester@example.com", PASSWORD)

    def test_login_sets_cookies(self) -> None:
        """Check that a correct login sets both token cookies.

        Expected: status ``200``, and the ``access_token`` and
        ``refresh_token`` cookies are marked as HttpOnly.
        """
        data = {"username": "tester", "password": PASSWORD}
        response = self.client.post(reverse("login"), data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies["access_token"]["httponly"])
        self.assertTrue(response.cookies["refresh_token"]["httponly"])

    def test_login_fails_with_wrong_password(self) -> None:
        """Check that a wrong password is rejected.

        Expected: status ``401`` and no ``access_token`` cookie.
        """
        data = {"username": "tester", "password": "wrong"}
        response = self.client.post(reverse("login"), data, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access_token", response.cookies)


class TokenAndLogoutTests(APITestCase):
    """Tests for the token refresh and the logout.

    They cover ``POST /api/token/refresh/`` and ``POST /api/logout/``,
    including the blacklist for refresh tokens after a logout.
    """

    def setUp(self) -> None:
        """Create a test user and log in before every test.

        The test client stores the cookies of the login response and sends
        them with every following request, just like a browser.
        """
        User.objects.create_user("tester", "tester@example.com", PASSWORD)
        data = {"username": "tester", "password": PASSWORD}
        self.client.post(reverse("login"), data, format="json")

    def test_refresh_sets_new_access_token(self) -> None:
        """Check that a valid refresh token creates a new access token.

        Expected: status ``200`` and a new ``access_token`` cookie.
        """
        response = self.client.post(reverse("token_refresh"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.cookies)

    def test_refresh_fails_without_cookie(self) -> None:
        """Check that the refresh fails without a refresh token cookie.

        All cookies are removed before the request.
        Expected: status ``401``.
        """
        self.client.cookies.clear()
        response = self.client.post(reverse("token_refresh"))
        self.assertEqual(response.status_code, 401)

    def test_logout_deletes_cookies(self) -> None:
        """Check that the logout deletes both token cookies.

        Expected: status ``200`` and both cookies have an empty value.
        """
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.cookies["access_token"].value, "")
        self.assertEqual(response.cookies["refresh_token"].value, "")

    def test_old_refresh_token_is_blacklisted(self) -> None:
        """Check that a refresh token can not be used anymore after the logout.

        The refresh token is saved before the logout and sent again afterwards.
        Expected: status ``401``, because the token is on the blacklist.
        """
        old_refresh_token = self.client.cookies["refresh_token"].value
        self.client.post(reverse("logout"))
        self.client.cookies["refresh_token"] = old_refresh_token
        response = self.client.post(reverse("token_refresh"))
        self.assertEqual(response.status_code, 401)

    def test_logout_requires_login(self) -> None:
        """Check that only logged-in users can log out.

        All cookies are removed before the request.
        Expected: status ``401``.
        """
        self.client.cookies.clear()
        response = self.client.post(reverse("logout"))
        self.assertEqual(response.status_code, 401)
