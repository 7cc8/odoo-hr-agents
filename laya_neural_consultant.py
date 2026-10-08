"""
محرك الاستشارة العصبية المشتركة لمنظومة الوكلاء: Laya Neural Consultant
======================================================================
يُتيح لأي وكيل في المنظومة طلب استشارة من النموذج العصبي متعدد اللغات
عند مواجهة غموض دلالي في اختيار الخطوة التالية المناسبة.

الفوارق الأساسية:
- هذا المحرك مُنفصل كلياً عن LayaService (المُصنِّف القواعدي).
- لا يُبدّل domain أو action_type المُعتمد من القواعد.
- لا يمنح تصريح تنفيذ أو اعتماد.
- نتيجته اقتراح احتمالي استشاري فقط.

أوضاع التشغيل (عبر متغيرات البيئة):
    LAYA_ENABLED=true   → تُفعّل الاستشارة العصبية (disabled افتراضياً)
    LAYA_MODE=shadow    → shadow: تُشغَّل ولا تُضاف للسياق (الوضع الآمن)
    LAYA_MODE=advisory  → advisory: نتيجتها معلومة غير ملزمة قابلة للاستخدام
"""

from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("laya_neural_consultant")

# ─── إعدادات من البيئة ────────────────────────────────────────────────────────
_LAYA_ENABLED: bool = os.environ.get("LAYA_ENABLED", "false").strip().lower() == "true"
_LAYA_MODE: str = os.environ.get("LAYA_MODE", "shadow").strip().lower()  # shadow | advisory

# مسار أوزان النموذج المحلية (laya-models/multilingual)
_LOCAL_MODELS_DIR = Path(__file__).resolve().parent / "laya-models"

# حد أقصى لعدد الرموز المسموحة في الإدخال (state_tokens_dropped > 0 = تحذير)
_MAX_INPUT_TOKENS_WARNING = 500

# تساهل مجموع الاحتمالات (±5%)
_PROB_SUM_TOLERANCE = 0.05

# ─── حالة المحرك الوحيد (Singleton per process) ──────────────────────────────
_engine_lock = threading.Lock()
_engine_instance: Optional[Any] = None  # Router instance
_engine_load_attempted: bool = False
_engine_load_error: Optional[str] = None
_inference_origin_printed: bool = False


# ─── نماذج البيانات ──────────────────────────────────────────────────────────

@dataclass
class ConsultationRequest:
    """
    طلب استشارة من وكيل.

    الحقول المُصنَّفة حسب موثوقية المصدر:
    - verified_facts: حقائق مُتحقق منها عبر فاحص أو مصدر موثوق.
    - user_claims: ادعاءات المستخدم غير المُتحقق منها.
    - agent_inferences: استنتاجات وكيل سابق (غير مضمونة).
    - missing_information: معلومات غير معروفة — لا تعادل false.
    - conflicts: تعارضات مُكتشفة.

    قواعد بناء allowed_choices:
    1. لا تُعرض execute_odoo أو أي أفعال تنفيذ مباشر دون استيفاء شروط الاعتماد المزدوج.
    2. لا يُسأل النموذج عن تجاوز قواعد الهوية أو الصلاحيات أو الاعتماد.
    3. إن لم يبقَ غموض دلالي حقيقي، يجب تجاوز الاستشارة كلياً دون استدعاء النموذج.
    """
    caller_agent: str
    stage: str
    question_id: str
    instructions: str
    allowed_choices: Dict[str, str]        # {choice_id: description}
    verified_facts: Optional[str] = None
    user_claims: Optional[str] = None
    agent_inferences: Optional[str] = None
    missing_information: Optional[str] = None
    conflicts: Optional[str] = None
    context: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class ConsultationResult:
    """
    نتيجة الاستشارة العصبية.

    تحذيرات صريحة:
    - execution_authorized = False دائماً.
    - suggested_choice احتمالي، ليس أمراً.
    - distribution_confidence ≠ answer_probability (مفهومان مختلفان).
    - probabilities ليست معايَرة ولا تُثبت صحة الاختيار.
    """
    status: str                             # ok | disabled | unavailable | invalid_request | invalid_response | error
    mode: str                               # shadow | advisory
    caller_agent: str
    stage: str
    question_id: str
    suggested_choice: Optional[str] = None
    probabilities: Optional[Dict[str, float]] = None
    answer_probability: Optional[float] = None    # احتمال الخيار المُختار (من النموذج)
    distribution_confidence: Optional[float] = None  # confidence الأصلي من النموذج
    model_id: Optional[str] = None
    latency_ms: Optional[float] = None
    error_code: Optional[str] = None
    truncation_warning: bool = False
    execution_authorized: bool = False      # دائماً False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "caller_agent": self.caller_agent,
            "stage": self.stage,
            "question_id": self.question_id,
            "suggested_choice": self.suggested_choice,
            "probabilities": self.probabilities,
            "answer_probability": self.answer_probability,
            "distribution_confidence": self.distribution_confidence,
            "model_id": self.model_id,
            "latency_ms": self.latency_ms,
            "error_code": self.error_code,
            "truncation_warning": self.truncation_warning,
            "execution_authorized": self.execution_authorized,
        }


# ─── التحميل الكسول للمحرك ────────────────────────────────────────────────────

def _load_engine() -> Optional[Any]:
    """
    تحميل Router بشكل كسول عند أول استشارة فعلية.
    كائن واحد لكل process. محمي بقفل ضد التهيئة المتزامنة.
    لا يُحمَّل عند import. لا يُسقط التطبيق عند الفشل.

    ملاحظة: لا يُضاف laya-main لـ sys.path حتى لا يُحجب النسخة 0.4.0 المثبتة.
    مسار الأوزان المحلية: laya-models/multilingual (هي cache ذاتية لـ HuggingFace).
    """
    global _engine_instance, _engine_load_attempted, _engine_load_error

    with _engine_lock:
        if _engine_load_attempted:
            return _engine_instance

        _engine_load_attempted = True
        try:
            # الاستيراد من .venv (النسخة 0.4.0) وليس من laya-main
            from laya import Router  # type: ignore

            # تعيين متغير البيئة للكاش المحلي إن كانت الأوزان موجودة محلياً
            multilingual_dir = _LOCAL_MODELS_DIR / "multilingual"
            if multilingual_dir.exists():
                # laya تستخدم HuggingFace cache — نحدد مسار الـ cache
                cache_dir = _LOCAL_MODELS_DIR / ".cache"
                if cache_dir.exists():
                    os.environ.setdefault("HF_HOME", str(_LOCAL_MODELS_DIR))

            router = Router(
                default="multilingual",
                preload=False,          # لا نُحمّل عند الإنشاء
                auto_task_detection=False,
            )

            _engine_instance = router
            logger.info(
                "laya_neural_consultant: Router loaded (laya 0.4.0, multilingual). "
                "Local weights dir: %s",
                str(multilingual_dir) if multilingual_dir.exists() else "not found — will fetch",
            )
        except Exception as exc:
            _engine_load_error = str(exc)
            _engine_instance = None
            logger.warning(
                "laya_neural_consultant: Failed to load Router — %s. "
                "All consultations will return status=unavailable.",
                exc,
            )

    return _engine_instance


# ─── الواجهة الرئيسية ─────────────────────────────────────────────────────────

def consult_decision(request: ConsultationRequest) -> ConsultationResult:
    """
    الواجهة المشتركة للاستشارة العصبية من أي وكيل في المنظومة.

    السلوك:
    - LAYA_ENABLED=false → status=disabled، لا يُحمَّل النموذج.
    - فشل التحميل → status=unavailable، لا اقتراح وهمي.
    - طلب غير صالح → status=invalid_request.
    - رد غير صالح → status=invalid_response.
    - نجاح → status=ok، suggested_choice من النموذج.

    ضوابط أمان غير قابلة للكسر:
    - execution_authorized = False دائماً.
    - لا تعديل لـ pending_action أو payload أو approval.
    - في shadow: النتيجة لا تُضاف لأي سياق.
    """
    mode = _LAYA_MODE if _LAYA_MODE in ("shadow", "advisory") else "shadow"

    base = ConsultationResult(
        status="disabled",
        mode=mode,
        caller_agent=request.caller_agent,
        stage=request.stage,
        question_id=request.question_id,
        execution_authorized=False,
    )

    # ── 1. التحقق من التفعيل ──────────────────────────────────────────────────
    if not _LAYA_ENABLED:
        return base

    # ── 2. التحقق من صحة الطلب ───────────────────────────────────────────────
    validation_error = _validate_request(request)
    if validation_error:
        return ConsultationResult(
            status="invalid_request",
            mode=mode,
            caller_agent=request.caller_agent,
            stage=request.stage,
            question_id=request.question_id,
            error_code=validation_error,
            execution_authorized=False,
        )

    # ── 3. تحميل المحرك ───────────────────────────────────────────────────────
    engine = _load_engine()
    if engine is None:
        return ConsultationResult(
            status="unavailable",
            mode=mode,
            caller_agent=request.caller_agent,
            stage=request.stage,
            question_id=request.question_id,
            error_code=f"engine_load_failed: {_engine_load_error or 'unknown'}",
            execution_authorized=False,
        )

    # ── 4. بناء state من الأدلة المُتاحة ─────────────────────────────────────
    state_parts = []
    if request.verified_facts:
        state_parts.append(f"[حقائق متحققة]: {request.verified_facts}")
    if request.user_claims:
        state_parts.append(f"[ادعاءات المستخدم - غير متحققة]: {request.user_claims}")
    if request.agent_inferences:
        state_parts.append(f"[استنتاجات الوكيل - غير مضمونة]: {request.agent_inferences}")
    if request.conflicts:
        state_parts.append(f"[تعارضات مكتشفة]: {request.conflicts}")
    if request.missing_information:
        state_parts.append(f"[معلومات غير معروفة - لا تعادل false]: {request.missing_information}")
    if request.context:
        state_parts.append(f"[سياق إضافي]: {request.context}")

    state = "\n".join(state_parts) if state_parts else "لا توجد أدلة مُتاحة."

    questions = {
        request.question_id: {
            "type": "choice",
            "instructions": request.instructions,
            "criteria": request.allowed_choices,
        }
    }

    # ── 5. الاستدلال ──────────────────────────────────────────────────────────
    global _inference_origin_printed
    if not _inference_origin_printed:
        _inference_origin_printed = True
        try:
            import laya
            origin_file = getattr(laya, "__file__", "unknown")
            origin_ver = getattr(laya, "__version__", "unknown")
            logger.info(
                "[Laya Neural Inference Origin] file=%s, version=%s",
                origin_file, origin_ver,
            )
            print(f"[Laya Neural Inference Origin] file={origin_file}, version={origin_ver}")
        except Exception as _orig_exc:
            logger.debug("Could not log laya origin: %s", _orig_exc)

    t0 = time.monotonic()
    try:
        raw = engine.predict(state, questions, model="multilingual")
        latency_ms = (time.monotonic() - t0) * 1000.0
    except Exception as exc:
        latency_ms = (time.monotonic() - t0) * 1000.0
        logger.warning(
            "laya_neural_consultant: inference error [%s/%s]: %s",
            request.caller_agent, request.question_id, exc,
        )
        return ConsultationResult(
            status="error",
            mode=mode,
            caller_agent=request.caller_agent,
            stage=request.stage,
            question_id=request.question_id,
            error_code=f"inference_error: {type(exc).__name__}",
            latency_ms=latency_ms,
            execution_authorized=False,
        )

    # ── 6. تحليل الرد ─────────────────────────────────────────────────────────
    parse_result = _parse_response(raw, request)
    if parse_result is None:
        return ConsultationResult(
            status="invalid_response",
            mode=mode,
            caller_agent=request.caller_agent,
            stage=request.stage,
            question_id=request.question_id,
            error_code="parse_failed",
            latency_ms=latency_ms,
            execution_authorized=False,
        )

    suggested, probs, answer_prob, dist_conf, model_id, trunc_warn = parse_result

    # ── 7. التحقق من صحة الاحتمالات ──────────────────────────────────────────
    prob_error = _validate_probabilities(probs, request.allowed_choices)
    if prob_error:
        return ConsultationResult(
            status="invalid_response",
            mode=mode,
            caller_agent=request.caller_agent,
            stage=request.stage,
            question_id=request.question_id,
            error_code=prob_error,
            latency_ms=latency_ms,
            execution_authorized=False,
        )

    # ── 8. تسجيل الاستشارة ────────────────────────────────────────────────────
    _log_consultation(
        request=request,
        mode=mode,
        suggested_choice=suggested,
        probabilities=probs,
        answer_probability=answer_prob,
        distribution_confidence=dist_conf,
        model_id=model_id,
        latency_ms=latency_ms,
        truncation_warning=trunc_warn,
    )

    return ConsultationResult(
        status="ok",
        mode=mode,
        caller_agent=request.caller_agent,
        stage=request.stage,
        question_id=request.question_id,
        suggested_choice=suggested,
        probabilities=probs,
        answer_probability=answer_prob,
        distribution_confidence=dist_conf,
        model_id=model_id,
        latency_ms=latency_ms,
        truncation_warning=trunc_warn,
        execution_authorized=False,
    )


# ─── دوال مساعدة ─────────────────────────────────────────────────────────────

def _validate_request(request: ConsultationRequest) -> Optional[str]:
    """يُعيد كود الخطأ أو None إن كان الطلب صالحاً."""
    if not request.instructions or not request.instructions.strip():
        return "empty_instructions"
    if not request.allowed_choices or not isinstance(request.allowed_choices, dict):
        return "empty_or_invalid_choices"
    if len(request.allowed_choices) < 2:
        return "choices_must_have_at_least_two"
    for key, val in request.allowed_choices.items():
        if not key or not key.strip():
            return "empty_choice_key"
        if not val or not isinstance(val, str):
            return "invalid_choice_description"
        # حظر عرض خيارات التنفيذ المباشر كاستشارة استدلالية دون استيفاء الاعتماد
        if key.strip().lower() in ("execute_odoo", "direct_execute", "force_write", "bypass_approval"):
            return "forbidden_execution_choice_in_consultation"
    return None


def _parse_response(
    raw: Dict[str, Any],
    request: ConsultationRequest,
) -> Optional[tuple]:
    """
    يُحلل رد النموذج ويُعيد:
    (suggested_choice, probabilities, answer_probability, distribution_confidence,
     model_id, truncation_warning)
    أو None عند الفشل.
    """
    try:
        answers = raw.get("answers", {})
        qdata = answers.get(request.question_id)
        if not qdata or not isinstance(qdata, dict):
            return None

        suggested = qdata.get("choice")
        if not suggested or not isinstance(suggested, str):
            return None

        # التحقق من أن الاختيار ضمن allowed_choices
        if suggested not in request.allowed_choices:
            logger.warning(
                "laya_neural_consultant: model returned choice %r not in allowed_choices %s",
                suggested, list(request.allowed_choices.keys()),
            )
            return None

        probs_raw = qdata.get("probabilities", {})
        if not isinstance(probs_raw, dict):
            return None

        # answer_probability: احتمال الخيار المُختار
        answer_prob = qdata.get("answer_confidence")
        if not isinstance(answer_prob, (int, float)):
            answer_prob = probs_raw.get(suggested)

        # distribution_confidence: الـ confidence الأصلي من النموذج
        dist_conf = qdata.get("confidence")

        # model_id
        routing = raw.get("routing", {})
        model_id = routing.get("model") or routing.get("repo")

        # تحقق من truncation
        usage = raw.get("usage", {})
        truncation_warning = bool(
            usage.get("truncated")
            or (usage.get("state_tokens_dropped", 0) or 0) > 0
        )

        # تحويل الاحتمالات لـ float
        probs: Dict[str, float] = {}
        for k, v in probs_raw.items():
            if isinstance(v, (int, float)):
                probs[k] = float(v)

        return suggested, probs, answer_prob, dist_conf, model_id, truncation_warning

    except Exception as exc:
        logger.warning("laya_neural_consultant: parse error: %s", exc)
        return None


def _validate_probabilities(
    probs: Optional[Dict[str, float]],
    allowed_choices: Dict[str, str],
) -> Optional[str]:
    """
    يتحقق من صحة الاحتمالات:
    - لا NaN أو Infinity.
    - لا قيم خارج [0, 1].
    - مجموعها ضمن تساهل ±5%.
    يُعيد كود الخطأ أو None إن كانت صالحة.
    """
    if not probs:
        return None  # الاحتمالات اختيارية

    for key, val in probs.items():
        if not isinstance(val, float):
            continue
        if math.isnan(val) or math.isinf(val):
            return f"invalid_probability_value: {key}={val}"
        if val < 0.0 or val > 1.0:
            return f"probability_out_of_range: {key}={val}"

    total = sum(v for v in probs.values() if isinstance(v, float))
    if abs(total - 1.0) > _PROB_SUM_TOLERANCE:
        # مجموع خارج التساهل — لا نُصحح بصمت
        logger.warning(
            "laya_neural_consultant: probabilities sum=%.4f (tolerance ±%.2f) — "
            "treating as advisory note, not correcting silently",
            total, _PROB_SUM_TOLERANCE,
        )
        # لا نرفض لكن نُسجّل — نعيد None فقط إن كان الانحراف كبيراً جداً (>20%)
        if abs(total - 1.0) > 0.20:
            return f"probabilities_sum_too_far_from_1: sum={total:.4f}"

    return None


def _log_consultation(
    request: ConsultationRequest,
    mode: str,
    suggested_choice: Optional[str],
    probabilities: Optional[Dict[str, float]],
    answer_probability: Optional[float],
    distribution_confidence: Optional[float],
    model_id: Optional[str],
    latency_ms: float,
    truncation_warning: bool,
) -> None:
    """
    يُسجل الاستشارة في سجل JSONL المخصص.
    لا يُسجّل نصوصاً حساسة أو بيانات موظفين أو أسراراً.
    """
    try:
        logs_dir = Path(__file__).resolve().parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "laya_consultation_audit.jsonl"

        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "correlation_id": request.correlation_id,
            "caller_agent": request.caller_agent,
            "stage": request.stage,
            "question_id": request.question_id,
            "mode": mode,
            "suggested_choice": suggested_choice,
            # نُسجّل الاحتمالات دون نصوص البيانات
            "answer_probability": answer_probability,
            "distribution_confidence": distribution_confidence,
            "model_id": model_id,
            "latency_ms": round(latency_ms, 1),
            "truncation_warning": truncation_warning,
            "execution_authorized": False,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        # فشل السجل لا يُحوَّل لنجاح وهمي
        logger.error("laya_neural_consultant: log write failed: %s", exc)


def get_engine_status() -> Dict[str, Any]:
    """حالة المحرك الحالية للتشخيص (بدون أسرار)."""
    return {
        "laya_enabled": _LAYA_ENABLED,
        "laya_mode": _LAYA_MODE,
        "engine_loaded": _engine_instance is not None,
        "load_attempted": _engine_load_attempted,
        "load_error": _engine_load_error,
        "local_models_dir": str(_LOCAL_MODELS_DIR),
        "multilingual_dir_exists": (_LOCAL_MODELS_DIR / "multilingual").exists(),
    }
