from config.settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Faster password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Use local storage for tests
FILE_STORAGE_BACKEND = "local"

# Simple static files storage for tests (no manifest required)
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
