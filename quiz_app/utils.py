import json
import re
import tempfile
from functools import lru_cache
from pathlib import Path

import whisper
import yt_dlp
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from google import genai
from google.genai import errors, types

from .models import Question, Quiz

WHISPER_MODEL_NAME = "base"
GEMINI_MODEL_NAMES = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
YOUTUBE_ID_PATTERN = re.compile(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)([\w-]{11})")
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
    """Return the 11-character video id of a YouTube URL, or None if it is no YouTube URL."""
    match = YOUTUBE_ID_PATTERN.search(url)
    return match.group(1) if match else None


def build_watch_url(video_id: str) -> str:
    """Return the standard YouTube watch URL for a video id."""
    return f"https://www.youtube.com/watch?v={video_id}"


def download_audio(video_url: str, target_folder: str) -> str:
    """Download the audio track of a YouTube video and return the file path."""
    tmp_filename = str(Path(target_folder) / "audio.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": tmp_filename,
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as downloader:
        info = downloader.extract_info(video_url, download=True)
        return downloader.prepare_filename(info)


@lru_cache(maxsize=1)
def get_whisper_model() -> whisper.Whisper:
    """Load the Whisper model once and reuse it for all later transcriptions."""
    return whisper.load_model(WHISPER_MODEL_NAME)


def transcribe_audio(audio_path: str) -> str:
    """Turn the spoken words of an audio file into plain text."""
    result = get_whisper_model().transcribe(audio_path, fp16=False)
    return result["text"].strip()


def remove_markdown(text: str) -> str:
    """Remove markdown code fences like ```json and ``` around the JSON text."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def ask_gemini(prompt: str) -> str:
    """Send the prompt to Gemini and return the answer text, trying the next model if one is busy."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    config = types.GenerateContentConfig(response_mime_type="application/json")
    for model_name in GEMINI_MODEL_NAMES:
        try:
            response = client.models.generate_content(
                model=model_name, contents=prompt, config=config
            )
            return response.text
        except errors.ServerError:
            continue
    raise RuntimeError("All Gemini models are currently unavailable.")


def generate_quiz_data(transcript: str) -> dict:
    """Create a quiz from the transcript with Gemini and return it as a dictionary."""
    answer_text = ask_gemini(QUIZ_PROMPT.format(transcript=transcript))
    return json.loads(remove_markdown(answer_text))

def validate_quiz_data(quiz_data: dict) -> None:
    """Raise a ValueError if the quiz from Gemini does not have the expected structure."""
    questions = quiz_data.get("questions", [])
    if len(questions) != 10:
        raise ValueError("Gemini did not return exactly 10 questions.")
    for question in questions:
        if len(question["question_options"]) != 4:
            raise ValueError("Each question needs exactly 4 options.")
        if question["answer"] not in question["question_options"]:
            raise ValueError("The answer must be one of the options.")


@transaction.atomic
def save_quiz(owner: User, video_url: str, quiz_data: dict) -> Quiz:
    """Store the quiz and all of its questions in the database in one step."""
    quiz = Quiz.objects.create(
        owner=owner,
        video_url=video_url,
        title=quiz_data["title"],
        description=quiz_data["description"],
    )
    for question in quiz_data["questions"]:
        Question.objects.create(
            quiz=quiz,
            question_title=question["question_title"],
            question_options=question["question_options"],
            answer=question["answer"],
        )
    return quiz


def create_quiz_from_url(owner: User, video_url: str) -> Quiz:
    """Run the full pipeline: download audio, transcribe it, generate and save the quiz."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_folder:
        audio_path = download_audio(video_url, temp_folder)
        transcript = transcribe_audio(audio_path)
    quiz_data = generate_quiz_data(transcript)
    validate_quiz_data(quiz_data)
    return save_quiz(owner, video_url, quiz_data)
