from django.conf import settings
from rest_framework.response import Response


def set_access_cookie(response: Response, access_token: str) -> None:
    """Store the access token as an HttpOnly cookie on the response."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Store the refresh token as an HttpOnly cookie on the response."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def delete_auth_cookies(response: Response) -> None:
    """Remove both token cookies from the browser."""
    response.delete_cookie("access_token", samesite=settings.COOKIE_SAMESITE)
    response.delete_cookie("refresh_token", samesite=settings.COOKIE_SAMESITE)
