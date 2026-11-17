from pathlib import Path
from datetime import timedelta
import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')
SECRET_KEY = env('SECRET_KEY', default='unsafe-development-key-change-me')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

INSTALLED_APPS = [
    "corsheaders",
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'unfold', 'unfold.contrib.filters', 'rest_framework', 'rest_framework_simplejwt', 'drf_spectacular',
    'apps.users', 'apps.crypto', 'apps.kyc', 'apps.compliance','apps.exchange',
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'core.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],
              'APP_DIRS':True,'OPTIONS':{'context_processors':[
              'django.template.context_processors.debug','django.template.context_processors.request',
              'django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': env('POSTGRES_DB'), 'USER': env('POSTGRES_USER'), 'PASSWORD': env('POSTGRES_PASSWORD'), 'HOST': env('POSTGRES_HOST', default='localhost'), 'PORT': env('POSTGRES_PORT', default='5432'), 'CONN_MAX_AGE': 60}}
AUTH_USER_MODEL = 'users.User'
AUTH_PASSWORD_VALIDATORS = [
 {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
 {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},
 {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
 {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Asia/Bishkek'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'assets']
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = int(env('EMAIL_PORT', default='') or 587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
EMAIL_TIMEOUT = 15

REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES':['apps.users.two_factor_authentication.TwoFactorJWTAuthentication'],
                  'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],
                  "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",}

SIMPLE_JWT = {'ACCESS_TOKEN_LIFETIME':timedelta(minutes=15), 'REFRESH_TOKEN_LIFETIME':timedelta(days=1),
              'ROTATE_REFRESH_TOKENS':True, 'BLACKLIST_AFTER_ROTATION':False,
              'USER_AUTHENTICATION_RULE':'apps.users.authentication.verified_user_authentication_rule'}

LOGGING = {'version':1,'disable_existing_loggers':False,
           'handlers':{'file':{'class':'logging.handlers.RotatingFileHandler','filename':str(BASE_DIR/'logs'/'django.log'),
                               'maxBytes':5_000_000,'backupCount':3}},
           'loggers':{'django':{'handlers':['file'],'level':'WARNING','propagate':True}}}

from core.unfold import configure_admin
configure_admin(globals())

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600

RUNEX_API_KEY = env("RUNEX_API_KEY", default="")
RUNEX_BASE_URL = env(
    "RUNEX_BASE_URL",
    default="https://kyt-api.ranex.kg",
)
RUNEX_TIMEOUT = env.int("RUNEX_TIMEOUT", default=30)


RUNEX_KYC_API_KEY = env("RUNEX_KYC_API_KEY", default="")
RUNEX_KYC_BASE_URL = env("RUNEX_KYC_BASE_URL", default="")
RUNEX_KYC_WEBHOOK_SECRET = env("RUNEX_KYC_WEBHOOK_SECRET", default="")
RUNEX_CATEGORY_KYC_LEVEL = env(
    "RUNEX_CATEGORY_KYC_LEVEL",
    default="KYC_LVL_1",
)

RUNEX_CATEGORY_KYB_LEVEL = env(
    "RUNEX_CATEGORY_KYB_LEVEL",
    default="KYB_LVL_1",
)

RUNEX_KYC_API_SECRET = env("RUNEX_KYC_API_SECRET", default="")
RUNEX_KYC_RETURN_URL = env("RUNEX_KYC_RETURN_URL", default="https://lk.bnbroker.kg/")
RUNEX_KYC_CONNECT_TIMEOUT = env.int("RUNEX_KYC_CONNECT_TIMEOUT", default=5)
RUNEX_KYC_READ_TIMEOUT = env.int("RUNEX_KYC_READ_TIMEOUT", default=20)

SPECTACULAR_SETTINGS = {
    "TITLE": "BNBroker API",
    "DESCRIPTION": "BNBroker cryptocurrency exchange backend API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVE_AUTHENTICATION": [],
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "displayRequestDuration": True,
        "persistAuthorization": True,
        "filter": True,
    },
}

TOTP_ENCRYPTION_KEY = env(
    "TOTP_ENCRYPTION_KEY",
    default="",
)


_BNBROKER_LOCAL_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5000",
    "http://127.0.0.1:5173",
]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5000",
    "http://127.0.0.1:5173",
    "https://bnbroker.navisdevs.ru",
    "https://lk.bnbroker.kg",
]