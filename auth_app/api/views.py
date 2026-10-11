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
    """Creates a new user account."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Validate the sent data and create the user."""
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "User created successfully!"}, status=status.HTTP_201_CREATED,)


class LoginView(APIView):
    """Logs a user in and sets the JWT cookies."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Check the credentials and return the user data with token cookies."""
        user = authenticate(
            username=request.data.get("username"),
            password=request.data.get("password"),
        )
        if user is None:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED,)
        return self.build_login_response(user)

    def build_login_response(self, user: User) -> Response:
        """Create the success response and attach both token cookies."""
        refresh = RefreshToken.for_user(user)
        response = Response({
            "detail": "Login successfully!",
            "user": {"id": user.id, "username": user.username, "email": user.email},
        })
        set_access_cookie(response, str(refresh.access_token))
        set_refresh_cookie(response, str(refresh))
        return response


class LogoutView(APIView):
    """Logs the user out by blacklisting the refresh token and deleting cookies."""

    def post(self, request: Request) -> Response:
        """Invalidate the refresh token and remove both cookies."""
        self.blacklist_refresh_token(request.COOKIES.get("refresh_token"))
        response = Response({
            "detail": "Log-Out successfully! All Tokens will be deleted. "
                      "Refresh token is now invalid."
        })
        delete_auth_cookies(response)
        return response

    def blacklist_refresh_token(self, raw_refresh: str | None) -> None:
        """Put the refresh token on the blacklist so it can never be used again."""
        if raw_refresh is None:
            return
        try:
            RefreshToken(raw_refresh).blacklist()
        except TokenError:
            pass


class CookieTokenRefreshView(APIView):
    """Creates a new access token from the refresh token cookie."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Read the refresh cookie and set a fresh access token cookie."""
        access_token = self.create_access_token(
            request.COOKIES.get("refresh_token"))
        if access_token is None:
            return Response({"detail": "Refresh token is missing or invalid."}, status=status.HTTP_401_UNAUTHORIZED,)
        response = Response({"detail": "Token refreshed"})
        set_access_cookie(response, access_token)
        return response

    def create_access_token(self, raw_refresh: str | None) -> str | None:
        """Return a new access token, or None if the refresh token is missing or invalid."""
        if raw_refresh is None:
            return None
        try:
            return str(RefreshToken(raw_refresh).access_token)
        except TokenError:
            return None
