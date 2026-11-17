"""Settings for the trusted local-network HTTP development server."""

from .settings import *  # noqa: F403

DEBUG = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
