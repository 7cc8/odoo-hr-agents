"""
محاسب التكلفة والاستهلاك (Cost Auditor & Token Telemetry)
=======================================================
يسجل استهلاك التوكنات ويحسب التكلفة التقديرية بالدولار:
1. تسجيل التوكنات (prompt_tokens, completion_tokens, total_tokens) في SQLite memory.db.
2. حساب التكلفة وفق جداول تسعير المزودين (المحلي Ollama مجاني $0.0، السحابي بحسب أسعار API).
3. توفير تقارير وإحصائيات تفصيلية عبر واجهة برمجية GET /api/telemetry/cost.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cost_auditor")


class CostAuditor:
    """محاسب استهلاك وتكلفة نماذج الذكاء الاصطناعي."""

    _instance: Optional[CostAuditor] = None

    # جداول التسعير لكل مليون توكن بالدولار الأمريكي (USD per 1M tokens)
    PRICING_PER_MILLION = {
        "ollama": {"input": 0.0, "output": 0.0},
        "local": {"input": 0.0, "output": 0.0},
        "gemini-3.8-flash": {"input": 0.075, "output": 0.30},
        "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "openrouter/auto": {"input": 0.15, "output": 0.60},
        "default_cloud": {"input": 0.20, "output": 0.80},
    }

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> CostAuditor:
        if cls._instance is None:
            cls._instance = cls(db_path=db_path)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path(__file__).resolve().parent.parent / "memory_store" / "memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def calculate_cost(self, provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """حساب التكلفة التقديرية بالدولار الأمريكي."""
        prov = (provider or "").lower()
        mod = (model or "").lower()

        if prov in ("local", "ollama") or "qwen" in mod or "llama" in mod:
            return 0.0

        rates = self.PRICING_PER_MILLION.get(mod)
        if not rates:
            for k, r in self.PRICING_PER_MILLION.items():
                if k in mod:
                    rates = r
                    break
        if not rates:
            rates = self.PRICING_PER_MILLION["default_cloud"]

        cost = (prompt_tokens * rates["input"] / 1_000_000) + (completion_tokens * rates["output"] / 1_000_000)
        return round(cost, 6)

    def record_usage(
        self,
        chat_id: str,
        operation_id: str,
        agent_name: str,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """تسجيل عملية استهلاك وحفظها في قاعدة البيانات."""
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = self.calculate_cost(provider, model, prompt_tokens, completion_tokens)
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO token_usage (
                        chat_id, operation_id, agent_name, model, provider,
                        prompt_tokens, completion_tokens, total_tokens,
                        estimated_cost_usd, latency_ms, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chat_id, operation_id, agent_name, model, provider,
                        prompt_tokens, completion_tokens, total_tokens,
                        cost_usd, latency_ms, now_iso
                    )
                )
                conn.commit()
        except Exception as e:
            logger.warning("تعذر تسجيل استهلاك التوكنات: %s", e)

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": cost_usd,
        }

    @staticmethod
    def _initialize_measured_usage(conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_response_usage (
                id INTEGER PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                total_tokens INTEGER,
                api_cost_usd REAL,
                latency_ms REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

    def record_model_response(self, provider: str, model: str, usage: Optional[Dict[str, Any]], latency_ms: float) -> None:
        """Store response telemetry only when the transport measured or returned it."""
        import math

        usage = usage if isinstance(usage, dict) else {}
        tokens = usage.get("total_tokens")
        if type(tokens) is not int or tokens < 0:
            # Some providers expose only the component counts.
            input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
            output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
            parts = [input_tokens, output_tokens]
            parts.extend(usage[key] for key in ("cache_creation_input_tokens", "cache_read_input_tokens") if key in usage)
            tokens = sum(parts) if all(type(n) is int and n >= 0 for n in parts) else None
        cost = usage.get("cost")
        if provider == "ollama":
            cost = 0.0
        elif type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
            cost = None

        from contextlib import closing

        with closing(self._get_conn()) as conn, conn:
            self._initialize_measured_usage(conn)
            conn.execute("""
                INSERT INTO llm_response_usage (provider, model, total_tokens, api_cost_usd, latency_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (provider, model, tokens, cost, latency_ms, datetime.now(timezone.utc).isoformat()))

    def get_cost_summary(self) -> Dict[str, Any]:
        """Exclude legacy estimates and expose missing provider measurements explicitly."""
        from contextlib import closing

        try:
            with closing(self._get_conn()) as conn, conn:
                self._initialize_measured_usage(conn)
                stats = """
                    COUNT(*) AS count, COUNT(total_tokens) AS usage_reported,
                    SUM(total_tokens) AS tokens, AVG(latency_ms) AS latency,
                    CASE WHEN COUNT(api_cost_usd) = COUNT(*) THEN SUM(api_cost_usd) END AS cost
                """
                row = conn.execute(f"SELECT {stats} FROM llm_response_usage").fetchone()
                by_provider = {
                    item["provider"]: {
                        "count": item["count"],
                        "tokens": item["tokens"],
                        "cost_usd": item["cost"],
                        "usage_reported_requests": item["usage_reported"],
                    }
                    for item in conn.execute(f"SELECT provider, {stats} FROM llm_response_usage GROUP BY provider")
                }
                return {
                    "status": "success",
                    "total_requests": row["count"],
                    "usage_reported_requests": row["usage_reported"],
                    "total_tokens": row["tokens"],
                    "total_cost_usd": row["cost"],
                    "avg_latency_ms": row["latency"],
                    "by_provider": by_provider,
                }
        except Exception as e:
            logger.warning("فشل استخراج ملخص التكلفة: %s", e)
            return {"status": "error"}
