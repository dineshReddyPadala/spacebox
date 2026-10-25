from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlsplit

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / '.env', override=False)
ENV = os.getenv('APP_ENV', 'development').lower()
PRODUCTION = ENV == 'production'
SITE_URL = os.getenv('SITE_URL', 'http://localhost:8000').rstrip('/')
APP_SECRET = os.getenv('APP_SECRET', 'development-only-do-not-deploy')
MEDIA_DIR = Path(os.getenv('MEDIA_DIR', str(BASE_DIR / 'private_media')))
DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'local.db'}")
# Render/older providers sometimes return postgres://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,testserver').split(',') if h.strip()]
CONTACT_EMAIL = os.getenv('CONTACT_EMAIL', 'spaceboxconcepts@gmail.com')
CONTACT_PHONE = os.getenv('CONTACT_PHONE', '+91 77991 01433')
SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT','587'))
SMTP_USER = os.getenv('SMTP_USER','')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD','')
SMTP_FROM = os.getenv('SMTP_FROM',CONTACT_EMAIL)
NOTIFY_EMAIL = os.getenv('NOTIFY_EMAIL',CONTACT_EMAIL)
SMTP_STARTTLS = os.getenv('SMTP_STARTTLS','true').lower() == 'true'

if PRODUCTION:
    if len(APP_SECRET) < 40 or APP_SECRET == 'development-only-do-not-deploy':
        raise RuntimeError('Production requires a unique APP_SECRET of at least 40 characters')
    if urlsplit(SITE_URL).scheme != 'https':
        raise RuntimeError('Production requires an HTTPS SITE_URL')
    if not ALLOWED_HOSTS or set(ALLOWED_HOSTS).issubset({'localhost','127.0.0.1','testserver'}):
        raise RuntimeError('Production requires ALLOWED_HOSTS for the real website domain')
    if DATABASE_URL.startswith('sqlite'):
        raise RuntimeError('Production requires a persistent PostgreSQL DATABASE_URL')
