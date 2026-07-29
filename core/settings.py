"""
Configurações do projeto core (Sistema de Gerência de Estoque).
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ATENÇÃO: troque essa chave antes de colocar em produção.
SECRET_KEY = 'django-insecure-troque-esta-chave-em-producao'

DEBUG = True

ALLOWED_HOSTS = ['*', 'juanvitoriodev.pythonanywhere.com']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # app do projeto
    'estoque',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Banco de dados
# Troque para PostgreSQL/MySQL em produção se preferir.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redireciona login/logout
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'estoque:dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Regras de negócio do estoque
# Como o campo "estoque mínimo" por produto foi removido do cadastro (para
# simplificar o dia a dia dos postos/secretarias), o sistema usa um limite
# único e global para sinalizar "estoque baixo". Ajuste esse número conforme
# a realidade da sua secretaria.
LIMITE_ESTOQUE_BAIXO = 10

# Quantos dias antes do vencimento um produto passa a ser sinalizado como
# "próximo do vencimento" no dashboard e nos relatórios.
DIAS_ALERTA_VENCIMENTO = 60