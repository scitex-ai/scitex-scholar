"""Initialize the genuine leaf Django app for frontend integration controls."""
import os
import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scitex_scholar._django.settings")
    django.setup()
