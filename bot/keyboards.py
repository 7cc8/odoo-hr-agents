"""Interactive Keyboards and Templates catalog for Telegram Bot."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

TEMPLATES_CATALOG: Dict[str, Dict[str, Any]] = {
    "master": {
        "title": "🏢 1. القالب الشامل لتأسيس المنشأة (Master)",
        "file": Path("templates") / "master" / "Master_Client_Onboarding_Template.xlsx",
        "caption": "🏢 <b>القالب الشامل لتأسيس المنشأة الجديدة في Odoo HR</b>\nيحتوي على كافة التبويبات لتأسيس الشركة، الفروع، الأقسام، الموظفين، العقود، الرواتب، والإجازات.",
    },
    "emp": {
        "title": "👥 2. قالب الموظفين ومواقع العمل",
        "file": Path("templates") / "modular" / "template_employees.xlsx",
        "caption": "👥 <b>قالب استيراد الموظفين ومواقع العمل</b>\nلتسجيل بيانات الموظفين، الهويات، الجنسيات، والأقسام والفروع.",
    },
    "contract": {
        "title": "📜 3. قالب العقود والبدلات (hr.version)",
        "file": Path("templates") / "modular" / "template_contracts_allowances.xlsx",
        "caption": "📜 <b>قالب عقود العمل والبدلات</b>\nلتوثيق العقود، الراتب الأساسي، بدل السكن، النقل، وفترة التجربة (مادة 53).",
    },
    "payroll": {
        "title": "💰 4. قالب الرواتب وتأمينات GOSI",
        "file": Path("templates") / "modular" / "template_payroll_gosi.xlsx",
        "caption": "💰 <b>قالب الرواتب والتأمينات الاجتماعية (GOSI)</b>\nلحسابات نسب التأمينات والآيبان البنكي لنظام حماية الأجور WPS.",
    },
    "timeoff": {
        "title": "🏖️ 5. قالب الإجازات والأرصدة",
        "file": Path("templates") / "modular" / "template_timeoff.xlsx",
        "caption": "🏖️ <b>قالب الإجازات والأرصدة الافتتاحية</b>\nلتسجيل الإجازات السنوية وإجازات المناسبات نظاماً (زواج، وفاة، مولود).",
    },
    "attend": {
        "title": "⏰ 6. قالب ساعات الحضور والدوام",
        "file": Path("templates") / "modular" / "template_attendance.xlsx",
        "caption": "⏰ <b>قالب كشف الحضور وساعات العمل</b>\nلتسجيل ساعات الدوام الفعلية، والتأخير والغياب الشهري.",
    },
    "overtime": {
        "title": "⏱️ 7. قالب العمل الإضافي (مادة 107)",
        "file": Path("templates") / "modular" / "template_overtime.xlsx",
        "caption": "⏱️ <b>قالب العمل الإضافي (الأوفرتايم)</b>\nلحساب ساعات الإضافي بمعامل 1.5x الأجر المعتاد بموجب المادة 107.",
    },
    "loan": {
        "title": "💳 8. قالب القروض وسلف الموظفين",
        "file": Path("templates") / "modular" / "template_loans_installments.xlsx",
        "caption": "💳 <b>قالب سلف وقروض الموظفين (مادة 92)</b>\nلجدولة الأقساط الشهرية مع ضمان عدم تجاوز 25% من الراتب.",
    },
    "disc": {
        "title": "⚖️ 9. قالب الجزاءات والإنذارات",
        "file": Path("templates") / "modular" / "template_disciplinary.xlsx",
        "caption": "⚖️ <b>قالب الجزاءات والإنذارات التأديبية</b>\nلتوثيق محاضر التحقيق وقرارات الخصم المعتمدة.",
    },
    "eos": {
        "title": "📑 10. قالب مكافأة نهاية الخدمة",
        "file": Path("templates") / "modular" / "template_end_of_service.xlsx",
        "caption": "📑 <b>قالب مكافأة نهاية الخدمة والتسويات</b>\nلحساب مستحقات انتهاء العقد والاستقالة والفصل وفق مواد نظام العمل.",
    },
    "appraisal": {
        "title": "🌟 11. قالب تقييمات الأداء",
        "file": Path("templates") / "modular" / "template_appraisals.xlsx",
        "caption": "🌟 <b>قالب تقييمات أداء الموظفين</b>\nلتقييم الأداء السنوي وفترة التجربة ومعدلات الأهداف والكفاءات.",
    },
    "recruit": {
        "title": "🎯 12. قالب شواغر التوظيف والمتقدمين",
        "file": Path("templates") / "modular" / "template_recruitment.xlsx",
        "caption": "🎯 <b>قالب شواغر التوظيف والمرشحين</b>\nلتسجيل المتقدمين ونتائج المقابلات وعروض العمل.",
    },
    "gr": {
        "title": "🏛️ 13. قالب المعاملات الحكومية والجوازات",
        "file": Path("templates") / "modular" / "template_gr_transactions.xlsx",
        "caption": "🏛️ <b>قالب المعاملات الحكومية والتأشيرات</b>\nلتجديد الإقامات والجوازات ورخص العمل عبر مقيم وقوى.",
    },
    "company": {
        "title": "🏢 14. قالب بيانات تأسيس الشركة",
        "file": Path("templates") / "modular" / "template_company_setup.xlsx",
        "caption": "🏢 <b>قالب تأسيس المنشأة والحسابات البنكية</b>\nللسجل التجاري والرقم الضريبي والآيبان والعنوان الوطني.",
    },
}


def get_main_menu_keyboard() -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "📥 استلم قوالب الإكسل (14 قالباً)", "callback_data": "menu:templates"},
                {"text": "🌴 طلب واستعلام الإجازات", "callback_data": "menu:leaves"},
            ],
            [
                {"text": "⏰ الحضور والعمل الإضافي", "callback_data": "menu:attendance"},
                {"text": "⚖️ الجزاءات والانضباط", "callback_data": "menu:disciplinary"},
            ],
            [
                {"text": "💼 نهاية الخدمة والتسويات", "callback_data": "menu:eos"},
                {"text": "🏛️ المعاملات ومقيم وقوى", "callback_data": "menu:gr"},
            ],
            [
                {"text": "🌟 تقييمات الأداء والموظفين", "callback_data": "menu:appraisal"},
                {"text": "💳 السلف وقروض الموظفين", "callback_data": "menu:loan"},
            ],
            [
                {"text": "🎯 شواغر التوظيف والمرشحين", "callback_data": "menu:recruitment"},
                {"text": "📜 عقود العمل وهيكلة الأجور", "callback_data": "menu:contract"},
            ],
            [
                {"text": "📊 المؤشرات والتحليلات الشاملة", "callback_data": "menu:analytics"},
                {"text": "💵 مسير الرواتب وحماية الأجور (WPS)", "callback_data": "menu:payroll"},
            ],
            [
                {"text": "🔗 اربط خادم Odoo جديداً", "callback_data": "odoo:edit_wizard"},
                {"text": "⚙️ راجع بيانات الاتصال الحالية", "callback_data": "menu:odoo_settings"},
            ],
            [
                {"text": "🏢 تصفح الشركات والفروع", "callback_data": "menu:show_companies"},
                {"text": "📈 تابع جاهزية الوكلاء", "callback_data": "menu:system_status"},
            ],
            [
                {"text": "📜 الخطابات وشهادات التعريف", "callback_data": "menu:letters"},
                {"text": "🧾 المصروفات والانتدابات", "callback_data": "menu:expenses"},
            ],
            [
                {"text": "🔔 تنبيهات وصلاحيات الوثائق", "callback_data": "menu:expiries"},
                {"text": "🛡️ تقرير التدقيق الرقابي PDF (سجل)", "callback_data": "audit:pdf"},
            ],
            [
                {"text": "🛠️ وكيل الإصلاح الذاتي (مصلح)", "callback_data": "musleh:info"},
            ],
            [
                {"text": "🔗 إعدادات وربط خادم Odoo", "callback_data": "menu:odoo_settings"},
            ]
        ]
    }


def get_templates_menu_keyboard() -> Dict[str, Any]:
    buttons = [
        [{"text": "🏢 1. حمّل القالب الشامل لتأسيس المنشأة (Master)", "callback_data": "get_tpl:master"}],
        [
            {"text": "👥 2. الموظفون", "callback_data": "get_tpl:emp"},
            {"text": "📜 3. العقود والبدلات", "callback_data": "get_tpl:contract"},
        ],
        [
            {"text": "💰 4. الرواتب والتأمينات", "callback_data": "get_tpl:payroll"},
            {"text": "🏖️ 5. الإجازات", "callback_data": "get_tpl:timeoff"},
        ],
        [
            {"text": "⏰ 6. الحضور والدوام", "callback_data": "get_tpl:attend"},
            {"text": "⏱️ 7. ساعات العمل الإضافية", "callback_data": "get_tpl:overtime"},
        ],
        [
            {"text": "💳 8. السلف والأقساط", "callback_data": "get_tpl:loan"},
            {"text": "⚖️ 9. الجزاءات والإنذارات", "callback_data": "get_tpl:disc"},
        ],
        [
            {"text": "📑 10. مكافأة نهاية الخدمة", "callback_data": "get_tpl:eos"},
            {"text": "🌟 11. تقييمات الأداء", "callback_data": "get_tpl:appraisal"},
        ],
        [
            {"text": "🎯 12. التوظيف والمرشحين", "callback_data": "get_tpl:recruit"},
            {"text": "🏛️ 13. المعاملات والجوازات", "callback_data": "get_tpl:gr"},
        ],
        [
            {"text": "🏢 14. بيانات المنشأة البنكية", "callback_data": "get_tpl:company"},
        ],
        [
            {"text": "🔙 عُد للقائمة الرئيسية", "callback_data": "menu:main"},
        ]
    ]
    return {"inline_keyboard": buttons}

