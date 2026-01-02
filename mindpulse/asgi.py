"""
ASGI config for Mindpulse project.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mindpulse.settings')

application = get_asgi_application()

