from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.test import APITestCase
from yt_dlp.utils import DownloadError

from quiz_app.models import Question, Quiz
from quiz_app.utils import (
    extract_video_id,
    remove_markdown,
    save_quiz,
    validate_quiz_data,
)

PASSWORD = "SecurePass123!"
VIDEO_URL = "https://www.youtube.com/watch?v=JkWeEKJRKmM"
SHARE_LINK = "https://youtu.be/JkWeEKJRKmM?si=x0EXYWYE4lVkpAm8"


def build_quiz_data(number_of_questions: int) -> dict:
    """Create fake quiz data in the same format as the answer of Gemini.

    Every question has the options ``A`` to ``D`` with ``A`` as the
    correct answer. With a number other than 10 the data can be used to
    test the validation.

    Args:
        number_of_questions: How many questions the quiz should contain.

    Returns:
        A dictionary with ``title``, ``description`` and ``questions``.
    """
    questions = []
    for number in range(number_of_questions):
        question = {
            "question_title": "Question " + str(number + 1),
            "question_options": ["A", "B", "C", "D"],
            "answer": "A",
        }
        questions.append(question)
    return {"title": "Test Quiz", "description": "A test.", "questions": questions}


class QuizTests(APITestCase):
    """Tests for reading, changing and deleting quizzes.

    They cover ``GET /api/quizzes/`` and ``GET``, ``PATCH``, ``PUT`` and
    ``DELETE`` on ``/api/quizzes/{id}/``, including the owner check.
    """

    def setUp(self) -> None:
        """Create two users and one quiz, then log in as the owner.

        The quiz is saved directly with ``save_quiz``, so no YouTube download,
        no Whisper and no Gemini is needed. The second user ``other`` is used
        to test the access to a foreign quiz.
        """
        self.owner = User.objects.create_user("owner", "owner@example.com", PASSWORD)
        User.objects.create_user("other", "other@example.com", PASSWORD)
        self.quiz = save_quiz(self.owner, VIDEO_URL, build_quiz_data(10))
        self.quiz_url = reverse("quiz-detail", kwargs={"pk": self.quiz.id})
        self.login("owner")

    def login(self, username: str) -> None:
        """Log in the given user with the test password.

        The cookies of the login response replace the cookies of the user who
        was logged in before.

        Args:
            username: The username of the user to log in.
        """
        data = {"username": username, "password": PASSWORD}
        self.client.post(reverse("login"), data, format="json")

    def test_list_shows_own_quizzes(self) -> None:
        """Check that the list contains the quiz of the logged-in user.

        Expected: status ``200`` and exactly one quiz.
        """
        response = self.client.get(reverse("quiz-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_list_is_empty_for_other_user(self) -> None:
        """Check that a user does not see the quizzes of other users.

        Expected: an empty list for the user ``other``.
        """
        self.login("other")
        response = self.client.get(reverse("quiz-list"))
        self.assertEqual(len(response.data), 0)

    def test_list_requires_login(self) -> None:
        """Check that the quiz list is only available after the login.

        All cookies are removed before the request.
        Expected: status ``401``.
        """
        self.client.cookies.clear()
        response = self.client.get(reverse("quiz-list"))
        self.assertEqual(response.status_code, 401)

    def test_detail_returns_quiz(self) -> None:
        """Check that the owner gets a single quiz with all of its questions.

        Expected: status ``200`` and 10 questions.
        """
        response = self.client.get(self.quiz_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["questions"]), 10)

    def test_detail_of_other_user_is_forbidden(self) -> None:
        """Check that a user can not read a foreign quiz.

        Expected: status ``403`` for the user ``other``.
        """
        self.login("other")
        response = self.client.get(self.quiz_url)
        self.assertEqual(response.status_code, 403)

    def test_detail_of_unknown_quiz_returns_404(self) -> None:
        """Check that a quiz id that does not exist returns status 404.

        Expected: status ``404``.
        """
        unknown_url = reverse("quiz-detail", kwargs={"pk": 9999})
        response = self.client.get(unknown_url)
        self.assertEqual(response.status_code, 404)

    def test_patch_changes_title(self) -> None:
        """Check that PATCH changes the title of a quiz.

        Expected: status ``200`` and the new title in the response.
        """
        data = {"title": "New title"}
        response = self.client.patch(self.quiz_url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "New title")

    def test_patch_does_not_change_video_url(self) -> None:
        """Check that the video URL can not be changed with PATCH.

        ``video_url`` is a read-only field, so the value from the request is
        ignored. Expected: the original video URL in the response.
        """
        data = {"video_url": "https://www.google.com/"}
        response = self.client.patch(self.quiz_url, data, format="json")
        self.assertEqual(response.data["video_url"], VIDEO_URL)

    def test_put_is_not_allowed(self) -> None:
        """Check that PUT is not supported.

        Only ``GET``, ``PATCH`` and ``DELETE`` are allowed on the detail
        endpoint. Expected: status ``405``.
        """
        response = self.client.put(self.quiz_url, {}, format="json")
        self.assertEqual(response.status_code, 405)

    def test_delete_removes_quiz_and_questions(self) -> None:
        """Check that deleting a quiz also deletes all of its questions.

        Expected: status ``204`` and no quizzes and no questions are left in
        the database.
        """
        response = self.client.delete(self.quiz_url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Quiz.objects.count(), 0)
        self.assertEqual(Question.objects.count(), 0)

    def test_delete_of_other_user_is_forbidden(self) -> None:
        """Check that a user can not delete a foreign quiz.

        Expected: status ``403`` and the quiz still exists.
        """
        self.login("other")
        response = self.client.delete(self.quiz_url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Quiz.objects.count(), 1)


class QuizCreateTests(APITestCase):
    """Tests for creating a quiz with ``POST /api/quizzes/``.

    The YouTube download, Whisper and Gemini are replaced by fake
    functions with ``unittest.mock.patch``. This way the tests run fast,
    without internet and without a Gemini API key.
    """

    def setUp(self) -> None:
        """Create a test user and log in before every test.

        The test client keeps the cookies of the login, so all requests in
        the test are sent as this user.
        """
        User.objects.create_user("owner", "owner@example.com", PASSWORD)
        data = {"username": "owner", "password": PASSWORD}
        self.client.post(reverse("login"), data, format="json")

    def create_quiz(self, url: str, fake_quiz_data: dict) -> Response:
        """Send a create request while download, Whisper and Gemini are faked.

        ``patch`` replaces the three functions in ``quiz_app.utils`` only
        inside the ``with`` blocks and returns fixed values instead of doing
        the real work.

        Args:
            url: The URL that is sent in the request body.
            fake_quiz_data: The quiz data that the faked Gemini function
                returns.

        Returns:
            The response of the create endpoint.
        """
        with patch("quiz_app.utils.download_audio", return_value="audio.webm"):
            with patch("quiz_app.utils.transcribe_audio", return_value="Some text"):
                with patch("quiz_app.utils.generate_quiz_data", return_value=fake_quiz_data):
                    data = {"url": url}
                    return self.client.post(reverse("quiz-list"), data, format="json")

    def test_create_quiz_from_share_link(self) -> None:
        """Check that a share link creates a quiz.

        The share link contains an extra parameter (``?si=...``).
        Expected: status ``201``, the video URL is saved in the normal watch
        format and the quiz has 10 questions.
        """
        response = self.create_quiz(SHARE_LINK, build_quiz_data(10))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["video_url"], VIDEO_URL)
        self.assertEqual(len(response.data["questions"]), 10)

    def test_create_rejects_other_websites(self) -> None:
        """Check that URLs from other websites are rejected.

        Expected: status ``400`` and no quiz is saved.
        """
        response = self.create_quiz(
            "https://www.google.com/", build_quiz_data(10))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_create_with_wrong_quiz_data_saves_nothing(self) -> None:
        """Check that invalid quiz data from Gemini is not saved.

        The faked Gemini answer contains only 3 instead of 10 questions.
        Expected: status ``500`` and no quiz is saved.
        """
        response = self.create_quiz(VIDEO_URL, build_quiz_data(3))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_create_returns_400_if_download_fails(self) -> None:
        """Check the response when the video can not be downloaded.

        The faked download raises a ``DownloadError``, like for a private or
        deleted video. Expected: status ``400``.
        """
        download_error = DownloadError("Video unavailable")
        with patch("quiz_app.utils.download_audio", side_effect=download_error):
            data = {"url": VIDEO_URL}
            response = self.client.post(
                reverse("quiz-list"), data, format="json")
        self.assertEqual(response.status_code, 400)

    def test_create_requires_login(self) -> None:
        """Check that only logged-in users can create a quiz.

        All cookies are removed before the request.
        Expected: status ``401``.
        """
        self.client.cookies.clear()
        response = self.create_quiz(VIDEO_URL, build_quiz_data(10))
        self.assertEqual(response.status_code, 401)


class UtilsTests(TestCase):
    """Tests for the helper functions in ``quiz_app/utils.py``.

    The functions are called directly, without a request.
    """

    def test_extract_video_id_from_share_link(self) -> None:
        """Check that the video id is found in a share link.

        Expected: the id ``JkWeEKJRKmM`` without the ``?si=...`` parameter.
        """
        self.assertEqual(extract_video_id(SHARE_LINK), "JkWeEKJRKmM")

    def test_extract_video_id_from_watch_url(self) -> None:
        """Check that the video id is found in a normal watch URL.

        Expected: the id ``JkWeEKJRKmM``.
        """
        self.assertEqual(extract_video_id(VIDEO_URL), "JkWeEKJRKmM")

    def test_extract_video_id_from_shorts_url(self) -> None:
        """Check that the video id is found in a shorts URL.

        Expected: the id ``JkWeEKJRKmM``.
        """
        url = "https://youtube.com/shorts/JkWeEKJRKmM"
        self.assertEqual(extract_video_id(url), "JkWeEKJRKmM")

    def test_extract_video_id_from_other_website(self) -> None:
        """Check that a URL from another website is not accepted.

        Expected: ``None``.
        """
        self.assertIsNone(extract_video_id("https://www.google.com/"))

    def test_remove_markdown(self) -> None:
        """Check that markdown code fences around the JSON are removed.

        Expected: only the plain JSON text is left.
        """
        text = '```json\n{"a": 1}\n```'
        self.assertEqual(remove_markdown(text), '{"a": 1}')

    def test_validate_quiz_data_with_wrong_answer(self) -> None:
        """Check that an answer which is not one of the options is rejected.

        Expected: ``validate_quiz_data`` raises a ``ValueError``.
        """
        quiz_data = build_quiz_data(10)
        quiz_data["questions"][0]["answer"] = "E"
        with self.assertRaises(ValueError):
            validate_quiz_data(quiz_data)
