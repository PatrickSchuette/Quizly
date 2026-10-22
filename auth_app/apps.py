from django.apps import AppConfig


class AuthAppConfig(AppConfig):
    """Configuration of the ``auth_app`` app.

    The app contains the registration, the login, the logout and the token
    refresh. Authentication works with JWT stored in HttpOnly cookies.
    """

    name = 'auth_app'
