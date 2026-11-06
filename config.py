import os,secrets
from pathlib import Path
BASE=Path(__file__).resolve().parent
SECRET_KEY=secrets.token_hex(32)
ALLOWED_HOSTS=os.getenv('HOSTS','localhost,127.0.0.1,testserver').split(',')
ROOT_URLCONF='rental.views'
INSTALLED_APPS=['rental']
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
MIDDLEWARE=['django.contrib.sessions.middleware.SessionMiddleware','django.middleware.csrf.CsrfViewMiddleware','rental.views.access']
SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies'
CSRF_USE_SESSIONS=True
DATABASES={'default':{'ENGINE':'django.db.backends.mysql','NAME':os.getenv('MYSQL_DATABASE','rental'),
  'USER':os.getenv('MYSQL_USER','root'),'PASSWORD':os.getenv('MYSQL_PASSWORD',''),
  'HOST':os.getenv('MYSQL_HOST','127.0.0.1'),'PORT':os.getenv('MYSQL_PORT','3306')}}
LANGUAGE_CODE='ru'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE/'templates']}]
