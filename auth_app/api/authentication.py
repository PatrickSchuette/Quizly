from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate users with the JWT access token stored in a cookie.

    The default ``JWTAuthentication`` of Simple JWT expects the token in
    the ``Authorization`` header. In Quizly the token is stored in an
    HttpOnly cookie named ``access_token`` instead, so JavaScript in the
    browser can not read it. This class reads the token from that cookie
    and then uses the normal validation of Simple JWT.

    It is set as default authentication class in ``REST_FRAMEWORK`` in
    ``core/settings.py``.
    """

    def authenticate(self, request: Request) -> tuple | None:
        """Read the access token from the cookie and return the matching user.

        Args:
            request: The incoming request with its cookies.

        Returns:
            A tuple ``(user, validated_token)`` if a valid token was found, or
            ``None`` if there is no ``access_token`` cookie. ``None`` tells
            Django REST Framework that the request is not authenticated, so
            protected views answer with status ``401``.

        Raises:
            InvalidToken: If the cookie contains an expired or invalid token.
                Django REST Framework turns this into a ``401`` response.
        """
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
