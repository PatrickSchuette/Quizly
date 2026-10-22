from django.conf import settings
from rest_framework.response import Response


def set_access_cookie(response: Response, access_token: str) -> None:
    """Store the access token as an HttpOnly cookie on the response.

    ``httponly=True`` means that JavaScript in the browser can not read
    the cookie. This protects the token against XSS attacks.

    ``secure`` and ``samesite`` are read from the settings
    (``COOKIE_SECURE`` and ``COOKIE_SAMESITE`` in the ``.env``). Locally
    the cookie works over ``http://``. On the server it is only sent over
    HTTPS and is also allowed when the frontend runs on another domain.

    Args:
        response: The response the cookie is attached to.
        access_token: The JWT access token as text.
    """
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Store the refresh token as an HttpOnly cookie on the response.

    The refresh token is valid for one day and is used to create new
    access tokens. It is stored with the same cookie options as the access
    token: HttpOnly, and ``secure`` and ``samesite`` from the settings
    (``COOKIE_SECURE`` and ``COOKIE_SAMESITE`` in the ``.env``).

    Args:
        response: The response the cookie is attached to.
        refresh_token: The JWT refresh token as text.
    """
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )


def delete_auth_cookies(response: Response) -> None:
    """Delete both token cookies in the browser.

    The backend can not remove a cookie from the browser directly. Instead
    the response sends both cookies again with an empty value and an
    expiry date in the past, so the browser deletes them. The ``samesite``
    value must match the value that was used when the cookies were set,
    otherwise the browser may ignore the deletion.

    Args:
        response: The response that deletes the cookies.
    """
    response.delete_cookie("access_token", samesite=settings.COOKIE_SAMESITE)
    response.delete_cookie("refresh_token", samesite=settings.COOKIE_SAMESITE)
