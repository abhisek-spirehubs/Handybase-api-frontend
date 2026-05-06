# !/usr/bin/env python
# """Django "manage.py" launcher for the frontend project.
# 
# This file was missing; create a minimal launcher that picks a reasonable
# settings module and ensures FASTAPI_BASE_URL from the environment is
# available via Django settings (as settings.FASTAPI_BASE_URL).
# """
# import os
# import sys
# 
# 
#!/usr/bin/env python
"""Django "manage.py" launcher for the frontend project.

This file was missing; create a minimal launcher that picks a reasonable
settings module and ensures FASTAPI_BASE_URL from the environment is
available via Django settings (as settings.FASTAPI_BASE_URL).
"""
import os
import sys


def main():
	# If a settings module is not already provided use local by default.
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

	# Ensure FASTAPI_BASE_URL from environment is present for code that
	# expects it on import (apps/core/api_client.py reads settings.FASTAPI_BASE_URL).
	# Provide a sensible default if not set.
	os.environ.setdefault(
		"FASTAPI_BASE_URL", os.getenv("FASTAPI_BASE_URL", "http://localhost:8000/api/v1")
	)

	try:
		from django.core.management import execute_from_command_line
	except ImportError as exc:
		raise ImportError(
			"Couldn't import Django. Are you sure it's installed and "
			"available on your PYTHONPATH environment variable?"
		) from exc

	execute_from_command_line(sys.argv)


if __name__ == "__main__":
	main()
