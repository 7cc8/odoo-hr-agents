import os
import pytest
from starlette.testclient import TestClient

# Ensure WRITE_API_TOKEN is available during test runs
TOKEN = os.environ.get("WRITE_API_TOKEN", "test-secret-api-token-2026")
os.environ["WRITE_API_TOKEN"] = TOKEN

_orig_init = TestClient.__init__

def _patched_init(self, app, *args, headers=None, **kwargs):
    if headers is None:
        headers = {"X-API-Key": os.environ.get("WRITE_API_TOKEN", TOKEN)}
    _orig_init(self, app, *args, headers=headers, **kwargs)

TestClient.__init__ = _patched_init
