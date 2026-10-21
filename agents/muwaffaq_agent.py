"""
وكيل المطابقة الذكية: «موفّق» (Muwaffaq Agentic Matching Agent)
====================================================================
موفّق هو الوكيل المسؤول عن المطابقة الذكية متعددة الاستراتيجيات:

الأدوار الرئيسية:
1. **الإدراك (Perceive)**: فهم السياق الدلالي والهدف من المطابقة
2. **التخطيط (Plan)**: اختيار استراتيجيات المطابقة المناسبة
3. **التنفيذ (Execute)**: تطبيق المطابقات (Exact/Fuzzy/Semantic/Contextual)
4. **التأمل (Reflect)**: تقييم الثقة والتعلم من النتائج

استراتيجيات المطابقة:
- **Exact Match**: مطابقة دقيقة 100%
- **Fuzzy Text Match**: مطابقة ضبابية نصية (Levenshtein, Soundex)
- **Semantic Match**: مطابقة دلالية (المعنى)
- **Contextual Match**: مطابقة سياقية (اعتماداً على السياق)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from agents.base_agent import BaseAgent
from matching_thresholds import (
    MUWAFFAQ_HIGH_CONFIDENCE,
    MUWAFFAQ_LOW_CONFIDENCE,
    MUWAFFAQ_MEDIUM_CONFIDENCE,
)

logger = logging.getLogger("muwaffaq_agent")


class MatchStrategy(str, Enum):
    """استراتيجيات المطابقة"""
    EXACT = "exact"  # مطابقة دقيقة 100%
    FUZZY_TEXT = "fuzzy_text"  # مطابقة ضبابية نصية
    SEMANTIC = "semantic"  # مطابقة دلالية (معنى)
    CONTEXTUAL = "contextual"  # مطابقة سياقية
    PHONETIC = "phonetic"  # مطابقة صوتية (Soundex)
    HYBRID = "hybrid"  # مزيج من عدة استراتيجيات


class MatchDecision(str, Enum):
    """قرارات موفّق"""
    ACCEPT_MATCH = "accept_match"  # قبول المطابقة (ثقة عالية)
    PROPOSE_MATCH = "propose_match"  # اقتراح مطابقة (ثقة متوسطة)
    REQUEST_REVIEW = "request_review"  # طلب مراجعة بشرية
    REJECT_NO_MATCH = "reject_no_match"  # رفض (لا توجد مطابقة)
    ESCALATE_AMBIGUOUS = "escalate_ambiguous"  # تصعيد (غموض)


@dataclass
class MatchCandidate:
    """مرشح للمطابقة"""
    candidate_id: str
    display_name: str
    confidence: float  # 0.0 - 1.0
    match_strategy: MatchStrategy
    match_details: Dict[str, Any]
    
    def __repr__(self) -> str:
        return f"<MatchCandidate '{self.display_name}' ({self.confidence:.0%})>"


@dataclass
class MatchResult:
    """نتيجة المطابقة"""
    status: str  # matched, proposed, no_match, ambiguous
    best_match: Optional[MatchCandidate]
    all_candidates: List[MatchCandidate]
    confidence: float
    decision: MatchDecision


class MuwaffaqAgent(BaseAgent):
    """
    وكيل المطابقة الذكية مع قدرات Agentic AI كاملة.
    
    الدورة الذكية:
    1. Perceive: فهم السياق والهدف من المطابقة
    2. Plan: اختيار استراتيجيات المطابقة
    3. Execute: تطبيق المطابقات
    4. Reflect: تقييم الثقة والتعلم
    """

    def __init__(self, llm_model: Optional[str] = None):
        super().__init__(
            name="muwaffaq",
            role="intelligent_matching_agent",
            llm_model=llm_model,
        )
        
        # سجل المطابقات المعتمدة (للتعلم)
        self._approved_matches: List[Dict[str, Any]] = []
        
        # عتبات الثقة
        self.confidence_thresholds = {
            "high": MUWAFFAQ_HIGH_CONFIDENCE,  # قبول تلقائي
            "medium": MUWAFFAQ_MEDIUM_CONFIDENCE,  # اقتراح للمراجعة
            "low": MUWAFFAQ_LOW_CONFIDENCE,  # رفض أو تصعيد
        }
        
        logger.info(f"✅ Muwaffaq Agent initialized")

    # ============================================================================
    # Agentic Loop Implementation
    # ============================================================================

    def perceive(self, match_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 1: الإدراك - فهم السياق الدلالي
        
        Args:
            match_request: طلب المطابقة
            
        Returns:
            perception: تحليل شامل للسياق
        """
        logger.info(f"🔍 Perceiving match request")
        
        # استخراج البيانات الأساسية
        perception = {
            "query": match_request.get("query", ""),
            "field_type": match_request.get("field_type", "text"),  # text, name, id, etc.
            "candidates": match_request.get("candidates", []),
            "context": match_request.get("context", {}),
            "min_confidence": match_request.get("min_confidence", MUWAFFAQ_MEDIUM_CONFIDENCE),
            "raw_request": match_request,
        }
        
        # تحليل نوع المطابقة المطلوبة
        perception["match_type"] = self._analyze_match_type(perception)
        
        # تحليل مستوى الحساسية
        perception["sensitivity"] = self._assess_match_sensitivity(perception)
        
        # تحديد الاستراتيجيات المناسبة
        perception["recommended_strategies"] = self._recommend_strategies(perception)
        
        logger.info(f"✅ Perception complete: {len(perception['candidates'])} candidates, {len(perception['recommended_strategies'])} strategies")
        return perception

    def plan(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 2: التخطيط - بناء استراتيجية المطابقة
        
        Args:
            perception: نتائج مرحلة الإدراك
            
        Returns:
            plan: خطة المطابقة المفصلة
        """
        logger.info(f"📋 Planning matching strategy")
        
        plan = {
            "strategies": perception["recommended_strategies"],
            "execution_order": [],
            "fallback_strategy": MatchStrategy.FUZZY_TEXT,
            "stop_on_high_confidence": True,
        }
        
        # ترتيب الاستراتيجيات
        # 1. Exact أولاً (سريع ودقيق)
        # 2. Fuzzy Text (متوسط)
        # 3. Semantic (بطيء لكن قوي)
        
        strategy_priority = {
            MatchStrategy.EXACT: 0,
            MatchStrategy.FUZZY_TEXT: 1,
            MatchStrategy.PHONETIC: 2,
            MatchStrategy.CONTEXTUAL: 3,
            MatchStrategy.SEMANTIC: 4,
        }
        
        plan["execution_order"] = sorted(
            plan["strategies"],
            key=lambda s: strategy_priority.get(s, 99)
        )
        
        logger.info(f"✅ Plan created: {len(plan['execution_order'])} strategies")
        return plan

    def execute(self, plan: Dict[str, Any], perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 3: التنفيذ - تطبيق المطابقات
        
        Args:
            plan: خطة المطابقة
            perception: نتائج الإدراك
            
        Returns:
            result: نتيجة المطابقة مع المرشحين
        """
        logger.info(f"⚡ Executing matching strategies")
        
        query = perception["query"]
        candidates = perception["candidates"]
        min_confidence = perception["min_confidence"]
        
        result = {
            "matched_candidates": [],
            "best_match": None,
            "confidence": 0.0,
            "strategy_used": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # تطبيق كل استراتيجية حسب الترتيب
        for strategy in plan["execution_order"]:
            try:
                matches = self._execute_strategy(
                    strategy=strategy,
                    query=query,
                    candidates=candidates,
                    context=perception["context"]
                )
                
                # إضافة المطابقات للنتائج
                result["matched_candidates"].extend(matches)
                
                # إذا وجدنا مطابقة بثقة عالية، نتوقف
                if plan["stop_on_high_confidence"]:
                    high_confidence_match = next(
                        (m for m in matches if m.confidence >= self.confidence_thresholds["high"]),
                        None
                    )
                    if high_confidence_match:
                        result["best_match"] = high_confidence_match
                        result["confidence"] = high_confidence_match.confidence
                        result["strategy_used"] = strategy
                        logger.info(f"✅ Found high-confidence match with {strategy}")
                        break
            
            except Exception as exc:
                logger.error(f"❌ Strategy {strategy} failed: {exc}")
                continue
        
        # إذا لم نجد مطابقة بثقة عالية، نأخذ الأفضل
        if not result["best_match"] and result["matched_candidates"]:
            result["matched_candidates"].sort(key=lambda m: m.confidence, reverse=True)
            result["best_match"] = result["matched_candidates"][0]
            result["confidence"] = result["best_match"].confidence
            result["strategy_used"] = result["best_match"].match_strategy
        
        # تحديد الحالة
        if result["best_match"]:
            if result["confidence"] >= self.confidence_thresholds["high"]:
                result["status"] = "matched"
            elif result["confidence"] >= self.confidence_thresholds["medium"]:
                result["status"] = "proposed"
            else:
                result["status"] = "low_confidence"
        else:
            result["status"] = "no_match"
        
        logger.info(f"✅ Execution complete: {result['status']}, confidence={result['confidence']:.2f}")
        return result

    def reflect(self, perception: Dict[str, Any], plan: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 4: التأمل - تقييم الثقة والتعلم
        
        Args:
            perception: نتائج الإدراك
            plan: الخطة المنفذة
            result: نتيجة التنفيذ
            
        Returns:
            reflection: تحليل شامل مع توصيات
        """
        logger.info(f"🤔 Reflecting on matching results")
        
        reflection = {
            "decision": self._make_decision(result),
            "confidence_assessment": "",
            "reasoning": [],
            "should_learn": False,
            "alternatives": [],
        }
        
        # تقييم الثقة
        if result["status"] == "matched":
            reflection["confidence_assessment"] = f"مطابقة قوية بثقة {result['confidence']:.0%}"
            reflection["reasoning"].append("الثقة عالية، يُوصى بالقبول التلقائي")
            reflection["should_learn"] = True
        
        elif result["status"] == "proposed":
            reflection["confidence_assessment"] = f"مطابقة محتملة بثقة {result['confidence']:.0%}"
            reflection["reasoning"].append("الثقة متوسطة، يُوصى بالمراجعة البشرية")
        
        elif result["status"] == "no_match":
            reflection["confidence_assessment"] = "لا توجد مطابقة مناسبة"
            reflection["reasoning"].append("لم يتم العثور على مرشح مناسب")
        
        # البدائل
        if len(result["matched_candidates"]) > 1:
            reflection["alternatives"] = [
                {
                    "candidate": c.display_name,
                    "confidence": c.confidence,
                    "strategy": c.match_strategy,
                }
                for c in sorted(result["matched_candidates"], key=lambda m: m.confidence, reverse=True)[:3]
            ]
        
        logger.info(f"✅ Reflection complete: decision={reflection['decision']}")
        return reflection

    # ============================================================================
    # Matching Strategies Implementation
    # ============================================================================

    def _execute_strategy(
        self,
        strategy: MatchStrategy,
        query: str,
        candidates: List[Any],
        context: Dict[str, Any]
    ) -> List[MatchCandidate]:
        """تنفيذ استراتيجية مطابقة محددة"""
        
        if strategy == MatchStrategy.EXACT:
            return self._exact_match(query, candidates)
        
        elif strategy == MatchStrategy.FUZZY_TEXT:
            return self._fuzzy_text_match(query, candidates)
        
        elif strategy == MatchStrategy.PHONETIC:
            return self._phonetic_match(query, candidates)
        
        elif strategy == MatchStrategy.CONTEXTUAL:
            return self._contextual_match(query, candidates, context)
        
        elif strategy == MatchStrategy.SEMANTIC:
            # TODO: implement semantic matching with embeddings
            return []
        
        return []

    def _exact_match(self, query: str, candidates: List[Any]) -> List[MatchCandidate]:
        """مطابقة دقيقة 100%"""
        matches = []
        
        query_lower = query.strip().lower()
        
        for candidate in candidates:
            candidate_name = self._extract_candidate_name(candidate)
            candidate_lower = candidate_name.strip().lower()
            
            if query_lower == candidate_lower:
                matches.append(MatchCandidate(
                    candidate_id=self._extract_candidate_id(candidate),
                    display_name=candidate_name,
                    confidence=1.0,
                    match_strategy=MatchStrategy.EXACT,
                    match_details={"type": "exact_match"},
                ))
        
        return matches

    def _fuzzy_text_match(self, query: str, candidates: List[Any]) -> List[MatchCandidate]:
        """مطابقة ضبابية نصية باستخدام SequenceMatcher"""
        matches = []
        
        query_lower = query.strip().lower()
        
        for candidate in candidates:
            candidate_name = self._extract_candidate_name(candidate)
            candidate_lower = candidate_name.strip().lower()
            
            # حساب التشابه
            similarity = SequenceMatcher(None, query_lower, candidate_lower).ratio()
            
            if similarity >= 0.6:  # عتبة التشابه
                matches.append(MatchCandidate(
                    candidate_id=self._extract_candidate_id(candidate),
                    display_name=candidate_name,
                    confidence=similarity,
                    match_strategy=MatchStrategy.FUZZY_TEXT,
                    match_details={
                        "type": "fuzzy_match",
                        "similarity_score": similarity,
                    },
                ))
        
        return sorted(matches, key=lambda m: m.confidence, reverse=True)

    def _phonetic_match(self, query: str, candidates: List[Any]) -> List[MatchCandidate]:
        """مطابقة صوتية (Soundex-like for Arabic)"""
        # TODO: implement Arabic-aware phonetic matching
        # حالياً نستخدم fuzzy match بسيط
        return []

    def _contextual_match(
        self,
        query: str,
        candidates: List[Any],
        context: Dict[str, Any]
    ) -> List[MatchCandidate]:
        """مطابقة سياقية (تعتمد على السياق)"""
        matches = []
        
        # مثال: إذا كان السياق يحتوي على قسم، نفضل المرشحين من نفس القسم
        preferred_department = context.get("department")
        
        for candidate in candidates:
            candidate_name = self._extract_candidate_name(candidate)
            candidate_dept = self._extract_candidate_attribute(candidate, "department")
            
            base_similarity = SequenceMatcher(None, query.lower(), candidate_name.lower()).ratio()
            
            # تعزيز النتيجة إذا كان من نفس القسم
            if preferred_department and candidate_dept == preferred_department:
                base_similarity = min(base_similarity + 0.15, 1.0)
            
            if base_similarity >= 0.6:
                matches.append(MatchCandidate(
                    candidate_id=self._extract_candidate_id(candidate),
                    display_name=candidate_name,
                    confidence=base_similarity,
                    match_strategy=MatchStrategy.CONTEXTUAL,
                    match_details={
                        "type": "contextual_match",
                        "context_boost": preferred_department == candidate_dept,
                    },
                ))
        
        return sorted(matches, key=lambda m: m.confidence, reverse=True)

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def _analyze_match_type(self, perception: Dict[str, Any]) -> str:
        """تحليل نوع المطابقة المطلوبة"""
        field_type = perception["field_type"]
        
        if field_type in ["name", "employee_name"]:
            return "person_name"
        elif field_type in ["department", "job_title"]:
            return "entity_name"
        elif field_type in ["id", "code"]:
            return "identifier"
        else:
            return "general_text"

    def _assess_match_sensitivity(self, perception: Dict[str, Any]) -> str:
        """تقييم مستوى حساسية المطابقة"""
        # إذا كان عدد المرشحين كبير، الحساسية أعلى
        if len(perception["candidates"]) > 100:
            return "high"
        elif len(perception["candidates"]) > 20:
            return "medium"
        else:
            return "low"

    def _recommend_strategies(self, perception: Dict[str, Any]) -> List[MatchStrategy]:
        """توصية باستراتيجيات المطابقة"""
        strategies = [MatchStrategy.EXACT, MatchStrategy.FUZZY_TEXT]
        
        # إضافة استراتيجيات إضافية حسب السياق
        if perception["context"]:
            strategies.append(MatchStrategy.CONTEXTUAL)
        
        if perception["field_type"] in ["name", "employee_name"]:
            strategies.append(MatchStrategy.PHONETIC)
        
        return strategies

    def _extract_candidate_name(self, candidate: Any) -> str:
        """استخراج اسم المرشح"""
        if isinstance(candidate, dict):
            return candidate.get("name", candidate.get("display_name", str(candidate)))
        elif isinstance(candidate, str):
            return candidate
        else:
            return str(candidate)

    def _extract_candidate_id(self, candidate: Any) -> str:
        """استخراج معرف المرشح"""
        if isinstance(candidate, dict):
            return str(candidate.get("id", candidate.get("name", "")))
        else:
            return str(candidate)

    def _extract_candidate_attribute(self, candidate: Any, attribute: str) -> Optional[str]:
        """استخراج صفة من المرشح"""
        if isinstance(candidate, dict):
            return candidate.get(attribute)
        return None

    def _make_decision(self, result: Dict[str, Any]) -> MatchDecision:
        """اتخاذ القرار النهائي"""
        if result["status"] == "matched":
            return MatchDecision.ACCEPT_MATCH
        elif result["status"] == "proposed":
            return MatchDecision.PROPOSE_MATCH
        elif result["status"] == "no_match":
            return MatchDecision.REJECT_NO_MATCH
        else:
            return MatchDecision.REQUEST_REVIEW

    # ============================================================================
    # Public API
    # ============================================================================

    def find_match(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        واجهة عامة للمطابقة الذكية
        
        تستخدم الدورة الذكية الكاملة:
        Perceive → Plan → Execute → Reflect
        """
        logger.info(f"🎯 Finding match for: {request.get('query')}")
        
        # الدورة الذكية الكاملة
        perception = self.perceive(request)
        plan = self.plan(perception)
        result = self.execute(plan, perception)
        reflection = self.reflect(perception, plan, result)
        
        # تنسيق النتيجة النهائية
        return {
            "status": result["status"],
            "best_match": {
                "id": result["best_match"].candidate_id if result["best_match"] else None,
                "name": result["best_match"].display_name if result["best_match"] else None,
                "confidence": result["best_match"].confidence if result["best_match"] else 0.0,
                "strategy": result["best_match"].match_strategy if result["best_match"] else None,
            } if result["best_match"] else None,
            "alternatives": reflection["alternatives"],
            "confidence": result["confidence"],
            "decision": reflection["decision"],
            "reasoning": reflection["reasoning"],
            "strategy_used": result["strategy_used"],
            "timestamp": result["timestamp"],
        }


# ============================================================================
# Singleton Factory
# ============================================================================

_GLOBAL_MUWAFFAQ: Optional[MuwaffaqAgent] = None


def get_muwaffaq_agent() -> MuwaffaqAgent:
    """الحصول على كائن وكيل موفّق المفرد (Singleton)"""
    global _GLOBAL_MUWAFFAQ
    if _GLOBAL_MUWAFFAQ is None:
        _GLOBAL_MUWAFFAQ = MuwaffaqAgent()
    return _GLOBAL_MUWAFFAQ
