#!/usr/bin/env python
"""
Django's command-line utility for administrative tasks.

================================================================================
🚨 CRITICAL AGENT & ARCHITECTURE NOTICE:
1. The ONLINE server and live database are the SOLE source of truth.
2. The user NEVER updates or manages real financial data on this local database.
3. This local workspace is strictly for writing code, fixing logic, building UI,
   and running automated test suites before pushing to Git.
================================================================================
"""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fpl_boys.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
