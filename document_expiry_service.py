"""
خدمة الرصد الاستباقي لانتهاء الوثائق والتنبيهات المجدولة (Document Expiry Monitoring Service)
==================================================================================================
الطبقة التنفيذية المستقلة لمراقبة وإشعار تواريخ انتهاء الوثائق الثبوتية وصلاحيات العمل (Phase 25):
1. هوية مقيم / الهوية الوطنية (id_expiry_date) - أنظمة الجوازات ومنصة مقيم.
2. جواز السفر (passport_expiration_date) - صلاحية السفر والتأشيرات (اشتراط 6 أشهر).
3. تأشيرة العمل / الدخول (visa_expire) - وزارة الخارجية وأنظمة العمل.
4. رخصة العمل (work_permit_expiration_date) - منصة قوى والاشتراطات المهنية.
5. انتهاء فترة التجربة (trial_date_end) - المادة 53 من نظام العمل (90 أو 180 يوماً).
6. انتهاء عقد العمل محدد المدة (contract_date_end) - المادتان 37 و 55 لغير السعوديين.

نوافذ التنبيه ومستويات الخطورة:
- منتهي الصلاحية (Expired): <= 0 يوم (غرامات فورية وإيقاف خدمات).
- حرج جداً (Critical): 1 إلى 7 أيام (يتطلب التجديد الفوري خلال أسبوع).
- تحذيري (Warning): 8 إلى 30 يوماً (أقل من شهر).
- تنبيه مبكر (Notice): 31 إلى 90 يوماً (بين شهر و 3 أشهر).

الضوابط:
- متوافق مع نظام العمل السعودي والأنظمة الحكومية (مقيم، قوى، التأمينات).
- توليد تقارير HTML تفاعلية وتقارير PDF عالية الجودة.
- دعم البث المباشر وقوالب تيليقرام التفاعلية.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from odoo_readonly_repository import OdooReadonlyRepository
from eos_service import detect_employee_nationality

EXPIRY_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "expiries")
EXPIRY_AUDIT_LOG = os.path.join(os.path.dirname(__file__), "logs", "expiry_monitor_log.jsonl")

# تصنيفات الوثائق وتفاصيلها النظامية
DOCUMENT_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "iqama": {
        "id": "iqama",
        "field_name": "id_expiry_date",
        "title_saudi_ar": "الهوية الوطنية",
        "title_expat_ar": "هوية مقيم (الإقامة)",
        "title_en": "National ID / Iqama",
        "applicable_to": "all",
        "legal_article_ar": "نظام الإقامة وجوازات السفر - غرامة 500 ريال للتأخير الأول وإيقاف خدمات المنشأة في مقيم",
        "authority": "المديرية العامة للجوازات / منصة مقيم",
    },
    "passport": {
        "id": "passport",
        "field_name": "passport_expiration_date",
        "title_saudi_ar": "جواز السفر السعودي",
        "title_expat_ar": "جواز السفر",
        "title_en": "Passport",
        "applicable_to": "all",
        "legal_article_ar": "اشتراط سريان الجواز لمدة 6 أشهر كحد أدنى لإصدار تأشيرات الخروج والعودة وتجديد الإقامة",
        "authority": "منصة أبشر / سفارات وقنصليات الدول",
    },
    "work_permit": {
        "id": "work_permit",
        "field_name": "work_permit_expiration_date",
        "title_saudi_ar": "تصريح العمل الميداني",
        "title_expat_ar": "رخصة العمل (منصة قوى)",
        "title_en": "Work Permit",
        "applicable_to": "expat",
        "legal_article_ar": "المادة 33 من نظام العمل - حظر تشغيل الوافد دون رخصة عمل سارية، وإيقاف الملف في منصة قوى",
        "authority": "وزارة الموارد البشرية والتنمية الاجتماعية / منصة قوى",
    },
    "visa": {
        "id": "visa",
        "field_name": "visa_expire",
        "title_saudi_ar": "تأشيرة رسمية",
        "title_expat_ar": "تأشيرة العمل / الدخول",
        "title_en": "Visa",
        "applicable_to": "expat",
        "legal_article_ar": "أنظمة الدخول والإقامة - ضرورة استكمال إجراءات إصدار الإقامة قبل انقضاء صلاحية التأشيرة",
        "authority": "وزارة الخارجية / المديرية العامة للجوازات",
    },
    "probation": {
        "id": "probation",
        "field_name": "trial_date_end",
        "title_saudi_ar": "فترة التجربة",
        "title_expat_ar": "فترة التجربة",
        "title_en": "Probation Period",
        "applicable_to": "all",
        "legal_article_ar": "المادة 53 من نظام العمل - لا تتجاوز 90 يوماً (أو 180 باتفاق كتابي)، وبانتهائها يثبت الموظف نظامياً",
        "authority": "نظام العمل السعودي (م/53)",
    },
    "contract": {
        "id": "contract",
        "field_name": "contract_date_end",
        "title_saudi_ar": "نهاية عقد العمل المحدد",
        "title_expat_ar": "نهاية عقد عمل المقيم",
        "title_en": "Employment Contract End Date",
        "applicable_to": "all",
        "legal_article_ar": "المادتان 37 و 55 - عقد غير السعودي يعد محدداً بمدته أو رخصة عمله، وينتهي بانقضاء أجله ما لم يجدد",
        "authority": "نظام العمل السعودي (م/37 وم/55)",
    },
}

SEVERITY_LEVELS: Dict[str, Dict[str, Any]] = {
    "expired": {
        "id": "expired",
        "label_ar": "منتهي الصلاحية",
        "label_en": "Expired",
        "badge_color": "#EF4444",
        "bg_color": "#FEF2F2",
        "emoji": "🔴",
        "priority": 1,
    },
    "critical": {
        "id": "critical",
        "label_ar": "حرج جداً (خلال 7 أيام)",
        "label_en": "Critical (<= 7 days)",
        "badge_color": "#F97316",
        "bg_color": "#FFF7ED",
        "emoji": "🚨",
        "priority": 2,
    },
    "warning": {
        "id": "warning",
        "label_ar": "تحذير (خلال شهر)",
        "label_en": "Warning (<= 30 days)",
        "badge_color": "#F59E0B",
        "bg_color": "#FFFBEB",
        "emoji": "⚠️",
        "priority": 3,
    },
    "notice": {
        "id": "notice",
        "label_ar": "تنبيه مبكر (خلال 90 يوماً)",
        "label_en": "Notice (<= 90 days)",
        "badge_color": "#0284C7",
        "bg_color": "#F0F9FF",
        "emoji": "ℹ️",
        "priority": 4,
    },
    "safe": {
        "id": "safe",
        "label_ar": "سارٍ (آمن)",
        "label_en": "Safe (> 90 days)",
        "badge_color": "#10B981",
        "bg_color": "#ECFDF5",
        "emoji": "✅",
        "priority": 5,
    },
}


@dataclass
class DocumentExpiryItem:
    employee_id: int
    employee_name: str
    is_saudi: bool
    nationality_text_ar: str
    identification_id: str
    job_title: str
    department_name: str
    category_id: str
    category_title_ar: str
    category_title_en: str
    field_name: str
    expiry_date: str
    days_remaining: int
    severity: str
    severity_label_ar: str
    severity_badge_color: str
    legal_article_ar: str
    authority: str


@dataclass
class DocumentExpiryScanResult:
    scan_date: str
    total_employees_scanned: int
    total_alerts: int
    expired_count: int
    critical_count: int
    warning_count: int
    notice_count: int
    safe_count: int
    items: List[DocumentExpiryItem]
    by_category: Dict[str, int]
    by_severity: Dict[str, int]
    by_department: Dict[str, int]


class DocumentExpiryService:
    """
    الخدمة الشاملة للرصد الاستباقي لانتهاء الوثائق والتنبيهات المجدولة.
    """

    def __init__(self, repo: Optional[OdooReadonlyRepository] = None):
        self.repo = repo or OdooReadonlyRepository()
        os.makedirs(EXPIRY_OUTPUT_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(EXPIRY_AUDIT_LOG), exist_ok=True)

    def _parse_date(self, val: Any) -> Optional[date]:
        """تحويل القيمة إلى كائن تاريخ صالح."""
        if not val or val is False:
            return None
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            val_clean = val.strip()[:10]
            try:
                return datetime.strptime(val_clean, "%Y-%m-%d").date()
            except ValueError:
                return None
        return None

    def _calculate_severity(self, days: int) -> str:
        """تحديد مستوى الخطورة وفق عدد الأيام المتبقية."""
        if days <= 0:
            return "expired"
        elif days <= 7:
            return "critical"
        elif days <= 30:
            return "warning"
        elif days <= 90:
            return "notice"
        return "safe"

    def scan_expiries(
        self,
        reference_date: Optional[date] = None,
        max_days: int = 90,
        category_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        department_filter: Optional[str] = None,
        employees_data: Optional[List[Dict[str, Any]]] = None,
    ) -> DocumentExpiryScanResult:
        """
        فحص شامل لكافة وثائق الموظفين وحساب الاستحقاقات ومستويات الخطورة.
        """
        today = reference_date or date.today()

        if employees_data is not None:
            employees = employees_data
        else:
            try:
                employees = self.repo.get_employees_for_expiry_monitoring(limit=500)
                if not employees:
                    employees = self.repo.get_employees(limit=500)
            except Exception:
                employees = []

        items: List[DocumentExpiryItem] = []
        by_category: Dict[str, int] = {k: 0 for k in DOCUMENT_CATEGORIES}
        by_severity: Dict[str, int] = {k: 0 for k in SEVERITY_LEVELS}
        by_dept: Dict[str, int] = {}

        for emp in employees:
            emp_id = emp.get("id") or 0
            emp_name = emp.get("name") or f"Employee #{emp_id}"
            is_saudi = detect_employee_nationality(emp)
            nationality_text = "مواطن سعودي" if is_saudi else "مقيم وافد"
            ident_id = str(emp.get("identification_id") or "").strip()

            job_val = emp.get("job_id")
            job_title = job_val[1] if isinstance(job_val, (list, tuple)) and len(job_val) > 1 else str(job_val or "موظف")

            dept_val = emp.get("department_id")
            dept_name = dept_val[1] if isinstance(dept_val, (list, tuple)) and len(dept_val) > 1 else str(dept_val or "الإدارة العامة")

            if department_filter and department_filter.lower() not in dept_name.lower():
                continue

            for cat_key, cat_meta in DOCUMENT_CATEGORIES.items():
                if category_filter and category_filter != cat_key:
                    continue

                # استثناء رخص العمل للوافدين فقط إذا كان الموظف سعودياً
                if cat_meta["applicable_to"] == "expat" and is_saudi:
                    continue

                field_name = cat_meta["field_name"]
                raw_date = emp.get(field_name)
                exp_date = self._parse_date(raw_date)

                if not exp_date:
                    continue

                days_diff = (exp_date - today).days
                severity = self._calculate_severity(days_diff)

                # إذا كانت خارج النافذة الزمنية المطلوبة وليست منتهية
                if days_diff > max_days:
                    continue

                if severity_filter and severity_filter != severity:
                    continue

                sev_info = SEVERITY_LEVELS.get(severity, SEVERITY_LEVELS["safe"])
                title_ar = cat_meta["title_saudi_ar"] if is_saudi else cat_meta["title_expat_ar"]

                item = DocumentExpiryItem(
                    employee_id=emp_id,
                    employee_name=emp_name,
                    is_saudi=is_saudi,
                    nationality_text_ar=nationality_text,
                    identification_id=ident_id,
                    job_title=job_title,
                    department_name=dept_name,
                    category_id=cat_key,
                    category_title_ar=title_ar,
                    category_title_en=cat_meta["title_en"],
                    field_name=field_name,
                    expiry_date=exp_date.isoformat(),
                    days_remaining=days_diff,
                    severity=severity,
                    severity_label_ar=sev_info["label_ar"],
                    severity_badge_color=sev_info["badge_color"],
                    legal_article_ar=cat_meta["legal_article_ar"],
                    authority=cat_meta["authority"],
                )
                items.append(item)

                by_category[cat_key] = by_category.get(cat_key, 0) + 1
                by_severity[severity] = by_severity.get(severity, 0) + 1
                by_dept[dept_name] = by_dept.get(dept_name, 0) + 1

        # ترتيب النتائج: المنتهي أولاً، ثم الحرج، ثم الأقرب تاريخاً
        items.sort(key=lambda x: (x.days_remaining, x.employee_id))

        total_alerts = len(items)
        scan_res = DocumentExpiryScanResult(
            scan_date=today.isoformat(),
            total_employees_scanned=len(employees),
            total_alerts=total_alerts,
            expired_count=by_severity.get("expired", 0),
            critical_count=by_severity.get("critical", 0),
            warning_count=by_severity.get("warning", 0),
            notice_count=by_severity.get("notice", 0),
            safe_count=by_severity.get("safe", 0),
            items=items,
            by_category=by_category,
            by_severity=by_severity,
            by_department=by_dept,
        )

        self._log_scan(scan_res)
        return scan_res

    def _log_scan(self, res: DocumentExpiryScanResult) -> None:
        """تسجيل نتائج الفحص في سجل التدقيق."""
        try:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scan_date": res.scan_date,
                "employees_scanned": res.total_employees_scanned,
                "total_alerts": res.total_alerts,
                "expired": res.expired_count,
                "critical": res.critical_count,
                "warning": res.warning_count,
                "notice": res.notice_count,
            }
            with open(EXPIRY_AUDIT_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def format_telegram_summary_message(
        self,
        scan_res: DocumentExpiryScanResult,
        top_n: int = 8,
    ) -> str:
        """
        صياغة بطاقة تقرير فحص الوثائق التفاعلية لقناة وتطبيقات تيليقرام.
        """
        total = scan_res.total_alerts
        exp_c = scan_res.expired_count
        crit_c = scan_res.critical_count
        warn_c = scan_res.warning_count
        not_c = scan_res.notice_count

        if total == 0:
            return (
                "✅ <b>سجل الوثائق الثبوتية ممتاز ونظامي!</b> 🏢\n"
                "────────────────────\n"
                f"• تم فحص <b>{scan_res.total_employees_scanned}</b> موظفاً في Odoo.\n"
                "• لا توجد أي وثائق منتهية أو قاربت على الانتهاء خلال الـ 90 يوماً القادمة.\n"
                "• كافة الهويات وجوازات السفر ورخص العمل سارية المفعول."
            )

        status_headline = "🚨 <b>تنبيه عاجل: توجد وثائق منتهية أو حرجة!</b>" if (exp_c > 0 or crit_c > 0) else "🔔 <b>تقرير متابعة صلاحيات الوثائق والعقود</b>"

        text = (
            f"{status_headline}\n"
            f"────────────────────\n"
            f"📅 <b>تاريخ الفحص:</b> <code>{scan_res.scan_date}</code>\n"
            f"👥 <b>إجمالي الموظفين المفحوصين:</b> <b>{scan_res.total_employees_scanned}</b>\n"
            f"📊 <b>إجمالي التنبيهات النشطة:</b> <b>{total}</b> وثيقة\n\n"
            f"<b>توزيع مستويات الخطورة:</b>\n"
            f"🔴 <b>منتهية الصلاحية:</b> <b>{exp_c}</b> (غرامات فورية)\n"
            f"🚨 <b>حرجة (خلال 7 أيام):</b> <b>{crit_c}</b>\n"
            f"⚠️ <b>تحذيرية (خلال 30 يوماً):</b> <b>{warn_c}</b>\n"
            f"ℹ️ <b>تنبيه مبكر (خلال 90 يوماً):</b> <b>{not_c}</b>\n"
            f"────────────────────\n"
            f"📋 <b>أبرز الوثائق المستحقة للتجديد:</b>\n\n"
        )

        for idx, item in enumerate(scan_res.items[:top_n], 1):
            sev_info = SEVERITY_LEVELS.get(item.severity, SEVERITY_LEVELS["safe"])
            emoji = sev_info["emoji"]

            if item.days_remaining < 0:
                day_str = f"منتهية منذ {abs(item.days_remaining)} يوم ⚠️"
            elif item.days_remaining == 0:
                day_str = "تنتهي اليوم!"
            else:
                day_str = f"متبقي {item.days_remaining} يوم"

            text += (
                f"{idx}. {emoji} <b>{item.employee_name}</b> (#{item.employee_id})\n"
                f"   • <b>{item.category_title_ar}:</b> <code>{item.expiry_date}</code> ({day_str})\n"
                f"   • القسم: {item.department_name} | {item.job_title}\n"
            )

        if total > top_n:
            rem = total - top_n
            text += f"\n<i>... وهناك {rem} وثائق أخرى تتطلب المتابعة.</i>\n"

        text += (
            "\n💡 <i>استخدم الأزرار أدناه لتصفية القائمة بحسب الأيام أو لتوليد تقرير PDF رسمي.</i>"
        )
        return text

    def render_html_report(self, scan_res: DocumentExpiryScanResult) -> str:
        """
        توليد تقرير HTML تفاعلي فائق الجمال وفق معايير الهوية المؤسسية السعودية.
        """
        rows_html = ""
        for idx, it in enumerate(scan_res.items, 1):
            if it.days_remaining < 0:
                day_badge = f'<span class="badge badge-expired">منتهية منذ {abs(it.days_remaining)} يوم</span>'
            elif it.days_remaining == 0:
                day_badge = '<span class="badge badge-critical">تنتهي اليوم</span>'
            elif it.days_remaining <= 7:
                day_badge = f'<span class="badge badge-critical">متبقي {it.days_remaining} أيام</span>'
            elif it.days_remaining <= 30:
                day_badge = f'<span class="badge badge-warning">متبقي {it.days_remaining} يوم</span>'
            else:
                day_badge = f'<span class="badge badge-notice">متبقي {it.days_remaining} يوم</span>'

            rows_html += f"""
            <tr>
                <td style="text-align: center; font-weight: 700;">{idx}</td>
                <td>
                    <div style="font-weight: 700; color: #0F172A;">{it.employee_name}</div>
                    <div style="font-size: 11px; color: #64748B;">#{it.employee_id} • {it.job_title}</div>
                </td>
                <td>
                    <div style="font-weight: 600;">{it.category_title_ar}</div>
                    <div style="font-size: 11px; color: #64748B;">{it.authority}</div>
                </td>
                <td>{it.department_name}</td>
                <td style="font-family: monospace; font-weight: 600; text-align: center;">{it.expiry_date}</td>
                <td style="text-align: center;">{day_badge}</td>
                <td style="font-size: 11px; color: #334155;">{it.legal_article_ar}</td>
            </tr>
            """

        if not scan_res.items:
            rows_html = """
            <tr>
                <td colspan="7" style="text-align: center; padding: 40px; color: #10B981; font-weight: 700;">
                    ✅ لا توجد وثائق منتهية أو قاربت على الانتهاء خلال فترة الفحص المحددة.
                </td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تقرير رصد صلاحيات الوثائق والهويات - {scan_res.scan_date}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        @page {{
            size: A4 landscape;
            margin: 10mm;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'IBM Plex Sans Arabic', -apple-system, sans-serif;
        }}
        body {{
            background: #F8FAFC;
            color: #0F172A;
            padding: 24px;
            font-size: 13px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #FFFFFF;
            padding: 28px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            border: 1px solid #E2E8F0;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #0F172A;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .title-section h1 {{
            font-size: 22px;
            font-weight: 700;
            color: #0F172A;
            margin-bottom: 4px;
        }}
        .title-section p {{
            font-size: 13px;
            color: #64748B;
        }}
        .meta-box {{
            text-align: left;
            font-size: 12px;
            color: #475569;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            padding: 14px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #E2E8F0;
        }}
        .stat-card .num {{
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 2px;
        }}
        .stat-card .label {{
            font-size: 11px;
            font-weight: 600;
        }}
        .card-total {{ background: #F1F5F9; color: #0F172A; }}
        .card-expired {{ background: #FEF2F2; color: #EF4444; border-color: #FCA5A5; }}
        .card-critical {{ background: #FFF7ED; color: #F97316; border-color: #FDBA74; }}
        .card-warning {{ background: #FFFBEB; color: #F59E0B; border-color: #FCD34D; }}
        .card-notice {{ background: #F0F9FF; color: #0284C7; border-color: #BAE6FD; }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th {{
            background: #0F172A;
            color: #FFFFFF;
            padding: 10px 12px;
            text-align: right;
            font-size: 12px;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #E2E8F0;
            vertical-align: middle;
        }}
        tr:hover td {{
            background: #F8FAFC;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-expired {{ background: #FEF2F2; color: #B91C1C; border: 1px solid #F87171; }}
        .badge-critical {{ background: #FFF7ED; color: #C2410C; border: 1px solid #FB923C; }}
        .badge-warning {{ background: #FFFBEB; color: #B45309; border: 1px solid #FBBF24; }}
        .badge-notice {{ background: #F0F9FF; color: #0369A1; border: 1px solid #38BDF8; }}

        .footer {{
            margin-top: 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            color: #64748B;
            border-top: 1px solid #E2E8F0;
            padding-top: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title-section">
                <h1>📋 تقرير الرصد الاستباقي لانتهاء الوثائق والصلاحيات</h1>
                <p>مراقبة شاملة لبطاقات الهوية والإقامات وجوازات السفر وتصاريح العمل وفترات التجربة والعقود</p>
            </div>
            <div class="meta-box">
                <div><b>تاريخ الفحص:</b> {scan_res.scan_date}</div>
                <div><b>إجمالي المفحوصين:</b> {scan_res.total_employees_scanned} موظفاً</div>
                <div><b>النظام:</b> Odoo ERP + أنظمة مقيم وقوى والعمل</div>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card card-total">
                <div class="num">{scan_res.total_alerts}</div>
                <div class="label">إجمالي التنبيهات المستحقة</div>
            </div>
            <div class="stat-card card-expired">
                <div class="num">{scan_res.expired_count}</div>
                <div class="label">منتهية الصلاحية (مخالفة)</div>
            </div>
            <div class="stat-card card-critical">
                <div class="num">{scan_res.critical_count}</div>
                <div class="label">حرجة (خلال 7 أيام)</div>
            </div>
            <div class="stat-card card-warning">
                <div class="num">{scan_res.warning_count}</div>
                <div class="label">تحذيرية (خلال 30 يوماً)</div>
            </div>
            <div class="stat-card card-notice">
                <div class="num">{scan_res.notice_count}</div>
                <div class="label">تنبيه مبكر (خلال 90 يوماً)</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 40px; text-align: center;">#</th>
                    <th>الموظف والوظيفة</th>
                    <th>الوثيقة / الصلاحية</th>
                    <th>الإدارة / القسم</th>
                    <th style="text-align: center;">تاريخ الانتهاء</th>
                    <th style="text-align: center;">المهلة المتبقية</th>
                    <th>السند والضابط النظامي</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <div class="footer">
            <div>تم التوليد آلياً عبر محرك الرقابة والاستباق الإداري لسراج • Odoo HR System</div>
            <div>مطابق للأنظمة السعودية: مقيم، قوى، التأمينات، ونظام العمل</div>
        </div>
    </div>
</body>
</html>"""
        return html

    def generate_pdf_report(
        self,
        scan_res: DocumentExpiryScanResult,
        output_filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        توليد تقرير PDF رسمي لمخرجات فحص الصلاحيات باستخدام Playwright.
        """
        html_content = self.render_html_report(scan_res)
        fname = output_filename or f"expiry_report_{scan_res.scan_date.replace('-', '')}.html"
        html_path = os.path.join(EXPIRY_OUTPUT_DIR, fname)
        pdf_path = html_path.replace(".html", ".pdf")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(f"file:///{os.path.abspath(html_path).replace(chr(92), '/')}")
                page.wait_for_timeout(500)
                page.pdf(
                    path=pdf_path,
                    format="A4",
                    landscape=True,
                    print_background=True,
                    margin={"top": "8mm", "bottom": "8mm", "left": "10mm", "right": "10mm"},
                )
                browser.close()
            return pdf_path if os.path.exists(pdf_path) else None
        except Exception:
            # في حال عدم توفر Playwright يعود بمسار HTML كبديل معتمد
            return None
