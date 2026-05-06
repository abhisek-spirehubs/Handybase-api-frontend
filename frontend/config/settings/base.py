"""Base settings for the frontend Django project.

This minimal configuration is intended to allow the Django dev server to run
and to expose environment variables (notably FASTAPI_BASE_URL) via settings.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Secret key — read from env for safety, but provide a default for local dev
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key")

# Installed apps — keep minimal to avoid unnecessary checks
INSTALLED_APPS = [
	"django.contrib.staticfiles",
	"django.contrib.sessions",
	"django.contrib.messages",
	"django.contrib.auth",
	"django.contrib.contenttypes",
	# Use AppConfig paths to ensure our AppConfig classes are picked up
	"apps.authentication.apps.AuthenticationConfig",
	"apps.core.apps.CoreConfig",
    "apps.dashboard.apps.DashboardConfig",
    'apps.subscription',
    "apps.notifications.apps.NotificationsConfig",
    "apps.chat.apps.ChatConfig",
]

MIDDLEWARE = [
	"django.middleware.security.SecurityMiddleware",
	"django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
	"django.middleware.common.CommonMiddleware",
	"django.middleware.csrf.CsrfViewMiddleware",
	"django.contrib.auth.middleware.AuthenticationMiddleware",
	"django.contrib.messages.middleware.MessageMiddleware",
	"whitenoise.middleware.WhiteNoiseMiddleware",
]

ROOT_URLCONF = "config.urls"

LANGUAGE_CODE = "en"
USE_I18N = True
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_NAME = "django_language"

LANGUAGES = [
    ('en', 'English'),
    ('es', 'Spanish'),
    ('fr', 'French'),
]

TEMPLATES = [
	{
		"BACKEND": "django.template.backends.django.DjangoTemplates",
		"DIRS": [BASE_DIR / "templates"],
		"APP_DIRS": True,
		"OPTIONS": {
			"context_processors": [
				"django.template.context_processors.debug",
				"django.template.context_processors.request",
				"django.contrib.auth.context_processors.auth",
				"django.contrib.messages.context_processors.messages",
				"django.template.context_processors.static",
                "django.template.context_processors.i18n",
			]
		},
	}
]

# Tell Django to use cookie-based sessions (stateless frontend)
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"

WSGI_APPLICATION = "config.wsgi.application"

# Static files (served by whitenoise in dev)
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Expose FASTAPI base URL into settings for code that imports settings.FASTAPI_BASE_URL
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000/api/v1")
