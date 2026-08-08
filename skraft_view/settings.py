import os
import sys
from pathlib import Path

RUNNING_FROZEN = bool(getattr(sys, "frozen", False))
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
PROJECT_DIR = BUNDLE_DIR


def _user_data_dir() -> Path:
    override = os.environ.get("SKRAFT_VIEW_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "skraft-view"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "skraft-view"

    return Path.home() / ".local" / "share" / "skraft-view"


DATA_DIR = _user_data_dir() if RUNNING_FROZEN else PROJECT_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = "dev-only-skraft-view-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "skraft_view.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PROJECT_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "skraft_view.wsgi.application"
ASGI_APPLICATION = "skraft_view.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [PROJECT_DIR / "static"]
STATIC_ROOT = DATA_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
