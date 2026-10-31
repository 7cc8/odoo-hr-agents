"""Test-wide settings.

The write-token tests used to rely on whatever WRITE_API_TOKEN the developer had in .env (which, following
the old CHAT_SETUP.md, was the value published in this repository). The server now refuses published values,
so the suite fixes its own token instead of depending on a developer's environment.
"""
import os

TEST_WRITE_TOKEN = "unit-test-write-token"

# Must run before web_service / telegram_bot are imported: both read the variable at import time, and
# load_dotenv() never overrides an existing variable.
os.environ["WRITE_API_TOKEN"] = TEST_WRITE_TOKEN
