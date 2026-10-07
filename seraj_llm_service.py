"""
خدمة الذكاء الاصطناعي لـ «سراج» عبر OpenRouter (Seraj LLM Service)
==================================================================
توفر ذكاءً فائقاً واستجابة طبيعية متقدمة لسراج باستخدام نماذج مجانية عملاقة (+27B حتى 120B/550B)،
مع التزام صارم بمبدأ منع التخمين والهلوسة (Zero Hallucination) عبر ربط الإجابات دوماً بحقائق
نظام Odoo، ومواد نظام العمل السعودي، وقرارات وكيلة التوجيه والتحقق «لايا».
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("seraj_llm_service")

# Candidate high-parameter free models (27B and above)
FREE_HIGH_PARAM_MODELS = [
    "openrouter/auto",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]


import re

def clean_math_formatting(text: str) -> str:
    r"""
    Cleans up any raw LaTeX formulas or mathematical markup that LLMs might generate,
    converting them into clean, human-readable Arabic text and arithmetic expressions.
    Example:
      \(5 \times \frac{1}{2} \text{ شهر} = 2.5 \text{ شهر}\) -> 5 × 1/2 شهر = 2.5 شهر
      \(3.5 \times 12,000 \text{ ريال} = 42,000 \text{ ريال}\) -> 3.5 × 12,000 ريال = 42,000 ريال
    """
    if not text:
        return text

    # Convert \frac{a}{b} -> a/b
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1/\2', text)
    # Convert \times and \cdot -> ×
    text = text.replace(r'\times', '×').replace(r'\cdot', '×')
    # Strip \text{...} -> inner text
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)
    # Strip \left and \right
    text = text.replace(r'\left', '').replace(r'\right', '')
    # Replace \[ and \] with newlines
    text = text.replace(r'\[', '\n').replace(r'\]', '\n')
    # Replace \( and \) with space
    text = text.replace(r'\(', '').replace(r'\)', '')
    # Replace \le, \leq -> ≤
    text = re.sub(r'\\leq?', '≤', text)
    # Replace \ge, \geq -> ≥
    text = re.sub(r'\\geq?', '≥', text)
    # Strip $$ or $
    text = text.replace('$$', '').replace('$', '')
    # Clean up LaTeX escaped characters
    text = text.replace(r'\%', '%').replace(r'\,', ' ').replace(r'\;', ' ').replace(r'\quad', ' ')
    # Normalize spaces
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


class SerajLLMService:
    """محرك التفكير واللغة الطبيعية لسراج المعتمد على نماذج +27B عبر OpenRouter."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 20,
    ) -> None:
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "") if api_key is None else api_key
        self.model = model or os.environ.get("OPENROUTER_MODEL", FREE_HIGH_PARAM_MODELS[0])
        self.timeout = timeout

    def is_configured(self) -> bool:
        """Returns True if the OpenRouter API key is set."""
        return bool(self.api_key and self.api_key.startswith("sk-or-"))

    def generate_grounded_response(
        self,
        user_query: str,
        user_name: str = "مستخدم",
        laya_decision: Optional[Dict[str, Any]] = None,
        odoo_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generates an intelligent, grounded Arabic response without guessing or hallucinating.
        Anchored strictly by Laya's classification and active Odoo context.
        """
        if not self.is_configured() or not user_query.strip():
            return None

        # Build strict zero-hallucination system prompt with authoritative Saudi Labor Law facts
        system_prompt = (
            "أنت «سراج» المساعد الاستشاري الذكي الرسمي لإدارة الموارد البشرية Odoo في المملكة العربية السعودية.\n"
            "تتعاون مع منظومة الوكلاء: وكيلة التوجيه والفرز الذكي «لايا»، ومنظومة الأمان والرقابة الصارمة «الحراس» (حراس النظام)، وفريق التدقيق والمطابقة «مدقق» و«فاحص»، ووكيل المعالجة والتصحيح الذكي «مصلح».\n\n"
            "قواعد ومصطلحات النظام الإلزامية:\n"
            "1. النظام تشغيلي وحقيقي ومعتمد 100%، ويُمنع منعاً باتاً وصف النظام أو عملياته بكلمات مثل 'تجربة' أو 'تجريبي' أو 'تجريبياً' (الاستثناء الوحيد هو 'فترة التجربة' العمالية الرسمية وفق المادة 53).\n"
            "2. يُحظر تماماً استخدام كلمة 'ترقيع' أو 'الترقيع'. المصطلح المهني المعتمد هو 'المعالجة والتصحيح التلقائي' أو 'المعالجة الذكية'.\n"
            "3. يعتمد النظام على وكيل الاستعلام والتدقيق «فاحص» (مستودع القراءة الحية في Odoo) للوصول المباشر والدقيق لبيانات المنشأة والموظفين بدون أي تخمين أو هلوسة.\n\n"
            "الحقائق النظامية الملزمة لنظام العمل السعودي ولائحته التنفيذية وتعديلات 1446هـ:\n"
            "• المادة 85 (مكافأة الاستقالة):\n"
            "  - خدمة أقل من سنتين: لا يستحق مكافأة (0).\n"
            "  - خدمة من سنتين إلى أقل من 5 سنوات: يستحق ثلث المكافأة (1/3).\n"
            "  - خدمة من 5 سنوات إلى أقل من 10 سنوات: يستحق ثلثي المكافأة (2/3).\n"
            "  - خدمة 10 سنوات فأكثر: يستحق المكافأة كاملة.\n"
            "• المادة 84 (مكافأة إنهاء العقد من صاحب العمل):\n"
            "  - أجر نصف شهر عن كل سنة من السنوات الخمس الأولى، وأجر شهر كامل عن كل سنة تالية.\n"
            "• المادة 107 (ساعات العمل الإضافية - الأوفرتايم):\n"
            "  - أجر الساعة الفعلي + 50% من الأجر الأساسي للساعة.\n"
            "• المادة 77 (التعويض عن الإنهاء غير المشروع):\n"
            "  - عقد غير محدد المدة: أجر 15 يوماً عن كل سنة خدمة (بحد أدنى أجر شهرين).\n"
            "  - عقد محدد المدة: أجر المدة المتبقية من العقد (بحد أدنى أجر شهرين).\n"
            "• المادة 70 (سقف الجزاءات التأديبية):\n"
            "  - لا يجوز حسم أكثر من أجر 5 أيام عن المخالفة الواحدة، ولا يزيد مجموع الحسم عن أجر 5 أيام في الشهر الواحد.\n"
            "• المادة 72 (تقادم وسقوط المخالفة):\n"
            "  - تسقط المخالفة إذا مضى 30 يوماً على اكتشافها دون اتخاذ إجراء تأديبي.\n"
            "• المادة 92 (سقف استقطاع السلف والقروض):\n"
            "  - لا يجوز أن يزيد القسط الشهري لسداد سلفة صاحب العمل عن 25% من الأجر الشهري.\n"
            "• المادة 53 (فترة التجربة):\n"
            "  - الأصل 90 يوماً، وتمديدها إلى 180 يوماً يشترط اتفاقاً كتابياً صريحاً بين الطرفين.\n"
            "• المادة 37 (عقد غير السعودي):\n"
            "  - يجب أن يكون مكتوباً ومحدد المدة دائماً، وبطلان العقود غير محددة المدة للمقيمين.\n"
            "• المادة 98 (ساعات العمل في رمضان):\n"
            "  - للمسلمين: 6 ساعات يومياً أو 36 ساعة أسبوعياً.\n"
            "• تعديلات 1446هـ:\n"
            "  - إجازة الوضع للأم العاملة (المادة 151): 12 أسبوعاً بأجر كامل (وليس 10 أسابيع).\n"
            "  - إجازة الأبوة (المادة 113): 3 أيام بأجر كامل.\n"
            "  - إجازة وفاة الأخ أو الأخت (المادة 113): 3 أيام بأجر كامل.\n"
            "  - إجازة الزواج (المادة 113): 5 أيام بأجر كامل.\n"
            "• التأمينات الاجتماعية (GOSI):\n"
            "  - الموظف السعودي: 9.75% موظف + 11.75% صاحب عمل (إجمالي 21.5%)، والحد الأقصى للأجر الخاضع هو 45,000 ريال.\n"
            "  - غير السعودي: 0% موظف + 2% صاحب عمل (أخطار مهنية).\n\n"
            "قواعد التنسيق وشكل الإجابة الصارمة:\n"
            "1. ممنوع منعاً باتاً استخدام صيغ أو رموز LaTeX أو الرياضيات المعقدة مثل (\\(, \\), \\frac, \\times, \\text, $$, \\cdot). اكتب الحسابات بصيغة عربية واضحة ومقروءة تماماً على الهواتف، مثال: (4 × 0.5 شهر = شهرين، وثلثها = 2/3 شهر راتب) أو (3.5 × 12,000 ريال = 42,000 ريال) بدون أي أقواس أو شرطات مائلة أو أكواد برمجية.\n"
            "2. أجب بشكل مباشر وموجز ومفيد وبدون تكلف، وتحدث باللغة العربية الفصحى الودودة والمهنية.\n"
            "3. لا تطلب أو تعرض أزراراً أو قوائم ما لم يطلب المستخدم ذلك صراحة."
        )

        context_lines = [f"اسم المستخدم: {user_name}"]
        if laya_decision:
            dom = laya_decision.get("domain_ar") or laya_decision.get("domain")
            act = laya_decision.get("action_type_ar") or laya_decision.get("action_type")
            expl = laya_decision.get("explanation_ar", "")
            context_lines.append(f"تصنيف لايا للمجال: {dom} | نوع الإجراء: {act}")
            if expl:
                context_lines.append(f"ملاحظة توجيه لايا: {expl}")

        if odoo_context:
            for k, v in odoo_context.items():
                context_lines.append(f"{k}: {v}")

        context_block = "\n".join(context_lines)

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"السياق الرقابي والعملياتي:\n{context_block}\n\nرسالة المستخدم الحالية:\n«{user_query}»\n\nأجب المستخدم بذكاء ووضوح وبدون أي تخمين وبدون رموز LaTeX الرياضية.",
            },
        ]

        # Try models in order of priority (primary + fallbacks)
        models_to_try = [self.model] + [m for m in FREE_HIGH_PARAM_MODELS if m != self.model]

        for candidate_model in models_to_try:
            try:
                resp = self._call_openrouter(candidate_model, messages)
                if resp and resp.strip():
                    return clean_math_formatting(resp.strip())
            except Exception as exc:
                logger.warning("OpenRouter model %s failed: %s", candidate_model, exc)

        return None

    def _call_openrouter(self, model_name: str, messages: List[Dict[str, str]]) -> Optional[str]:
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2,   # Low temperature for strict factual grounding
            "max_tokens": 600,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "OdooHRAgents/1.0",
                "HTTP-Referer": "https://odoo-hr-agents.local",
                "X-Title": "Odoo HR Seraj Agent",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            choices = res_data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
        return None
