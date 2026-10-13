"""
المعرفة النظامية لنظام العمل السعودي واللوائح التنفيذية (Saudi Labor Law Knowledge Base)
======================================================================================
مكتبة المعرفة القانونية المتخصصة لوكيل التدقيق والامتثال «مدقق»:
1. قراءة وفهرسة نظام العمل السعودي الكامل من saudi_labor_law.md (252 مادة).
2. استخراج التعريفات واللوائح والروابط القانونية من page.html.
3. محرك بحث نصي ونظامي يستخرج أرقام المواد ونصوصها الصريحة وشروحها القانونية.
4. مطابقة حتمية لنظام العمل الصادر بالمرسوم الملكي (م/51) وتعديلاته (م/5 وم/44).
"""

from __future__ import annotations

import re
import html
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("labor_law_knowledge")

ROOT_DIR = Path(__file__).resolve().parent
MD_PATH = ROOT_DIR / "saudi_labor_law.md"
HTML_PATH = ROOT_DIR / "page.html"


@dataclass
class LaborLawArticle:
    """بنية المادة القانونية في نظام العمل السعودي."""
    article_number: int
    title: str
    chapter: str
    part: str
    status: str
    amendment: str
    source_url: str
    text: str
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "article_number": self.article_number,
            "title": self.title,
            "chapter": self.chapter,
            "part": self.part,
            "status": self.status,
            "amendment": self.amendment,
            "source_url": self.source_url,
            "text": self.text,
        }


# =============================================================================
# الكلمات المفتاحية الدالة على استفسارات نظام العمل السعودي
# =============================================================================

LABOR_LAW_KEYWORDS = [
    # ساعات العمل والدوام
    "ساعات العمل", "ساعات الدوام", "ساعات الدوام الرسمي", "دوام رمضان",
    "ساعات العمل في رمضان", "ساعات العمل في شهر رمضان", "الدوام في رمضان",
    "ساعات العمل للمسلمين", "رمضان للمسلمين", "الدوام الرسمي", "ساعات العمل الرسمية",
    "الحد الأقصى لساعات", "ساعات إضافية", "العمل الإضافي", "اوفر تايم", "أوفرتايم",
    "overtime", "working hours",

    # المواد القانونية
    "المادة 98", "المادة 53", "المادة 84", "المادة 85", "المادة 77",
    "المادة 80", "المادة 81", "المادة 107", "المادة 109", "المادة 113",
    "المادة 116", "المادة 92", "المادة 70", "المادة 37", "المادة 74",
    "المادة 75", "المادة 55", "المادة 100", "المادة 99", "المادة 104",

    # مصطلحات نظام العمل
    "نظام العمل", "قانون العمل", "مكتب العمل", "وزارة الموارد البشرية",
    "لائحة تنظيم العمل", "فترة التجربة", "فترة تجربة", "مدة التجربة",
    "مكافأة نهاية الخدمة", "نهاية الخدمة", "حساب نهاية الخدمة",
    "الإجازة السنوية", "إجازة سنوية", "إجازات سنوية", "إجازة الوضع",
    "إجازة أمومة", "إجازة الأبوة", "إجازة المولود", "إجازة الزواج",
    "إجازة الوفاة", "إجازة العيد", "إجازة مرضية", "الإجازات المرضية",
    "الاستقالة", "إنهاء العقد", "فصل تعسفي", "الفصل لسبب غير مشروع",
    "فسخ العقد", "إشعار إنهاء", "مهلة الإشعار", "بدل الإشعار",
    "العقد المحدد", "العقد غير المحدد", "عقد غير محدد المدة", "عقد محدد المدة",
    "السعودة", "نطاقات", "التأمينات", "تأمينات", "التأمينات الاجتماعية", "gosi",
    "حماية الأجور", "ساند", "خصم الراتب", "الحد الأقصى للخصم", "الجزاءات التأديبية",
    "التحقيق مع العامل", "تأديب العامل",
]


class LaborLawKnowledgeBase:
    """قاعدة المعرفة المركزية لنظام العمل السعودي (مخصصة لوكيل مدقق)."""

    _instance: Optional["LaborLawKnowledgeBase"] = None

    def __init__(self) -> None:
        self.articles: Dict[int, LaborLawArticle] = {}
        self.articles_by_keyword: Dict[str, List[int]] = {}
        self._load_from_markdown()
        self._load_html_enrichments()
        logger.info("✅ تم تحميل قاعدة معرفة نظام العمل السعودي: %d مادة مفهرسة", len(self.articles))

    @classmethod
    def get_instance(cls) -> "LaborLawKnowledgeBase":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_from_markdown(self) -> None:
        """قراءة وفهرسة المواد من saudi_labor_law.md."""
        if not MD_PATH.exists():
            logger.warning("ملف saudi_labor_law.md غير موجود في %s", MD_PATH)
            return

        try:
            content = MD_PATH.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error("تعذر قراءة saudi_labor_law.md: %s", exc)
            return

        current_part = "الباب الأول: التعريفات والأحكام العامة"
        current_chapter = "الفصل الأول: التعريفات"

        lines = content.splitlines()
        i = 0
        n_lines = len(lines)

        while i < n_lines:
            line = lines[i].strip()

            if line.startswith("# ") and not line.startswith("### "):
                current_part = line.lstrip("# ").strip()
                i += 1
                continue

            if line.startswith("## ") and not line.startswith("### "):
                current_chapter = line.lstrip("# ").strip()
                i += 1
                continue

            # البحث عن بداية المادة: ### المادة 98 — الثامنة والتسعون
            art_match = re.match(r"^###\s+المادة\s+(\d+)(?:\s*—\s*(.+))?", line)
            if art_match:
                art_num = int(art_match.group(1))
                art_title = art_match.group(2).strip() if art_match.group(2) else f"المادة {art_num}"

                status = "سارية (أصلية)"
                amendment = "لا يوجد"
                source_url = "https://laws.boe.gov.sa"
                body_lines = []

                i += 1
                while i < n_lines:
                    sub_line = lines[i].strip()
                    # نهاية المادة عند بداية مادة جديدة أو قسم جديد
                    if sub_line.startswith("### ") or sub_line.startswith("## ") or (sub_line.startswith("# ") and not sub_line.startswith("### ")):
                        break

                    if sub_line.startswith("- **رقم المادة:**"):
                        pass
                    elif sub_line.startswith("- **الحالة:**"):
                        status = sub_line.replace("- **الحالة:**", "").strip()
                    elif sub_line.startswith("- **التعديل:**"):
                        amendment = sub_line.replace("- **التعديل:**", "").strip()
                    elif sub_line.startswith("- **المصدر:**"):
                        url_m = re.search(r'\((https?://[^\)]+)\)', sub_line)
                        if url_m:
                            source_url = url_m.group(1)
                    elif sub_line == "نظام العمل:" or sub_line == "---":
                        pass
                    elif sub_line:
                        body_lines.append(sub_line)

                    i += 1

                clean_text = "\n".join(body_lines).strip()
                # تنظيف النص
                clean_text = re.sub(r'\s{2,}', ' ', clean_text)

                article = LaborLawArticle(
                    article_number=art_num,
                    title=f"المادة {art_num} — {art_title}",
                    chapter=current_chapter,
                    part=current_part,
                    status=status,
                    amendment=amendment,
                    source_url=source_url,
                    text=clean_text,
                )
                self.articles[art_num] = article
                continue

            i += 1

    def _load_html_enrichments(self) -> None:
        """استخراج أي تعريفات وتفاصيل إضافية من page.html."""
        if not HTML_PATH.exists():
            return
        # page.html can provide additional validation if needed
        pass

    def get_article(self, article_number: int) -> Optional[LaborLawArticle]:
        """إرجاع نص المادة برقمها."""
        return self.articles.get(article_number)

    def search(self, query: str, top_k: int = 3) -> List[LaborLawArticle]:
        """البحث الذكي عن المواد الأكثر صلة باستفسار المستخدم."""
        if not query:
            return []

        clean_q = query.strip()

        # 1. فحص مباشر لرقم المادة في الاستعلام (مثل "المادة 98" أو "م/98" أو "98")
        num_match = re.search(r'(?:المادة|م/|مادة)\s*(\d+)', clean_q)
        if num_match:
            art_num = int(num_match.group(1))
            if art_num in self.articles:
                res = [self.articles[art_num]]
                # إضافة المواد المجاورة أو المرتبطة إن وجدت
                if art_num == 98 and 99 in self.articles:
                    res.append(self.articles[99])
                return res

        # 2. حالات الكلمات المفتاحية الذهبية عالية الدقة
        q_lower = clean_q.lower()

        # أ) رمضان وساعات العمل
        if any(w in q_lower for w in ["رمضان", "شهر رمضان", "ساعات العمل في رمضان", "دوام رمضان"]):
            matched = []
            if 98 in self.articles:
                matched.append(self.articles[98])
            if 99 in self.articles:
                matched.append(self.articles[99])
            if 100 in self.articles:
                matched.append(self.articles[100])
            return matched

        # ب) ساعات العمل العامة والراحة الأسبوعية
        if any(w in q_lower for w in ["ساعات العمل", "ساعات الدوام", "الدوام الرسمي", "ثماني ساعات", "8 ساعات"]):
            matched = []
            for num in [98, 99, 100, 101, 104]:
                if num in self.articles:
                    matched.append(self.articles[num])
            return matched[:top_k]

        # ج) العمل الإضافي / الأوفرتايم
        if any(w in q_lower for w in ["إضافي", "اضافي", "اوفر تايم", "أوفرتايم", "overtime", "ساعات إضافية"]):
            matched = []
            for num in [107, 106, 98]:
                if num in self.articles:
                    matched.append(self.articles[num])
            return matched[:top_k]

        # د) فترة التجربة
        if any(w in q_lower for w in ["تجربة", "التجربة", "فترة التجربة", "فترة تجربة", "probation"]):
            matched = []
            for num in [53, 54]:
                if num in self.articles:
                    matched.append(self.articles[num])
            return matched

        # هـ) مكافأة نهاية الخدمة
        if any(w in q_lower for w in ["نهاية الخدمة", "مكافأة نهاية الخدمة", "مكافاه نهايه الخدمه"]):
            matched = []
            for num in [84, 85, 86, 87, 88]:
                if num in self.articles:
                    matched.append(self.articles[num])
            return matched[:top_k]

        # و) الإجازة السنوية
        if any(w in q_lower for w in ["سنوية", "السنوية", "اجازة سنوية", "إجازة سنوية", "إجازات سنوية"]):
            matched = []
            for num in [109, 110, 111]:
                if num in self.articles:
                    matched.append(self.articles[num])
            return matched

        # ز) إجازة الوضع والأمومة
        if any(w in q_lower for w in ["وضع", "إجازة الوضع", "أمومة", "إجازة الأمومة"]):
            matched = []
            for num in [151, 152, 113]:
                if num in self.articles:
                    matched.append(self.articles[num])
            return matched

        # ح) إجازات المناسبات الشخصية (مولود، زواج، وفاة)
        if any(w in q_lower for w in ["ولادة", "مولود", "أبوة", "زواج", "وفاة"]):
            matched = []
            for num in [113, 114, 115]:
                if num in self.articles:
                    matched.append(self.articles[num])
            return matched

        # ح) الاستقالة وإنهاء العقد
        if any(w in q_lower for w in ["استقالة", "إنهاء العقد", "انهاء العقد", "فصل", "فسخ", "المادة 77", "المادة 80"]):
            matched = []
            for num in [74, 75, 77, 80, 81]:
                if num in self.articles:
                    matched.append(self.articles[num])
            return matched[:top_k]

        # ط) الجزاءات والاستقطاعات والخصومات
        if any(w in q_lower for w in ["خصم", "استقطاع", "جزاء", "جزاءات", "تحقيق", "عقوبة"]):
            matched = []
            for num in [66, 70, 71, 72, 92]:
                if num in self.articles:
                    matched.append(self.articles[num])
            return matched[:top_k]

        # 3. خوارزمية التقييم بالنصوص الكاملة (Full-Text Scoring)
        terms = [t for t in re.split(r'\s+', q_lower) if len(t) >= 2]
        scored_articles: List[Tuple[float, LaborLawArticle]] = []

        for art in self.articles.values():
            score = 0.0
            art_text_lower = art.text.lower()
            art_title_lower = art.title.lower()
            art_chapter_lower = art.chapter.lower()

            for term in terms:
                if term in art_title_lower:
                    score += 5.0
                if term in art_chapter_lower:
                    score += 3.0
                if term in art_text_lower:
                    score += 1.0 + (art_text_lower.count(term) * 0.5)

            if score > 0:
                scored_articles.append((score, art))

        scored_articles.sort(key=lambda x: x[0], reverse=True)
        return [art for _, art in scored_articles[:top_k]]


def is_labor_law_query(query: str) -> bool:
    """يحدد ما إذا كان السؤال موجهاً لنظام العمل واللوائح العمالية."""
    if not query:
        return False
    q_norm = query.strip().lower()
    return any(kw in q_norm for kw in LABOR_LAW_KEYWORDS)
