import os

from celery import Celery

# Set the default configuration module, if one is not aleady defined.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'discovery.settings.local')

app = Celery('discovery')
app.config_from_object('django.conf:settings', namespace='CELERY')
