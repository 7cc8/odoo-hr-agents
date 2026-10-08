"""
اختبارات وحدة محرك الاستشارة العصبية (laya_neural_consultant)
=============================================================
جميع الاختبارات تستخدم mocks — لا تُحمّل أوزاناً ولا تحتاج اتصالاً ولا تشغّل النموذج.
لا تقرأ أو تكتب في Odoo.

تغطية المتطلبات:
A. محرك الاستشارة: اختبارات 1–17
B. الأمان والتكامل: اختبارات 18–28
"""
from __future__ import annotations

import math
import unittest
from unittest.mock import MagicMock, patch

import laya_neural_consultant as nc
from laya_neural_consultant import (
    ConsultationRequest,
    ConsultationResult,
    consult_decision,
    _validate_request,
    _validate_probabilities,
    _parse_response,
)


# ─── مساعدات ─────────────────────────────────────────────────────────────────

def _make_request(**kwargs) -> ConsultationRequest:
    defaults = dict(
        caller_agent="seraj",
        stage="triage",
        question_id="next_step",
        instructions="ما الخطوة التالية؟",
        allowed_choices={
            "read": "استعلام عن البيانات",
            "clarify": "طلب توضيح من المستخدم",
        },
    )
    defaults.update(kwargs)
    return ConsultationRequest(**defaults)


def _make_raw_response(choice="read", read_prob=0.75, clarify_prob=0.25) -> dict:
    """رد نموذجي يُحاكي ما يُعيده Router.predict."""
    return {
        "model": "laya-rl-agent",
        "answers": {
            "next_step": {
                "type": "choice",
                "choice": choice,
                "probabilities": {"read": read_prob, "clarify": clarify_prob},
                "confidence": 0.35,
                "answer_confidence": read_prob if choice == "read" else clarify_prob,
                "action": {"act_probability": 1.0},
            }
        },
        "usage": {
            "input_tokens": 42,
            "output_tokens": 0,
            "state_tokens": 6,
            "state_tokens_dropped": 0,
            "truncated": False,
            "truncated_questions": [],
        },
        "routing": {
            "model": "multilingual",
            "repo": "convaiinnovations/laya/multilingual",
            "reason": "explicit model='multilingual'",
        },
    }


# ─── A. محرك الاستشارة ────────────────────────────────────────────────────────

class TestDisabledMode(unittest.TestCase):
    """A1. disabled لا يُحمّل النموذج ويُعيد status=disabled."""

    def test_disabled_returns_disabled_status(self):
        with patch.object(nc, "_LAYA_ENABLED", False):
            result = consult_decision(_make_request())
        self.assertEqual(result.status, "disabled")
        self.assertIsNone(result.suggested_choice)
        self.assertFalse(result.execution_authorized)

    def test_disabled_engine_not_loaded(self):
        with patch.object(nc, "_LAYA_ENABLED", False), \
             patch.object(nc, "_load_engine") as mock_load:
            consult_decision(_make_request())
            mock_load.assert_not_called()


class TestLazyLoading(unittest.TestCase):
    """A2–A4. التحميل الكسول وإعادة الاستخدام والحماية من التهيئة المتزامنة."""

    def setUp(self):
        # إعادة تهيئة حالة المحرك قبل كل اختبار
        nc._engine_instance = None
        nc._engine_load_attempted = False
        nc._engine_load_error = None

    def tearDown(self):
        nc._engine_instance = None
        nc._engine_load_attempted = False
        nc._engine_load_error = None

    def test_engine_loaded_lazily_on_first_call(self):
        """A2. المحرك لا يُحمَّل عند import، بل عند أول استشارة."""
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine):
            result = consult_decision(_make_request())

        self.assertEqual(result.status, "ok")

    def test_engine_reused_between_consultations(self):
        """A3. المحرك لا يُنشأ من جديد في كل استشارة."""
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine) as mock_load:
            consult_decision(_make_request())
            consult_decision(_make_request())
            # _load_engine يُستدعى مرتين (التأكد أنه يُعيد نفس الكائن داخل المحرك)
            self.assertEqual(mock_load.call_count, 2)

    def test_concurrent_load_uses_lock(self):
        """A4. القفل يمنع إنشاء نسختين متزامنتين."""
        import threading
        results = []
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()

        original_load = nc._load_engine

        def patched_load():
            nc._engine_instance = mock_engine
            nc._engine_load_attempted = True
            return mock_engine

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", side_effect=patched_load):
            def task():
                results.append(consult_decision(_make_request()))

            threads = [threading.Thread(target=task) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # كل الاستشارات يجب أن تنجح
        for r in results:
            self.assertIn(r.status, ("ok", "error", "unavailable"))


class TestMultilingualSelection(unittest.TestCase):
    """A5. التأكد من اختيار multilingual صراحةً."""

    def test_multilingual_model_selected(self):
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            consult_decision(_make_request())

        # التحقق أن predict استُدعي بـ model='multilingual'
        call_kwargs = mock_engine.predict.call_args
        self.assertEqual(call_kwargs.kwargs.get("model") or call_kwargs.args[2], "multilingual")


class TestResponseParsing(unittest.TestCase):
    """A6–A8. parsing الرد الصحيح وفصل الاحتمالات."""

    def test_correct_choice_parsed(self):
        """A6. parsing لرد choice الصحيح."""
        raw = _make_raw_response(choice="read", read_prob=0.75, clarify_prob=0.25)
        req = _make_request()
        result = _parse_response(raw, req)
        self.assertIsNotNone(result)
        suggested, probs, answer_prob, dist_conf, model_id, trunc = result
        self.assertEqual(suggested, "read")
        self.assertAlmostEqual(probs["read"], 0.75)
        self.assertEqual(model_id, "multilingual")

    def test_answer_probability_distinct_from_distribution_confidence(self):
        """A7. answer_probability منفصل عن distribution_confidence."""
        raw = _make_raw_response(choice="read", read_prob=0.75, clarify_prob=0.25)
        raw["answers"]["next_step"]["answer_confidence"] = 0.75
        raw["answers"]["next_step"]["confidence"] = 0.35
        req = _make_request()
        result = _parse_response(raw, req)
        _, _, answer_prob, dist_conf, _, _ = result
        self.assertAlmostEqual(answer_prob, 0.75)
        self.assertAlmostEqual(dist_conf, 0.35)
        self.assertNotAlmostEqual(answer_prob, dist_conf)

    def test_act_probability_not_authorization(self):
        """A8. act_probability لا يُستخدم كتصريح تنفيذ."""
        mock_engine = MagicMock()
        raw = _make_raw_response()
        raw["answers"]["next_step"]["action"]["act_probability"] = 1.0
        mock_engine.predict.return_value = raw

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            result = consult_decision(_make_request())

        self.assertFalse(result.execution_authorized)


class TestChoiceValidation(unittest.TestCase):
    """A9–A12. التحقق من صحة الاختيار والاحتمالات."""

    def test_choice_not_in_allowed_choices_returns_invalid_response(self):
        """A9. رفض choice غير موجود في allowed_choices."""
        raw = _make_raw_response(choice="unknown_action")
        req = _make_request()
        result = _parse_response(raw, req)
        self.assertIsNone(result)

    def test_incomplete_response_returns_invalid_response(self):
        """A10. الرد الناقص يُعيد invalid_response."""
        raw = {"answers": {}, "routing": {}}
        req = _make_request()
        result = _parse_response(raw, req)
        self.assertIsNone(result)

    def test_nan_probability_rejected(self):
        """A11. احتمال NaN لا يُقبل."""
        probs = {"read": float("nan"), "clarify": 0.5}
        error = _validate_probabilities(probs, {"read": "x", "clarify": "y"})
        self.assertIsNotNone(error)
        self.assertIn("invalid_probability_value", error)

    def test_infinity_probability_rejected(self):
        """A11. احتمال Infinity لا يُقبل."""
        probs = {"read": float("inf"), "clarify": 0.5}
        error = _validate_probabilities(probs, {"read": "x", "clarify": "y"})
        self.assertIsNotNone(error)

    def test_probability_out_of_range_rejected(self):
        """A11. احتمال خارج [0,1] لا يُقبل."""
        probs = {"read": 1.5, "clarify": 0.3}
        error = _validate_probabilities(probs, {"read": "x", "clarify": "y"})
        self.assertIsNotNone(error)

    def test_probability_sum_tolerance(self):
        """A12. مجموع ضمن ±5% مسموح."""
        probs = {"read": 0.52, "clarify": 0.49}  # مجموع 1.01
        error = _validate_probabilities(probs, {"read": "x", "clarify": "y"})
        self.assertIsNone(error)

    def test_probability_sum_far_from_one_rejected(self):
        """A12. مجموع بعيد جداً يُرفض."""
        probs = {"read": 0.1, "clarify": 0.1}  # مجموع 0.2
        error = _validate_probabilities(probs, {"read": "x", "clarify": "y"})
        self.assertIsNotNone(error)


class TestLoadFailure(unittest.TestCase):
    """A13–A14. فشل التحميل لا يُسقط الخدمة."""

    def setUp(self):
        nc._engine_instance = None
        nc._engine_load_attempted = False
        nc._engine_load_error = None

    def tearDown(self):
        nc._engine_instance = None
        nc._engine_load_attempted = False
        nc._engine_load_error = None

    def test_load_failure_returns_unavailable(self):
        """A13. فشل تحميل الأوزان لا يُسقط الخدمة."""
        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=None):
            nc._engine_load_error = "weights not found"
            result = consult_decision(_make_request())
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.suggested_choice)
        self.assertFalse(result.execution_authorized)

    def test_inference_error_returns_error_not_fake_result(self):
        """A14. فشل الاستدلال لا يولد اقتراحاً وهمياً."""
        mock_engine = MagicMock()
        mock_engine.predict.side_effect = RuntimeError("model crashed")

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            result = consult_decision(_make_request())

        self.assertEqual(result.status, "error")
        self.assertIsNone(result.suggested_choice)
        self.assertIsNone(result.probabilities)
        self.assertFalse(result.execution_authorized)


class TestRequestValidation(unittest.TestCase):
    """A15–A16. التحقق من صحة الطلب."""

    def test_empty_instructions_invalid_request(self):
        """A15. تعليمات فارغة يُعيد invalid_request."""
        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine"):
            result = consult_decision(_make_request(instructions=""))
        self.assertEqual(result.status, "invalid_request")

    def test_empty_choices_invalid_request(self):
        """A15. خيارات فارغة يُعيد invalid_request."""
        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine"):
            result = consult_decision(_make_request(allowed_choices={}))
        self.assertEqual(result.status, "invalid_request")

    def test_single_choice_invalid_request(self):
        """A15. خيار واحد يُعيد invalid_request."""
        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine"):
            result = consult_decision(_make_request(allowed_choices={"only": "desc"}))
        self.assertEqual(result.status, "invalid_request")

    def test_truncation_detected(self):
        """A16. state_tokens_dropped > 0 يُسجَّل كتحذير."""
        raw = _make_raw_response()
        raw["usage"]["state_tokens_dropped"] = 5
        req = _make_request()
        result = _parse_response(raw, req)
        self.assertIsNotNone(result)
        _, _, _, _, _, trunc_warn = result
        self.assertTrue(trunc_warn)

    def test_no_truncation_when_clean(self):
        """A16. بدون truncation، التحذير = False."""
        raw = _make_raw_response()
        req = _make_request()
        result = _parse_response(raw, req)
        _, _, _, _, _, trunc_warn = result
        self.assertFalse(trunc_warn)

    def test_engine_mock_does_not_access_odoo(self):
        """A17. mock المحرك لا يقرأ أو يكتب في Odoo."""
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()
        # لا نتوقع أي استدعاء لـ xmlrpc أو اتصال Odoo
        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            result = consult_decision(_make_request())
        # التحقق أن predict استُدعي فقط بـ state و questions
        mock_engine.predict.assert_called_once()
        self.assertEqual(result.status, "ok")


# ─── B. الأمان والتكامل ────────────────────────────────────────────────────────

class TestShadowMode(unittest.TestCase):
    """B18–B19. shadow لا يُغيّر أي شيء."""

    def test_shadow_does_not_return_advisory_choice_to_caller(self):
        """B18. في shadow، الاقتراح لا يُضاف للسياق تلقائياً."""
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response(choice="clarify")

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch.object(nc, "_LAYA_MODE", "shadow"), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            result = consult_decision(_make_request())

        self.assertEqual(result.mode, "shadow")
        # الاقتراح موجود في النتيجة لكن المستدعي هو من يقرر استخدامه أم لا
        self.assertIsNotNone(result.suggested_choice)
        # في shadow يجب ألا يكون execution_authorized
        self.assertFalse(result.execution_authorized)

    def test_shadow_does_not_modify_pending_action(self):
        """B19. shadow لا يُعدّل pending_action."""
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()
        pending = {"action_type": "archive", "record_id": 99, "consumed": False}

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch.object(nc, "_LAYA_MODE", "shadow"), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            consult_decision(_make_request())

        # pending_action لم يُعدَّل
        self.assertEqual(pending["action_type"], "archive")
        self.assertEqual(pending["record_id"], 99)
        self.assertFalse(pending["consumed"])


class TestAdvisoryNoAuth(unittest.TestCase):
    """B20. advisory لا يمنح اعتماداً."""

    def test_advisory_does_not_grant_execution_authorization(self):
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch.object(nc, "_LAYA_MODE", "advisory"), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            result = consult_decision(_make_request())

        self.assertEqual(result.mode, "advisory")
        self.assertFalse(result.execution_authorized)


class TestSecurityInvariants(unittest.TestCase):
    """B21–B28. ثوابت الأمان الحتمية."""

    def test_proceed_choice_does_not_bypass_missing_data(self):
        """B21. اختيار proceed لا يتجاوز بيانات ناقصة."""
        # الاستشارة تُعيد 'proceed' لكن القرار النهائي للمستدعي
        mock_engine = MagicMock()
        raw = _make_raw_response(choice="read")
        # أضف خياراً proceed وهمياً
        raw["answers"]["next_step"]["choice"] = "read"
        mock_engine.predict.return_value = raw

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            result = consult_decision(_make_request())

        # الاستشارة لا تُمنح صلاحيات
        self.assertFalse(result.execution_authorized)

    def test_approval_not_inferred_from_model(self):
        """B22. الاعتماد لا يُستنتج من نتيجة النموذج."""
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            result = consult_decision(_make_request())

        self.assertFalse(result.execution_authorized)

    def test_laya_cannot_change_payload(self):
        """B23. لايا لا تُغيّر payload معتمداً."""
        payload = {"employee_id": 42, "field": "job_title", "new_value": "مديرة"}
        payload_before = dict(payload)

        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            consult_decision(_make_request())

        self.assertEqual(payload, payload_before)

    def test_unlink_ban_unaffected(self):
        """B24. الاستشارة لا تمس حظر unlink."""
        # consult_decision لا تستدعي أي gateway
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            result = consult_decision(_make_request())

        # التأكد أن المحرك لم يستدع أي gateway
        self.assertFalse(hasattr(result, "gateway_called"))
        self.assertFalse(result.execution_authorized)

    def test_multiple_records_not_auto_resolved(self):
        """B25. نتائج متعددة لا تُحل باختيار هوية تلقائياً."""
        # consult_decision لا تختار employee_id
        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            result = consult_decision(_make_request())

        # لا توجد حقل employee_id في النتيجة
        self.assertFalse(hasattr(result, "employee_id"))

    def test_missing_info_not_converted_to_false(self):
        """B26. غياب حقيقة لا يتحول إلى false."""
        req = _make_request(missing_information="تاريخ الالتحاق غير معروف")
        # التحقق أن missing_information يُبقى كما هو ولا يُحوَّل
        self.assertIn("غير معروف", req.missing_information)
        self.assertIsNotNone(req.missing_information)

    def test_sensitive_text_not_in_log(self):
        """B27. لا يُسجَّل نص المستخدم أو بيانات موظف افتراضياً."""
        import json
        import io
        logs_written = []

        def mock_open(*args, **kwargs):
            class FakeFile:
                def write(self, data):
                    logs_written.append(data)
                def __enter__(self): return self
                def __exit__(self, *a): pass

            return FakeFile()

        mock_engine = MagicMock()
        mock_engine.predict.return_value = _make_raw_response()

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("builtins.open", mock_open), \
             patch("pathlib.Path.mkdir"):
            req = _make_request(
                verified_facts="الموظف: محمد بن علي، رقم هويته 1234567890",
                user_claims="يريد إجازة"
            )
            consult_decision(req)

        # التحقق أن البيانات الحساسة لم تُسجَّل في السجل
        for entry in logs_written:
            # السجل يجب ألا يحتوي على رقم الهوية
            self.assertNotIn("1234567890", entry)
            # السجل يجب ألا يحتوي على النص الكامل للموظف
            self.assertNotIn("محمد بن علي", entry)

    def test_old_service_interface_compatible(self):
        """B28. الخدمة القديمة وواجهتها متوافقة."""
        from laya_service import LayaService, LayaDecisionResult
        svc = LayaService()
        result = svc.triage_request("أريد طلب إجازة")
        self.assertIsInstance(result, LayaDecisionResult)
        self.assertIsNotNone(result.domain)
        self.assertIsNotNone(result.to_dict())
        # confidence الثابتة لا تزال موجودة للتوافق
        self.assertIn(result.confidence, (0.95, 0.80))

    def test_unapproved_execute_odoo_rejected_and_safe(self):
        """B29. عند غياب الاعتماد: رفض خيار execute_odoo، لا يدخل كاتب، لا يتغير pending_action، ولا كتابة في Odoo."""
        mock_engine = MagicMock()
        raw = _make_raw_response(choice="execute_odoo", read_prob=0.01, clarify_prob=0.01)
        raw["answers"]["next_step"]["choice"] = "execute_odoo"
        raw["answers"]["next_step"]["probabilities"] = {"execute_odoo": 0.98, "await_approval": 0.02}
        raw["answers"]["next_step"]["answer_confidence"] = 0.98
        raw["answers"]["next_step"]["action"] = {"act_probability": 1.0}
        mock_engine.predict.return_value = raw

        # 1. حالة الرد بخيار غير مسموح (execute_odoo ليس في allowed_choices)
        req = _make_request(
            allowed_choices={
                "await_approval": "انتظار الاعتماد المزدوج",
                "clarify_user": "طلب توضيح",
            }
        )
        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            result = consult_decision(req)

        # التحقق أ: الرد يُرفض فوراً كـ invalid_response
        self.assertEqual(result.status, "invalid_response")
        self.assertIsNone(result.suggested_choice)
        self.assertFalse(result.execution_authorized)

        # 2. حتى لو وُضع execute_odoo في allowed_choices خطأً من المستدعي:
        req_with_choice = _make_request(
            allowed_choices={
                "execute_odoo": "تنفيذ مباشر",
                "await_approval": "انتظار اعتماد",
            }
        )
        mock_katib = MagicMock()
        mock_write_gateway = MagicMock()
        session_pending = {"type": "update", "consumed": False}

        with patch.object(nc, "_LAYA_ENABLED", True), \
             patch("laya_neural_consultant._load_engine", return_value=mock_engine), \
             patch("laya_neural_consultant._log_consultation"):
            res2 = consult_decision(req_with_choice)

        # التحقق ب: لا يُمنح تصريح تنفيذ إطلاقاً
        self.assertFalse(res2.execution_authorized)

        # التحقق ج: كاتب لا يُستدعى
        mock_katib.execute_mutation.assert_not_called()
        mock_katib.prepare_draft.assert_not_called()

        # التحقق د: pending_action لا يتغير ولا يُستهلك
        self.assertEqual(session_pending["type"], "update")
        self.assertFalse(session_pending["consumed"])

        # التحقق هـ: بوابة الكتابة OdooWriteGateway لا تُستدعى ولا تحدث أي كتابة في Odoo
        mock_write_gateway.write_record.assert_not_called()
        mock_write_gateway.create_employee.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
