"""
خدمة وكيلة القرار السريع والتوجيه الذكي: «لايا» (Laya Decision & Triage Engine)
=============================================================================
مبنية على محرك القرارات غير المتكرر (Non-Autoregressive Decision Engine)
المستند إلى مستودع Laya الأصلي (https://github.com/NandhaKishorM/laya)
الموجود في: D:\\mjrm0\\Documents\\odoo-hr-agents\\laya-main

دور «لايا» في منظومة الوكلاء:
1. توجيه واستشعار النوايا الفوري (Sub-50ms Triage & Intent Classification) عبر تحليل النصوص باللغة العربية والإنجليزية.
2. تصنيف مجالات الموارد البشرية العشرة (إجازات، حضور، عقود، رواتب، جزاءات، سلف، نهاية خدمة، علاقات حكومية، تقييم، توظيف، تدقيق، تحليلات).
3. تحديد نوع الإجراء (استعلام، محاكاة تجريبية، تعديل/كتابة، طلب حذف محظور، استخراج تقارير).
4. تفعيل حواجز الأمان (Safety Gateways): تمييز العمليات الحساسة التي تتطلب مبدأ التحقق المزدوج Four-Eyes،
   والاعتراض الفوري لطلبات الحذف (unlink) وتحويلها إلى أرشفة آمنة قبل الوصول إلى بوابات الكتابة.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# مسار مستودع laya-main المحلي (للتوثيق والاحتياط)
LAYA_REPO_PATH = Path(__file__).resolve().parent / "laya-main"

# محاولة استيراد حزمة laya المثبتة في البيئة أولاً لمنع حجب الإصدار الأحدث (shadowing)
try:
    import laya
    import laya.lang as laya_lang
    HAS_NATIVE_LAYA = True
except ImportError:
    # احتياطي فقط في حال عدم تثبيت حزمة laya في البيئة
    if LAYA_REPO_PATH.exists() and str(LAYA_REPO_PATH) not in sys.path:
        sys.path.append(str(LAYA_REPO_PATH))
    try:
        import laya
        import laya.lang as laya_lang
        HAS_NATIVE_LAYA = True
    except Exception:
        HAS_NATIVE_LAYA = False
except Exception:
    HAS_NATIVE_LAYA = False


@dataclass
class LayaDecisionResult:
    """نتيجة القرار المصنف والموجه عبر وكيلة لايا."""
    user_text: str
    script: str
    is_arabic: bool
    domain: str
    domain_ar: str
    action_type: str
    action_type_ar: str
    requires_four_eyes: bool
    is_deletion_blocked: bool
    suggested_agent: str
    suggested_agent_ar: str
    confidence: float
    explanation_ar: str
    extracted_entities: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_text": self.user_text,
            "script": self.script,
            "is_arabic": self.is_arabic,
            "domain": self.domain,
            "domain_ar": self.domain_ar,
            "action_type": self.action_type,
            "action_type_ar": self.action_type_ar,
            "requires_four_eyes": self.requires_four_eyes,
            "is_deletion_blocked": self.is_deletion_blocked,
            "suggested_agent": self.suggested_agent,
            "suggested_agent_ar": self.suggested_agent_ar,
            "confidence": self.confidence,
            "explanation_ar": self.explanation_ar,
            "extracted_entities": self.extracted_entities,
        }


class LayaService:
    """
    الواجهة التنفيذية لوكيلة لايا (Laya) لتوجيه واستشعار قرارات منظومة الموارد البشرية Odoo.
    """

    DOMAINS_CRITERIA = {
        "leaves": {
            "ar": "إدارة الإجازات والأرصدة",
            "keywords": ["إجازة", "اجازة", "إجازات", "اجازات", "سنوية", "مرضية", "رصيد", "عطلة", "استئذان", "leave", "leaves"],
            "agent": "leave_service",
            "agent_ar": "وكيل الإجازات",
        },
        "attendance": {
            "ar": "الحضور والانصراف والدوام",
            "keywords": ["حضور", "انصراف", "دوام", "بصمة", "تأخير", "اوفرتايم", "إضافي", "اضافي", "ساعات", "attendance", "checkin", "checkout"],
            "agent": "attendance_service",
            "agent_ar": "وكيل الحضور والانصراف",
        },
        "contracts": {
            "ar": "عقود العمل وهيكلة الأجور",
            "keywords": ["عقد", "عقود", "راتب", "رواتب", "أجر", "اجر", "أساسي", "اساسي", "بدل", "بدلات", "سكن", "نقل", "تأمينات", "gosi", "contract", "wage"],
            "agent": "contract_service",
            "agent_ar": "وكيل العقود والأجور",
        },
        "payroll": {
            "ar": "مسيرات الرواتب وحماية الأجور (WPS)",
            "keywords": ["مسير", "مسيرات", "رواتب", "قسيمة", "قسائم", "payslip", "payroll", "wps", "مدد", "حماية الأجور", "سيف", "sif"],
            "agent": "payroll_service",
            "agent_ar": "وكيل مسيرات الرواتب",
        },
        "disciplinary": {
            "ar": "الجزاءات والمخالفات العمالية",
            "keywords": ["جزاء", "جزاءات", "مخالفة", "مخالفات", "إنذار", "انذار", "تحقيق", "خصم", "انضباط", "disciplinary", "penalty"],
            "agent": "disciplinary_service",
            "agent_ar": "وكيل الجزاءات والانضباط",
        },
        "eos": {
            "ar": "مكافأة نهاية الخدمة والتسويات",
            "keywords": ["نهاية خدمة", "نهايه خدمه", "مكافأة", "مكافاه", "استقالة", "فصل", "تسوية", "تصفية", "مادة 84", "مادة 85", "eos", "end of service"],
            "agent": "eos_service",
            "agent_ar": "وكيل نهاية الخدمة",
        },
        "loans": {
            "ar": "السلف والقروض الميسرة",
            "keywords": ["سلفة", "سلفه", "سلف", "قرض", "قروض", "أقساط", "اقساط", "استقطاع", "loan", "advance"],
            "agent": "loan_service",
            "agent_ar": "وكيل السلف والقروض",
        },
        "gr": {
            "ar": "العلاقات الحكومية والجوازات (GR)",
            "keywords": ["إقامة", "اقامة", "تأشيرة", "تاشيرة", "خروج وعودة", "قوى", "مقيم", "جوازات", "مهنة", "كرت عمل", "gr", "visa", "iqama"],
            "agent": "gr_service",
            "agent_ar": "وكيل العلاقات الحكومية",
        },
        "appraisal": {
            "ar": "تقييم الأداء والكفاءات",
            "keywords": ["تقييم", "تقييمات", "أداء", "اداء", "أهداف", "اهداف", "كفاءة", "ترقية", "مكافأة أداء", "appraisal", "evaluation"],
            "agent": "appraisal_service",
            "agent_ar": "وكيل تقييم الأداء",
        },
        "recruitment": {
            "ar": "التوظيف وإدارة المرشحين",
            "keywords": ["توظيف", "شاغر", "شواغر", "مرشح", "مرشحين", "مقابلة", "عرض عمل", "سيرة ذاتية", "recruit", "recruitment", "applicant"],
            "agent": "recruitment_service",
            "agent_ar": "وكيل الاستقطاب والتوظيف",
        },
        "analytics": {
            "ar": "المؤشرات التنفيذية ومحاكي نطاقات",
            "keywords": ["مؤشرات", "إحصائيات", "احصائيات", "تحليلات", "داشبورد", "لوحة", "نطاقات", "توطين", "سعودة", "محاكي", "kpi", "analytics", "dashboard"],
            "agent": "analytics_service",
            "agent_ar": "وكيل التحليلات والمؤشرات",
        },
        "audit": {
            "ar": "سجلات التدقيق والحوكمة والرقابة (سجل)",
            "keywords": ["سجل", "تدقيق", "رقابة", "تقرير pdf", "سجلات", "حوكمة", "audit", "log", "pdf", "تقرير التدقيق"],
            "agent": "sijil_service",
            "agent_ar": "وكيل الرقابة والتدقيق (سجل)",
        },
        "letters": {
            "ar": "الخطابات الرسمية وشهادات الرواتب",
            "keywords": ["خطاب", "خطابات", "شهادة", "شهاده", "تعريف", "تثبيت", "غرفة تجارية", "سفارة", "بنكي", "letter", "certificate"],
            "agent": "letter_service",
            "agent_ar": "وكيل الخطابات والموافقات",
        },
        "expenses": {
            "ar": "المصروفات والانتدابات ونفقات السفر",
            "keywords": ["مصروف", "مصروفات", "انتداب", "تذكرة", "فندق", "فاتورة", "فواتير", "عهدة", "إعاشة", "نثريات", "expense", "expenses", "travel"],
            "agent": "expense_service",
            "agent_ar": "وكيل المصروفات والانتدابات",
        },
        "expiries": {
            "ar": "صلاحيات الوثائق والتنبيهات المجدولة",
            "keywords": ["انتهاء", "صلاحية", "صلاحيات", "هوية", "إقامة", "اقامة", "جواز", "جوازات", "تأشيرة", "تاشيرة", "رخصة عمل", "تجربة", "عقد عمل", "expiry", "expiries", "document"],
            "agent": "document_expiry_service",
            "agent_ar": "وكيل رصد الصلاحيات والوثائق",
        },
    }


    ACTION_KEYWORDS = {
        "delete": ["احذف", "حذف", "امسح", "مسح", "ازالة", "إزالة", "delete", "unlink", "remove", "drop"],
        "update": ["عدل", "تعديل", "غير", "تغيير", "حدث", "تحديث", "كتابة", "تسجيل", "انشئ", "إنشاء", "اعتماد", "update", "write", "create", "modify", "edit"],
        "report": ["تقرير", "ملف", "pdf", "بي دي اف", "طباعة", "تصدير", "report", "export", "download"],
        "dry_run": ["محاكاة", "فحص", "تجربة", "تأكد", "مدقق", "قبل التنفيذ", "dry run", "test", "check"],
        "query": ["استعلام", "عرض", "كم", "ماهو", "ما هو", "أين", "بيانات", "تفاصيل", "رصيد", "query", "show", "get", "view"],
    }

    def __init__(self):
        self.has_native_laya = HAS_NATIVE_LAYA
        self.version = getattr(laya, "__version__", "0.3.28") if HAS_NATIVE_LAYA else "integrated"

    def analyze_script(self, text: str) -> Dict[str, Any]:
        """فحص النص ولغته عبر تقنيات laya.lang."""
        if self.has_native_laya:
            try:
                res = laya_lang.analyse(text)
                return {
                    "script": res.get("script", "unknown"),
                    "is_arabic": res.get("script") == "arabic",
                    "details": res,
                }
            except Exception:
                pass

        # تحليل احتياطي مدمج
        has_arabic = bool(re.search(r"[\u0600-\u06FF]", text))
        has_latin = bool(re.search(r"[a-zA-Z]", text))
        script = "arabic" if (has_arabic and not has_latin) else ("mixed" if (has_arabic and has_latin) else "latin")
        return {
            "script": script,
            "is_arabic": has_arabic,
            "details": {"script": script},
        }

    def triage_request(self, user_text: str) -> LayaDecisionResult:
        """
        إجراء التوجيه السريع وتحديد النية والوكيل المستهدف والحواجز الأمنية.
        """
        clean_text = user_text.strip().lower()
        script_info = self.analyze_script(clean_text)
        is_ar = script_info["is_arabic"]

        # 1. كشف نوع الإجراء (Action Type)
        action_type = "query"
        for act, kws in self.ACTION_KEYWORDS.items():
            if any(kw in clean_text for kw in kws):
                action_type = act
                break

        # 2. كشف المجال (Domain Classification)
        matched_domain = "general"
        highest_score = 0
        for dom, info in self.DOMAINS_CRITERIA.items():
            score = sum(1 for kw in info["keywords"] if kw in clean_text)
            if score > highest_score:
                highest_score = score
                matched_domain = dom

        if matched_domain == "general":
            # تدقيق إضافي إذا كان النص يخص سجل أو بي دي اف
            if "pdf" in clean_text or "تقرير" in clean_text or "سجل" in clean_text:
                matched_domain = "audit"
            elif any(w in clean_text for w in ["مرحبا", "سلام", "هلا", "مساعدة", "اوامر", "قائمة"]):
                matched_domain = "general"
                action_type = "menu"

        domain_meta = self.DOMAINS_CRITERIA.get(matched_domain, {
            "ar": "الاستعلام العام وسراج",
            "agent": "seraj_orchestrator",
            "agent_ar": "الوكيل المنسق (سراج)"
        })

        # 3. قواعد الأمان وحواجز التحقق المزدوج
        is_deletion_blocked = (action_type == "delete")
        requires_four_eyes = (action_type in ("update", "delete"))

        # 4. استخراج الكيانات الأساسية (الأرقام، المعرفات، التواريخ)
        extracted = self._extract_entities(user_text)

        # 5. صياغة التفسير والشرح
        action_names_ar = {
            "delete": "طلب حذف كلي (محظور أمنياً)",
            "update": "تعديل أو إنشاء بيانات (يتطلب التحقق المزدوج)",
            "dry_run": "محاكاة وفحص نظامي مسبق",
            "query": "استعلام وقراءة آمنة",
            "report": "استخراج تقرير أو مستند PDF",
            "menu": "قائمة الخيارات الرئيسية",
        }

        if is_deletion_blocked:
            explanation = (
                f"صنفت «لايا» الطلب كنية لحذف سجل في مجال ({domain_meta['ar']}). "
                f"وحاجز الأمان الرقابي لـ «الحراس» يمنع استدعاء unlink قطعياً لحماية المنظومة؛ والبديل المعتمد هو الأرشفة أو إنهاء الخدمة."
            )
        elif requires_four_eyes:
            explanation = (
                f"صنفت «لايا» الطلب كإجراء تعديل/كتابة في ({domain_meta['ar']}). "
                f"وتفرض ضوابط «الحراس» التحقق المسبق من «مدقق» ثم تفويضاً كتابياً صريحاً (Four-Eyes)."
            )
        else:
            explanation = f"صنفت «لايا» الطلب كاستعلام آمن ضمن نطاق ({domain_meta['ar']})."

        confidence = 0.95 if highest_score > 0 else 0.80

        return LayaDecisionResult(
            user_text=user_text,
            script=script_info["script"],
            is_arabic=is_ar,
            domain=matched_domain,
            domain_ar=domain_meta["ar"],
            action_type=action_type,
            action_type_ar=action_names_ar.get(action_type, action_type),
            requires_four_eyes=requires_four_eyes,
            is_deletion_blocked=is_deletion_blocked,
            suggested_agent=domain_meta["agent"],
            suggested_agent_ar=domain_meta["agent_ar"],
            confidence=confidence,
            explanation_ar=explanation,
            extracted_entities=extracted,
        )

    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """استخراج سريع للمعرفات والأرقام والتواريخ والأسماء."""
        entities: Dict[str, Any] = {}
        # أرقام المعرفات (ID) مثل #100 أو رقم 100 أو للموظف 100
        id_match = re.search(r"(?:معرف|رقم|id|#|موظف|للموظف)\s*(\d+)", text, re.IGNORECASE)
        if id_match:
            entities["employee_id"] = int(id_match.group(1))

        # استبعاد الاستفسارات القانونية والأسئلة العامة والإحصائية من البحث عن اسم الموظف
        general_question_markers = [
            "نظام العمل", "المادة", "مادة", "ساعات العمل", "كم ساعات", "كيف يتم", "ما هي", "ماهي",
            "ما هو", "ماهو", "هل يجوز", "كم عدد", "كم", "عدد", "احسب", "قائمة", "عرض", "الشركات",
            "المؤرشفين", "المؤرشفة", "مؤرشف", "المنشآت", "تقرير", "كشف", "من هم", "أين", "اين",
            "الشركة الثانية", "الشركة الأولى", "الشركة الثالثة", "الكل", "جميع الشركات"
        ]
        is_legal_or_general_inquiry = any(kw in text for kw in general_question_markers)

        # 1. استخراج اسم الموظف إذا ذُكر صراحة بصيغة بحث أو تحديد
        # مثل: ابحث عن موظف اسمه أحمد / عن الموظف ناصر / للموظف القحطاني / اسمه أحمد
        search_match = re.search(r"(?:ابحث عن|بحث عن|عن)?\s*(?:موظف\s+)?(?:اسمه|اسمها)\s+([أ-ي\w\s]{2,25})", text)
        if search_match and not is_legal_or_general_inquiry:
            cand = search_match.group(1).strip().strip("؟?!.,")
            if cand and len(cand) >= 2 and cand not in ("الجديد", "الحالي", "السابق", "العمل", "الشركة", "المنشأة", "موظف"):
                entities["employee_query"] = cand

        if not entities.get("employee_query"):
            search_prefix_match = re.search(r"(?:ابحث عن|بحث عن)\s+(?:موظف\s+)?([أ-ي\w\s]{2,25})", text)
            if search_prefix_match and not is_legal_or_general_inquiry:
                cand = search_prefix_match.group(1).strip().strip("؟?!.,")
                if cand and len(cand) >= 2 and cand not in ("الجديد", "الحالي", "السابق", "العمل", "الشركة", "المنشأة", "موظف"):
                    entities["employee_query"] = cand

        name_match = re.search(r"(?:للموظف|للموظفة|الموظف|الموظفة|عن الموظف|عن الموظفة)\s+([أ-ي\w\s]{2,25})", text)
        if name_match and not is_legal_or_general_inquiry and not entities.get("employee_query"):
            cand = name_match.group(1).strip()
            # استبعاد الكلمات الوصفية الشائعة
            if cand and len(cand) >= 2 and cand not in ("الجديد", "الحالي", "السابق", "العمل", "الشركة", "المنشأة", "المؤرشف", "المؤرشفين"):
                entities["employee_query"] = cand

        # استخراج اسم الموظف يتم فقط عند وجود دلالة لغوية صريحة (مثل: ابحث عن موظف اسمه X، عن الموظف X)
        # ولا يتم افتراض أي نص أو رموز قصيرة كأسماء موظفين تجنباً لتحويل الأسئلة أو الاستعلامات إلى بحث بالاسم.
        pass

        # عدد الأيام مثل 5 أيام
        days_match = re.search(r"(\d+)\s*(?:يوم|ايام|أيام|days)", text, re.IGNORECASE)
        if days_match:
            entities["days"] = int(days_match.group(1))

        # المبالغ المالية مثل 8000 ريال أو بمبلغ 1200 أو بقيمة 500
        money_match = re.search(r"(?:بمبلغ|مبلغ|بقيمة|قيمة)\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if not money_match:
            money_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:ريال|رس|sar)", text, re.IGNORECASE)
        if money_match:
            entities["amount"] = float(money_match.group(1))

        # التواريخ بصيغة YYYY-MM-DD
        dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        if dates:
            entities["dates"] = dates

        return entities

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "Laya Decision Engine",
            "version": self.version,
            "has_native_laya": self.has_native_laya,
            "laya_source_repo": "https://github.com/NandhaKishorM/laya",
            "local_path": str(LAYA_REPO_PATH),
            "domains_supported": list(self.DOMAINS_CRITERIA.keys()),
        }
