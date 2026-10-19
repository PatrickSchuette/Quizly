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
    """Return fake quiz data that looks like the answer from Gemini."""
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
    """Tests for reading, changing and deleting quizzes."""

    def setUp(self) -> None:
        """Create two users and one quiz, then log in as the owner."""
        self.owner = User.objects.create_user("owner", "owner@example.com", PASSWORD)
        User.objects.create_user("other", "other@example.com", PASSWORD)
        self.quiz = save_quiz(self.owner, VIDEO_URL, build_quiz_data(10))
        self.quiz_url = reverse("quiz-detail", kwargs={"pk": self.quiz.id})
        self.login("owner")

    def login(self, username: str) -> None:
        """Log in the given user."""
        data = {"username": username, "password": PASSWORD}
        self.client.post(reverse("login"), data, format="json")

    def test_list_shows_own_quizzes(self) -> None:
        """The list contains the quiz of the logged-in user."""
        response = self.client.get(reverse("quiz-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_list_is_empty_for_other_user(self) -> None:
        """Another user does not see the quiz of the owner."""
        self.login("other")
        response = self.client.get(reverse("quiz-list"))
        self.assertEqual(len(response.data), 0)

    def test_list_requires_login(self) -> None:
        """Without login the list returns 401."""
        self.client.cookies.clear()
        response = self.client.get(reverse("quiz-list"))
        self.assertEqual(response.status_code, 401)

    def test_detail_returns_quiz(self) -> None:
        """The owner gets the quiz with all 10 questions."""
        response = self.client.get(self.quiz_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["questions"]), 10)

    def test_detail_of_other_user_is_forbidden(self) -> None:
        """A foreign quiz returns 403."""
        self.login("other")
        response = self.client.get(self.quiz_url)
        self.assertEqual(response.status_code, 403)

    def test_detail_of_unknown_quiz_returns_404(self) -> None:
        """A quiz id that does not exist returns 404."""
        unknown_url = reverse("quiz-detail", kwargs={"pk": 9999})
        response = self.client.get(unknown_url)
        self.assertEqual(response.status_code, 404)

    def test_patch_changes_title(self) -> None:
        """PATCH changes the title of the quiz."""
        data = {"title": "New title"}
        response = self.client.patch(self.quiz_url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "New title")

    def test_patch_does_not_change_video_url(self) -> None:
        """The video URL can not be changed with PATCH."""
        data = {"video_url": "https://www.google.com/"}
        response = self.client.patch(self.quiz_url, data, format="json")
        self.assertEqual(response.data["video_url"], VIDEO_URL)

    def test_put_is_not_allowed(self) -> None:
        """PUT is not supported and returns 405."""
        response = self.client.put(self.quiz_url, {}, format="json")
        self.assertEqual(response.status_code, 405)

    def test_delete_removes_quiz_and_questions(self) -> None:
        """Deleting a quiz also deletes its questions."""
        response = self.client.delete(self.quiz_url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Quiz.objects.count(), 0)
        self.assertEqual(Question.objects.count(), 0)

    def test_delete_of_other_user_is_forbidden(self) -> None:
        """A user can not delete a foreign quiz."""
        self.login("other")
        response = self.client.delete(self.quiz_url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Quiz.objects.count(), 1)


class QuizCreateTests(APITestCase):
    """Tests for creating a quiz. YouTube, Whisper and Gemini are replaced by fakes."""

    def setUp(self) -> None:
        """Create a user and log in."""
        User.objects.create_user("owner", "owner@example.com", PASSWORD)
        data = {"username": "owner", "password": PASSWORD}
        self.client.post(reverse("login"), data, format="json")

    def create_quiz(self, url: str, fake_quiz_data: dict) -> Response:
        """Send a create request while download, Whisper and Gemini are faked."""
        with patch("quiz_app.utils.download_audio", return_value="audio.webm"):
            with patch("quiz_app.utils.transcribe_audio", return_value="Some text"):
                with patch("quiz_app.utils.generate_quiz_data", return_value=fake_quiz_data):
                    data = {"url": url}
                    return self.client.post(reverse("quiz-list"), data, format="json")

    def test_create_quiz_from_share_link(self) -> None:
        """A share link creates a quiz and is saved as normal watch URL."""
        response = self.create_quiz(SHARE_LINK, build_quiz_data(10))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["video_url"], VIDEO_URL)
        self.assertEqual(len(response.data["questions"]), 10)

    def test_create_rejects_other_websites(self) -> None:
        """A URL that is not from YouTube returns 400."""
        response = self.create_quiz(
            "https://www.google.com/", build_quiz_data(10))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_create_with_wrong_quiz_data_saves_nothing(self) -> None:
        """If Gemini returns only 3 questions, nothing is saved."""
        with self.assertLogs("quiz_app.api.views", level="ERROR"):
            response = self.create_quiz(VIDEO_URL, build_quiz_data(3))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_create_returns_400_if_download_fails(self) -> None:
        """A video that can not be downloaded returns 400."""
        download_error = DownloadError("Video unavailable")
        with patch("quiz_app.utils.download_audio", side_effect=download_error):
            data = {"url": VIDEO_URL}
            response = self.client.post(
                reverse("quiz-list"), data, format="json")
        self.assertEqual(response.status_code, 400)

    def test_create_requires_login(self) -> None:
        """Without login no quiz can be created."""
        self.client.cookies.clear()
        response = self.create_quiz(VIDEO_URL, build_quiz_data(10))
        self.assertEqual(response.status_code, 401)


class UtilsTests(TestCase):
    """Tests for the helper functions in utils.py."""

    def test_extract_video_id_from_share_link(self) -> None:
        """The id is found in a share link."""
        self.assertEqual(extract_video_id(SHARE_LINK), "JkWeEKJRKmM")

    def test_extract_video_id_from_watch_url(self) -> None:
        """The id is found in a normal watch URL."""
        self.assertEqual(extract_video_id(VIDEO_URL), "JkWeEKJRKmM")

    def test_extract_video_id_from_shorts_url(self) -> None:
        """The id is found in a shorts URL."""
        url = "https://youtube.com/shorts/JkWeEKJRKmM"
        self.assertEqual(extract_video_id(url), "JkWeEKJRKmM")

    def test_extract_video_id_from_other_website(self) -> None:
        """A URL from another website returns None."""
        self.assertIsNone(extract_video_id("https://www.google.com/"))

    def test_remove_markdown(self) -> None:
        """The markdown around the JSON is removed."""
        text = '```json\n{"a": 1}\n```'
        self.assertEqual(remove_markdown(text), '{"a": 1}')

    def test_validate_quiz_data_with_wrong_answer(self) -> None:
        """An answer that is not one of the options raises a ValueError."""
        quiz_data = build_quiz_data(10)
        quiz_data["questions"][0]["answer"] = "E"
        with self.assertRaises(ValueError):
            validate_quiz_data(quiz_data)
