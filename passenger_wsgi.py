import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')

import django
django.setup()

# Auto-apply database migrations on server reload/startup
try:
    from django.core.management import call_command
    call_command('migrate', interactive=False)
except Exception as e:
    print(f"Auto-migration notice: {e}")

# Import and expose WSGI application for LiteSpeed / Phusion Passenger
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
