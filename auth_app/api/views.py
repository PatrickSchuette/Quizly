from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from auth_app.utils import (
    delete_auth_cookies,
    set_access_cookie,
    set_refresh_cookie,
)
from .serializers import RegistrationSerializer


class RegistrationView(APIView):
    """Create a new user account (``POST /api/register/``).

    The endpoint is public: no login is needed and no authentication is
    checked, because a new user does not have a token yet. The validation
    and the creation of the user are done by ``RegistrationSerializer``.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Validate the registration data and create the user.

        Args:
            request: The request with ``username``, ``email``, ``password``
                and ``confirmed_password`` in its body.

        Returns:
            A response with a success message and status ``201``. If the data
            is invalid, Django REST Framework automatically returns status
            ``400`` with the error messages of the serializer.
        """
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "User created successfully!"}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Log a user in and set the JWT cookies (``POST /api/login/``).

    The endpoint is public, because the user is not logged in yet. After a
    successful login the access token and the refresh token are sent to
    the browser as HttpOnly cookies. The browser then sends them
    automatically with every following request.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Check the username and the password and log the user in.

        Django's ``authenticate`` function compares the password with the
        hashed password in the database. The error message is the same for a
        wrong username and a wrong password, so nobody can find out which
        usernames exist.

        Args:
            request: The request with ``username`` and ``password`` in its
                body.

        Returns:
            A response with the user data and both token cookies, or a
            response with status ``401`` if the credentials are wrong.
        """
        user = authenticate(
            username=request.data.get("username"),
            password=request.data.get("password"),
        )
        if user is None:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
        return self.build_login_response(user)

    def build_login_response(self, user: User) -> Response:
        """Create the success response for a login and attach the cookies.

        A new refresh token is created for the user, and the access token is
        derived from it. Both tokens are stored as cookies on the response.
        The response body only contains the public data of the user.

        Args:
            user: The user that was successfully authenticated.

        Returns:
            A response with status ``200``, a success message and the ``id``,
            ``username`` and ``email`` of the user.
        """
        refresh = RefreshToken.for_user(user)
        response = Response({
            "detail": "Login successfully!",
            "user": {"id": user.id, "username": user.username, "email": user.email},
        })
        set_access_cookie(response, str(refresh.access_token))
        set_refresh_cookie(response, str(refresh))
        return response


class LogoutView(APIView):
    """Log the user out (``POST /api/logout/``).

    Only logged-in users can use this endpoint. The refresh token is put on
    the blacklist, so it can not be used to create new access tokens
    anymore, and both token cookies are deleted in the browser.
    """

    def post(self, request: Request) -> Response:
        """Blacklist the refresh token and delete both token cookies.

        Args:
            request: The request of the logged-in user. The refresh token is
                read from the ``refresh_token`` cookie.

        Returns:
            A response with status ``200`` and a success message. The response
            tells the browser to delete the ``access_token`` and the
            ``refresh_token`` cookie.
        """
        raw_refresh = request.COOKIES.get("refresh_token")
        self.blacklist_refresh_token(raw_refresh)
        response = Response({
            "detail": "Log-Out successfully! All Tokens will be deleted. "
                      "Refresh token is now invalid."
        })
        delete_auth_cookies(response)
        return response

    def blacklist_refresh_token(self, raw_refresh: str | None) -> None:
        """Put the refresh token on the blacklist, so it can not be used again.

        The blacklist is provided by the ``token_blacklist`` app of Simple JWT
        and is stored in the database. If the token is missing, already on the
        blacklist or invalid, nothing happens, because the user should be
        logged out in any case.

        Args:
            raw_refresh: The refresh token from the cookie, or ``None`` if the
                cookie does not exist.
        """
        if raw_refresh is None:
            return
        try:
            RefreshToken(raw_refresh).blacklist()
        except TokenError:
            pass


class CookieTokenRefreshView(APIView):
    """Create a new access token from the refresh token cookie.

    Endpoint: ``POST /api/token/refresh/``. The access token is only valid
    for 30 minutes. When it has expired, the frontend calls this endpoint
    to get a new one, without asking the user to log in again.

    The endpoint is public, because it is called exactly when the access
    token is no longer valid. The refresh token in the cookie is the proof
    of the user's identity.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Read the refresh token cookie and set a new access token cookie.

        Args:
            request: The request with the ``refresh_token`` cookie.

        Returns:
            A response with status ``200`` and a new ``access_token`` cookie,
            or a response with status ``401`` if the refresh token is missing,
            expired, invalid or on the blacklist.
        """
        raw_refresh = request.COOKIES.get("refresh_token")
        access_token = self.create_access_token(raw_refresh)
        if access_token is None:
            return Response({"detail": "Refresh token is missing or invalid."}, status=401)
        response = Response({"detail": "Token refreshed"})
        set_access_cookie(response, access_token)
        return response

    def create_access_token(self, raw_refresh: str | None) -> str | None:
        """Create a new access token from a refresh token.

        Creating ``RefreshToken`` from the text checks the signature, the
        expiry date and the blacklist of the token.

        Args:
            raw_refresh: The refresh token from the cookie, or ``None`` if the
                cookie does not exist.

        Returns:
            The new access token as text, or ``None`` if the refresh token is
            missing, expired, invalid or on the blacklist.
        """
        if raw_refresh is None:
            return None
        try:
            return str(RefreshToken(raw_refresh).access_token)
        except TokenError:
            return None
