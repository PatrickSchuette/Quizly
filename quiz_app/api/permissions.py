from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from quiz_app.models import Quiz


class IsQuizOwner(BasePermission):
    """Allow access to a quiz only for the user who created it.

    Used in ``QuizDetailView``. A logged-in user who requests a quiz of
    another user gets status ``403``.
    """

    def has_object_permission(self, request: Request, view: APIView, obj: Quiz) -> bool:
        """Check whether the requesting user is the owner of the quiz.

        Django REST Framework calls this method after the quiz was loaded from
        the database, in ``get_object`` of the detail view. If the quiz does
        not exist, the view returns ``404`` before this method runs.

        Args:
            request: The incoming request with the logged-in user.
            view: The view that handles the request.
            obj: The quiz that should be read, changed or deleted.

        Returns:
            ``True`` if the quiz belongs to the requesting user, otherwise
            ``False``.
        """
        return obj.owner == request.user
