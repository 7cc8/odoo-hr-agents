"""
وكيل التنسيق الذكي الشامل: «سراج» (Seraj Meta-Agent)
=======================================================
سراج المحسّن هو Meta-Agent يدير جميع الوكلاء الأخرى بذكاء:

الأدوار الرئيسية:
1. **الإدراك (Perceive)**: فهم نية المستخدم والسياق الكامل
2. **التخطيط (Plan)**: اختيار الوكيل/الوكلاء المناسبين ديناميكياً
3. **التنفيذ (Execute)**: تنسيق تنفيذ الوكلاء المختارين
4. **التأمل (Reflect)**: تقييم النتائج والتعلم من التجارب

القدرات المتقدمة:
- ذاكرة طويلة المدى (Long-term Memory)
- اختيار وكيل ديناميكي (Dynamic Agent Selection)
- التعلم من التفاعلات (Learning from Interactions)
- شرح القرارات (Decision Explanation)
- Meta-reasoning (التفكير عن التفكير)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from agents.base_agent import BaseAgent, AgentGoal, AgentMemory

logger = logging.getLogger("seraj_meta_agent")


class AgentType(str, Enum):
    """أنواع الوكلاء المتاحين"""
    FAHAS = "fahas"  # فاحص - Query
    MUSLEH = "musleh"  # مصلح - Diagnostic
    HARES = "hares"  # حارس - Security
    KATIB = "katib"  # كاتب - Write
    MUDAQQIQ = "mudaqqiq"  # مدقق - Compliance
    MUWAFFAQ = "muwaffaq"  # موفّق - Matching
    SIJIL = "sijil"  # سجل - Audit


class IntentType(str, Enum):
    """أنواع النوايا"""
    QUERY = "query"  # استعلام
    WRITE = "write"  # كتابة
    ANALYZE = "analyze"  # تحليل
    MATCH = "match"  # مطابقة
    AUDIT = "audit"  # تدقيق
    CLARIFY = "clarify"  # توضيح
    COMPLEX = "complex"  # معقد (يحتاج عدة وكلاء)


@dataclass
class AgentSelectionReasoning:
    """تفسير اختيار الوكيل"""
    selected_agents: List[AgentType]
    reasoning: str
    confidence: float  # 0.0 - 1.0
    execution_order: List[AgentType]
    parallel_possible: bool


@dataclass
class InteractionLearning:
    """التعلم من التفاعل"""
    user_query: str
    intent: IntentType
    agents_used: List[AgentType]
    success: bool
    user_feedback: Optional[str]
    timestamp: str


class SerajMetaAgent(BaseAgent):
    """
    وكيل التنسيق الذكي الشامل (Meta-Agent).
    
    يدير جميع الوكلاء الأخرى ويتعلم من التجارب.
    """

    def __init__(self, llm_model: Optional[str] = None):
        super().__init__(
            name="seraj",
            role="meta_orchestrator_agent",
            llm_model=llm_model,
        )
        
        # قاعدة معرفة الوكلاء
        self.agent_capabilities = self._init_agent_capabilities()
        
        # ذاكرة طويلة المدى
        self.long_term_memory: List[InteractionLearning] = []
        
        # إحصائيات الأداء
        self.agent_performance = {agent: {"success": 0, "failure": 0} for agent in AgentType}
        
        # أنماط مُتعلّمة
        self.learned_patterns: Dict[str, List[AgentType]] = {}
        
        logger.info(f"✅ Seraj Meta-Agent initialized with {len(self.agent_capabilities)} agents")

    # ============================================================================
    # Agent Capabilities Knowledge Base
    # ============================================================================

    def _init_agent_capabilities(self) -> Dict[AgentType, Dict[str, Any]]:
        """قاعدة معرفة قدرات كل وكيل"""
        return {
            AgentType.FAHAS: {
                "name_ar": "فاحص",
                "capabilities": ["query", "search", "list", "count", "filter"],
                "keywords": ["كم", "عدد", "أين", "من", "ماهو", "ما هو", "اعرض", "أظهر"],
                "models": ["hr.employee", "hr.contract", "hr.payslip", "hr.leave", "hr.attendance"],
                "typical_queries": ["كم موظف", "أين الموظف", "ماهو الراتب"],
            },
            AgentType.MUSLEH: {
                "name_ar": "مصلح",
                "capabilities": ["diagnose", "fix", "heal", "auto_correct"],
                "keywords": ["صلح", "عالج", "أصلح", "خطأ", "مشكلة"],
                "use_cases": ["rejected data", "validation errors", "data healing"],
            },
            AgentType.HARES: {
                "name_ar": "حارس",
                "capabilities": ["security", "authorization", "risk_assessment"],
                "keywords": ["أمان", "صلاحية", "خطر", "حماية"],
                "use_cases": ["write protection", "environment check", "permission validation"],
            },
            AgentType.KATIB: {
                "name_ar": "كاتب",
                "capabilities": ["create", "update", "archive", "delete"],
                "keywords": ["أنشئ", "عدل", "أرشف", "احذف", "أضف"],
                "models": ["hr.employee", "hr.contract", "hr.payslip"],
            },
            AgentType.MUDAQQIQ: {
                "name_ar": "مدقق",
                "capabilities": ["compliance", "validation", "rule_checking"],
                "keywords": ["تحقق", "امتثال", "قانون", "نظام", "مخالفة"],
                "rules": ["labor_law", "gosi", "wps", "contracts"],
            },
            AgentType.MUWAFFAQ: {
                "name_ar": "موفّق",
                "capabilities": ["matching", "fuzzy_search", "entity_resolution"],
                "keywords": ["طابق", "ابحث عن", "جد", "شبيه"],
                "strategies": ["exact", "fuzzy", "semantic", "contextual"],
            },
            AgentType.SIJIL: {
                "name_ar": "سجل",
                "capabilities": ["audit", "monitoring", "anomaly_detection", "reporting"],
                "keywords": ["سجل", "تدقيق", "تقرير", "مراقبة"],
                "scopes": ["comprehensive", "selective", "anomaly_only", "proactive"],
            },
        }

    # ============================================================================
    # Agentic Loop Implementation
    # ============================================================================

    def perceive(self, user_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 1: الإدراك - فهم نية المستخدم والسياق
        
        Args:
            user_request: طلب المستخدم
            
        Returns:
            perception: تحليل شامل للطلب
        """
        logger.info(f"🔍 Perceiving user request")
        
        query = user_request.get("query", "")
        context = user_request.get("context", {})
        
        perception = {
            "query": query,
            "intent": self._classify_intent(query),
            "context": context,
            "complexity": self._assess_complexity(query),
            "entities": self._extract_entities(query),
            "ambiguity_score": self._assess_ambiguity(query),
            "raw_request": user_request,
        }
        
        # البحث في الذاكرة الطويلة عن تفاعلات مشابهة
        perception["similar_past_interactions"] = self._find_similar_interactions(query)
        
        # تحليل السياق
        perception["requires_clarification"] = perception["ambiguity_score"] > 0.7
        
        logger.info(f"✅ Perception complete: intent={perception['intent']}, complexity={perception['complexity']}")
        return perception

    def plan(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 2: التخطيط - اختيار الوكيل/الوكلاء المناسبين
        
        Args:
            perception: نتائج مرحلة الإدراك
            
        Returns:
            plan: خطة التنفيذ مع الوكلاء المختارين
        """
        logger.info(f"📋 Planning agent selection")
        
        # اختيار الوكيل/الوكلاء ديناميكياً
        selection = self._select_agents_dynamically(perception)
        
        plan = {
            "selected_agents": selection.selected_agents,
            "execution_order": selection.execution_order,
            "parallel_possible": selection.parallel_possible,
            "reasoning": selection.reasoning,
            "confidence": selection.confidence,
            "fallback_strategy": self._determine_fallback(perception),
        }
        
        # إذا كانت الثقة منخفضة، نطلب توضيح
        if selection.confidence < 0.6:
            plan["request_clarification"] = True
            plan["clarification_question"] = self._generate_clarification_question(perception)
        
        logger.info(f"✅ Plan created: {len(selection.selected_agents)} agent(s), confidence={selection.confidence:.2f}")
        return plan

    def execute(self, plan: Dict[str, Any], perception: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 3: التنفيذ - تنسيق تنفيذ الوكلاء
        
        Args:
            plan: خطة التنفيذ
            perception: نتائج الإدراك
            
        Returns:
            result: نتائج التنفيذ من الوكلاء
        """
        logger.info(f"⚡ Executing plan with {len(plan['selected_agents'])} agent(s)")
        
        result = {
            "agent_results": {},
            "overall_success": False,
            "errors": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # إذا كان يحتاج توضيح، نتوقف
        if plan.get("request_clarification"):
            result["needs_clarification"] = True
            result["clarification_question"] = plan["clarification_question"]
            return result
        
        # تنفيذ كل وكيل حسب الترتيب
        for agent_type in plan["execution_order"]:
            try:
                logger.info(f"   Executing {agent_type}...")
                agent_result = self._execute_agent(agent_type, perception, result)
                result["agent_results"][agent_type] = agent_result
                
                # تحديث إحصائيات الأداء
                if agent_result.get("success"):
                    self.agent_performance[agent_type]["success"] += 1
                else:
                    self.agent_performance[agent_type]["failure"] += 1
            
            except Exception as exc:
                logger.error(f"❌ Agent {agent_type} failed: {exc}")
                result["errors"].append(f"{agent_type}: {str(exc)}")
                self.agent_performance[agent_type]["failure"] += 1
                
                # استراتيجية Fallback
                if plan.get("fallback_strategy"):
                    logger.info(f"   Trying fallback strategy...")
                    # TODO: implement fallback
        
        # تحديد النجاح الكلي
        result["overall_success"] = len(result["errors"]) == 0
        
        logger.info(f"✅ Execution complete: success={result['overall_success']}")
        return result

    def reflect(self, perception: Dict[str, Any], plan: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """
        المرحلة 4: التأمل - تقييم النتائج والتعلم
        
        Args:
            perception: نتائج الإدراك
            plan: الخطة المنفذة
            result: نتائج التنفيذ
            
        Returns:
            reflection: تحليل شامل مع تعلم
        """
        logger.info(f"🤔 Reflecting on execution")
        
        reflection = {
            "success": result["overall_success"],
            "agents_used": plan["selected_agents"],
            "confidence_in_decision": plan["confidence"],
            "lessons_learned": [],
            "improvements": [],
            "should_learn": False,
        }
        
        # تحليل النجاح/الفشل
        if result["overall_success"]:
            reflection["lessons_learned"].append("اختيار الوكلاء كان صحيحاً")
            reflection["should_learn"] = True
            
            # تسجيل نمط ناجح
            self._record_successful_pattern(perception["query"], plan["selected_agents"])
        
        else:
            reflection["lessons_learned"].append(f"حدثت أخطاء: {result['errors']}")
            reflection["improvements"].append("مراجعة اختيار الوكلاء")
        
        # تحليل أداء الوكلاء
        reflection["agent_performance_summary"] = self._summarize_agent_performance()
        
        # توصيات للمستقبل
        reflection["recommendations"] = self._generate_recommendations(perception, plan, result)
        
        # حفظ في الذاكرة الطويلة
        if reflection["should_learn"]:
            self._save_to_long_term_memory(perception, plan, result)
        
        logger.info(f"✅ Reflection complete: should_learn={reflection['should_learn']}")
        return reflection

    # ============================================================================
    # Dynamic Agent Selection
    # ============================================================================

    def _select_agents_dynamically(self, perception: Dict[str, Any]) -> AgentSelectionReasoning:
        """اختيار الوكيل/الوكلاء المناسبين ديناميكياً"""
        
        intent = perception["intent"]
        query = perception["query"].lower()
        complexity = perception["complexity"]
        
        selected = []
        reasoning_parts = []
        
        # القواعد الأساسية حسب النية
        if intent == IntentType.QUERY:
            selected.append(AgentType.FAHAS)
            reasoning_parts.append("استعلام → فاحص")
        
        elif intent == IntentType.WRITE:
            # مسار الكتابة الكامل
            selected.extend([AgentType.MUDAQQIQ, AgentType.HARES, AgentType.KATIB, AgentType.SIJIL])
            reasoning_parts.append("كتابة → مدقق → حارس → كاتب → سجل")
        
        elif intent == IntentType.MATCH:
            selected.append(AgentType.MUWAFFAQ)
            reasoning_parts.append("مطابقة → موفّق")
        
        elif intent == IntentType.AUDIT:
            selected.append(AgentType.SIJIL)
            reasoning_parts.append("تدقيق → سجل")
        
        elif intent == IntentType.COMPLEX:
            # تحليل معقد - نختار حسب الكلمات المفتاحية
            selected = self._select_for_complex_query(query)
            reasoning_parts.append(f"معقد → {len(selected)} وكلاء")
        
        # البحث في الأنماط المُتعلّمة
        learned_agents = self._get_learned_pattern(query)
        if learned_agents:
            # نضيف فقط الوكلاء الجديدة
            for agent in learned_agents:
                if agent not in selected:
                    selected.append(agent)
                    reasoning_parts.append(f"من التعلم: {agent}")
        
        # تحديد ترتيب التنفيذ
        execution_order = self._determine_execution_order(selected, intent)
        
        # حساب الثقة
        confidence = self._calculate_selection_confidence(perception, selected)
        
        # هل يمكن التنفيذ المتوازي؟
        parallel_possible = len(selected) > 1 and intent != IntentType.WRITE
        
        return AgentSelectionReasoning(
            selected_agents=selected,
            reasoning=" | ".join(reasoning_parts),
            confidence=confidence,
            execution_order=execution_order,
            parallel_possible=parallel_possible,
        )

    def _select_for_complex_query(self, query: str) -> List[AgentType]:
        """اختيار وكلاء لاستعلام معقد"""
        selected = []
        
        # تحليل الكلمات المفتاحية
        for agent_type, info in self.agent_capabilities.items():
            keywords = info.get("keywords", [])
            if any(kw in query for kw in keywords):
                selected.append(agent_type)
        
        # على الأقل فاحص
        if not selected:
            selected.append(AgentType.FAHAS)
        
        return selected

    def _determine_execution_order(self, agents: List[AgentType], intent: IntentType) -> List[AgentType]:
        """تحديد ترتيب تنفيذ الوكلاء"""
        
        # ترتيب ثابت لمسار الكتابة
        if intent == IntentType.WRITE:
            write_order = [AgentType.MUDAQQIQ, AgentType.HARES, AgentType.KATIB, AgentType.SIJIL]
            return [a for a in write_order if a in agents]
        
        # ترتيب حسب الأولوية
        priority = {
            AgentType.FAHAS: 1,
            AgentType.MUSLEH: 2,
            AgentType.MUWAFFAQ: 3,
            AgentType.MUDAQQIQ: 4,
            AgentType.HARES: 5,
            AgentType.KATIB: 6,
            AgentType.SIJIL: 7,
        }
        
        return sorted(agents, key=lambda a: priority.get(a, 99))

    def _calculate_selection_confidence(self, perception: Dict[str, Any], selected: List[AgentType]) -> float:
        """حساب الثقة في اختيار الوكلاء"""
        
        # الثقة الأساسية
        confidence = 0.7
        
        # زيادة الثقة إذا وجدنا نمط مُتعلّم
        if self._get_learned_pattern(perception["query"]):
            confidence += 0.2
        
        # تقليل الثقة إذا كان غامض
        if perception["ambiguity_score"] > 0.5:
            confidence -= 0.3
        
        # تقليل الثقة إذا كان معقد جداً
        if perception["complexity"] == "very_high":
            confidence -= 0.2
        
        return max(0.0, min(1.0, confidence))

    # ============================================================================
    # Intent Classification & Analysis
    # ============================================================================

    def _classify_intent(self, query: str) -> IntentType:
        """تصنيف نية المستخدم"""
        q = query.lower()
        
        # استعلام
        if any(kw in q for kw in ["كم", "عدد", "أين", "من", "ماهو", "ما هو", "اعرض"]):
            return IntentType.QUERY
        
        # كتابة
        if any(kw in q for kw in ["أنشئ", "عدل", "أرشف", "احذف", "أضف", "حدث"]):
            return IntentType.WRITE
        
        # مطابقة
        if any(kw in q for kw in ["طابق", "ابحث عن", "جد", "شبيه"]):
            return IntentType.MATCH
        
        # تدقيق
        if any(kw in q for kw in ["سجل", "تدقيق", "تقرير", "مراقبة"]):
            return IntentType.AUDIT
        
        # توضيح
        if len(q) < 10 or "؟" in q:
            return IntentType.CLARIFY
        
        # معقد (افتراضي)
        return IntentType.COMPLEX

    def _assess_complexity(self, query: str) -> str:
        """تقييم تعقيد الاستعلام"""
        q = query.lower()
        
        # عدد الشروط
        conditions = len([w for w in ["و", "أو", "ثم", "بعد", "قبل"] if w in q])
        
        if conditions >= 3:
            return "very_high"
        elif conditions >= 2:
            return "high"
        elif conditions == 1:
            return "medium"
        else:
            return "low"

    def _extract_entities(self, query: str) -> List[str]:
        """استخراج الكيانات من الاستعلام"""
        # TODO: implement NER (Named Entity Recognition)
        entities = []
        
        # كشف بسيط للأرقام
        import re
        numbers = re.findall(r'\d+', query)
        entities.extend([f"number:{n}" for n in numbers])
        
        return entities

    def _assess_ambiguity(self, query: str) -> float:
        """تقييم مستوى الغموض"""
        ambiguity = 0.0
        
        q = query.lower()
        
        # قصير جداً
        if len(q) < 20:
            ambiguity += 0.3
        
        # يحتوي على كلمات غامضة
        ambiguous_words = ["شيء", "حاجة", "هذا", "ذاك", "تلك"]
        if any(w in q for w in ambiguous_words):
            ambiguity += 0.4
        
        return min(1.0, ambiguity)

    # ============================================================================
    # Learning & Memory
    # ============================================================================

    def _find_similar_interactions(self, query: str) -> List[InteractionLearning]:
        """البحث عن تفاعلات مشابهة في الذاكرة"""
        # TODO: implement semantic similarity search
        similar = []
        
        for interaction in self.long_term_memory[-10:]:  # آخر 10
            if interaction.user_query.lower() in query.lower() or query.lower() in interaction.user_query.lower():
                similar.append(interaction)
        
        return similar

    def _record_successful_pattern(self, query: str, agents: List[AgentType]) -> None:
        """تسجيل نمط ناجح"""
        # استخراج الكلمات المفتاحية
        keywords = query.lower().split()[:3]  # أول 3 كلمات
        pattern_key = " ".join(keywords)
        
        self.learned_patterns[pattern_key] = agents

    def _get_learned_pattern(self, query: str) -> Optional[List[AgentType]]:
        """الحصول على نمط مُتعلّم"""
        keywords = query.lower().split()[:3]
        pattern_key = " ".join(keywords)
        
        return self.learned_patterns.get(pattern_key)

    def _save_to_long_term_memory(
        self,
        perception: Dict[str, Any],
        plan: Dict[str, Any],
        result: Dict[str, Any]
    ) -> None:
        """حفظ التفاعل في الذاكرة الطويلة"""
        interaction = InteractionLearning(
            user_query=perception["query"],
            intent=perception["intent"],
            agents_used=plan["selected_agents"],
            success=result["overall_success"],
            user_feedback=None,  # TODO: collect feedback
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        self.long_term_memory.append(interaction)
        
        # الاحتفاظ بآخر 100 تفاعل فقط
        if len(self.long_term_memory) > 100:
            self.long_term_memory = self.long_term_memory[-100:]

    # ============================================================================
    # Performance & Analytics
    # ============================================================================

    def _summarize_agent_performance(self) -> Dict[str, Any]:
        """ملخص أداء الوكلاء"""
        summary = {}
        
        for agent, stats in self.agent_performance.items():
            total = stats["success"] + stats["failure"]
            if total > 0:
                summary[agent] = {
                    "success_rate": stats["success"] / total,
                    "total_calls": total,
                }
        
        return summary

    def _generate_recommendations(
        self,
        perception: Dict[str, Any],
        plan: Dict[str, Any],
        result: Dict[str, Any]
    ) -> List[str]:
        """توليد توصيات"""
        recommendations = []
        
        if not result["overall_success"]:
            recommendations.append("مراجعة اختيار الوكلاء")
            recommendations.append("التحقق من البيانات المدخلة")
        
        if plan["confidence"] < 0.7:
            recommendations.append("طلب توضيح من المستخدم في المرات القادمة")
        
        return recommendations

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def _execute_agent(
        self,
        agent_type: AgentType,
        perception: Dict[str, Any],
        previous_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """تنفيذ وكيل محدد"""
        # TODO: integrate with actual agents
        # هنا نستدعي الوكيل الفعلي
        
        return {
            "agent": agent_type,
            "success": True,
            "data": {},
        }

    def _determine_fallback(self, perception: Dict[str, Any]) -> Optional[str]:
        """تحديد استراتيجية fallback"""
        if perception["ambiguity_score"] > 0.7:
            return "request_clarification"
        return None

    def _generate_clarification_question(self, perception: Dict[str, Any]) -> str:
        """توليد سؤال توضيح"""
        return f"هل تقصد: {perception['query']}؟ يرجى التوضيح."

    # ============================================================================
    # Public API
    # ============================================================================

    def orchestrate(self, user_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        واجهة عامة للتنسيق الذكي
        
        تستخدم الدورة الذكية الكاملة:
        Perceive → Plan → Execute → Reflect
        """
        logger.info(f"🎯 Orchestrating: {user_request.get('query', '')[:50]}...")
        
        # الدورة الذكية الكاملة
        perception = self.perceive(user_request)
        plan = self.plan(perception)
        result = self.execute(plan, perception)
        reflection = self.reflect(perception, plan, result)
        
        # تنسيق النتيجة النهائية
        return {
            "success": result["overall_success"],
            "needs_clarification": result.get("needs_clarification", False),
            "clarification_question": result.get("clarification_question"),
            "agent_results": result["agent_results"],
            "agents_used": plan["selected_agents"],
            "reasoning": plan["reasoning"],
            "confidence": plan["confidence"],
            "reflection": reflection,
            "timestamp": result["timestamp"],
        }

    def _reflect_on_execution(
        self,
        query: str,
        selected_agents: List[str],
        agent_results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        مراجعة نتائج التنفيذ والتعلم منها
        
        Args:
            query: الاستعلام الأصلي
            selected_agents: الوكلاء المختارة
            agent_results: نتائج الوكلاء {agent_name: result}
        
        Returns:
            dict مع:
            - success_rate: نسبة النجاح (0-1)
            - learning_insights: دروس مستفادة
            - should_save_pattern: هل يجب حفظ هذا النمط؟
        """
        total_agents = len(selected_agents)
        if total_agents == 0:
            return {
                "success_rate": 0.0,
                "learning_insights": ["لم يتم اختيار أي وكلاء"],
                "should_save_pattern": False,
            }
        
        successes = 0
        failures = 0
        insights = []
        
        # تحليل نتائج كل وكيل
        for agent_name in selected_agents:
            result = agent_results.get(agent_name, {})
            
            if agent_name == "fahas":
                if result.get("last_error") is None:
                    successes += 1
                else:
                    failures += 1
                    insights.append(f"فاحص: فشل في الاستعلام - {result.get('last_error', '')}")
            
            elif agent_name == "musleh":
                healed = result.get("healed_data", [])
                if len(healed) > 0:
                    successes += 1
                    insights.append(f"مصلح: تم إصلاح {len(healed)} سجل")
                else:
                    failures += 1
            
            elif agent_name == "hares":
                approved = result.get("security_approved", False)
                if approved:
                    successes += 1
                else:
                    failures += 1
                    insights.append(f"حارس: رفض العملية - {result.get('security_decision', '')}")
            
            elif agent_name == "katib":
                write_success = result.get("write_success", False)
                if write_success:
                    successes += 1
                    insights.append("كاتب: نجح في الكتابة")
                else:
                    failures += 1
                    insights.append("كاتب: فشل في الكتابة")
            
            elif agent_name == "mudaqqiq":
                approved = result.get("compliance_approved", False)
                if approved:
                    successes += 1
                else:
                    failures += 1
                    violations = result.get("compliance_violations", [])
                    insights.append(f"مدقق: {len(violations)} مخالفات")
            
            elif agent_name == "muwaffaq":
                found = result.get("match_found", False)
                confidence = result.get("match_confidence", 0.0)
                if found and confidence > 0.7:
                    successes += 1
                    insights.append(f"موفّق: مطابقة بثقة {confidence:.0%}")
                else:
                    failures += 1
                    insights.append("موفّق: لم يجد مطابقة مناسبة")
            
            elif agent_name == "sijil":
                logged = result.get("audit_logged", False)
                if logged:
                    successes += 1
                else:
                    failures += 1
        
        success_rate = successes / total_agents if total_agents > 0 else 0.0
        
        # دروس عامة
        if success_rate >= 0.8:
            insights.append(f"✅ نمط ناجح: {', '.join(selected_agents)} للاستعلام '{query}'")
        elif success_rate <= 0.3:
            insights.append(f"❌ نمط فاشل: ربما يحتاج اختيار وكلاء مختلفين")
        
        return {
            "success_rate": success_rate,
            "learning_insights": insights,
            "should_save_pattern": success_rate >= 0.7,
            "successes": successes,
            "failures": failures,
        }
    
    def _save_learned_pattern(self, pattern: Dict[str, Any]) -> None:
        """
        حفظ نمط متعلم للاستخدام المستقبلي
        
        Args:
            pattern: النمط المتعلم مع:
                - intent: النية
                - query_type: نوع الاستعلام
                - selected_agents: الوكلاء المختارة
                - success: هل نجح؟
                - success_rate: نسبة النجاح
        """
        # حالياً نحفظ في الذاكرة المؤقتة
        # في Phase 5 سنستخدم Vector DB
        
        if not hasattr(self, "_learned_patterns_cache"):
            self._learned_patterns_cache = []
        
        self._learned_patterns_cache.append({
            **pattern,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        })
        
        # الحد الأقصى 100 نمط في الذاكرة
        if len(self._learned_patterns_cache) > 100:
            self._learned_patterns_cache = self._learned_patterns_cache[-100:]
        
        logger.info(f"💾 تم حفظ نمط متعلم: {pattern.get('intent')} - {pattern.get('selected_agents')}")


# ============================================================================
# Singleton Factory
# ============================================================================

_GLOBAL_SERAJ: Optional[SerajMetaAgent] = None


def get_seraj_meta_agent() -> SerajMetaAgent:
    """الحصول على كائن سراج المفرد (Singleton)"""
    global _GLOBAL_SERAJ
    if _GLOBAL_SERAJ is None:
        _GLOBAL_SERAJ = SerajMetaAgent()
    return _GLOBAL_SERAJ
