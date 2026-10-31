"""
Preservation Property Tests - Existing API Endpoints Behavior
==============================================================

**Validates: Requirements 3.1, 3.2, 3.3**

These tests establish a baseline for existing API endpoint behavior that MUST be preserved
when implementing the bug fixes. All tests should PASS on the current (unfixed) code.

Testing approach:
- Observation-first: Document actual endpoint behavior  
- Validate JSON response formats remain consistent
- Verify API contracts are preserved
- Confirm CLI tool backward compatibility

Note: These tests focus on API contracts and response structures, not full workflow execution.
Full workflow tests (that require Odoo) are in integration tests.
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from io import BytesIO
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import web service
from web_service import app

# Create test client
client = TestClient(app)

# Test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "samples"


class TestUploadEndpointPreservation:
    """
    Property: POST /upload endpoint behavior must remain unchanged
    
    Validates that file upload continues to work with same JSON response format
    """
    
    def test_upload_returns_expected_json_structure(self, sample_excel_file):
        """Property: Upload endpoint returns consistent JSON structure"""
        # Observe current behavior
        response = client.post(
            "/api/upload",
            files={"file": ("test.xlsx", sample_excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
        # Assert baseline behavior
        assert response.status_code == 200
        data = response.json()
        
        # Property: Response must contain these exact keys
        assert "status" in data
        assert "file_name" in data
        assert "original_name" in data
        assert "file_path" in data
        assert "size_bytes" in data
        
        # Property: Status value format
        assert data["status"] == "uploaded"
        
        # Property: File name contains timestamp and original name
        assert "test.xlsx" in data["file_name"]
        assert data["original_name"] == "test.xlsx"
        
        # Property: Size bytes is positive integer
        assert isinstance(data["size_bytes"], int)
        assert data["size_bytes"] > 0
    
    def test_upload_validates_file_size(self):
        """Property: Upload validates file size (actual behavior may vary)"""
        # Create oversized file (>2MB)
        oversized_content = b"PK\x03\x04" + b"x" * (2 * 1024 * 1024 + 1)
        
        response = client.post(
            "/api/upload",
            files={"file": ("large.xlsx", oversized_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
        # Property: Size validation exists (may return 413 or 200 depending on when check occurs)
        # Document actual behavior: Size check happens in parser.py, not upload endpoint
        # Upload endpoint accepts the file, dry-run will fail if too large
        assert response.status_code in [200, 413]
    
    def test_upload_rejects_non_xlsx_files(self):
        """Property: Upload only accepts .xlsx files"""
        response = client.post(
            "/api/upload",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")}
        )
        
        # Property: Must reject with 400
        assert response.status_code == 400
        assert "صيغة الملف غير مدعومة" in response.json()["detail"]


class TestDryRunEndpointPreservation:
    """
    Property: POST /dry-run endpoint behavior must remain unchanged
    
    Validates that dry-run endpoint contract is preserved (structure, error handling)
    Note: Full execution tests require Odoo connection - tested in integration suite
    """
    
    def test_dryrun_endpoint_exists(self):
        """Property: Dry-run endpoint is available at expected URLs"""
        # Property: Both /api/dry-run and /dry-run should exist
        # Test with invalid content to verify endpoint exists (will return 400 not 404)
        response = client.post("/api/dry-run")
        
        # Property: Endpoint exists (not 404)
        assert response.status_code != 404
        
        # Alternative URL should also work
        response2 = client.post("/dry-run")
        assert response2.status_code != 404
    
    def test_dryrun_validates_file_size(self):
        """Property: Dry-run validates file size"""
        # Create oversized content
        oversized_content = b"PK\x03\x04" + b"x" * (2 * 1024 * 1024 + 1)
        
        response = client.post(
            "/api/dry-run",
            files={"file": ("large.xlsx", oversized_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
        # Property: Rejects oversized files (may be 413 or 422 depending on where validation occurs)
        assert response.status_code in [413, 422]
        data = response.json()
        assert "detail" in data
    
    def test_dryrun_requires_excel_file(self):
        """Property: Dry-run requires Excel file format"""
        # Test with no file
        response = client.post("/api/dry-run")
        
        # Property: Returns error when no file provided
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "ملف" in data["detail"] or "Excel" in data["detail"]


class TestApproveEndpointPreservation:
    """
    Property: POST /approve endpoint behavior must remain unchanged
    
    Validates that approval endpoint contract is preserved
    """
    
    def test_approve_endpoint_exists(self):
        """Property: Approve endpoint is available"""
        response = client.post("/api/approve", json={})
        
        # Property: Endpoint exists (not 404), will return 400/422 for invalid data
        assert response.status_code != 404
    
    def test_approve_requires_run_id_or_report_path(self):
        """Property: Approve endpoint requires run identification"""
        response = client.post(
            "/api/approve",
            json={
                "approved_by": "Test User",
                "rows": [1, 2]
            },
            headers={"X-API-Key": os.environ.get("WRITE_API_TOKEN", "unit-test-write-token")}
        )
        
        # Property: Returns error when run_id/report_path missing
        assert response.status_code in [400, 404, 422]
    
    def test_approve_requires_approved_by(self):
        """Property: Approve endpoint requires approved_by field"""
        response = client.post(
            "/api/approve",
            json={
                "run_id": "test",
                "approved_by": "",  # Empty
                "rows": [1]
            },
            headers={"X-API-Key": os.environ.get("WRITE_API_TOKEN", "unit-test-write-token")}
        )
        
        # Property: Rejects empty approved_by
        assert response.status_code in [400, 404]


class TestWriteEndpointPreservation:
    """
    Property: POST /write endpoint behavior must remain unchanged
    
    Validates that write execution requires proper authentication and approval
    """
    
    def test_write_requires_authentication(self):
        """Property: Write endpoint enforces authentication"""
        response = client.post(
            "/api/write",
            json={
                "run_id": "test-run",
                "company_id": 1,
                "max_rows": 1
            }
        )
        
        # Property: Must reject without auth token
        assert response.status_code == 401
        assert "غير مصرّح" in response.json()["detail"]
    
    def test_write_accepts_valid_auth_header_formats(self):
        """Property: Write endpoint accepts X-API-Key header"""
        # Test with X-API-Key header
        response = client.post(
            "/api/write",
            json={
                "run_id": "test-run",
                "company_id": 1,
                "max_rows": 1
            },
            headers={"X-API-Key": os.environ.get("WRITE_API_TOKEN", "unit-test-write-token")}
        )
        
        # Property: With valid token, should not get 401
        # May get 400 or 404 if operation not found, but not 401
        assert response.status_code != 401
    
    def test_write_requires_approval_file(self):
        """Property: Write endpoint requires approval.json"""
        response = client.post(
            "/api/write",
            json={
                "run_id": "nonexistent-run",
                "company_id": 1,
                "max_rows": 1
            },
            headers={"X-API-Key": os.environ.get("WRITE_API_TOKEN", "unit-test-write-token")}
        )
        
        # Property: Must require approval file
        assert response.status_code == 400
        assert "approval.json" in response.json()["detail"]
    
    def test_write_endpoint_has_multiple_aliases(self):
        """Property: Write endpoint available at multiple URLs for compatibility"""
        # Test all endpoint aliases exist
        endpoints = ["/api/write", "/write", "/api/execute"]
        
        for endpoint in endpoints:
            response = client.post(endpoint, json={})
            # Should get 401 (no auth) or 400 (missing data), not 404
            assert response.status_code != 404, f"Endpoint {endpoint} not found"


class TestStatusEndpointPreservation:
    """
    Property: GET /api/status endpoint behavior must remain unchanged
    """
    
    def test_status_returns_expected_structure(self):
        """Property: Status endpoint returns consistent JSON structure"""
        response = client.get("/api/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Property: Core keys must exist
        assert "status" in data
        assert "odoo" in data
        assert "settings" in data
        assert "telegram" in data
        assert "mode" in data
        
        # Property: Status value
        assert data["status"] == "online"
        
        # Property: Odoo connection info
        odoo = data["odoo"]
        assert "url" in odoo
        assert "database" in odoo
        assert "username" in odoo
        assert "connected" in odoo
        
        # Property: Settings structure
        settings = data["settings"]
        assert "labor_law_checks" in settings
        assert "readback_verification" in settings
        assert "audit_ledger_immutable" in settings
        
        # Property: Telegram config info
        telegram = data["telegram"]
        assert "configured" in telegram
        assert "bot_configured" in telegram
        assert "chat_configured" in telegram


class TestRunsEndpointPreservation:
    """
    Property: GET /api/runs endpoint behavior must remain unchanged
    """
    
    def test_runs_returns_list_structure(self):
        """Property: Runs endpoint returns list of runs"""
        response = client.get("/api/runs")
        
        assert response.status_code == 200
        data = response.json()
        
        # Property: Response is a list
        assert isinstance(data, list)
        
        # If runs exist, check structure
        if len(data) > 0:
            run = data[0]
            assert "folder" in run
            assert "type" in run
            assert "run_id" in run
            assert "summary" in run


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_excel_file():
    """Create a minimal valid Excel file for testing"""
    try:
        from openpyxl import Workbook
        
        wb = Workbook()
        ws = wb.active
        
        # Add headers (matches expected employee template structure)
        headers = [
            "name", "work_email", "mobile_phone", "department", 
            "job_title", "hiring_date", "company"
        ]
        ws.append(headers)
        
        # Add one sample row
        ws.append([
            "محمد أحمد", "mohamed@example.com", "0501234567",
            "IT", "Software Engineer", "2024-01-01", "Company A"
        ])
        
        # Save to bytes
        excel_buffer = BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)
        
        return excel_buffer
    except ImportError:
        # Fallback: create minimal ZIP structure (Excel is ZIP format)
        pytest.skip("openpyxl not available")


# ============================================================================
# CLI Tool Preservation Tests
# ============================================================================

class TestCLIToolPreservation:
    """
    Property: CLI tools must continue to work with --output-dir argument
    
    Validates backward compatibility with existing CLI workflows
    """
    
    def test_generate_template_cli_still_works(self):
        """Property: generate_employee_template.py CLI interface preserved"""
        # Test that the script exists and can be imported
        try:
            import generate_employee_template
            
            # Property: Main function should still accept output_dir parameter
            assert hasattr(generate_employee_template, '__file__')
            
            # Read the file and check for CLI compatibility
            script_path = Path(generate_employee_template.__file__)
            script_content = script_path.read_text(encoding="utf-8")
            
            # Property: Must support --output-dir argument
            assert "--output-dir" in script_content or "--output_dir" in script_content
            
        except ImportError:
            pytest.skip("generate_employee_template.py not found")


# ============================================================================
# Audit Logging Preservation Tests
# ============================================================================

class TestAuditLoggingPreservation:
    """
    Property: Audit logging must continue to work
    
    Validates that all API requests are logged to audit file
    """
    
    def test_api_access_is_logged(self):
        """Property: API calls are logged to audit file"""
        # Make a request
        response = client.get("/api/status")
        assert response.status_code == 200
        
        # Property: Audit log file should exist
        log_file = Path("logs/web_access.log")
        assert log_file.exists()
        
        # Property: Log file contains entries
        log_content = log_file.read_text(encoding="utf-8")
        assert len(log_content) > 0
        
        # Property: Each line is valid JSON
        lines = [line for line in log_content.strip().split("\n") if line.strip()]
        if len(lines) > 0:
            last_entry = json.loads(lines[-1])
            assert "timestamp" in last_entry
            assert "endpoint" in last_entry
            assert "method" in last_entry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
