from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticates users with the JWT stored in the 'access_token' cookie."""

    def authenticate(self, request: Request) -> tuple | None:
        """Read the access token from the cookie and return (user, token) or None."""
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
