"""Settings for the workstation's HTTP development server."""

from .settings import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["*"]
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
