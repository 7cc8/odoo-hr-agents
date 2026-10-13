"""
Bug Condition Exploration Test: State Fields Missing

This test verifies that `SerajState` in `graph/state.py` lacks the required fields:
- rejected_rows_details
- user_execution_choice
- auto_execute

CRITICAL: This test is EXPECTED TO FAIL on unfixed code.
Failure confirms the bug exists (missing fields in SerajState).
After fixes are applied, this test should PASS.

Requirements: 2.17, 2.18, 2.19
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, get_type_hints

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest


def test_seraj_state_has_rejected_rows_details_field():
    """
    Test that SerajState TypedDict includes rejected_rows_details field.
    
    Expected to FAIL on unfixed code (field missing).
    Expected to PASS after fix is applied.
    """
    from graph.state import SerajState
    
    # Get type hints from SerajState
    type_hints = get_type_hints(SerajState)
    
    # Check that rejected_rows_details field exists
    assert "rejected_rows_details" in type_hints, (
        "SerajState is missing 'rejected_rows_details' field. "
        "This confirms bug: state cannot store detailed rejection information."
    )
    
    # Verify the type is Optional[List[Dict[str, Any]]]
    field_type = str(type_hints["rejected_rows_details"])
    assert "List" in field_type, (
        f"rejected_rows_details should be a List type, got: {field_type}"
    )
    assert "Dict" in field_type, (
        f"rejected_rows_details should be a List[Dict], got: {field_type}"
    )


def test_seraj_state_has_user_execution_choice_field():
    """
    Test that SerajState TypedDict includes user_execution_choice field.
    
    Expected to FAIL on unfixed code (field missing).
    Expected to PASS after fix is applied.
    """
    from graph.state import SerajState
    
    # Get type hints from SerajState
    type_hints = get_type_hints(SerajState)
    
    # Check that user_execution_choice field exists
    assert "user_execution_choice" in type_hints, (
        "SerajState is missing 'user_execution_choice' field. "
        "This confirms bug: state cannot track user's approval decision (execute/fix/cancel)."
    )
    
    # Verify the type is Optional[str]
    field_type = str(type_hints["user_execution_choice"])
    assert "str" in field_type, (
        f"user_execution_choice should be a str type, got: {field_type}"
    )


def test_seraj_state_has_auto_execute_field():
    """
    Test that SerajState TypedDict includes auto_execute field.
    
    Expected to FAIL on unfixed code (field missing).
    Expected to PASS after fix is applied.
    """
    from graph.state import SerajState
    
    # Get type hints from SerajState
    type_hints = get_type_hints(SerajState)
    
    # Check that auto_execute field exists
    assert "auto_execute" in type_hints, (
        "SerajState is missing 'auto_execute' field. "
        "This confirms bug: state cannot flag operations for auto-execution."
    )
    
    # Verify the type is Optional[bool]
    field_type = str(type_hints["auto_execute"])
    assert "bool" in field_type, (
        f"auto_execute should be a bool type, got: {field_type}"
    )


def test_state_instance_can_access_new_fields():
    """
    Test that a SerajState instance can access the new fields without KeyError.
    
    This test creates a state dict and tries to access the new fields.
    Expected to FAIL on unfixed code (accessing undefined fields).
    Expected to PASS after fix is applied.
    """
    from graph.state import SerajState
    
    # Create a sample state with the new fields
    state: SerajState = {
        "operation_id": "test-123",
        "rejected_rows_details": [
            {
                "row_number": 1,
                "name": "Test Employee",
                "reason_ar": "خطأ في البيانات",
                "field": "department",
                "value": "Invalid Dept",
                "suggestion": "Use 'Sales' department",
                "can_auto_fix": True
            }
        ],
        "user_execution_choice": "execute",
        "auto_execute": True
    }
    
    # Try to access the new fields - should not raise KeyError
    try:
        rejected_details = state.get("rejected_rows_details")
        user_choice = state.get("user_execution_choice")
        auto_exec = state.get("auto_execute")
        
        # Verify values are accessible
        assert rejected_details is not None, "rejected_rows_details should be accessible"
        assert user_choice == "execute", "user_execution_choice should be accessible"
        assert auto_exec is True, "auto_execute should be accessible"
        
    except KeyError as e:
        pytest.fail(
            f"KeyError when accessing new field: {e}. "
            "This confirms bug: fields are not defined in SerajState."
        )


def test_all_three_fields_present_together():
    """
    Integration test: verify all three fields are present in SerajState.
    
    Expected to FAIL on unfixed code (all three fields missing).
    Expected to PASS after fix is applied.
    """
    from graph.state import SerajState
    
    # Get type hints from SerajState
    type_hints = get_type_hints(SerajState)
    
    required_fields = [
        "rejected_rows_details",
        "user_execution_choice", 
        "auto_execute"
    ]
    
    missing_fields = [field for field in required_fields if field not in type_hints]
    
    assert len(missing_fields) == 0, (
        f"SerajState is missing {len(missing_fields)} required field(s): {missing_fields}. "
        "This confirms bug: state management incomplete for conditional execution workflow."
    )


def test_state_fields_have_optional_types():
    """
    Test that all new fields are Optional (can be None).
    
    Expected to FAIL on unfixed code (fields don't exist).
    Expected to PASS after fix is applied.
    """
    from graph.state import SerajState
    
    # Get type hints from SerajState
    type_hints = get_type_hints(SerajState)
    
    # All three fields should be Optional
    required_fields = [
        "rejected_rows_details",
        "user_execution_choice",
        "auto_execute"
    ]
    
    for field in required_fields:
        if field in type_hints:
            field_type = str(type_hints[field])
            # Check if Optional or Union with None
            assert "Optional" in field_type or "None" in field_type, (
                f"Field '{field}' should be Optional, got: {field_type}"
            )


if __name__ == "__main__":
    # Run tests and display results
    pytest.main([__file__, "-v", "--tb=short"])
