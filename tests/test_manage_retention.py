"""Tests for manage_retention.py (fully mocked and isolated using tmp_path)."""

from __future__ import annotations

import io
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import manage_retention as mr


class TestAuditDetection:
    def test_writer_results_file_detected(self, tmp_path):
        f = tmp_path / "writer_results_12345.jsonl"
        f.write_text("{}", encoding="utf-8")
        assert mr.is_writer_folder_or_audit(f) is True

    def test_writer_results_inside_directory_detected(self, tmp_path):
        sub = tmp_path / "nested"
        sub.mkdir()
        f = sub / "writer_results_abcdef.jsonl"
        f.write_text("{}", encoding="utf-8")
        assert mr.is_writer_folder_or_audit(tmp_path) is True

    def test_regular_dry_run_folder_not_audit(self, tmp_path):
        report = tmp_path / "dry_run_report.json"
        report.write_text("{}", encoding="utf-8")
        assert mr.is_writer_folder_or_audit(tmp_path) is False

    def test_nonexistent_path(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist"
        assert mr.is_writer_folder_or_audit(nonexistent) is False


class TestFolderInfoAndScanning:
    def test_get_folder_info(self, tmp_path):
        folder = tmp_path / "run_1"
        folder.mkdir()
        (folder / "dry_run_report.json").write_text("hello", encoding="utf-8")

        info = mr.get_folder_info(folder)
        assert info["name"] == "run_1"
        assert info["is_dry_run"] is True
        assert info["is_audit"] is False
        assert info["size_bytes"] == 5

    def test_scan_output_directory_empty_or_missing(self, tmp_path):
        assert mr.scan_output_directory(tmp_path / "missing") == []
        assert mr.scan_output_directory(tmp_path) == []

    def test_scan_output_directory_orders_by_mtime(self, tmp_path):
        f1 = tmp_path / "run_old"
        f1.mkdir()
        time.sleep(0.01)
        f2 = tmp_path / "run_new"
        f2.mkdir()

        res = mr.scan_output_directory(tmp_path)
        assert len(res) == 2
        assert res[0]["name"] == "run_new"
        assert res[1]["name"] == "run_old"


class TestRetentionCleaning:
    def test_clean_expired_reports_preview_mode(self, tmp_path):
        old_folder = tmp_path / "run_old"
        old_folder.mkdir()
        (old_folder / "dry_run_report.json").write_text("data", encoding="utf-8")

        # Artificially set mtime to 40 days ago
        old_time = time.time() - (40 * 86400)
        os.utime(old_folder, (old_time, old_time))

        # Preview mode
        summary = mr.clean_expired_reports(output_root=tmp_path, days=30, execute=False)
        assert summary["inspected_total"] == 1
        assert summary["eligible_for_deletion"] == 1
        assert summary["deleted_count"] == 0
        assert old_folder.exists()  # Not deleted in preview

    def test_clean_expired_reports_execute_mode(self, tmp_path):
        old_folder = tmp_path / "run_old"
        old_folder.mkdir()
        (old_folder / "dry_run_report.json").write_text("data", encoding="utf-8")

        old_time = time.time() - (40 * 86400)
        os.utime(old_folder, (old_time, old_time))

        # Execute mode
        summary = mr.clean_expired_reports(output_root=tmp_path, days=30, execute=True)
        assert summary["eligible_for_deletion"] == 1
        assert summary["deleted_count"] == 1
        assert not old_folder.exists()

    def test_audit_folders_are_never_deleted(self, tmp_path):
        audit_folder = tmp_path / "audit_run"
        audit_folder.mkdir()
        (audit_folder / "writer_results_test.jsonl").write_text('{"status":"created"}', encoding="utf-8")

        # Set mtime to 100 days ago
        old_time = time.time() - (100 * 86400)
        os.utime(audit_folder, (old_time, old_time))

        summary = mr.clean_expired_reports(output_root=tmp_path, days=30, execute=True)
        assert summary["inspected_total"] == 1
        assert summary["protected_audit"] == 1
        assert summary["eligible_for_deletion"] == 0
        assert summary["deleted_count"] == 0
        assert audit_folder.exists()

    def test_recent_folders_are_retained(self, tmp_path):
        recent_folder = tmp_path / "run_recent"
        recent_folder.mkdir()
        (recent_folder / "dry_run_report.json").write_text("data", encoding="utf-8")

        summary = mr.clean_expired_reports(output_root=tmp_path, days=30, execute=True)
        assert summary["retained_active"] == 1
        assert summary["eligible_for_deletion"] == 0
        assert recent_folder.exists()


class TestCli:
    def test_cli_missing_output_dir(self, tmp_path, capsys):
        code = mr.main(["--output-dir", str(tmp_path / "nonexistent")])
        assert code == 0
        out = capsys.readouterr().out
        assert "does not exist" in out

    def test_cli_list_flag(self, tmp_path, capsys):
        folder = tmp_path / "run_1"
        folder.mkdir()
        code = mr.main(["--output-dir", str(tmp_path), "--list"])
        assert code == 0
        out = capsys.readouterr().out
        assert "run_1" in out

    def test_cli_preview_and_execute(self, tmp_path, capsys):
        folder = tmp_path / "run_old"
        folder.mkdir()
        old_time = time.time() - (50 * 86400)
        os.utime(folder, (old_time, old_time))

        # Preview
        code_prev = mr.main(["--output-dir", str(tmp_path), "--days", "30"])
        assert code_prev == 0
        out_prev = capsys.readouterr().out
        assert "[Preview Mode]" in out_prev
        assert folder.exists()

        # Execute
        code_exec = mr.main(["--output-dir", str(tmp_path), "--days", "30", "--execute"])
        assert code_exec == 0
        out_exec = capsys.readouterr().out
        assert "[Execution Completed]" in out_exec
        assert not folder.exists()
