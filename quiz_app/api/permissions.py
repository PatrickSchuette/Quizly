from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from quiz_app.models import Quiz


class IsQuizOwner(BasePermission):
    """Allows access only if the quiz belongs to the logged-in user."""

    def has_object_permission(self, request: Request, view: APIView, obj: Quiz) -> bool:
        """Return True if the requesting user is the owner of the quiz."""
        return obj.owner == request.user
