"""Shared, platform-agnostic configuration.

Importing this module loads the .env file, so it must be imported before any
platform config module (e.g. telegram/config.py) reads os.getenv.
"""
import os
from dotenv import load_dotenv

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
