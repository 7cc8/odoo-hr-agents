import os
import json
import tempfile
import unittest
import uuid
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from openpyxl import Workbook

from approval_schema import new_approval_timestamps
from web_service import app
import parser


HEADERS = ["name", "work_email", "work_phone", "mobile_phone", "job_title", "company", "department", "job", "hiring_date"]


def create_sample_xlsx(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Employees"
    ws.append(HEADERS)
    ws.append(["سارة الغامدي", "sara@example.com", "", "0501112233", "مهندس", "شركة النخبة الذكية للتقنية", "تقنية المعلومات", "مهندس برمجيات", "2026-10-06"])
    wb.save(path)


class WebServiceTests(unittest.TestCase):

    def setUp(self):
        self._orig_token = os.environ.get("WRITE_API_TOKEN")
        os.environ["WRITE_API_TOKEN"] = "unit-test-write-token"
        self.client = TestClient(app)
        self.tmpdir = Path("output") / f"test_tmp_{uuid.uuid4().hex[:8]}"
        self.tmpdir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self._orig_token is not None:
            os.environ["WRITE_API_TOKEN"] = self._orig_token
        else:
            os.environ.pop("WRITE_API_TOKEN", None)
        if hasattr(self, "tmpdir") and self.tmpdir.exists():
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_root_returns_html(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("بوابة أتمتة إدخال الموظفين في Odoo", response.text)

    def test_get_guide_returns_html(self):
        response = self.client.get("/guide")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("دليل تشغيل استيراد الموظفين", response.text)

    def test_get_status_returns_json(self):
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("odoo", data)
        self.assertIn("telegram", data)

    def test_get_runs_returns_list(self):
        response = self.client.get("/runs")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_upload_endpoint_saves_file(self):
        xlsx_path = self.tmpdir / "upload_test.xlsx"
        create_sample_xlsx(xlsx_path)

        with open(xlsx_path, "rb") as f:
            res = self.client.post("/upload", files={"file": ("upload_test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "uploaded")
        self.assertTrue(Path(data["file_path"]).exists())
        self.assertGreater(data["size_bytes"], 0)

    def test_upload_endpoint_rejects_oversized_file(self):
        xlsx_path = self.tmpdir / "oversized.xlsx"
        create_sample_xlsx(xlsx_path)

        with patch.object(parser, "MAX_FILE_SIZE_BYTES", 10):
            with open(xlsx_path, "rb") as f:
                res = self.client.post("/upload", files={"file": ("oversized.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
            self.assertEqual(res.status_code, 413)
            self.assertIn("يتجاوز الحد الأقصى", res.json()["detail"])

    def test_dry_run_rejects_non_xlsx(self):
        txt_file = self.tmpdir / "test.txt"
        txt_file.write_text("dummy")
        with open(txt_file, "rb") as f:
            response = self.client.post("/dry-run", files={"file": ("test.txt", f, "text/plain")})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Excel", response.json()["detail"])

    @patch("dry_run_report.OdooReadonlyRepository")
    def test_dry_run_and_approval_flow(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.get_session_info.return_value = {
            "odoo_url": "https://example.odoo.com",
            "odoo_db": "test_db",
            "uid": 1,
            "server_version": "19.0",
        }
        mock_repo.get_live_reference_snapshot.return_value = {
            "companies": [{"id": 15, "name": "شركة النخبة الذكية للتقنية", "active": True}],
            "departments": [{"id": 8, "name": "تقنية المعلومات", "complete_name": "تقنية المعلومات", "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True}],
            "jobs": [{"id": 22, "name": "مهندس برمجيات", "company_id": [15, "شركة النخبة الذكية للتقنية"], "active": True}],
        }
        mock_repo.search_employees_by_keys.return_value = []
        mock_repo_cls.return_value = mock_repo

        xlsx_path = self.tmpdir / "test_import.xlsx"
        create_sample_xlsx(xlsx_path)

        with open(xlsx_path, "rb") as f:
            dry_run_res = self.client.post(
                "/dry-run",
                files={"file": ("test_import.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

        self.assertEqual(dry_run_res.status_code, 200)
        report_data = dry_run_res.json()
        self.assertEqual(report_data["summary"]["row_count"], 1)
        self.assertEqual(report_data["rows"][0]["final_status"], "accepted")
        self.assertEqual(report_data["rows"][0]["display_name"], "سارة الغامدي")
        self.assertEqual(report_data["rows"][0]["display_hiring_date"], "2026-10-06")

        report_file_path = report_data["report_path"]
        input_file_path = report_data["input_path"]
        run_id = report_data["header"]["run_id"]

        # Test GET /dry-run/{run_id} (Section 3)
        get_res = self.client.get(f"/dry-run/{run_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["run_id"], run_id)

        # Test POST /approve (Section 3)
        approval_res = self.client.post(
            "/approve",
            headers={"X-API-Key": "unit-test-write-token"},
            json={
                "report_path": report_file_path,
                "input_path": input_file_path,
                "approved_by": "خالد",
                "rows": [2],
            },
        )
        self.assertEqual(approval_res.status_code, 200)
        app_json = approval_res.json()
        self.assertEqual(app_json["status"], "success")
        self.assertEqual(app_json["approved_count"], 1)
        self.assertTrue(Path(app_json["approval_path"]).exists())

    def test_approve_rejects_unaccepted_row(self):
        fake_report = {
            "header": {"run_id": "r1", "source_hash": "h1"},
            "rows": [
                {"excel_row_number": 2, "final_status": "rejected", "row_hash": "hash2"},
            ],
        }
        rep_file = self.tmpdir / "dry_run_report.json"
        rep_file.write_text(json.dumps(fake_report), encoding="utf-8")

        response = self.client.post(
            "/approve",
            headers={"X-API-Key": "unit-test-write-token"},
            json={
                "report_path": str(rep_file),
                "input_path": "dummy.xlsx",
                "approved_by": "خالد",
                "rows": [2],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("لا يمكن اعتماد صفوف مرفوضة", response.json()["detail"])

    # Acceptance Test 3.2.1: /write rejects without valid auth token
    def test_write_rejects_without_auth_token(self):
        res = self.client.post(
            "/write",
            json={"run_id": "dummy_run"},
        )
        self.assertEqual(res.status_code, 401)
        self.assertIn("غير مصرّح", res.json()["detail"])

    # Acceptance Test 3.2.2: /write rejects if not preceded by /approve for same run_id
    def test_write_rejects_without_prior_approval(self):
        res = self.client.post(
            "/write",
            headers={"X-API-Key": "unit-test-write-token"},
            json={"run_id": "non_existent_run"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("توقف الأمان", res.json()["detail"])

    # Acceptance Test 3.2.3: /write invokes run_writer() with exact signature
    @patch("writer.run_writer")
    @patch("web_service.OdooWriteGateway")
    @patch("web_service.OdooReadonlyRepository")
    def test_write_calls_run_writer_with_exact_signature(self, mock_repo, mock_gw, mock_writer):
        mock_writer.return_value = {
            "footer": {"status_counts": {"created": 1, "failed": 0, "skipped": 0}},
            "rows": [{"status": "created", "odoo_id": 999, "name": "سارة"}],
            "results_path": "output/test.jsonl",
        }

        # Create valid report and approval
        report_data = {
            "header": {"run_id": "run_test_1", "source_hash": "hash123", "source_file_name": "test.xlsx"},
            "rows": [{"excel_row_number": 2, "final_status": "accepted", "row_hash": "rowhash2"}],
        }
        approval_data = {
            "run_id": "run_test_1",
            "source_hash": "hash123",
            "source_file_name": "test.xlsx",
            "approved_by": "خالد",
            **new_approval_timestamps(),
            "approved_row_hashes": ["rowhash2"],
        }
        rep_p = self.tmpdir / "dry_run_report.json"
        app_p = self.tmpdir / "approval.json"
        inp_p = self.tmpdir / "test.xlsx"
        rep_p.write_text(json.dumps(report_data), encoding="utf-8")
        app_p.write_text(json.dumps(approval_data), encoding="utf-8")
        create_sample_xlsx(inp_p)

        res = self.client.post(
            "/write",
            headers={"X-API-Key": "unit-test-write-token"},
            json={
                "input_path": str(inp_p),
                "report_path": str(rep_p),
                "approval_path": str(app_p),
                "company_id": 15,
                "max_rows": 5,
            },
        )
        self.assertEqual(res.status_code, 200)
        mock_writer.assert_called_once()
        args, kwargs = mock_writer.call_args
        self.assertEqual(Path(args[0]).resolve(), inp_p.resolve())
        self.assertEqual(Path(args[1]).resolve(), rep_p.resolve())
        self.assertEqual(Path(args[2]).resolve(), app_p.resolve())
        self.assertEqual(kwargs["company_id"], 15)
        self.assertEqual(kwargs["max_rows"], 5)

    # Acceptance Test 3.2.4: /write/{run_id}/stream reads lines as SSE
    def test_write_stream_reads_lines(self):
        run_id = "stream_run_123"
        out_folder = Path("output") / f"{run_id}_20261005"
        out_folder.mkdir(parents=True, exist_ok=True)
        results_file = out_folder / f"writer_results_{run_id}.jsonl"
        results_file.write_text(
            json.dumps({"record_type": "row", "status": "created", "name": "أحمد"}) + "\n" +
            json.dumps({"record_type": "footer", "status_counts": {"created": 1}}) + "\n",
            encoding="utf-8"
        )

        res = self.client.get(f"/write/{run_id}/stream")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/event-stream", res.headers["content-type"])
        self.assertIn("data: ", res.text)
        self.assertIn("record_type", res.text)

    def test_download_template_returns_file(self):
        response = self.client.get("/download-template")
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
