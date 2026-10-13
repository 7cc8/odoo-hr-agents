"""
Bug Condition Exploration Test - Dry-Run Rejection Details Unclear

هذا الاختبار يتحقق من أن dry-run response يحتوي على تفاصيل rejection كافية.
الهدف: إثبات وجود المشكلة قبل تطبيق الإصلاحات.

**CRITICAL**: هذا الاختبار يجب أن **يفشل** على الكود غير المُصلح.
الفشل يُثبت وجود المشكلة.

Expected Behavior on UNFIXED code: الاختبار يفشل لأن:
1. Response لا يحتوي على حقل `rejected_rows_details` مع معلومات غنية
2. Rejection info بسيط (row number + reasons فقط)
3. لا توجد معلومات: name, reason_ar, field, value, suggestion
4. Dashboard HTML لا يحتوي على expandable rejection table

Expected Behavior on FIXED code: الاختبار ينجح لأن:
1. Response يحتوي على `rejected_rows_details` array
2. كل rejection يحتوي على: row_number, name, reason_ar, field, value, suggestion, can_auto_fix
3. Dashboard يعرض جدول تفصيلي قابل للتوسيع

Requirements: 2.5, 2.6, 2.7, 2.8
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys
import json
from openpyxl import Workbook

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web_service import app


class TestBugConditionDryRunDetails:
    """
    Bug Condition Exploration Tests for Dry-Run Rejection Details
    
    These tests verify that dry-run responses currently lack detailed rejection information.
    ALL TESTS SHOULD FAIL on unfixed code - this proves the bug exists.
    """
    
    @pytest.fixture
    def client(self):
        """Create a test client for the web service"""
        return TestClient(app)
    
    @pytest.fixture
    def sample_excel_with_errors(self, tmp_path):
        """
        Create a sample Excel file with intentional errors for testing.
        
        This file will have:
        - Some rows with valid data (should be accepted)
        - Some rows with errors (department not found, invalid job, etc.)
        """
        wb = Workbook()
        ws = wb.active
        ws.title = "Employees"
        
        # Header row
        headers = [
            "Name", "Work Email", "Mobile Phone", "Job Title", 
            "Department", "Company", "Hiring Date", "Nationality", 
            "ID Number", "Gender", "Marital Status"
        ]
        ws.append(headers)
        
        # Valid rows (these should be accepted)
        ws.append([
            "أحمد محمد", "ahmed@company.com", "+966501234567", "Software Engineer",
            "IT Department", "Main Company", "2023-01-15", "Saudi", 
            "1234567890", "Male", "Single"
        ])
        
        ws.append([
            "فاطمة علي", "fatima@company.com", "+966507654321", "HR Manager",
            "HR Department", "Main Company", "2023-02-20", "Saudi",
            "0987654321", "Female", "Married"
        ])
        
        # Invalid rows (these should be rejected)
        # Row 4: Invalid department
        ws.append([
            "محمد أحمد", "mohammad@company.com", "+966503334444", "Sales Manager",
            "قسم المبيعات الخيالي", "Main Company", "2023-03-10", "Saudi",
            "1122334455", "Male", "Single"
        ])
        
        # Row 5: Invalid job title
        ws.append([
            "سارة خالد", "sara@company.com", "+966505556666", "مسمى وظيفي غير موجود",
            "IT Department", "Main Company", "2023-04-05", "Saudi",
            "2233445566", "Female", "Single"
        ])
        
        # Row 6: Invalid email format
        ws.append([
            "عبدالله يوسف", "invalid-email", "+966507778888", "Software Engineer",
            "IT Department", "Main Company", "2023-05-12", "Saudi",
            "3344556677", "Male", "Married"
        ])
        
        # Row 7: Missing required field (no name)
        ws.append([
            "", "noname@company.com", "+966509990000", "Developer",
            "IT Department", "Main Company", "2023-06-18", "Saudi",
            "4455667788", "Male", "Single"
        ])
        
        # Row 8: Invalid date format
        ws.append([
            "نورة سعيد", "noura@company.com", "+966501112222", "Accountant",
            "Finance Department", "Main Company", "not-a-date", "Saudi",
            "5566778899", "Female", "Single"
        ])
        
        file_path = tmp_path / "test_with_errors.xlsx"
        wb.save(file_path)
        return file_path
    
    def test_dry_run_response_missing_detailed_rejection_field(self, client, sample_excel_with_errors):
        """
        Test 1: Dry-run response SHOULD contain `rejected_rows_details` field
        
        Bug Condition: User uploads file with errors and runs dry-run
        Expected on UNFIXED Code: Response has basic rejection info only → TEST FAILS ❌
        Expected on FIXED Code: Response has `rejected_rows_details` array → TEST PASSES ✅
        
        This test EXPECTS the detailed field to exist. If it doesn't, the test FAILS,
        proving the bug exists.
        """
        # Upload the file with errors
        with open(sample_excel_with_errors, "rb") as f:
            response = client.post(
                "/dry-run",
                files={"file": ("test_with_errors.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        
        assert response.status_code == 200, "Dry-run should succeed"
        
        data = response.json()
        
        # Check that we have some rejected rows (the file intentionally has errors)
        summary = data.get("summary", {})
        status_counts = summary.get("status_counts", {})
        rejected_count = status_counts.get("rejected", 0) + status_counts.get("failed", 0)
        
        # We expect at least 3 rejected rows based on our test file
        assert rejected_count >= 3, (
            f"Test file should have at least 3 rejected rows, got {rejected_count}. "
            f"Status counts: {status_counts}"
        )
        
        # *** CRITICAL CHECK: This SHOULD exist on fixed code ***
        # On UNFIXED code, this field will NOT exist, causing the test to FAIL
        assert "rejected_rows_details" in data, (
            f"❌ BUG DETECTED: Response missing 'rejected_rows_details' field. "
            f"Current response has keys: {list(data.keys())}. "
            f"Expected structure: {{'rejected_rows_details': [{{'row_number': N, 'name': '...', 'reason_ar': '...', ...}}]}}. "
            f"This proves that dry-run does not return detailed rejection information."
        )
        
        # Additional verification: the field should be a non-empty list
        rejected_rows_details = data.get("rejected_rows_details", [])
        assert isinstance(rejected_rows_details, list), (
            f"rejected_rows_details should be a list, got {type(rejected_rows_details)}"
        )
        
        assert len(rejected_rows_details) > 0, (
            f"❌ BUG DETECTED: rejected_rows_details exists but is empty. "
            f"Expected at least {rejected_count} items with detailed rejection info."
        )
    
    def test_rejection_details_structure_completeness(self, client, sample_excel_with_errors):
        """
        Test 2: Each rejection detail SHOULD contain comprehensive information
        
        Bug Condition: Rejection details lack user-friendly information
        Expected on UNFIXED Code: Missing fields like name, reason_ar, field, suggestion → TEST FAILS ❌
        Expected on FIXED Code: Each rejection has all required fields → TEST PASSES ✅
        
        Required fields per rejection:
        - row_number: The Excel row number
        - name: Employee name from that row
        - reason_ar: Arabic translation of error reason
        - field: Which field caused the error
        - value: The problematic value
        - suggestion: Suggested fix
        - can_auto_fix: Boolean indicating if Musleh can fix it
        """
        # Upload the file with errors
        with open(sample_excel_with_errors, "rb") as f:
            response = client.post(
                "/dry-run",
                files={"file": ("test_with_errors.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        
        assert response.status_code == 200, "Dry-run should succeed"
        data = response.json()
        
        # Get rejected_rows_details (will fail on unfixed code)
        rejected_rows_details = data.get("rejected_rows_details", [])
        
        assert len(rejected_rows_details) > 0, (
            "This test requires rejected_rows_details to exist (previous test should have failed)"
        )
        
        # Check the FIRST rejection for required fields
        first_rejection = rejected_rows_details[0]
        
        required_fields = [
            "row_number",
            "name", 
            "reason_ar",
            "field",
            "value",
            "suggestion",
            "can_auto_fix"
        ]
        
        missing_fields = [field for field in required_fields if field not in first_rejection]
        
        assert len(missing_fields) == 0, (
            f"❌ BUG DETECTED: Rejection details missing required fields: {missing_fields}. "
            f"Current structure: {first_rejection.keys()}. "
            f"Expected structure should include: {required_fields}. "
            f"This proves that rejection details are not formatted with user-friendly information."
        )
        
        # Verify data types
        assert isinstance(first_rejection["row_number"], int), "row_number should be an integer"
        assert isinstance(first_rejection["name"], str), "name should be a string"
        assert isinstance(first_rejection["reason_ar"], str), "reason_ar should be Arabic text"
        assert isinstance(first_rejection["field"], str), "field should be a string"
        assert isinstance(first_rejection["value"], str), "value should be a string"
        assert isinstance(first_rejection["suggestion"], str), "suggestion should be a string"
        assert isinstance(first_rejection["can_auto_fix"], bool), "can_auto_fix should be a boolean"
        
        # Verify reason_ar contains Arabic text (basic check)
        assert len(first_rejection["reason_ar"]) > 0, "reason_ar should not be empty"
        
        # Verify suggestion provides guidance
        assert len(first_rejection["suggestion"]) > 0, "suggestion should not be empty"
    
    def test_all_rejected_rows_have_details(self, client, sample_excel_with_errors):
        """
        Test 3: ALL rejected rows SHOULD have corresponding rejection details
        
        Bug Condition: Count mismatch between rejected rows and rejection details
        Expected on UNFIXED Code: No rejection details or count mismatch → TEST FAILS ❌
        Expected on FIXED Code: All rejected rows have detailed entries → TEST PASSES ✅
        """
        # Upload the file with errors
        with open(sample_excel_with_errors, "rb") as f:
            response = client.post(
                "/dry-run",
                files={"file": ("test_with_errors.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        
        assert response.status_code == 200, "Dry-run should succeed"
        data = response.json()
        
        # Get rejection count from summary
        summary = data.get("summary", {})
        status_counts = summary.get("status_counts", {})
        rejected_count = status_counts.get("rejected", 0) + status_counts.get("failed", 0)
        
        # Get detailed rejection list
        rejected_rows_details = data.get("rejected_rows_details", [])
        details_count = len(rejected_rows_details)
        
        # The counts should match
        assert details_count == rejected_count, (
            f"❌ BUG DETECTED: Mismatch between rejected count ({rejected_count}) "
            f"and rejection details count ({details_count}). "
            f"Every rejected row should have a corresponding detailed entry. "
            f"This indicates incomplete rejection detail formatting."
        )
        
        # Verify each rejection has unique row numbers (no duplicates or missing)
        row_numbers = [detail["row_number"] for detail in rejected_rows_details]
        unique_row_numbers = set(row_numbers)
        
        assert len(row_numbers) == len(unique_row_numbers), (
            f"❌ Duplicate row numbers found in rejection details: {row_numbers}. "
            f"Each rejected row should appear exactly once."
        )
    
    def test_dashboard_missing_rejection_table_ui(self, client):
        """
        Test 4: Dashboard HTML SHOULD contain expandable rejection details table
        
        Bug Condition: User views dry-run results but sees only counts
        Expected on UNFIXED Code: No rejection table UI → TEST FAILS ❌
        Expected on FIXED Code: Expandable table with columns for details → TEST PASSES ✅
        
        Expected UI elements:
        - Rejection details section/container
        - Table with headers: Row #, Name, Reason (Arabic), Field, Value, Suggested Fix
        - JavaScript to populate table dynamically
        """
        # Fetch the main dashboard HTML
        response = client.get("/")
        
        assert response.status_code == 200, "Dashboard should be accessible"
        
        html_content = response.text.lower()
        
        # Check for SPECIFIC rejection table UI indicators
        # These SHOULD exist on fixed code to display rejection details
        table_ui_indicators = {
            "rejectiondetails": False,  # Expected section ID
            "rejection": False,  # General rejection keyword
            "row #": False,  # Expected table header
            "reason": False,  # Expected table header
            "suggested fix": False,  # Expected table header
            "expandable": False or "expand" in html_content,  # Expandable functionality
            "rejectiontablebody": False,  # Expected table body ID for dynamic population
        }
        
        # Check which indicators are present
        for indicator in list(table_ui_indicators.keys()):
            if indicator in html_content:
                table_ui_indicators[indicator] = True
        
        found_count = sum(table_ui_indicators.values())
        
        # We EXPECT at least 4 specific indicators to confirm the table UI exists
        # On unfixed code, these won't exist, causing this test to FAIL
        assert found_count >= 4, (
            f"❌ BUG DETECTED: Dashboard HTML missing rejection details table UI. "
            f"Found {found_count}/7 indicators: {table_ui_indicators}. "
            f"Expected at least 4 indicators (rejection section, table headers, expandable, etc.) "
            f"This proves the Dashboard does not display detailed rejection information in a table format."
        )
    
    def test_current_response_has_only_basic_rejection_info(self, client, sample_excel_with_errors):
        """
        Test 5: Verify current response structure (baseline documentation)
        
        This test documents the CURRENT (unfixed) response structure.
        It verifies what EXISTS now, to contrast with what SHOULD exist.
        
        Current structure typically has:
        - rows: array with excel_row_number, final_status, reasons
        - summary: with status_counts
        
        This test will PASS on unfixed code (documents current behavior)
        but is useful to show the BEFORE state.
        """
        # Upload the file with errors
        with open(sample_excel_with_errors, "rb") as f:
            response = client.post(
                "/dry-run",
                files={"file": ("test_with_errors.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        
        assert response.status_code == 200, "Dry-run should succeed"
        data = response.json()
        
        # Document current structure
        print("\n" + "="*70)
        print("CURRENT (UNFIXED) DRY-RUN RESPONSE STRUCTURE")
        print("="*70)
        print(f"Top-level keys: {list(data.keys())}")
        
        if "summary" in data:
            print(f"Summary keys: {list(data['summary'].keys())}")
            print(f"Status counts: {data['summary'].get('status_counts', {})}")
        
        if "rows" in data and len(data["rows"]) > 0:
            first_row = data["rows"][0]
            print(f"First row keys: {list(first_row.keys())}")
            print(f"First row sample: {json.dumps(first_row, indent=2, ensure_ascii=False)}")
        
        # Check if rejected_rows_details exists (it shouldn't on unfixed code)
        has_detailed_field = "rejected_rows_details" in data
        print(f"\nHas 'rejected_rows_details' field: {has_detailed_field}")
        
        if not has_detailed_field:
            print("\n⚠️  CONFIRMED: Current response does NOT have rejected_rows_details field")
            print("This is the BUG we are testing for.")
        
        print("="*70 + "\n")
        
        # This assertion documents expected unfixed behavior
        # On unfixed code: this will be TRUE (test passes, documenting the bug)
        # On fixed code: this will be FALSE (test fails, showing the fix is applied)
        # However, we structure it to FAIL on unfixed code to match the pattern
        
        # Actually, let's make this fail on unfixed code to be consistent
        assert "rejected_rows_details" in data, (
            "❌ EXPECTED FAILURE ON UNFIXED CODE: This confirms the bug exists. "
            "The dry-run response does not contain 'rejected_rows_details' field. "
            "Current response only has basic info: rows with excel_row_number, final_status, and reasons array."
        )


def test_integration_summary():
    """
    Integration Test Summary
    
    This test documents the expected behavior of bug condition exploration.
    """
    print("\n" + "="*70)
    print("BUG CONDITION EXPLORATION: DRY-RUN REJECTION DETAILS")
    print("="*70)
    print("\nTest Philosophy:")
    print("- These tests EXPECT dry-run to return detailed rejection information")
    print("- On UNFIXED code: tests FAIL (proving bug exists)")
    print("- On FIXED code: tests PASS (proving bug is resolved)")
    print("\nExpected Test Results on UNFIXED Code:")
    print("1. ❌ FAIL: Response missing 'rejected_rows_details' field")
    print("2. ❌ FAIL: Rejection details lack required fields (name, reason_ar, field, value, suggestion)")
    print("3. ❌ FAIL: Count mismatch or missing details for rejected rows")
    print("4. ❌ FAIL: Dashboard UI missing rejection details table")
    print("5. ❌ FAIL: Current response only has basic rejection info")
    print("\nCounterexamples (what the failures prove):")
    print("- dry_run_report.py produces simple structure without rich details")
    print("- agentic_nodes.py::seraj_meta_orchestration lacks _format_rejection_details() method")
    print("- web_service.py /dry-run endpoint doesn't format rejection details")
    print("- Dashboard HTML doesn't include expandable rejection table UI")
    print("- No Arabic translation of error messages")
    print("- No suggested fixes for common errors")
    print("\n" + "="*70)
    print("INTERPRETATION GUIDE:")
    print("- If ALL tests FAIL → Bug confirmed, proceed to implementation")
    print("- If ANY test PASSES → Feature partially implemented, investigate")
    print("- After fixes: ALL tests should PASS")
    print("="*70 + "\n")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
