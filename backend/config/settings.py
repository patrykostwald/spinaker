from __future__ import annotations

import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

environ.Env.read_env(ROOT_DIR / ".env", overwrite=False)
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)
SEJM_TERM = env.int('SEJM_TERM', default=10)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=env.bool("DEBUG", default=False))
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "backend", "testserver"]))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "news",
    "scraper",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "news.middleware.FrontendDomainMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

if os.environ.get("PYTEST_VERSION") or env.bool("USE_SQLITE", default=False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 30, "transaction_mode": "IMMEDIATE"},
        }
    }
else:
    DATABASES = {
        "default": env.db(
            "DATABASE_URL",
            default="postgres://spin:spin@localhost:5432/spin_clinic",
        )
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pl"
TIME_ZONE = "Europe/Warsaw"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "x-csrftoken",
    "accept",
    "authorization",
    "content-type",
    "origin",
    "x-requested-with",
    "x-frontend-domain",
]

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=CORS_ALLOWED_ORIGINS,
)

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Polish News Aggregator API",
    "DESCRIPTION": "REST API dla spin.clinic i przeszlosc.today — wyszukiwanie timeline, wątki i artykuły.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

NEWSAPI_KEY = env("NEWSAPI_KEY", default="")
TWITTER_BEARER_TOKEN = env("TWITTER_BEARER_TOKEN", default="")
GDELT_DEFAULT_KEYWORD = env("GDELT_DEFAULT_KEYWORD", default="Polska")

DOMAIN_THREAD_TYPE = {
    "spin.clinic": "factcheck",
    "www.spin.clinic": "factcheck",
    "localhost:3000": "factcheck",
    "przeszlosc.today": "context",
    "www.przeszlosc.today": "context",
    "localhost:3001": "context",
}

# Optional future apps: allauth, allauth.account, django_comments_xtd.
# Install and migrate them explicitly before enabling account/comment UI.
CACHES = {"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"
    if DATABASES["default"]["ENGINE"].endswith("sqlite3") else "django.core.cache.backends.redis.RedisCache",
    "LOCATION": env("REDIS_URL", default="redis://localhost:6379/1"),
}}
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = ["rest_framework.throttling.AnonRateThrottle", "rest_framework.throttling.UserRateThrottle"]
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {"anon": "100/min", "user": "100/min"}
REST_FRAMEWORK["NUM_PROXIES"] = env.int("TRUSTED_PROXY_COUNT", default=0)
NEWSAPI_TIER = env("NEWSAPI_TIER", default="free")
NEWSAPI_ENABLED = env.bool("NEWSAPI_ENABLED", default=False)
TWITTER_ENABLED = env.bool("TWITTER_ENABLED", default=False)
TWITTER_API_TIER = env("TWITTER_API_TIER", default="free")
NEWSAPI_DAILY_REQUEST_LIMIT = env.int("NEWSAPI_DAILY_REQUEST_LIMIT", default=100)
TWITTER_MONTHLY_READ_LIMIT = env.int("TWITTER_MONTHLY_READ_LIMIT", default=9600)
PATRONITE_URL = env("PATRONITE_URL", default="")
LOGGING = {"version": 1, "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"}}
if env("SENTRY_DSN", default=""):
    import sentry_sdk
    sentry_sdk.init(dsn=env("SENTRY_DSN"), send_default_pii=False)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    if not DATABASES['default']['ENGINE'].endswith('sqlite3') and SECRET_KEY in ('dev-insecure-change-me', 'change-me-in-production'):
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('Set a unique DJANGO_SECRET_KEY for production.')

BUYCOFFEE_URL = env("BUYCOFFEE_URL", default="")

YOUTUBE_API_KEY = env('YOUTUBE_API_KEY', default='')
YOUTUBE_ENABLED = env.bool('YOUTUBE_ENABLED', default=False)
YOUTUBE_DAILY_REQUEST_LIMIT = env.int('YOUTUBE_DAILY_REQUEST_LIMIT', default=50)

# Paid providers remain disabled until owner supplies credentials and limits.
EXTERNAL_SEARCH_ENABLED = env.bool('EXTERNAL_SEARCH_ENABLED', default=False)
BRAVE_SEARCH_API_KEY = env('BRAVE_SEARCH_API_KEY', default='')
EXTERNAL_SEARCH_DAILY_LIMIT = env.int('EXTERNAL_SEARCH_DAILY_LIMIT', default=100)
EXTERNAL_SEARCH_CACHE_SECONDS = env.int('EXTERNAL_SEARCH_CACHE_SECONDS', default=0)
EXTERNAL_SEARCH_ARCHIVE_URLS = env.bool('EXTERNAL_SEARCH_ARCHIVE_URLS', default=True)
