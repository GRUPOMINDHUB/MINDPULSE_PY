"""
WSGI config for Mindpulse project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mindpulse.settings')

application = get_wsgi_application()

