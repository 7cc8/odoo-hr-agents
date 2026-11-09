"""
Bug Condition Exploration Test - Agent Timeline Hidden
========================================================

**CRITICAL**: هذا الاختبار يجب أن يفشل على الكود غير المُصلح - الفشل يُثبت وجود المشكلة.
**DO NOT attempt to fix the test or code when it fails**.

الهدف (GOAL): كشف counterexamples تُثبت أن agent execution غير مرئي للمستخدمين.

Expected Outcome: الاختبار **يفشل** (هذا صحيح - يُثبت وجود المشكلة):
- Endpoint `/api/agent-traces/{operation_id}` مفقود (404)
- Dashboard لا يحتوي على timeline UI component
- Agents لا تُصدر events مُهيكلة بالشكل المطلوب للعرض في Dashboard

Counterexamples to Document:
- لا يوجد API endpoint `/api/agent-traces/{operation_id}`
- لا يوجد integration بين agent_events_service.py والـ Dashboard
- Dashboard HTML لا يحتوي على "Agent Timeline" section
- Events المُسجلة حالياً غير كافية للعرض التفاعلي المطلوب

_Requirements: 2.13, 2.14, 2.15, 2.16_
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import re


@pytest.fixture
def client():
    """Create test client for web service."""
    from web_service import app
    return TestClient(app)


@pytest.fixture
def mock_operation_id():
    """Generate a mock operation ID for testing."""
    return "op_test_1234567890"


class TestAgentTimelineHidden:
    """
    Validation Test Suite (Phase 4.1.4): Agent Timeline مرئي ومتاح للمستخدمين
    
    هذه الاختبارات تتأكد من أن agent execution traces متاحة للمستخدمين:
    1. API endpoint موجود ويعمل (200 OK)
    2. Dashboard UI يحتوي على Agent Timeline section
    3. Events منظمة ومسجلة بشكل صحيح
    4. Real-time polling mechanism موجود
    """

    def test_agent_traces_endpoint_returns_404(self, client, mock_operation_id):
        """
        Validation 1: API endpoint `/api/agent-traces/{operation_id}` موجود ويُرجع 200 OK
        """
        response = client.get(f"/api/agent-traces/{mock_operation_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "operation_id" in data
        assert "events" in data
        assert isinstance(data["events"], list)
        print(f"✓ Verified: /api/agent-traces/{mock_operation_id} returns 200 with events list")

    def test_dashboard_lacks_agent_timeline_section(self, client):
        """
        Validation 2: Dashboard HTML يحتوي على Agent Timeline section
        """
        response = client.get("/")
        assert response.status_code == 200, "Dashboard should be accessible"
        
        html_content = response.text.lower()
        
        # Verify Agent Timeline section exists
        assert "agent timeline" in html_content or "agenttimeline" in html_content, (
            "Dashboard should contain 'Agent Timeline' section"
        )
        assert "timelinecontainer" in html_content or "timeline-container" in html_content, (
            "Dashboard should contain timeline container element"
        )
        js_res = client.get("/js/dashboard.js")
        combined = (html_content + " " + js_res.text.lower()) if js_res.status_code == 200 else html_content
        assert "updateagenttimeline" in combined, (
            "Dashboard should contain updateAgentTimeline JavaScript function"
        )
        print("✓ Verified: Dashboard contains Agent Timeline section and JS functions")

    def test_agent_events_service_exists_but_not_integrated(self):
        """
        Validation 3: agent_events_service مدمج في web_service.py أو راوترات api/routers/
        """
        audit_router_path = Path(__file__).parent.parent / "api" / "routers" / "audit.py"
        web_service_path = Path(__file__).parent.parent / "web_service.py"
        combined_content = ""
        if audit_router_path.exists():
            combined_content += audit_router_path.read_text(encoding="utf-8")
        if web_service_path.exists():
            combined_content += "\n" + web_service_path.read_text(encoding="utf-8")
            
        assert "/api/agent-traces" in combined_content, (
            "web_service / audit router must include /api/agent-traces endpoint"
        )
        assert "get_agent_events" in combined_content or "agent_events_service" in combined_content, (
            "web_service / audit router must use agent events service"
        )
        print("✓ Verified: agent_events_service is properly integrated into web_service/api routers")

    def test_agents_dont_emit_dashboard_ready_events(self, mock_operation_id):
        """
        Validation 4: Agents يُصدرون structured events جاهزة للـ Dashboard
        """
        from agents.agent_events_service import emit_agent_event, get_agent_events, clear_agent_events
        
        clear_agent_events(mock_operation_id)
        
        emit_agent_event(
            operation_id=mock_operation_id,
            agent="Fahas (Query)",
            action="perceive",
            reasoning="Understanding data requirements...",
            status="in_progress"
        )
        
        emit_agent_event(
            operation_id=mock_operation_id,
            agent="Fahas (Query)",
            action="execute",
            decision="Fetched 45 records",
            status="success"
        )
        
        events = get_agent_events(mock_operation_id)
        assert len(events) == 2, f"Expected 2 events, got {len(events)}"
        assert events[0]["agent"] == "Fahas (Query)"
        assert events[0]["action"] == "perceive"
        assert events[1]["status"] == "success"
        
        clear_agent_events(mock_operation_id)
        print("✓ Verified: Events emitted and retrieved successfully with structured data")

    def test_no_real_time_timeline_updates(self, client):
        """
        Validation 5: وجود real-time timeline updates polling في Dashboard
        """
        response = client.get("/")
        assert response.status_code == 200
        
        html_content = response.text.lower()
        js_res = client.get("/js/dashboard.js")
        combined = (html_content + " " + js_res.text.lower()) if js_res.status_code == 200 else html_content
        assert "setinterval" in combined and "updateagenttimeline" in combined, (
            "Dashboard should have polling mechanism for timeline updates"
        )
        print("✓ Verified: Dashboard has polling mechanism for agent timeline")


class TestAgentTimelineBugSummary:
    """
    Summary Test: التأكد من عمل جميع ميزات Agent Timeline
    """
    
    def test_comprehensive_bug_condition_summary(self, client, mock_operation_id):
        """
        Comprehensive check confirming timeline features are operational.
        """
        indicators = []
        
        # 1. Check API endpoint
        response = client.get(f"/api/agent-traces/{mock_operation_id}")
        assert response.status_code == 200
        indicators.append("✓ API endpoint /api/agent-traces/{operation_id} returns 200")
        
        # 2. Check Dashboard UI
        response = client.get("/")
        html = response.text.lower()
        assert "agent timeline" in html or "agenttimeline" in html
        indicators.append("✓ Dashboard has Agent Timeline UI")
        
        # 3. Check web_service / audit router integration
        audit_router_path = Path(__file__).parent.parent / "api" / "routers" / "audit.py"
        web_service_path = Path(__file__).parent.parent / "web_service.py"
        combined_content = ""
        if audit_router_path.exists():
            combined_content += audit_router_path.read_text(encoding="utf-8")
        if web_service_path.exists():
            combined_content += "\n" + web_service_path.read_text(encoding="utf-8")
        assert "/api/agent-traces" in combined_content
        indicators.append("✓ web_service / audit router has agent-traces endpoint")
        
        # 4. Check polling mechanism
        js_res = client.get("/js/dashboard.js")
        combined = (html + " " + js_res.text.lower()) if js_res.status_code == 200 else html
        assert "setinterval" in combined and "updateagenttimeline" in combined
        indicators.append("✓ Dashboard has polling for timeline updates")
        
        print("\n" + "="*70)
        print("AGENT TIMELINE VALIDATION SUMMARY (Phase 4.1.4)")
        print("="*70)
        for ind in indicators:
            print(ind)
        print("="*70)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
