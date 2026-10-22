import json
import os
import tempfile

import whisper
import yt_dlp
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from google import genai
from google.genai import errors

from .models import Question, Quiz

WHISPER_MODEL_NAME = "base"
GEMINI_MODEL_NAMES = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
YOUTUBE_MARKERS = [
    "youtube.com/watch?v=",
    "youtu.be/",
    "youtube.com/shorts/",
    "youtube.com/embed/",
    "youtube.com/live/",
]
QUIZ_PROMPT = """Based on the following transcript, generate a quiz in valid JSON format.

The quiz must follow this exact structure:
{{
  "title": "Create a concise quiz title based on the topic of the transcript.",
  "description": "Summarize the transcript in no more than 150 characters. Do not include any quiz questions or answers.",
  "questions": [
    {{
      "question_title": "The question goes here.",
      "question_options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": "The correct answer from the above options"
    }},
    ...
    (exactly 10 questions)
  ]
}}

Requirements:
- Each question must have exactly 4 distinct answer options.
- Only one correct answer is allowed per question, and it must be present in 'question_options'.
- The output must be valid JSON and parsable as-is (e.g., using Python's json.loads).
- Do not include explanations, comments, or any text outside the JSON.

Transcript:
{transcript}
"""


def extract_video_id(url: str) -> str | None:
    """Find the video id in a YouTube URL.

    The function looks for one of the known YouTube link formats from
    ``YOUTUBE_MARKERS``. A YouTube video id is always 11 characters long,
    so the 11 characters after the marker are taken. Everything after the
    id, like ``?si=...`` or ``&t=9s``, is ignored.

    Args:
        url: The URL entered by the user, for example
            ``https://youtu.be/JkWeEKJRKmM?si=x0EXYWYE4lVkpAm8``.

    Returns:
        The 11-character video id, for example ``JkWeEKJRKmM``, or
        ``None`` if the URL is not a YouTube link.
    """
    for marker in YOUTUBE_MARKERS:
        if marker in url:
            text_after_marker = url.split(marker)[1]
            video_id = text_after_marker[:11]
            if len(video_id) == 11:
                return video_id
    return None


def build_watch_url(video_id: str) -> str:
    """Build the standard YouTube watch URL for a video id.

    Args:
        video_id: The 11-character YouTube video id.

    Returns:
        The URL in the format ``https://www.youtube.com/watch?v=VIDEO_ID``.
    """
    return f"https://www.youtube.com/watch?v={video_id}"


def download_audio(video_url: str, target_folder: str) -> str:
    """Download only the audio track of a YouTube video.

    yt-dlp chooses the best available audio format. The video itself is
    not downloaded, which saves time and storage. The file is named
    ``audio`` and gets the file extension of the downloaded format, for
    example ``audio.webm``. Playlists are ignored, only the single video
    is downloaded.

    Args:
        video_url: The YouTube watch URL of the video.
        target_folder: The folder the audio file is saved in. In this
            project it is a temporary folder that is deleted afterwards.

    Returns:
        The full path of the downloaded audio file.

    Raises:
        yt_dlp.utils.DownloadError: If the video does not exist, is
            private or can not be downloaded.
    """
    tmp_filename = os.path.join(target_folder, "audio.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": tmp_filename,
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as downloader:
        info = downloader.extract_info(video_url, download=True)
        return downloader.prepare_filename(info)


def transcribe_audio(audio_path: str) -> str:
    """Turn the spoken words of an audio file into plain text with Whisper.

    Whisper runs locally on the server and needs FFmpeg to read the audio
    file. The model from ``WHISPER_MODEL_NAME`` is used; ``base`` is a
    good compromise between speed and quality on a computer without a
    graphics card. On the first run Whisper downloads the model once.
    ``fp16=False`` is set, because half precision only works on graphics
    cards.

    Args:
        audio_path: The full path of the audio file.

    Returns:
        The transcript of the audio without leading and trailing spaces.
    """
    model = whisper.load_model(WHISPER_MODEL_NAME)
    result = model.transcribe(audio_path, fp16=False)
    return result["text"].strip()


def remove_markdown(text: str) -> str:
    """Remove markdown code fences around the JSON answer of Gemini.

    Language models sometimes put JSON into a markdown code block, which
    starts with three backticks and ``json`` and ends with three
    backticks. ``json.loads`` can not read text with these characters, so
    they are removed.

    Args:
        text: The answer text from Gemini.

    Returns:
        The text without code fences and without leading and trailing
        spaces.
    """
    text = text.replace("```json", "")
    text = text.replace("```JSON", "")
    text = text.replace("```", "")
    return text.strip()


def ask_gemini(prompt: str) -> str:
    """Send a prompt to Gemini and return the answer text.

    The models in ``GEMINI_MODEL_NAMES`` are tried one after another. If a
    model is overloaded, Gemini answers with a server error and the next
    model is tried. ``response_mime_type`` tells Gemini to answer with
    JSON only. The API key is read from ``GEMINI_API_KEY`` in the
    settings.

    Errors other than server errors, for example an invalid API key, are
    not caught and stop the creation of the quiz.

    Args:
        prompt: The full prompt including the transcript.

    Returns:
        The answer text of the first model that responded.

    Raises:
        RuntimeError: If all models in ``GEMINI_MODEL_NAMES`` are
            unavailable.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    config = {"response_mime_type": "application/json"}
    for model_name in GEMINI_MODEL_NAMES:
        try:
            response = client.models.generate_content(
                model=model_name, contents=prompt, config=config
            )
            return response.text
        except errors.ServerError:
            print("Gemini model is busy, trying the next one:", model_name)
    raise RuntimeError("All Gemini models are currently unavailable.")


def generate_quiz_data(transcript: str) -> dict:
    """Create the content of the quiz from a transcript with Gemini.

    The transcript is inserted into ``QUIZ_PROMPT``, which describes the
    exact JSON structure of the quiz. The answer of Gemini is cleaned from
    markdown and converted from JSON text into a Python dictionary.

    Args:
        transcript: The transcript of the video.

    Returns:
        A dictionary with ``title``, ``description`` and a list of
        ``questions``. Each question has ``question_title``,
        ``question_options`` and ``answer``.

    Raises:
        json.JSONDecodeError: If the answer of Gemini is not valid JSON.
        RuntimeError: If no Gemini model is available.
    """
    prompt = QUIZ_PROMPT.format(transcript=transcript)
    answer_text = ask_gemini(prompt)
    clean_text = remove_markdown(answer_text)
    return json.loads(clean_text)


def validate_quiz_data(quiz_data: dict) -> None:
    """Check that the quiz from Gemini has the expected structure.

    Gemini does not always follow the prompt exactly, so the data is
    checked before it is saved: there must be exactly 10 questions, every
    question must have exactly 4 options, and the correct answer must be
    one of these options.

    Args:
        quiz_data: The quiz dictionary returned by ``generate_quiz_data``.

    Raises:
        ValueError: If one of the checks fails.
        KeyError: If a required key like ``questions`` is missing.
    """
    questions = quiz_data["questions"]
    if len(questions) != 10:
        raise ValueError("Gemini did not return exactly 10 questions.")
    for question in questions:
        if len(question["question_options"]) != 4:
            raise ValueError("Each question needs exactly 4 options.")
        if question["answer"] not in question["question_options"]:
            raise ValueError("The answer must be one of the options.")


def save_question(quiz: Quiz, question: dict) -> None:
    """Save one question of a quiz in the database.

    Args:
        quiz: The quiz the question belongs to.
        question: A dictionary with ``question_title``,
            ``question_options`` and ``answer``.
    """
    Question.objects.create(
        quiz=quiz,
        question_title=question["question_title"],
        question_options=question["question_options"],
        answer=question["answer"],
    )


@transaction.atomic
def save_quiz(owner: User, video_url: str, quiz_data: dict) -> Quiz:
    """Save a quiz and all of its questions in the database.

    The decorator ``@transaction.atomic`` puts all database writes into
    one transaction: either the quiz and all of its questions are saved,
    or nothing is saved. This way an error while saving a question never
    leaves a quiz without questions in the database.

    Args:
        owner: The user who created the quiz.
        video_url: The YouTube watch URL of the video.
        quiz_data: The validated quiz dictionary with ``title``,
            ``description`` and ``questions``.

    Returns:
        The saved quiz.
    """
    quiz = Quiz.objects.create(
        owner=owner,
        video_url=video_url,
        title=quiz_data["title"],
        description=quiz_data["description"],
    )
    for question in quiz_data["questions"]:
        save_question(quiz, question)
    return quiz


def create_quiz_from_url(owner: User, video_url: str) -> Quiz:
    """Create a complete quiz from a YouTube URL.

    This function runs the whole process:

    1. Download the audio track of the video into a temporary folder.
    2. Transcribe the audio with Whisper.
    3. Let Gemini create the quiz from the transcript.
    4. Check the structure of the quiz.
    5. Save the quiz and its questions in the database.

    The temporary folder and the audio file are deleted automatically as
    soon as the transcript exists. ``ignore_cleanup_errors=True`` prevents
    an error on Windows, where the file can still be locked for a moment.

    Args:
        owner: The user who creates the quiz.
        video_url: The YouTube watch URL of the video.

    Returns:
        The saved quiz with all of its questions.

    Raises:
        yt_dlp.utils.DownloadError: If the video can not be downloaded.
        ValueError: If the quiz from Gemini has the wrong structure.
        RuntimeError: If no Gemini model is available.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_folder:
        audio_path = download_audio(video_url, temp_folder)
        transcript = transcribe_audio(audio_path)
    quiz_data = generate_quiz_data(transcript)
    validate_quiz_data(quiz_data)
    return save_quiz(owner, video_url, quiz_data)
