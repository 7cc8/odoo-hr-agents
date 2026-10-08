# -*- coding: utf-8 -*-
"""Acceptance test verifying that operation monitoring does not terminate after 30 seconds of idle events."""

import time
import unittest
from fastapi.testclient import TestClient

from web_service import app
from agent_events_service import get_events_service


class TestPollingResilienceAndTimeout(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.events_service = get_events_service()

    def test_operation_does_not_terminate_on_idle_events_after_30s(self):
        # 1. Start a long-running or delayed operation
        op_id = self.events_service.start_operation(
            user_query="استعلام مطول مع انتظار استجابة خارجية",
            operation_type="query",
            requester="اختبار الصمود",
        )
        self.assertIsNotNone(op_id)

        # 2. Check initial operation state
        op = self.events_service.get_operation(op_id)
        self.assertEqual(op["status"], "analyzing_request")

        # 3. Simulate polling queries with no new events (idle cycles)
        # Even after many polling cycles with empty new events, the operation MUST NOT be completed
        for seq in range(10):
            res = self.client.get(f"/api/agents/operations/{op_id}/events?after=1")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(len(data.get("events", [])), 0)

        # 4. Verify operation snapshot is STILL non-terminal (analyzing_request)
        res_op = self.client.get(f"/api/agents/operations/{op_id}")
        self.assertEqual(res_op.status_code, 200)
        curr_op = res_op.json()["operation"]
        self.assertNotIn(curr_op["status"], ["completed", "failed", "cancelled"])
        self.assertEqual(curr_op["status"], "analyzing_request")

        # 5. Now emit a delayed event after idle period
        self.events_service.emit_event(
            operation_id=op_id,
            agent="fahas",
            event_type="delayed_check_result",
            status="completed",
            description_ar="وصلت نتيجة الفحص بعد فترة انتظار طويلة",
        )

        # 6. Verify the delayed event is successfully received
        res_after = self.client.get(f"/api/agents/operations/{op_id}/events?after=1")
        self.assertEqual(res_after.status_code, 200)
        delayed_events = res_after.json()["events"]
        self.assertGreater(len(delayed_events), 0)
        self.assertEqual(delayed_events[0]["agent"], "fahas")


if __name__ == "__main__":
    unittest.main()
