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

if (not os.environ.get("PYTEST_VERSION") and "pytest" not in __import__("sys").modules
        and os.environ.get('SKIP_DOTENV') != '1'):
    environ.Env.read_env(ROOT_DIR / ".env", overwrite=False)
    environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

PUSH_ENABLED = env.bool('PUSH_ENABLED', default=False)
VAPID_PUBLIC_KEY = env('VAPID_PUBLIC_KEY', default='')
VAPID_PRIVATE_KEY = env('VAPID_PRIVATE_KEY', default='')
VAPID_SUBJECT = env('VAPID_SUBJECT', default='')
SEJM_TERM = env.int('SEJM_TERM', default=10)

# Spina v3 (docs/SPINA_V3_API.md): wszystko domyślnie wyłączone; włączenie to decyzja właściciela.
CAUSAL_CHAIN_ENABLED = env.bool('CAUSAL_CHAIN_ENABLED', default=False)
PRZEKAZ_SPIN_STRENGTH_ENABLED = env.bool('PRZEKAZ_SPIN_STRENGTH_ENABLED', default=False)
ELECTION_SILENCE = env.bool('ELECTION_SILENCE', default=False)  # cisza wyborcza: łańcuchy niepubliczne, bez generowania
PRZESZLOSC_VOTES_LIST_ENABLED = env.bool('PRZESZLOSC_VOTES_LIST_ENABLED', default=False)
PRZESZLOSC_NETWORK_ENABLED = env.bool('PRZESZLOSC_NETWORK_ENABLED', default=False)
POSITION_PAIRS_ENABLED = env.bool('POSITION_PAIRS_ENABLED', default=False)  # „Wcześniej i teraz”: tylko pary zatwierdzone
# Zgłoszenia błędów par (recenzja Codex 2): automatyczne zdjęcie z API tylko od zweryfikowanego zgłaszającego albo
# po N niezależnych zgłoszeniach z kont w oknie; SLA decyzji człowieka opisane w docs/SPINA_V3_API.md.
POSITION_PAIR_REPORT_THRESHOLD = env.int('POSITION_PAIR_REPORT_THRESHOLD', default=3)
POSITION_PAIR_REPORT_WINDOW_HOURS = env.int('POSITION_PAIR_REPORT_WINDOW_HOURS', default=24)
POSITION_PAIR_REVIEW_SLA_HOURS = env.int('POSITION_PAIR_REVIEW_SLA_HOURS', default=48)
# Recenzja Fable 13.10 (docs/SPINA_V3_API.md, docs/RUNBOOK_KILL_SWITCH.md):
# stary automatyczny blok „Zmiana zdania” (position_changes) i linia social - domyślnie WYŁĄCZONE (zmiana zachowania produkcji).
POSITION_CHANGES_LEGACY_ENABLED = env.bool('POSITION_CHANGES_LEGACY_ENABLED', default=False)
POSITION_PAIR_ACCOUNT_MIN_AGE_DAYS = env.int('POSITION_PAIR_ACCOUNT_MIN_AGE_DAYS', default=7)  # konta liczone w progu
POSITION_PAIR_CONFIRM_HOURS = env.int('POSITION_PAIR_CONFIRM_HOURS', default=48)  # ważność linku potwierdzającego e-mail
POSITION_PAIR_CONTACT_RETENTION_DAYS = env.int('POSITION_PAIR_CONTACT_RETENTION_DAYS', default=90)
# Domeny, z których potwierdzony e-mail zgłaszającego zdejmuje parę jak VerifiedReporter (lista do przeglądu prawnika).
# Pusta = lista z pliku backend/news/config/official_domains.json (z dziennikiem zmian w bazie, komenda domeny_urzedowe);
# ustawiona w env = zastępuje plik w całości.
POSITION_PAIR_OFFICIAL_DOMAINS = env.list('POSITION_PAIR_OFFICIAL_DOMAINS', default=[])
# Decyzje właściciela 13.10: klauzula art. 14 RODO w profilu (szkic do prawnika) i oświadczenia majątkowe - domyślnie wyłączone.
PRZESZLOSC_PRIVACY_NOTICE_ENABLED = env.bool('PRZESZLOSC_PRIVACY_NOTICE_ENABLED', default=False)
ASSETS_DECLARATIONS_ENABLED = env.bool('ASSETS_DECLARATIONS_ENABLED', default=False)
ASSETS_DECLARATIONS_DELAY_SECONDS = env.float('ASSETS_DECLARATIONS_DELAY_SECONDS', default=5.0)
ASSETS_ROBOTS_FAIL_OPEN = env.bool('ASSETS_ROBOTS_FAIL_OPEN', default=False)  # robots.txt niedostępny: domyślnie nie pobieramy
# Cisza wyborcza jako okno dat (ISO 8601, np. 2027-10-09T00:00:00+02:00); też SiteFlag ELECTION_SILENCE w adminie.
from django.utils.dateparse import parse_datetime as _parse_datetime  # noqa: E402
ELECTION_SILENCE_FROM = _parse_datetime(env('ELECTION_SILENCE_FROM', default='') or '') if env('ELECTION_SILENCE_FROM', default='') else None
ELECTION_SILENCE_UNTIL = _parse_datetime(env('ELECTION_SILENCE_UNTIL', default='') or '') if env('ELECTION_SILENCE_UNTIL', default='') else None

# Institutional reports use a small separate quota and only spare free-model capacity.
REPORTS_ENABLED = env.bool('REPORTS_ENABLED', default=False)
REPORTS_DAILY_CALLS = env.int('REPORTS_DAILY_CALLS', default=12)
REPORTS_DIAGNOSIS_RESERVE_RATIO = env.float('REPORTS_DIAGNOSIS_RESERVE_RATIO', default=0.8)
REPORTS_MIN_WEEKS = env.int('REPORTS_MIN_WEEKS', default=4)
REPORTS_MIN_WEEKLY_PER_CAMP = env.int('REPORTS_MIN_WEEKLY_PER_CAMP', default=10)
REPORTS_MIN_STATEMENTS = env.int('REPORTS_MIN_STATEMENTS', default=30)
REPORTS_MIN_VOTES = env.int('REPORTS_MIN_VOTES', default=10)
REPORTS_MIN_RESEARCH = env.int('REPORTS_MIN_RESEARCH', default=100)
REPORTS_MIN_TOPIC = env.int('REPORTS_MIN_TOPIC', default=20)
REPORTS_AUDIENCES = env.list('REPORTS_AUDIENCES', default=[
    'biura-poselskie', 'kluby', 'agencje-pr-pa', 'dzialy-gr', 'monitoring-mediow',
    'redakcje', 'think-tanki', 'uczelnie'])

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
CLINIC_VIDEO_MONTHLY_ALERT_PLN = env.float('CLINIC_VIDEO_MONTHLY_ALERT_PLN', default=50)
CLINIC_VIDEO_USD_PLN = env.float('CLINIC_VIDEO_USD_PLN', default=4.0)
DAILY_MESSAGE_PAID_FALLBACK_USD = env('DAILY_MESSAGE_PAID_FALLBACK_USD', default='0.05')
DEBUG = env.bool("DJANGO_DEBUG", default=env.bool("DEBUG", default=False))
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "backend", "testserver"]))
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# User-controlled X sharing. OAuth identity is used only to unlock compose
# controls; the application never stores user access tokens or posts for them.
X_USER_OAUTH_ENABLED = env.bool('X_USER_OAUTH_ENABLED', default=False)
X_USER_OAUTH_CLIENT_ID = env('X_USER_OAUTH_CLIENT_ID', default='')
X_USER_OAUTH_REDIRECT_URI = env('X_USER_OAUTH_REDIRECT_URI', default='')
X_USER_OAUTH_SUCCESS_PATH = env('X_USER_OAUTH_SUCCESS_PATH', default='/konto')

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
    "spina3",
]

PREVIEW_KEY = env("PREVIEW_KEY", default="")

MIDDLEWARE = [
    "news.preview.PreviewMiddleware",
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

if (
    os.environ.get("PYTEST_VERSION")
    and not env.bool("USE_POSTGRES_FOR_TESTS", default=False)
) or env.bool("USE_SQLITE", default=False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(env("SQLITE_DATABASE_PATH", default=str(BASE_DIR / "db.sqlite3"))),
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
    "TITLE": "spin.clinic API",
    "DESCRIPTION": "REST API spin.clinic: pasek materiałów i konfiguracja portalu, materiały i ich kontekst, "
                   "nitki, reakcje, rejestr osób publicznych oraz narzędzia redakcji. "
                   "Każdy materiał ma źródło, datę i odnośnik do oryginału.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Dwa zestawy wyborów dla pól „camp” (konta polityczne / nitki redakcyjne) — jawne nazwy w schemacie.
    "ENUM_NAME_OVERRIDES": {
        "AccountCampEnum": "news.political_models.ACCOUNT_CAMPS",
        "EditorialCampEnum": "news.political_models.EDITORIAL_CAMPS",
    },
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
RESEARCH_METADATA_NETWORK_ENABLED = env.bool("RESEARCH_METADATA_NETWORK_ENABLED", default=False)
SOURCE_ACCESS_AUTOPROBE_ENABLED = env.bool("SOURCE_ACCESS_AUTOPROBE_ENABLED", default=False)
# Official BZP metadata is disabled until the operator explicitly enables it
# in the deployment environment.  The adapter never falls back to enabled.
BZP_API_ENABLED = env.bool("BZP_API_ENABLED", default=False)
# przeszłość.today w becie (właściciel 7.10): wszystkie funkcje Pro otwarte dla każdego, bez cen (news.przeszlosc_dostep).
PRZESZLOSC_BETA_ALL_FEATURES = env.bool("PRZESZLOSC_BETA_ALL_FEATURES", default=True)
EDITOR_NETWORK_PREVIEW_ENABLED = env.bool("EDITOR_NETWORK_PREVIEW_ENABLED", default=False)
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
# Darmowy dzienny limit YouTube Data API w jednostkach (search = 100, pozostałe = 1); reset o północy czasu pacyficznego.
YOUTUBE_DAILY_UNITS = env.int('YOUTUBE_DAILY_UNITS', default=10000)

# Paid providers remain disabled until owner supplies credentials and limits.
EXTERNAL_SEARCH_ENABLED = env.bool('EXTERNAL_SEARCH_ENABLED', default=False)
BRAVE_SEARCH_API_KEY = env('BRAVE_SEARCH_API_KEY', default='')
EXTERNAL_SEARCH_DAILY_LIMIT = env.int('EXTERNAL_SEARCH_DAILY_LIMIT', default=100)
EXTERNAL_SEARCH_CACHE_SECONDS = env.int('EXTERNAL_SEARCH_CACHE_SECONDS', default=0)
EXTERNAL_SEARCH_ARCHIVE_URLS = env.bool('EXTERNAL_SEARCH_ARCHIVE_URLS', default=True)

# Private evidentiary box snapshots (news.evidence_snapshot): off by default,
# no bulk capture, no production Supabase storage. See docs/EVIDENCE_SNAPSHOT.md.
EVIDENCE_SNAPSHOT_ENABLED = env.bool('EVIDENCE_SNAPSHOT_ENABLED', default=False)
EVIDENCE_SNAPSHOT_STORAGE_ROOT = env('EVIDENCE_SNAPSHOT_STORAGE_ROOT', default='')
# Załączniki do uwag klientów zbudujmi (29.10): zdjęcia i filmy do podmiany, poza katalogiem publicznym.
# Na VPS katalog jest wolumenem Dockera (docker-compose.production.yml), link do pliku jest podpisany.
ZBUDUJMI_NOTE_FILES_ROOT = env('ZBUDUJMI_NOTE_FILES_ROOT', default=str(BASE_DIR / 'media' / 'private' / 'zbudujmi-uwagi'))
ZBUDUJMI_NOTE_IMAGE_MAX_MB = env.int('ZBUDUJMI_NOTE_IMAGE_MAX_MB', default=25)
ZBUDUJMI_NOTE_VIDEO_MAX_MB = env.int('ZBUDUJMI_NOTE_VIDEO_MAX_MB', default=500)
ZBUDUJMI_NOTE_FILES_PER_DAY = env.int('ZBUDUJMI_NOTE_FILES_PER_DAY', default=20)
ZBUDUJMI_NOTE_FILES_KEEP_DAYS = env.int('ZBUDUJMI_NOTE_FILES_KEEP_DAYS', default=90)
ZBUDUJMI_NOTE_FILES_MIN_FREE_GB = env.int('ZBUDUJMI_NOTE_FILES_MIN_FREE_GB', default=5)

# Private, local-only extraction from explicitly allowed evidence snapshots.
# There is intentionally no scheduler or public endpoint wired to this flag.
EVIDENCE_TEXT_EXTRACTION_ENABLED = env.bool(
    'EVIDENCE_TEXT_EXTRACTION_ENABLED', default=False)

# Dedicated outreach mailbox. Disabled until its private credentials are set
# locally; incoming mail is read-only and never triggers outbound mail.
SOURCE_MAIL_IMAP_ENABLED = env.bool('SOURCE_MAIL_IMAP_ENABLED', default=False)
SOURCE_MAIL_IMAP_HOST = env('SOURCE_MAIL_IMAP_HOST', default='')
SOURCE_MAIL_IMAP_PORT = env.int('SOURCE_MAIL_IMAP_PORT', default=993)
SOURCE_MAIL_IMAP_USERNAME = env('SOURCE_MAIL_IMAP_USERNAME', default='')
SOURCE_MAIL_IMAP_PASSWORD = env('SOURCE_MAIL_IMAP_PASSWORD', default='')
SOURCE_MAIL_SMTP_ENABLED = env.bool('SOURCE_MAIL_SMTP_ENABLED', default=False)
SOURCE_MAIL_SMTP_HOST = env('SOURCE_MAIL_SMTP_HOST', default='')
SOURCE_MAIL_SMTP_PORT = env.int('SOURCE_MAIL_SMTP_PORT', default=465)
SOURCE_MAIL_SMTP_USERNAME = env('SOURCE_MAIL_SMTP_USERNAME', default='')
SOURCE_MAIL_SMTP_PASSWORD = env('SOURCE_MAIL_SMTP_PASSWORD', default='')
SOURCE_MAIL_SMTP_FROM = env('SOURCE_MAIL_SMTP_FROM', default='')

# Phase 2 remains opt-in on every deployment.
ACCOUNTS_ENABLED = env.bool('ACCOUNTS_ENABLED', default=False)
# Właściciel 9.10, zlecenie 113: szybsze alerty wyłącznie po włączeniu flagi.
ALERTS_FAST_MODE = env.bool('ALERTS_FAST_MODE', default=False)
ALERTS_FAST_POLL_SECONDS = env.int('ALERTS_FAST_POLL_SECONDS', default=60)
THREADS_ENABLED = env.bool('THREADS_ENABLED', default=False)
PUSH_ENABLED = env.bool('PUSH_ENABLED', default=False)
GOOGLE_OAUTH_CLIENT_ID = env('GOOGLE_OAUTH_CLIENT_ID', default='')
GOOGLE_OAUTH_CLIENT_SECRET = env('GOOGLE_OAUTH_CLIENT_SECRET', default='')
ACCOUNT_PUBLIC_URL = env('ACCOUNT_PUBLIC_URL', default='https://spin.clinic').rstrip('/')
ACCOUNT_TERMS_VERSION = env('ACCOUNT_TERMS_VERSION', default='2026-10-03')
ACCOUNT_PRIVACY_VERSION = env('ACCOUNT_PRIVACY_VERSION', default='2026-10-03')
PASSWORD_RESET_TIMEOUT = 3600

X_OAUTH_CLIENT_ID = env('X_OAUTH_CLIENT_ID', default='')
X_OAUTH_CLIENT_SECRET = env('X_OAUTH_CLIENT_SECRET', default='')

# spina3.pl (zlecenie 11.10.2026): konfiguracja modelu oceny i flag w jednym miejscu (spina3.config);
# tutaj tylko przełączniki środowiskowe. Produkcja: ustawienia przez zmienne środowiskowe, nie w kodzie.
SPINA3 = {
    'scoring': {
        'mode': env('SPINA3_MODE', default='zgodnosc'),
    },
    'flags': {
        'enabled': env.bool('SPINA3_ENABLED', default=True),
        'pins_enabled': env.bool('SPINA3_PINS_ENABLED', default=True),
        'levels_visible': env.bool('SPINA3_LEVELS_VISIBLE', default=True),
        'views_enabled': env.bool('SPINA3_VIEWS_ENABLED', default=True),
        'url_pins_enabled': env.bool('SPINA3_URL_PINS_ENABLED', default=True),
        'allow_image_pins': env.bool('ALLOW_IMAGE_PINS', default=False),
        'chains_enabled': env.bool('SPINA3_CHAINS_ENABLED', default=False),
        'public_profiles': env.bool('SPINA3_PUBLIC_PROFILES', default=False),
        'election_silence_start': env('SPINA3_ELECTION_SILENCE_START', default=''),
        'election_silence_end': env('SPINA3_ELECTION_SILENCE_END', default=''),
        'election_silence_pause_user_pins': env.bool('SPINA3_ELECTION_SILENCE_PAUSE_USER_PINS', default=False),
        # v2 (12.10.2026): oceny przypięcia autora, komentarze, przejmowanie boxów importera bez przypięcia
        'ratings_enabled': env.bool('SPINA3_RATINGS_ENABLED', default=True),
        'comments_enabled': env.bool('SPINA3_COMMENTS_ENABLED', default=True),
        'adopt_authorless_boxes': env.bool('SPINA3_ADOPT_AUTHORLESS_BOXES', default=True),
        'election_silence_pause_ratings': env.bool('SPINA3_ELECTION_SILENCE_PAUSE_RATINGS', default=False),
        'election_silence_pause_comments': env.bool('SPINA3_ELECTION_SILENCE_PAUSE_COMMENTS', default=False),
        'url_fetch_enabled': env.bool('SPINA3_URL_FETCH_ENABLED', default=False),
        'import_press': env.bool('SPINA3_IMPORT_PRESS', default=False),
        'auth_mode': env('SPINA3_AUTH_MODE', default='session'),
    },
}
SPINA3_DR_SPIN_USERNAME = env('SPINA3_DR_SPIN_USERNAME', default='dr_spin')
SPINA3_PUBLIC_URL = env('SPINA3_PUBLIC_URL', default='https://spina3.pl').rstrip('/')
SPINA3_SPIN_CLINIC_URL = env('SPINA3_SPIN_CLINIC_URL', default='https://spin.clinic').rstrip('/')
SPINA3_PRZESZLOSC_URL = env('SPINA3_PRZESZLOSC_URL', default='https://przeszlosc.today').rstrip('/')
SPINA3_PRZESZLOSC_PERSON_PATH = env('SPINA3_PRZESZLOSC_PERSON_PATH', default='/osoby/{slug}')
# Wspólne logowanie (spina3.sso): usługa kont na osobnej domenie, tokeny krótkie; nazwy zmiennych, nigdy wartości w repo.
SPINA3_SSO_ISSUER = env('SPINA3_SSO_ISSUER', default='')          # np. https://konto.iapply.pl
SPINA3_SSO_AUDIENCE = env('SPINA3_SSO_AUDIENCE', default='spina3')
SPINA3_SSO_CODE_MAX_AGE = env.int('SPINA3_SSO_CODE_MAX_AGE', default=120)
SPINA3_SSO_TOKEN_MAX_AGE = env.int('SPINA3_SSO_TOKEN_MAX_AGE', default=900)
