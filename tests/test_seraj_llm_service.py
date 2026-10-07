"""
Unit tests for Seraj LLM Service (OpenRouter 27B+ integration).
"""

import unittest
from unittest.mock import MagicMock, patch

from seraj_llm_service import SerajLLMService


class TestSerajLLMService(unittest.TestCase):
    def setUp(self):
        self.service = SerajLLMService(api_key="sk-or-v1-testmockkey")

    def test_is_configured(self):
        self.assertTrue(self.service.is_configured())
        empty_service = SerajLLMService(api_key="")
        self.assertFalse(empty_service.is_configured())

    @patch("seraj_llm_service.SerajLLMService._call_openrouter")
    def test_generate_grounded_response_success(self, mock_call):
        mock_call.return_value = "تستحق إجازة سنوية قدرها 21 يوماً وفق المادة 109."

        resp = self.service.generate_grounded_response(
            user_query="كم رصيد إجازاتي؟",
            user_name="خالد",
            laya_decision={"domain_ar": "إدارة الإجازات", "action_type_ar": "استعلام"},
        )
        self.assertIsNotNone(resp)
        self.assertIn("المادة 109", resp)
        mock_call.assert_called_once()

    @patch("seraj_llm_service.SerajLLMService._call_openrouter")
    def test_generate_grounded_response_fallback_on_model_error(self, mock_call):
        # First model fails, second succeeds
        mock_call.side_effect = [Exception("Upstream 429"), "رد بديل بنجاح"]

        resp = self.service.generate_grounded_response(
            user_query="استفسار",
            user_name="سالم",
        )
        self.assertEqual(resp, "رد بديل بنجاح")
        self.assertEqual(mock_call.call_count, 2)


if __name__ == "__main__":
    unittest.main()
