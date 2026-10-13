"""
Bug Condition Exploration Test - Template Generation Missing

هذا الاختبار يتحقق من توفر template generation API endpoints والواجهة.
الهدف: إثبات وجود المشكلة قبل تطبيق الإصلاحات.

**CRITICAL**: هذا الاختبار يجب أن **يفشل** على الكود غير المُصلح.
الفشل يُثبت وجود المشكلة.

Expected Behavior on UNFIXED code: الاختبار يفشل لأن:
1. لا يوجد endpoint POST /api/template/generate (يتوقع 200، يجد 404)
2. لا يوجد endpoint GET /api/template/download/<template_id> (يتوقع FileResponse، يجد 404)
3. Dashboard HTML لا يحتوي على UI section لتوليد القوالب (يبحث عن UI، لا يجد)

Expected Behavior on FIXED code: الاختبار ينجح لأن جميع الوظائف موجودة.

Requirements: 2.1, 2.2, 2.3, 2.4
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web_service import app


class TestBugConditionTemplateGeneration:
    """
    Bug Condition Exploration Tests for Template Generation Feature
    
    These tests verify that the template generation feature is currently missing.
    ALL TESTS SHOULD FAIL on unfixed code - this proves the bug exists.
    """
    
    @pytest.fixture
    def client(self):
        """Create a test client for the web service"""
        return TestClient(app)
    
    def test_template_generation_api_endpoint_missing(self, client):
        """
        Test 1: POST /api/template/generate endpoint should exist and return 200
        
        Bug Condition: User attempts to generate a company-specific template via API
        Expected on UNFIXED Code: 404 Not Found → TEST FAILS ❌
        Expected on FIXED Code: 200 OK with template generation response → TEST PASSES ✅
        
        This test EXPECTS the endpoint to exist. If it doesn't, the test FAILS,
        proving the bug exists.
        """
        # Attempt to call the template generation API
        response = client.post(
            "/api/template/generate",
            data={
                "company_id": 1,
                "template_type": "employee",
                "include_example_row": False,
                "language": "ar"
            }
        )
        
        # We EXPECT this endpoint to exist and return 200 (on fixed code)
        # On unfixed code, it will return 404/405, causing this test to FAIL
        assert response.status_code == 200, (
            f"❌ BUG DETECTED: POST /api/template/generate returned {response.status_code} instead of 200. "
            f"This proves the template generation API endpoint is missing. "
            f"Expected structure: {{'status': 'success', 'template_id': '...', 'download_url': '...'}}"
        )
    
    def test_template_download_endpoint_missing(self, client):
        """
        Test 2: GET /api/template/download/<template_id> endpoint should exist and return file
        
        Bug Condition: User attempts to download a previously generated template
        Expected on UNFIXED Code: 404 Not Found → TEST FAILS ❌
        Expected on FIXED Code: 200 OK with file download → TEST PASSES ✅
        """
        # Attempt to download a template by ID
        # Note: This will fail because we can't generate a real template_id without the generation endpoint
        # But we can still test that the download endpoint route exists
        test_template_id = "test-template-id-123"
        response = client.get(f"/api/template/download/{test_template_id}")
        
        # We EXPECT this endpoint to exist (even if it returns 404 for unknown template_id)
        # The key is: it should be a valid route, not returning 404 for route not found
        # On fixed code: might return 404 "template not found" but endpoint exists
        # On unfixed code: returns 404 "route not found"
        
        # If status is 404, check if it's "route not found" (unfixed) vs "template not found" (fixed)
        if response.status_code == 404:
            # Try to determine if it's a routing 404 or a logical 404
            # Routing 404 typically has different error message
            detail = response.json().get("detail", "") if response.headers.get("content-type", "").startswith("application/json") else ""
            
            # If detail contains "Not Found" without specifics, it's likely a routing 404
            assert "template" in detail.lower() or "not found" not in detail.lower(), (
                f"❌ BUG DETECTED: GET /api/template/download/<id> endpoint does not exist (routing 404). "
                f"Expected endpoint to exist and return either a file or 'template not found' error."
            )
        else:
            # On fixed code, we expect either 200 (if template exists) or proper 404 with message
            assert response.status_code in [200, 404], (
                f"❌ Unexpected status code: {response.status_code}"
            )
    
    def test_dashboard_ui_missing_template_section(self, client):
        """
        Test 3: Dashboard HTML SHOULD contain Template Generation UI section
        
        Bug Condition: User opens dashboard looking for template generation feature
        Expected on UNFIXED Code: No template generation section → TEST FAILS ❌
        Expected on FIXED Code: Section with company selector and generate button → TEST PASSES ✅
        """
        # Fetch the main dashboard HTML
        response = client.get("/")
        
        assert response.status_code == 200, "Dashboard should be accessible"
        
        html_content = response.text.lower()
        
        # Check for SPECIFIC template generation UI indicators
        # These SHOULD exist on fixed code
        template_ui_indicators = {
            "template-section": False,  # Expected class name
            "generate template": False,  # Expected button/heading text
            "/api/template/generate": False,  # Expected form action
            "templateform": False,  # Expected form ID
            "template_type": False,  # Expected form field for template type selection
            "include_example_row": False  # Expected checkbox field
        }
        
        # Check which indicators are present
        for indicator in template_ui_indicators.keys():
            if indicator in html_content:
                template_ui_indicators[indicator] = True
        
        found_count = sum(template_ui_indicators.values())
        
        # We EXPECT at least 3 specific indicators to confirm the UI section exists
        # On unfixed code, these won't exist, causing this test to FAIL
        assert found_count >= 3, (
            f"❌ BUG DETECTED: Dashboard HTML missing template generation UI section. "
            f"Found {found_count}/6 indicators: {template_ui_indicators}. "
            f"Expected at least 3 indicators (template-section, generate template button, form, etc.) "
            f"This proves the Dashboard UI for template generation is missing."
        )
    
    def test_existing_download_template_endpoint_is_static(self, client):
        """
        Test 4: Template generation should support company-specific parameters
        
        This test confirms that template generation SHOULD be company-aware.
        
        Bug Condition: Existing endpoint is static, not company-specific
        Expected on UNFIXED Code: Static template regardless of company_id → TEST FAILS ❌
        Expected on FIXED Code: Different templates for different companies → TEST PASSES ✅
        
        Note: This is a softer check - we verify that a company-aware generation
        endpoint exists, not that the static endpoint has changed.
        """
        # The existing static endpoint /api/download-template should still work
        response_static = client.get("/api/download-template")
        assert response_static.status_code == 200, "Static endpoint should still work"
        
        # But the NEW generation endpoint should exist and be company-aware
        # Try to generate templates for two different companies
        response_company1 = client.post(
            "/api/template/generate",
            data={"company_id": 1, "template_type": "employee"}
        )
        
        response_company2 = client.post(
            "/api/template/generate",
            data={"company_id": 2, "template_type": "employee"}
        )
        
        # On FIXED code, both should succeed
        # On UNFIXED code, both will return 404, causing this test to FAIL
        assert response_company1.status_code == 200, (
            f"❌ BUG DETECTED: Dynamic template generation for company 1 failed with {response_company1.status_code}. "
            f"Expected company-specific template generation API to exist."
        )
        
        assert response_company2.status_code == 200, (
            f"❌ BUG DETECTED: Dynamic template generation for company 2 failed with {response_company2.status_code}. "
            f"Expected company-specific template generation API to exist."
        )
        
        # Verify responses contain company-specific data
        data1 = response_company1.json()
        data2 = response_company2.json()
        
        assert "template_id" in data1, "Response should contain template_id"
        assert "download_url" in data1, "Response should contain download_url"
        assert data1["template_id"] != data2["template_id"], (
            "Different companies should generate different template IDs"
        )


def test_integration_summary():
    """
    Integration Test Summary
    
    This test documents the expected behavior of bug condition exploration.
    """
    print("\n" + "="*70)
    print("BUG CONDITION EXPLORATION TEST SUITE")
    print("="*70)
    print("\nTest Philosophy:")
    print("- These tests are written to EXPECT the features to exist")
    print("- On UNFIXED code: tests FAIL (proving bug exists)")
    print("- On FIXED code: tests PASS (proving bug is resolved)")
    print("\nExpected Test Results on UNFIXED Code:")
    print("1. ❌ FAIL: POST /api/template/generate endpoint missing (expects 200, gets 404)")
    print("2. ❌ FAIL: GET /api/template/download/<id> endpoint missing (expects route, gets 404)")
    print("3. ❌ FAIL: Dashboard UI missing template generation section (expects UI elements, finds none)")
    print("4. ❌ FAIL: Company-specific generation missing (expects company-aware API, gets 404)")
    print("\nCounterexamples (what the failures prove):")
    print("- web_service.py does not define /api/template/generate")
    print("- web_service.py does not define /api/template/download/<id>")
    print("- Dashboard HTML does not include template generation form")
    print("- No integration between generate_employee_template.py and API")
    print("- Existing /api/download-template is static, not company-specific")
    print("\n" + "="*70)
    print("INTERPRETATION GUIDE:")
    print("- If ALL tests FAIL → Bug confirmed, proceed to implementation")
    print("- If ANY test PASSES → Feature partially implemented, investigate")
    print("- After fixes: ALL tests should PASS")
    print("="*70 + "\n")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
