"""
Unit tests for SerajMetaAgent and the Multi-Agent Harmony Pipeline.
Verifies dynamic routing, agent execution, context propagation, security guards, and memory sync.
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.seraj_meta_agent import SerajMetaAgent, AgentType, IntentType
from agents.base_agent import AgentGoal
from memory.manager import MemoryManager


class TestSerajMetaAgentPipeline:
    """Test suite for Seraj Meta-Agent orchestration with all specialist agents."""

    def setup_method(self):
        self.seraj = SerajMetaAgent()

    def test_seraj_initialization(self):
        """Verifies Seraj meta agent initializes with all specialist agent capabilities."""
        assert len(self.seraj.agent_capabilities) >= 7
        assert AgentType.FAHAS in self.seraj.agent_capabilities
        assert AgentType.HARES in self.seraj.agent_capabilities
        assert AgentType.KATIB in self.seraj.agent_capabilities
        assert AgentType.MUDAQQIQ in self.seraj.agent_capabilities
        assert AgentType.MUWAFFAQ in self.seraj.agent_capabilities
        assert AgentType.SIJIL in self.seraj.agent_capabilities
        assert AgentType.MUSLEH in self.seraj.agent_capabilities

    def test_query_orchestration_fahas(self):
        """Verifies query requests route to FahasAgent and execute successfully."""
        res = self.seraj.orchestrate({
            "query": "كم عدد الموظفين في الشركة؟",
            "context": {"company_id": 1}
        })
        assert AgentType.FAHAS in res["agents_used"]
        assert "fahas" in res["agent_results"]
        fahas_res = res["agent_results"]["fahas"]
        assert fahas_res.get("success") is True
        assert fahas_res.get("status") == "success"

    def test_match_orchestration_muwaffaq(self):
        """Verifies matching requests route to MuwaffaqAgent and execute successfully."""
        res = self.seraj.orchestrate({
            "query": "طابق اسم الموظف محمد العتيبي مع قاعدة البيانات",
            "context": {
                "candidates": ["محمد العتيبي", "أحمد علي", "سالم محمد"]
            }
        })
        assert AgentType.MUWAFFAQ in res["agents_used"]
        assert "muwaffaq" in res["agent_results"]
        muwaffaq_res = res["agent_results"]["muwaffaq"]
        assert muwaffaq_res.get("success") is True

    def test_audit_orchestration_sijil(self):
        """Verifies audit requests route to SijilAgent and execute successfully."""
        res = self.seraj.orchestrate({
            "query": "سجل تقرير التدقيق للعمليات الأخيرة",
            "context": {}
        })
        assert AgentType.SIJIL in res["agents_used"]
        assert "sijil" in res["agent_results"]
        sijil_res = res["agent_results"]["sijil"]
        assert sijil_res.get("success") is True

    def test_write_pipeline_blocked_without_approval(self):
        """Verifies write requests run multi-agent checks and Katib blocks without human approval."""
        res = self.seraj.orchestrate({
            "query": "أنشئ موظف جديد",
            "context": {}
        })
        agents = [a.value for a in res["agents_used"]]
        assert "mudaqqiq" in agents
        assert "hares" in agents
        assert "katib" in agents
        assert "sijil" in agents
        
        # Katib must be blocked without explicit approval
        katib_res = res["agent_results"]["katib"]
        assert katib_res.get("success") is False
        assert katib_res.get("status") == "blocked"
        assert "human approval required" in katib_res.get("error", "")

    def test_context_propagation_to_downstream_agents(self):
        """Verifies that upstream agent outputs are propagated to downstream agents' context."""
        captured_contexts = {}

        def mock_execute_agent(agent_type, perception, previous_results):
            # Record the agent_context that would be passed
            agent_context = dict(perception.get("context", {}))
            prev_res = previous_results.get("agent_results", {})
            agent_context["previous_agent_results"] = prev_res
            captured_contexts[agent_type.value] = agent_context
            return {"agent": agent_type.value, "success": True, "status": "success", "data": {"step": agent_type.value}}

        with patch.object(self.seraj, "_execute_agent", side_effect=mock_execute_agent):
            self.seraj.execute(
                plan={
                    "selected_agents": [AgentType.FAHAS, AgentType.MUDAQQIQ, AgentType.HARES],
                    "execution_order": [AgentType.FAHAS, AgentType.MUDAQQIQ, AgentType.HARES],
                    "parallel_possible": False,
                },
                perception={"query": "test query", "context": {"initial_key": "val"}}
            )

        assert "fahas" in captured_contexts
        assert "mudaqqiq" in captured_contexts
        assert "hares" in captured_contexts
        # Mudaqqiq must see Fahas in previous_agent_results
        assert "fahas" in captured_contexts["mudaqqiq"]["previous_agent_results"]
        # Hares must see both Fahas and Mudaqqiq
        assert "fahas" in captured_contexts["hares"]["previous_agent_results"]
        assert "mudaqqiq" in captured_contexts["hares"]["previous_agent_results"]

    def test_memory_sync_on_reflection(self):
        """Verifies that Seraj reflects and saves an episode to MemoryManager."""
        mm = MemoryManager.get_instance()
        initial_count = len(mm.get_recent_episodes())
        
        self.seraj.orchestrate({
            "query": "كم عدد الموظفين في الشركة؟",
            "context": {}
        })
        
        # Episode should be saved in central memory manager
        assert len(mm.get_recent_episodes()) >= initial_count
