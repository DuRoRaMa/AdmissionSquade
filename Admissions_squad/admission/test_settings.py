from .settings import *  # noqa: F401,F403

# Локальные настройки только для автотестов.
# Не трогаем основную БД разработки.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test.sqlite3",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True

# В тестах удобнее видеть настоящие ошибки.
DEBUG = True
