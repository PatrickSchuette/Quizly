# 🧠 Quizly Backend API

## 📌 Description
Quizly is a quiz generator backend built with Django and Django REST
Framework. Users paste a YouTube link, the backend downloads the audio track,
transcribes it locally with Whisper AI and lets Google Gemini Flash create a
quiz with 10 questions and 4 answer options each. Users can play, rename and
delete their quizzes.

**Note:** This repository contains the backend only. The matching frontend is
provided separately here:
[Developer-Akademie-Backendkurs/project.Quizly](https://github.com/Developer-Akademie-Backendkurs/project.Quizly).
Clone and run it independently (see the CORS note below for connecting them).

---

## ⚙️ Tech Stack
- Python 3.14
- Django 6.1.2
- Django REST Framework 3.18.3
- djangorestframework-simplejwt 5.5.1 (JWT in HttpOnly cookies)
- django-cors-headers 4.9.0
- yt-dlp 2026.8.19 (YouTube audio download)
- openai-whisper 20250625 (local speech-to-text)
- google-genai 2.29.0 (Gemini Flash)
- python-dotenv 1.2.4
- SQLite

---

## 📋 Requirements
These programs must be installed **globally** on your system, they are not
part of `requirements.txt`:

- **FFMPEG** – required by Whisper AI to read the audio files
```bash
# Windows
winget install --id Gyan.FFmpeg -e

# macOS
brew install ffmpeg

# Linux (Debian/Ubuntu)
sudo apt install ffmpeg
```

- **Deno** – JavaScript runtime that yt-dlp needs to extract YouTube videos
```bash
# Windows
winget install DenoLand.Deno

# macOS
brew install deno

# Linux
curl -fsSL https://deno.land/install.sh | sh
```

  Restart your terminal afterwards and check both installations with:
```bash
ffmpeg -version
deno --version
```

- **Gemini API key** – free, see [Environment Variables](#-environment-variables)

---

## 🚀 Quickstart Instructions

- Clone the repository:
```bash
git clone https://github.com/PatrickSchuette/Quizly.git
```

- Create a virtual environment:
```bash
python -m venv env
```

- Activate the virtual environment:
```bash
# Windows
env\Scripts\activate

# macOS/Linux
source env/bin/activate
```

- Install dependencies:
```bash
pip install -r requirements.txt
```

  Whisper installs PyTorch as well, so this step can take a few minutes.

- Create a `.env` file in the project root, see
  [Environment Variables](#-environment-variables) below

- Run database migrations:
```bash
python manage.py migrate
```

- Create a superuser:
```bash
python manage.py createsuperuser
```

- Run the server:
```bash
python manage.py runserver
```

---

## 🔑 Environment Variables

All secret and local settings are loaded from a `.env` file in the project
root (next to `manage.py`). This file is **not** included in this
repository, so you have to create it yourself.

- Create the file `.env` with this content:
```bash
SECRET_KEY='your-secret-key-here'
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
GEMINI_API_KEY='your-gemini-api-key-here'
```

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key, used for signing the JWT tokens |
| `DEBUG` | `True` for local development, `False` in production |
| `ALLOWED_HOSTS` | Comma-separated list of host names the server answers to |
| `GEMINI_API_KEY` | API key for Google Gemini Flash |

### Create a `SECRET_KEY`
Run this command with the virtual environment activated and copy the output
into your `.env`:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Create a `GEMINI_API_KEY`
1. Open [Google AI Studio](https://aistudio.google.com/apikey) and sign in
   with a Google account
2. Click **Create API key**
3. Copy the key into your `.env`

The Gemini Flash models are free to use; no payment details are needed.

**Note:** Never commit the `.env` file. It is already listed in
`.gitignore`. Set `DEBUG=False` and a real `ALLOWED_HOSTS` value before any
production deployment.

---

# 📡 API Overview

## 🔐 Authentication
- `POST /api/register/` → register a new user
- `POST /api/login/` → login user, sets `access_token` and `refresh_token`
  as HttpOnly cookies
- `POST /api/logout/` → logout user, blacklists the refresh token and
  deletes both cookies
- `POST /api/token/refresh/` → creates a new access token from the
  refresh token cookie

## 📝 Quizzes
- `GET /api/quizzes/` → list all quizzes of the logged-in user
- `POST /api/quizzes/` → create a quiz from a YouTube URL
- `GET /api/quizzes/{id}/` → get a single quiz with all questions (owner only)
- `PATCH /api/quizzes/{id}/` → update title and description (owner only)
- `DELETE /api/quizzes/{id}/` → delete a quiz and all its questions
  (owner only)

---

## ⚠️ Notes

- Authentication uses JWT stored in **HttpOnly cookies**. The frontend never
  sees the token; the browser sends the cookies automatically with every
  request. No `Authorization` header is needed.
- The access token is valid for 30 minutes, the refresh token for 1 day.
  After logout the refresh token is put on a blacklist and can not be used
  again.
- CORS is allowed for the local frontend at `http://127.0.0.1:5500`
  (`CORS_ALLOWED_ORIGINS` in `core/settings.py`). Open the frontend via
  `127.0.0.1`, not `localhost`, otherwise the browser does not send the
  cookies. Change the port there if your frontend runs on a different one.
- Every YouTube link format is accepted (`watch?v=`, `youtu.be/` share
  links, `shorts/`, `embed/`, `live/`). The video URL is always saved as
  `https://www.youtube.com/watch?v=VIDEO_ID`.
- Creating a quiz takes some time: the audio is downloaded, transcribed and
  sent to Gemini. Use short videos (2–5 minutes) for testing. On the first
  run Whisper downloads its `base` model once (about 140 MB).
- If the first Gemini model is overloaded, the backend automatically tries
  the next model from `GEMINI_MODEL_NAMES` in `quiz_app/utils.py`.
- Quizzes and single questions can be edited in the Django admin panel at
  `http://127.0.0.1:8000/admin/`.

---

# 🧪 Testing

## Automated Test Suite
The project includes automated tests for both apps. YouTube, Whisper and
Gemini are replaced by fake functions, so the tests run without internet
and without an API key.
```bash
python manage.py test auth_app.tests quiz_app.tests
```

## Postman Collection
A Postman Collection and Environment file covering both happy-path and
unhappy-path scenarios across all endpoints:

- [Quizly.postman_collection.json](./postmanJson/Quizly.postman_collection.json)
- [Quizly.postman_environment.json](./postmanJson/Quizly.postman_environment.json)

To use them:
1. Import both files into Postman
2. Select the "Quizly" environment
3. Run the full collection top-to-bottom via the Collection Runner (later
   requests depend on usernames/IDs set by earlier ones)
4. `create_quiz` really generates a quiz, so the server needs a valid
   `GEMINI_API_KEY` and this request takes a while