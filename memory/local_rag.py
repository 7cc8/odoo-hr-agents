"""
المسترجع المحلي المدمج لقواعد ونظام العمل (Local RAG via SQLite FTS5 & Text Matching)
==================================================================================
يوفر استرجاعاً فائق السرعة وبدون تبعيات خارجية لمواد نظام العمل السعودي واللوائح والسياسات:
1. الفهرسة الكاملة لمواد نظام العمل (245 مادة معتمدة) في جدول rag_chunks و rag_fts.
2. الاستعلام عبر SQLite FTS5 مع تقييم التطابق الدلالي واللفظي (BM25 / Word Overlap).
3. حقن المواد والفقرات ذات الصلة تلقائياً في سياق سراج ووكيل التدقيق «مدقق».
"""

from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("local_rag")


class LocalRAG:
    """محرك الاسترجاع المعزز بالتوليد المحلي عبر SQLite FTS5."""

    _instance: Optional[LocalRAG] = None

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> LocalRAG:
        if cls._instance is None:
            cls._instance = cls(db_path=db_path)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path(__file__).resolve().parent.parent / "memory_store" / "memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_index_populated()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_index_populated(self) -> None:
        """التحقق من وجود المواد المؤرشفة، وفهرسة نظام العمل إن كان الجدول فارغاً."""
        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM rag_chunks")
                row = cur.fetchone()
                count = row[0] if row else 0

                if count == 0:
                    logger.info("فهرسة مواد نظام العمل السعودي في Local RAG لأول مرة...")
                    self._populate_saudi_labor_law(conn)
        except Exception as e:
            logger.warning("تعذر التحقق من فهرس Local RAG: %s", e)

    def _populate_saudi_labor_law(self, conn: sqlite3.Connection) -> None:
        """جلب مواد نظام العمل السعودي من LaborLawKnowledgeBase وحفظها في قاعدة البيانات."""
        try:
            from labor_law_knowledge import LaborLawKnowledgeBase
            kb = LaborLawKnowledgeBase.get_instance()
            articles = kb.articles  # Dict[int, LaborLawArticle]

            for art_num, art in articles.items():
                title = getattr(art, "title", f"المادة {art_num}")
                text = getattr(art, "text", "")
                cat = getattr(art, "category", "نظام العمل السعودي")
                source = "نظام العمل السعودي — المرسوم الملكي (م/51)"
                chunk_id = f"art_{art_num}"

                conn.execute(
                    """
                    INSERT OR IGNORE INTO rag_chunks (chunk_id, category, article_number, title, content, source, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (chunk_id, cat, str(art_num), title, text, source, json.dumps({"article_number": art_num}, ensure_ascii=False))
                )

                # إدراج في جدول FTS5 للبحث السريع
                try:
                    conn.execute(
                        """
                        INSERT INTO rag_fts (title, content, category, source)
                        VALUES (?, ?, ?, ?)
                        """,
                        (title, text, cat, source)
                    )
                except Exception:
                    pass

            # إضافة سياسات الموارد البشرية العامة الشائعة
            hr_policies = [
                ("policy_probation", "فترة التجربة والتقييم", "فترة التجربة لا تزيد عن 90 يوماً ويجوز تمديدها باتفاق خطي صريح إلى 180 يوماً كحد أقصى وفق المادة 53 من نظام العمل، ولا يجوز وضع العامل تحت التجربة أكثر من مرة لدى صاحب عمل واحد إلا بموافقة العامل في مهنة مختلفة.", "لوائح الموارد البشرية", "سياسات المنشأة"),
                ("policy_overtime", "ضوابط العمل الإضافي وأجر الساعات الإضافية", "أجر ساعات العمل الإضافية يحسب بأجر الساعة مضافاً إليه 50% من الأجر الأساسي وفق المادة 107 من نظام العمل. وجميع ساعات العمل في أيام الأعياد والعطل الرسمية تعتبر ساعات إضافية.", "لوائح الموارد البشرية", "سياسات المنشأة"),
                ("policy_eosb", "قواعد استحقاق مكافأة نهاية الخدمة", "تستحق مكافأة نهاية الخدمة بواقع أجر نصف شهر عن كل سنة من السنوات الخمس الأولى، وأجر شهر كامل عن كل سنة تالية وفق المادة 84. في حالة استقالة العامل يستحق ثلث المكافأة من 2 إلى 5 سنوات، وثلثيها من 5 إلى 10 سنوات، وكامل المكافأة إذا بلغت 10 سنوات فأكثر وفق المادة 85.", "لوائح الموارد البشرية", "سياسات المنشأة"),
                ("policy_annual_leave", "رصيد واستحقاق الإجازات السنوية", "يستحق العامل إجازة سنوية مدفوعة الأجر لا تقل عن 21 يوماً تزاد إلى 30 يوماً إذا أمضى في خدمة صاحب العمل خمس سنوات متصلة وفق المادة 109. ولا يجوز النزول عنها أو التنازل عن مقابلها أثناء سريان العقد.", "لوائح الموارد البشرية", "سياسات المنشأة"),
            ]

            for pid, ptitle, pcontent, pcat, psource in hr_policies:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO rag_chunks (chunk_id, category, article_number, title, content, source, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (pid, pcat, None, ptitle, pcontent, psource, json.dumps({"policy_id": pid}, ensure_ascii=False))
                )
                try:
                    conn.execute(
                        """
                        INSERT INTO rag_fts (title, content, category, source)
                        VALUES (?, ?, ?, ?)
                        """,
                        (ptitle, pcontent, pcat, psource)
                    )
                except Exception:
                    pass

            conn.commit()
            logger.info("تمت فهرسة %d مادة وسياسة بنجاح في Local RAG.", len(articles) + len(hr_policies))
        except Exception as e:
            logger.error("فشل إدراج مواد نظام العمل في Local RAG: %s", e)

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        البحث الذكي في مواد النظام والسياسات:
        1. فحص رقم المادة المباشر إذا كان مذكوراً مثل «المادة 84» أو «م/107».
        2. البحث عبر FTS5 full-text search مع ranking.
        3. تقييم الكلمات المفتاحية بالتشابه اللفظي (Word overlap scoring) للتأكد من أفضل دقة.
        """
        clean_q = query.strip()
        if not clean_q:
            return []

        # 1. فحص رقم المادة صراحة
        art_match = re.search(r'(?:المادة|مادة|م/|الماده)\s*(\d+)', clean_q)
        if art_match:
            art_num = art_match.group(1)
            direct_art = self.get_article_by_number(art_num)
            if direct_art:
                direct_art["score"] = 1.0
                return [direct_art]

        results: List[Dict[str, Any]] = []

        # 2. البحث عبر SQLite FTS5
        words = [w for w in re.split(r'[\s,.:;!?؟\-–]+', clean_q) if len(w) > 2]
        safe_fts_query = " OR ".join([f'"{w}"' for w in words[:6]]) if words else f'"{clean_q}"'

        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                if safe_fts_query:
                    sql = """
                        SELECT c.article_number, c.title, c.content, c.category, c.source
                        FROM rag_fts f
                        JOIN rag_chunks c ON c.title = f.title
                        WHERE rag_fts MATCH ?
                        ORDER BY rank
                        LIMIT ?
                    """
                    cur.execute(sql, (safe_fts_query, top_k * 2))
                    rows = cur.fetchall()
                    for r in rows:
                        results.append({
                            "article_number": r["article_number"],
                            "title": r["title"],
                            "content": r["content"],
                            "category": r["category"],
                            "source": r["source"],
                        })
        except Exception as fts_err:
            logger.debug("FTS5 match failed, fallback to LIKE search: %s", fts_err)

        # 3. مسار احتياطي عبر LIKE إذا لم تعيد FTS نتائج كافية
        if len(results) < top_k:
            try:
                with self._get_conn() as conn:
                    cur = conn.cursor()
                    like_terms = words[:3] if words else [clean_q]
                    clauses = " OR ".join(["content LIKE ?" for _ in like_terms])
                    params = [f"%{w}%" for w in like_terms]
                    params.append(top_k * 2)

                    cur.execute(
                        f"""
                        SELECT article_number, title, content, category, source
                        FROM rag_chunks
                        WHERE {clauses}
                        LIMIT ?
                        """,
                        params
                    )
                    for r in cur.fetchall():
                        # منع التكرار
                        if not any(res["title"] == r["title"] for res in results):
                            results.append({
                                "article_number": r["article_number"],
                                "title": r["title"],
                                "content": r["content"],
                                "category": r["category"],
                                "source": r["source"],
                            })
            except Exception as e:
                logger.debug("LIKE search failed: %s", e)

        # 4. إعادة الترتيب بحساب تشابه الكلمات (Jaccard / Token Overlap)
        q_tokens = set(words)
        scored_results = []
        for item in results:
            content_tokens = set(re.findall(r'[\w]+', item.get("content", "") + " " + item.get("title", "")))
            if content_tokens and q_tokens:
                overlap = len(q_tokens.intersection(content_tokens))
                score = overlap / (len(q_tokens) + 1e-5)
            else:
                score = 0.1
            item["score"] = round(score, 3)
            scored_results.append(item)

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

    def get_article_by_number(self, article_num: str) -> Optional[Dict[str, Any]]:
        """استرجاع مادة محددة برقمها."""
        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT article_number, title, content, category, source FROM rag_chunks WHERE article_number = ? LIMIT 1",
                    (str(article_num),)
                )
                r = cur.fetchone()
                if r:
                    return {
                        "article_number": r["article_number"],
                        "title": r["title"],
                        "content": r["content"],
                        "category": r["category"],
                        "source": r["source"],
                    }
        except Exception as e:
            logger.warning("فشل استرجاع المادة %s: %s", article_num, e)
        return None

    def format_context_for_prompt(self, chunks: List[Dict[str, Any]]) -> str:
        """تنسيق القطع المسترجعة لتضمينها في سياق النموذج اللغوي."""
        if not chunks:
            return ""
        lines = ["📜 **المواد والمراجع النظامية المعتمدة من المسترجع المحلي (Local RAG):**"]
        for c in chunks:
            art_num = f" (م/{c['article_number']})" if c.get('article_number') else ""
            lines.append(f"• **{c.get('title')}{art_num}:**")
            lines.append(f"> {c.get('content')}")
            if c.get("source"):
                lines.append(f"*المصدر:* {c.get('source')}\n")
        return "\n".join(lines)

