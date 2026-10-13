"""
Bug Condition Exploration Test - Auto-Execute Missing

هذا الاختبار يتحقق من أن النظام يُنفذ العمليات تلقائياً عندما لا توجد أخطاء.
الهدف: إثبات وجود المشكلة قبل تطبيق الإصلاحات.

**CRITICAL**: هذا الاختبار يجب أن **يفشل** على الكود غير المُصلح.
الفشل يُثبت وجود المشكلة.

Expected Behavior on UNFIXED code: الاختبار يفشل لأن:
1. Dry-run مع 0 أخطاء (ملف نظيف) لا يُنفذ تلقائياً - ينتظر موافقة المستخدم
2. النظام ينتظر الموافقة حتى عندما جميع الصفوف مقبولة
3. `SerajState` لا يحتوي على حقل `auto_execute` أو قيمته False
4. لا توجد `conditional_execution_node` في LangGraph للتفرع بناءً على عدد الصفوف المرفوضة

Expected Behavior on FIXED code: الاختبار ينجح لأن:
1. Dry-run مع 0 أخطاء يُنفذ تلقائياً بدون انتظار
2. `SerajState` يحتوي على `auto_execute: bool` 
3. توجد `conditional_execution_node` في LangGraph تفحص rejected_rows == 0

Requirements: 2.9, 2.10, 2.11, 2.12
"""

import pytest
from pathlib import Path
import sys
import json
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from graph.state import SerajState


class TestBugConditionAutoExecute:
    """
    Bug Condition Exploration Tests for Auto-Execute Feature
    
    These tests verify that clean dry-runs (0 rejected rows) do NOT auto-execute.
    ALL TESTS SHOULD FAIL on unfixed code - this proves the bug exists.
    """
    
    def test_seraj_state_missing_auto_execute_field(self):
        """
        Test 1: SerajState SHOULD have auto_execute field
        
        Bug Condition: SerajState lacks the auto_execute field to trigger immediate execution
        Expected on UNFIXED Code: Field missing or not defined → TEST FAILS ❌
        Expected on FIXED Code: Field exists in SerajState TypedDict → TEST PASSES ✅
        
        This test EXPECTS the field to exist. If it doesn't, the test FAILS,
        proving the state management bug exists.
        """
        # Check if SerajState has auto_execute field defined
        # TypedDict annotations are stored in __annotations__
        state_annotations = SerajState.__annotations__ if hasattr(SerajState, '__annotations__') else {}
        
        # We EXPECT auto_execute to be defined
        assert 'auto_execute' in state_annotations, (
            f"❌ BUG DETECTED: SerajState is missing 'auto_execute' field. "
            f"This field is required to trigger immediate execution when rejected_rows == 0. "
            f"Current fields: {list(state_annotations.keys())}"
        )
        
        # Verify it has the correct type (Optional[bool])
        import typing
        auto_execute_type = state_annotations.get('auto_execute')
        
        # Check if it's Optional[bool] or bool
        is_bool_type = (
            auto_execute_type == bool or
            (hasattr(typing, 'get_origin') and typing.get_origin(auto_execute_type) == typing.Union) or
            str(auto_execute_type).lower().find('bool') >= 0
        )
        
        assert is_bool_type, (
            f"❌ BUG DETECTED: 'auto_execute' field has incorrect type. "
            f"Expected Optional[bool], got {auto_execute_type}"
        )
    
    def test_seraj_state_missing_user_execution_choice_field(self):
        """
        Test 2: SerajState SHOULD have user_execution_choice field
        
        Bug Condition: SerajState lacks user_execution_choice to track user decisions
        Expected on UNFIXED Code: Field missing → TEST FAILS ❌
        Expected on FIXED Code: Field exists → TEST PASSES ✅
        """
        state_annotations = SerajState.__annotations__ if hasattr(SerajState, '__annotations__') else {}
        
        assert 'user_execution_choice' in state_annotations, (
            f"❌ BUG DETECTED: SerajState is missing 'user_execution_choice' field. "
            f"This field is required to track user approval decisions (execute/fix/cancel). "
            f"Current fields: {list(state_annotations.keys())}"
        )
        
        # Verify it has the correct type (Optional[str])
        user_choice_type = state_annotations.get('user_execution_choice')
        is_str_type = (
            user_choice_type == str or
            str(user_choice_type).lower().find('str') >= 0
        )
        
        assert is_str_type, (
            f"❌ BUG DETECTED: 'user_execution_choice' field has incorrect type. "
            f"Expected Optional[str], got {user_choice_type}"
        )
    
    def test_seraj_state_missing_rejected_rows_details_field(self):
        """
        Test 3: SerajState SHOULD have rejected_rows_details field
        
        Bug Condition: SerajState lacks detailed rejection information
        Expected on UNFIXED Code: Field missing → TEST FAILS ❌
        Expected on FIXED Code: Field exists → TEST PASSES ✅
        """
        state_annotations = SerajState.__annotations__ if hasattr(SerajState, '__annotations__') else {}
        
        assert 'rejected_rows_details' in state_annotations, (
            f"❌ BUG DETECTED: SerajState is missing 'rejected_rows_details' field. "
            f"This field is required to store detailed rejection information for user review. "
            f"Current fields: {list(state_annotations.keys())}"
        )
    
    def test_conditional_execution_node_missing(self):
        """
        Test 4: LangGraph SHOULD have conditional_execution_node
        
        Bug Condition: No branching logic in LangGraph to decide auto-execute vs wait-for-approval
        Expected on UNFIXED Code: Function not found → TEST FAILS ❌
        Expected on FIXED Code: Function exists in agentic_nodes.py → TEST PASSES ✅
        """
        try:
            # Try to import the conditional execution node
            from graph.agentic_nodes import conditional_execution_node
            
            # If we get here, the function exists
            assert callable(conditional_execution_node), (
                f"❌ BUG DETECTED: conditional_execution_node exists but is not callable"
            )
            
        except ImportError as e:
            # Function doesn't exist - this is the expected bug
            pytest.fail(
                f"❌ BUG DETECTED: conditional_execution_node is missing from graph.agentic_nodes. "
                f"This function is required to branch execution based on rejected_rows count. "
                f"Import error: {e}"
            )
        except AttributeError as e:
            pytest.fail(
                f"❌ BUG DETECTED: conditional_execution_node is not defined in graph.agentic_nodes. "
                f"This function is required for conditional execution workflow. "
                f"Attribute error: {e}"
            )
    
    def test_conditional_execution_node_logic(self):
        """
        Test 5: conditional_execution_node SHOULD set auto_execute=True when rejected_rows=0
        
        Bug Condition: Even if node exists, it might not implement auto-execute logic correctly
        Expected on UNFIXED Code: Node missing or logic incorrect → TEST FAILS ❌
        Expected on FIXED Code: Node sets auto_execute=True when no rejections → TEST PASSES ✅
        """
        try:
            from graph.agentic_nodes import conditional_execution_node
        except (ImportError, AttributeError):
            pytest.skip("conditional_execution_node doesn't exist - covered by test_conditional_execution_node_missing")
        
        # Test with clean state (0 rejected rows)
        clean_state: SerajState = {
            'rejected_rows_details': [],  # No rejections
            'excel_validation_stats': {
                'accepted': 50,
                'rejected': 0
            },
            'excel_row_count': 50
        }
        
        result = conditional_execution_node(clean_state)
        
        # We EXPECT auto_execute to be True for clean data
        assert 'auto_execute' in result, (
            f"❌ BUG DETECTED: conditional_execution_node doesn't set 'auto_execute' field. "
            f"Returned keys: {list(result.keys())}"
        )
        
        assert result.get('auto_execute') is True, (
            f"❌ BUG DETECTED: conditional_execution_node should set auto_execute=True "
            f"when rejected_rows=0, but got {result.get('auto_execute')}. "
            f"Clean imports should execute immediately without user approval."
        )
    
    def test_conditional_execution_node_waits_for_approval_on_errors(self):
        """
        Test 6: conditional_execution_node SHOULD set auto_execute=False when rejected_rows>0
        
        Bug Condition: Node should wait for user approval when there are rejections
        Expected on UNFIXED Code: Node missing or always waits → TEST FAILS ❌ on clean data
        Expected on FIXED Code: Node sets auto_execute=False for dirty data → TEST PASSES ✅
        """
        try:
            from graph.agentic_nodes import conditional_execution_node
        except (ImportError, AttributeError):
            pytest.skip("conditional_execution_node doesn't exist - covered by test_conditional_execution_node_missing")
        
        # Test with dirty state (5 rejected rows)
        dirty_state: SerajState = {
            'rejected_rows_details': [
                {'row_number': 1, 'name': 'Test 1', 'reason_ar': 'خطأ'},
                {'row_number': 2, 'name': 'Test 2', 'reason_ar': 'خطأ'},
                {'row_number': 3, 'name': 'Test 3', 'reason_ar': 'خطأ'},
                {'row_number': 4, 'name': 'Test 4', 'reason_ar': 'خطأ'},
                {'row_number': 5, 'name': 'Test 5', 'reason_ar': 'خطأ'},
            ],
            'excel_validation_stats': {
                'accepted': 45,
                'rejected': 5
            },
            'excel_row_count': 50
        }
        
        result = conditional_execution_node(dirty_state)
        
        assert 'auto_execute' in result, (
            f"❌ conditional_execution_node doesn't set 'auto_execute' field. "
            f"Returned keys: {list(result.keys())}"
        )
        
        assert result.get('auto_execute') is False, (
            f"❌ conditional_execution_node should set auto_execute=False "
            f"when rejected_rows>0, but got {result.get('auto_execute')}. "
            f"Dirty imports should wait for user approval."
        )
    
    def test_routing_function_exists_in_build_graph(self):
        """
        Test 7: build_graph.py SHOULD have route_after_conditional_execution function
        
        Bug Condition: No routing logic to branch after conditional execution
        Expected on UNFIXED Code: Function missing → TEST FAILS ❌
        Expected on FIXED Code: Function exists → TEST PASSES ✅
        """
        try:
            from graph.build_graph import route_after_conditional_execution
            
            assert callable(route_after_conditional_execution), (
                f"❌ route_after_conditional_execution exists but is not callable"
            )
            
        except ImportError as e:
            pytest.fail(
                f"❌ BUG DETECTED: route_after_conditional_execution is missing from graph.build_graph. "
                f"This routing function is required to branch execution based on auto_execute flag. "
                f"Import error: {e}"
            )
        except AttributeError as e:
            pytest.fail(
                f"❌ BUG DETECTED: route_after_conditional_execution is not defined in graph.build_graph. "
                f"Attribute error: {e}"
            )
    
    def test_routing_logic_routes_to_execute_on_auto_execute(self):
        """
        Test 8: Routing function SHOULD route to execute_write when auto_execute=True
        
        Bug Condition: Routing might not handle auto_execute correctly
        Expected on UNFIXED Code: Routing missing or incorrect → TEST FAILS ❌
        Expected on FIXED Code: Routes to execute_write → TEST PASSES ✅
        """
        try:
            from graph.build_graph import route_after_conditional_execution
        except (ImportError, AttributeError):
            pytest.skip("route_after_conditional_execution doesn't exist - covered by previous test")
        
        # Test with auto_execute=True
        auto_execute_state: SerajState = {
            'auto_execute': True,
            'user_execution_choice': 'execute'
        }
        
        route = route_after_conditional_execution(auto_execute_state)
        
        # We EXPECT it to route to execution (not wait)
        assert route in ['execute_write', 'katib_write', 'write'], (
            f"❌ BUG DETECTED: route_after_conditional_execution should route to execution "
            f"when auto_execute=True, but returned '{route}'. "
            f"Expected one of: execute_write, katib_write, write"
        )
    
    def test_routing_logic_routes_to_end_on_cancel(self):
        """
        Test 9: Routing function SHOULD route to end when user cancels
        
        Bug Condition: Routing might not handle cancellation
        Expected on UNFIXED Code: Routing missing or incorrect → TEST FAILS ❌
        Expected on FIXED Code: Routes to end → TEST PASSES ✅
        """
        try:
            from graph.build_graph import route_after_conditional_execution
        except (ImportError, AttributeError):
            pytest.skip("route_after_conditional_execution doesn't exist - covered by previous test")
        
        # Test with cancel choice
        cancel_state: SerajState = {
            'auto_execute': False,
            'user_execution_choice': 'cancel'
        }
        
        route = route_after_conditional_execution(cancel_state)
        
        # We EXPECT it to route to end
        assert route == 'end', (
            f"❌ BUG DETECTED: route_after_conditional_execution should route to 'end' "
            f"when user_execution_choice='cancel', but returned '{route}'"
        )
    
    def test_api_approve_conditional_endpoint_missing(self):
        """
        Test 10: API SHOULD have /api/approve-conditional endpoint
        
        Bug Condition: No endpoint to handle user approval decisions after dry-run
        Expected on UNFIXED Code: Endpoint missing (404) → TEST FAILS ❌
        Expected on FIXED Code: Endpoint exists → TEST PASSES ✅
        """
        from fastapi.testclient import TestClient
        from web_service import app
        
        client = TestClient(app)
        
        # Try to call the conditional approval endpoint
        response = client.post(
            "/api/approve-conditional",
            data={
                "operation_id": "test-op-123",
                "choice": "execute"
            }
        )
        
        # We EXPECT this endpoint to exist (even if it fails for other reasons like missing operation)
        # The key is: status should NOT be 404 (route not found)
        assert response.status_code != 404, (
            f"❌ BUG DETECTED: POST /api/approve-conditional endpoint does not exist. "
            f"This endpoint is required to handle user approval decisions. "
            f"Got status {response.status_code}"
        )
        
        # It's OK if it returns 422 (validation error) or 400 (bad request) - those mean the endpoint exists
        assert response.status_code in [200, 400, 422, 500], (
            f"❌ Unexpected status code: {response.status_code}. "
            f"Endpoint should exist and return 200/400/422/500, not {response.status_code}"
        )


def test_integration_summary():
    """
    Integration Test Summary
    
    This test documents the expected behavior of bug condition exploration.
    """
    print("\n" + "="*70)
    print("BUG CONDITION EXPLORATION TEST SUITE - AUTO-EXECUTE")
    print("="*70)
    print("\nTest Philosophy:")
    print("- These tests are written to EXPECT auto-execute functionality to exist")
    print("- On UNFIXED code: tests FAIL (proving bug exists)")
    print("- On FIXED code: tests PASS (proving bug is resolved)")
    print("\nExpected Test Results on UNFIXED Code:")
    print("1. ❌ FAIL: SerajState missing 'auto_execute' field")
    print("2. ❌ FAIL: SerajState missing 'user_execution_choice' field")
    print("3. ❌ FAIL: SerajState missing 'rejected_rows_details' field")
    print("4. ❌ FAIL: conditional_execution_node not found in agentic_nodes.py")
    print("5. ❌ FAIL: conditional_execution_node logic doesn't set auto_execute")
    print("6. ❌ SKIP: (skipped because node doesn't exist)")
    print("7. ❌ FAIL: route_after_conditional_execution not found in build_graph.py")
    print("8. ❌ SKIP: (skipped because routing function doesn't exist)")
    print("9. ❌ SKIP: (skipped because routing function doesn't exist)")
    print("10. ❌ FAIL: POST /api/approve-conditional endpoint missing (404)")
    print("\nCounterexamples (what the failures prove):")
    print("- graph/state.py::SerajState lacks auto_execute, user_execution_choice, rejected_rows_details")
    print("- graph/agentic_nodes.py lacks conditional_execution_node function")
    print("- graph/build_graph.py lacks route_after_conditional_execution function")
    print("- web_service.py lacks /api/approve-conditional endpoint")
    print("- No conditional branching logic based on rejected_rows count")
    print("\nRoot Cause Analysis:")
    print("The system always waits for user approval, even when dry-run has 0 errors.")
    print("This creates unnecessary delays and poor user experience for clean imports.")
    print("\n" + "="*70)
    print("INTERPRETATION GUIDE:")
    print("- If ALL tests FAIL → Bug confirmed, proceed to implementation")
    print("- If ANY test PASSES → Feature partially implemented, investigate")
    print("- After fixes: ALL tests should PASS")
    print("="*70 + "\n")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
