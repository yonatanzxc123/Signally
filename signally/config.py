"""
Central configuration file.

Keeping configuration in one place makes future migration easier.
For example, when moving to PostgreSQL on Raspberry Pi + FastAPI,
we will mostly change DATABASE_URL and possibly add Redis settings.
"""

from __future__ import annotations

import os

DATABASE_URL = os.getenv("SIGNALLY_DATABASE_URL", "sqlite:///signally.db")
DEFAULT_SCAN_TARGET = os.getenv("SIGNALLY_DEFAULT_SCAN_TARGET", "192.168.1.0/24")
