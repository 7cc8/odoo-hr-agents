"""
Learning System - نظام التعلم الذكي
===================================

يتعلم من التجارب السابقة ويحسن القرارات
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from memory.manager import MemoryManager
from memory.types import Episode, SemanticKnowledge

logger = logging.getLogger("memory.learning")


class LearningSystem:
    """
    نظام التعلم الذكي
    
    يوفر:
    1. تتبع النجاحات والفشل
    2. اكتشاف الأنماط
    3. تحسين الاستراتيجيات
    4. نقل المعرفة بين الوكلاء
    """
    
    def __init__(self, memory_manager: MemoryManager):
        """
        Args:
            memory_manager: مدير الذاكرة
        """
        self.memory = memory_manager
        
        # cache للإحصائيات
        self._stats_cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 300  # 5 دقائق
        
        logger.info("✅ LearningSystem initialized")
    
    # ========================================================================
    # Success/Failure Tracking
    # ========================================================================
    
    def get_agent_performance(
        self,
        agent: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        الحصول على أداء وكيل معين
        
        Args:
            agent: اسم الوكيل
            days: عدد الأيام (افتراضي: 30)
        
        Returns:
            إحصائيات الأداء
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        episodes = self.memory.search_episodes(
            agent=agent,
            time_range=(cutoff, datetime.now()),
            limit=1000,  # نحلل آخر 1000 حلقة
        )
        
        if not episodes:
            return {
                "agent": agent,
                "total_episodes": 0,
                "success_rate": 0.0,
                "avg_confidence": 0.0,
                "avg_duration_ms": 0.0,
            }
        
        total = len(episodes)
        successes = sum(1 for e in episodes if e.success)
        
        confidences = [e.confidence for e in episodes]
        durations = [e.duration_ms for e in episodes]
        
        # تحليل الاستراتيجيات
        strategy_counter = Counter()
        for episode in episodes:
            for strategy in episode.strategies_used:
                strategy_counter[strategy] += 1
        
        # الاستراتيجيات الناجحة
        successful_strategies = Counter()
        for episode in episodes:
            if episode.success:
                for strategy in episode.strategies_used:
                    successful_strategies[strategy] += 1
        
        # حساب success rate لكل استراتيجية
        strategy_success_rates = {}
        for strategy, count in strategy_counter.items():
            successful = successful_strategies.get(strategy, 0)
            strategy_success_rates[strategy] = successful / count if count > 0 else 0.0
        
        return {
            "agent": agent,
            "total_episodes": total,
            "success_rate": successes / total,
            "avg_confidence": sum(confidences) / total,
            "avg_duration_ms": sum(durations) / total,
            "most_used_strategies": strategy_counter.most_common(5),
            "best_strategies": sorted(
                strategy_success_rates.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
        }
    
    def get_overall_performance(self, days: int = 30) -> Dict[str, Any]:
        """الحصول على أداء النظام ككل"""
        cutoff = datetime.now() - timedelta(days=days)
        
        episodes = self.memory.search_episodes(
            time_range=(cutoff, datetime.now()),
            limit=5000,
        )
        
        if not episodes:
            return {
                "total_episodes": 0,
                "success_rate": 0.0,
                "agents_performance": {},
            }
        
        # تجميع بالوكيل
        agent_episodes = defaultdict(list)
        for episode in episodes:
            agent_episodes[episode.agent].append(episode)
        
        # حساب الأداء لكل وكيل
        agents_performance = {}
        for agent, agent_eps in agent_episodes.items():
            total = len(agent_eps)
            successes = sum(1 for e in agent_eps if e.success)
            
            agents_performance[agent] = {
                "total": total,
                "success_rate": successes / total,
                "avg_confidence": sum(e.confidence for e in agent_eps) / total,
            }
        
        total = len(episodes)
        successes = sum(1 for e in episodes if e.success)
        
        return {
            "total_episodes": total,
            "success_rate": successes / total,
            "agents_performance": agents_performance,
            "time_range_days": days,
        }
    
    # ========================================================================
    # Pattern Discovery
    # ========================================================================
    
    def discover_patterns(
        self,
        agent: str,
        intent: str,
        min_occurrences: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        اكتشاف الأنماط المتكررة
        
        Args:
            agent: الوكيل
            intent: النية
            min_occurrences: الحد الأدنى للتكرار
        
        Returns:
            قائمة الأنماط المكتشفة
        """
        # الحصول على حلقات ناجحة
        episodes = self.memory.get_successful_patterns(
            agent=agent,
            intent=intent,
            min_confidence=0.7,
            limit=100,
        )
        
        if len(episodes) < min_occurrences:
            return []
        
        # تجميع الاستراتيجيات
        strategy_sequences = []
        for episode in episodes:
            if episode.strategies_used:
                # نحول القائمة إلى tuple ليكون hashable
                strategy_sequences.append(tuple(episode.strategies_used))
        
        # عد التكرارات
        sequence_counter = Counter(strategy_sequences)
        
        # الأنماط المكتشفة
        patterns = []
        for sequence, count in sequence_counter.items():
            if count >= min_occurrences:
                # حساب متوسط الثقة لهذا النمط
                pattern_episodes = [
                    e for e in episodes
                    if tuple(e.strategies_used) == sequence
                ]
                
                avg_confidence = sum(e.confidence for e in pattern_episodes) / len(pattern_episodes)
                avg_duration = sum(e.duration_ms for e in pattern_episodes) / len(pattern_episodes)
                
                patterns.append({
                    "strategies": list(sequence),
                    "occurrences": count,
                    "success_rate": 1.0,  # فقط الناجحة
                    "avg_confidence": avg_confidence,
                    "avg_duration_ms": avg_duration,
                })
        
        # ترتيب بالتكرار
        patterns.sort(key=lambda p: p["occurrences"], reverse=True)
        
        logger.info(f"🔍 Discovered {len(patterns)} patterns for {agent}/{intent}")
        return patterns
    
    def recommend_strategy(
        self,
        agent: str,
        intent: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        اقتراح أفضل استراتيجية بناءً على التعلم
        
        Args:
            agent: الوكيل
            intent: النية
            context: السياق (اختياري)
        
        Returns:
            الاستراتيجية الموصى بها
        """
        # الحصول على الأنماط
        patterns = self.discover_patterns(agent, intent, min_occurrences=2)
        
        if not patterns:
            return None
        
        # أفضل نمط
        best_pattern = patterns[0]
        
        # أول استراتيجية في النمط
        if best_pattern["strategies"]:
            recommended = best_pattern["strategies"][0]
            logger.info(f"💡 Recommended strategy for {agent}/{intent}: {recommended}")
            return recommended
        
        return None
    
    # ========================================================================
    # Knowledge Transfer
    # ========================================================================
    
    def transfer_knowledge(
        self,
        from_agent: str,
        to_agent: str,
        intent: str,
    ) -> int:
        """
        نقل المعرفة من وكيل إلى آخر
        
        Args:
            from_agent: الوكيل المصدر
            to_agent: الوكيل الهدف
            intent: النية المشتركة
        
        Returns:
            عدد المعارف المنقولة
        """
        # الحصول على أنماط ناجحة من المصدر
        source_patterns = self.discover_patterns(
            agent=from_agent,
            intent=intent,
            min_occurrences=3,
        )
        
        if not source_patterns:
            logger.info(f"No patterns to transfer from {from_agent} to {to_agent}")
            return 0
        
        transferred = 0
        
        for pattern in source_patterns[:5]:  # أفضل 5 أنماط
            # إنشاء معرفة دلالية
            concept = f"Strategy pattern for {intent}"
            description = f"Learned from {from_agent}: use {', '.join(pattern['strategies'])}"
            
            knowledge_id = self.memory.save_knowledge(
                category=f"transfer_{to_agent}",
                concept=concept,
                description=description,
                related_concepts=[from_agent, to_agent, intent],
                examples=[f"Use when: {intent}"],
                confidence=pattern["avg_confidence"],
                source=f"transfer_from_{from_agent}",
                tags=["knowledge_transfer", intent],
                metadata={
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "occurrences": pattern["occurrences"],
                },
            )
            
            transferred += 1
            logger.info(f"📚 Transferred knowledge {knowledge_id} from {from_agent} to {to_agent}")
        
        return transferred
    
    def auto_transfer_knowledge(self, min_performance_gap: float = 0.2) -> Dict[str, int]:
        """
        نقل تلقائي للمعرفة من الوكلاء الأفضل للأضعف
        
        Args:
            min_performance_gap: الفجوة الأدنى في الأداء لتفعيل النقل
        
        Returns:
            عدد المعارف المنقولة لكل وكيل
        """
        # الحصول على أداء جميع الوكلاء
        overall = self.get_overall_performance(days=30)
        agents_perf = overall["agents_performance"]
        
        if len(agents_perf) < 2:
            logger.info("Not enough agents for knowledge transfer")
            return {}
        
        # ترتيب بالأداء
        sorted_agents = sorted(
            agents_perf.items(),
            key=lambda x: x[1]["success_rate"],
            reverse=True
        )
        
        transferred = {}
        
        # نقل من الأفضل للأضعف
        for i in range(len(sorted_agents) - 1):
            best_agent, best_perf = sorted_agents[i]
            weak_agent, weak_perf = sorted_agents[i + 1]
            
            gap = best_perf["success_rate"] - weak_perf["success_rate"]
            
            if gap >= min_performance_gap:
                # نقل المعرفة
                count = self.transfer_knowledge(
                    from_agent=best_agent,
                    to_agent=weak_agent,
                    intent="read",  # يمكن تعميمه
                )
                
                transferred[weak_agent] = count
                logger.info(f"✅ Transferred {count} knowledge items from {best_agent} to {weak_agent}")
        
        return transferred
    
    # ========================================================================
    # Strategy Optimization
    # ========================================================================
    
    def suggest_improvements(self, agent: str) -> List[str]:
        """
        اقتراحات لتحسين أداء وكيل
        
        Args:
            agent: الوكيل
        
        Returns:
            قائمة الاقتراحات
        """
        suggestions = []
        
        # الحصول على الأداء
        perf = self.get_agent_performance(agent, days=30)
        
        if perf["total_episodes"] < 10:
            suggestions.append("Need more data - less than 10 episodes in the last 30 days")
            return suggestions
        
        # تحليل success rate
        if perf["success_rate"] < 0.7:
            suggestions.append(f"⚠️ Low success rate ({perf['success_rate']:.0%}). Consider:")
            
            # اقتراح أفضل الاستراتيجيات
            if perf["best_strategies"]:
                best = perf["best_strategies"][0]
                suggestions.append(f"  - Use '{best[0]}' more often (success rate: {best[1]:.0%})")
        
        # تحليل الثقة
        if perf["avg_confidence"] < 0.6:
            suggestions.append(f"⚠️ Low confidence ({perf['avg_confidence']:.0%}). Consider:")
            suggestions.append("  - Review perception logic")
            suggestions.append("  - Add more validation")
        
        # تحليل الوقت
        if perf["avg_duration_ms"] > 5000:
            suggestions.append(f"⚠️ Slow performance ({perf['avg_duration_ms']:.0f}ms average). Consider:")
            suggestions.append("  - Optimize execute phase")
            suggestions.append("  - Add caching")
        
        if not suggestions:
            suggestions.append(f"✅ Performance looks good! (success: {perf['success_rate']:.0%}, confidence: {perf['avg_confidence']:.0%})")
        
        return suggestions
    
    # ========================================================================
    # Statistics
    # ========================================================================
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """الحصول على إحصائيات التعلم"""
        overall = self.get_overall_performance(days=30)
        
        # عدد الأنماط المكتشفة
        agents = list(overall["agents_performance"].keys())
        total_patterns = 0
        
        for agent in agents:
            patterns = self.discover_patterns(agent, "read", min_occurrences=2)
            total_patterns += len(patterns)
        
        return {
            "total_episodes": overall["total_episodes"],
            "overall_success_rate": overall["success_rate"],
            "active_agents": len(agents),
            "discovered_patterns": total_patterns,
            "time_range_days": 30,
        }
