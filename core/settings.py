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
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'unfold', 'unfold.contrib.filters', 'rest_framework', 'rest_framework_simplejwt', 'apps.users', 'apps.crypto', 'apps.kyc', 'apps.compliance',
]
MIDDLEWARE = [
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
STATIC_URL = 'static/'
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
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework_simplejwt.authentication.JWTAuthentication'],
                  'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated']}
SIMPLE_JWT = {'ACCESS_TOKEN_LIFETIME':timedelta(minutes=15), 'REFRESH_TOKEN_LIFETIME':timedelta(days=1),
              'ROTATE_REFRESH_TOKENS':True, 'BLACKLIST_AFTER_ROTATION':False,
              'USER_AUTHENTICATION_RULE':'apps.users.authentication.verified_user_authentication_rule'}
LOGGING = {'version':1,'disable_existing_loggers':False,
           'handlers':{'file':{'class':'logging.handlers.RotatingFileHandler','filename':str(BASE_DIR/'logs'/'django.log'),
                               'maxBytes':5_000_000,'backupCount':3}},
           'loggers':{'django':{'handlers':['file'],'level':'WARNING','propagate':True}}}

from core.unfold import configure_admin
configure_admin(globals())
