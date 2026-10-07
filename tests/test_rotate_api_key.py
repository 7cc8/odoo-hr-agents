"""Tests for scripts/rotate_api_key.py (all Odoo calls mocked, no network)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path so rotate_api_key can be imported
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts"))

import scripts.rotate_api_key as rotate_mod


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    """Set required env vars for every test; individual tests may override."""
    monkeypatch.setenv("ODOO_URL", "https://test.odoo.com/")
    monkeypatch.setenv("ODOO_DB", "test-db-123")
    monkeypatch.setenv("ODOO_USERNAME", "testuser")
    monkeypatch.setenv("ODOO_API_KEY", "abcdef1234567890abcdef1234567890abcdef99")


class TestInfo:
    def test_info_returns_zero(self, capsys):
        rc = rotate_mod.cmd_info()
        assert rc == 0
        out = capsys.readouterr().out
        assert "test.odoo.com" in out
        assert "test-db-123" in out
        assert "testuser" in out

    def test_info_masks_key(self, capsys):
        rotate_mod.cmd_info()
        out = capsys.readouterr().out
        # Full key must NOT appear
        assert "abcdef1234567890abcdef1234567890abcdef99" not in out
        # Masked version should appear (first 6 + *** + last 4)
        assert "abcdef***f99" in out or "***" in out


class TestVerify:
    @patch("scripts.rotate_api_key.xmlrpc.client.ServerProxy")
    def test_verify_success(self, mock_sp_cls, capsys):
        mock_common = MagicMock()
        mock_models = MagicMock()
        mock_sp_cls.side_effect = [mock_common, mock_models]

        mock_common.authenticate.return_value = 42
        mock_common.version.return_value = {"server_version": "19.0+e"}
        mock_models.execute_kw.side_effect = [10, 3, 2]  # employee, dept, job counts

        rc = rotate_mod.cmd_verify()
        assert rc == 0
        out = capsys.readouterr().out
        assert "PASSED" in out
        assert "uid=42" in out

    @patch("scripts.rotate_api_key.xmlrpc.client.ServerProxy")
    def test_verify_auth_fail(self, mock_sp_cls, capsys):
        mock_common = MagicMock()
        mock_sp_cls.side_effect = [mock_common]

        mock_common.authenticate.return_value = False

        rc = rotate_mod.cmd_verify()
        assert rc == 1
        err = capsys.readouterr().err
        assert "invalid or expired" in err

    @patch("scripts.rotate_api_key.xmlrpc.client.ServerProxy")
    def test_verify_connection_error(self, mock_sp_cls, capsys):
        mock_common = MagicMock()
        mock_sp_cls.side_effect = [mock_common]

        mock_common.authenticate.side_effect = ConnectionError("timeout")

        rc = rotate_mod.cmd_verify()
        assert rc == 1
        err = capsys.readouterr().err
        assert "Could not connect" in err


class TestMaskKey:
    def test_long_key(self):
        result = rotate_mod._mask_key("abcdef1234567890abcdef1234567890abcdef99")
        assert result.startswith("abcdef")
        assert result.endswith("f99")
        assert "***" in result
        # Full key must not be in result
        assert "1234567890" not in result

    def test_short_key(self):
        result = rotate_mod._mask_key("shortkey")
        assert "***" in result
        assert len(result) < len("shortkey") + 3  # shorter than original


class TestMain:
    def test_verify_flag(self):
        with patch.object(rotate_mod, "cmd_verify", return_value=0) as mock:
            rc = rotate_mod.main(["--verify"])
            assert rc == 0
            mock.assert_called_once()

    def test_info_flag(self):
        with patch.object(rotate_mod, "cmd_info", return_value=0) as mock:
            rc = rotate_mod.main(["--info"])
            assert rc == 0
            mock.assert_called_once()

    def test_missing_flag_exits(self):
        with pytest.raises(SystemExit):
            rotate_mod.main([])


class TestMissingEnv:
    def test_missing_var_exits(self, monkeypatch):
        monkeypatch.delenv("ODOO_API_KEY")
        with pytest.raises(SystemExit) as exc_info:
            rotate_mod.cmd_info()
        assert exc_info.value.code == 2
