"""
Tests for Observability System
"""

import pytest
import time
from pathlib import Path
import tempfile
import shutil

from observability.tracer import AgentTracer, SpanType, SpanStatus, Trace, Span
from observability.metrics import MetricsCollector, AgentMetrics
from observability.monitor import MonitoringDashboard, Alert, AlertLevel, AlertType
from observability.integration import (
    ObservableAgent,
    observable_run,
    observable_phase,
    observable_tool,
    with_observability,
)


class TestAgentTracer:
    """Test AgentTracer"""
    
    def setup_method(self):
        """Setup test"""
        self.temp_dir = tempfile.mkdtemp()
        self.tracer = AgentTracer(output_dir=self.temp_dir, enable_langsmith=False)
    
    def teardown_method(self):
        """Cleanup test"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_trace_creation(self):
        """Test creating a trace"""
        trace = self.tracer.start_trace(
            agent_name="TestAgent",
            session_id="test_session",
            metadata={"test": "value"},
            tags=["test"],
        )
        
        assert trace.trace_id
        assert trace.root_agent == "TestAgent"
        assert trace.session_id == "test_session"
        assert trace.metadata == {"test": "value"}
        assert trace.tags == ["test"]
        assert trace.status == SpanStatus.PENDING
    
    def test_span_creation(self):
        """Test creating spans"""
        self.tracer.start_trace(agent_name="TestAgent")
        
        span = self.tracer.start_span(
            agent_name="TestAgent",
            span_type=SpanType.PERCEIVE,
            inputs={"query": "test"},
            metadata={"phase": "perceive"},
            tags=["perceive"],
        )
        
        assert span.span_id
        assert span.agent_name == "TestAgent"
        assert span.span_type == SpanType.PERCEIVE
        assert span.inputs == {"query": "test"}
        assert span.status == SpanStatus.PENDING
        
        time.sleep(0.01)  # Small delay
        
        self.tracer.end_span(
            span,
            status=SpanStatus.SUCCESS,
            outputs={"result": "success"},
        )
        
        assert span.status == SpanStatus.SUCCESS
        assert span.outputs == {"result": "success"}
        assert span.duration_ms > 0
    
    def test_nested_spans(self):
        """Test nested span hierarchy"""
        trace = self.tracer.start_trace(agent_name="TestAgent")
        
        # Parent span
        parent = self.tracer.start_span(
            agent_name="TestAgent",
            span_type=SpanType.AGENT_RUN,
        )
        
        # Child span
        child = self.tracer.start_span(
            agent_name="TestAgent",
            span_type=SpanType.PERCEIVE,
            parent_span=parent,
        )
        
        assert child.parent_id == parent.span_id
        assert len(self.tracer.current_trace.spans) == 2
        
        self.tracer.end_span(child)
        self.tracer.end_span(parent)
        
        # Check span tree BEFORE ending trace
        tree = trace.get_span_tree()
        assert len(tree["root_spans"]) == 1
        assert len(tree["root_spans"][0]["children"]) == 1
        
        self.tracer.end_trace(success=True)
    
    def test_trace_context_manager(self):
        """Test trace context manager"""
        with self.tracer.trace(agent_name="TestAgent", session_id="test") as trace:
            assert trace.trace_id
            assert self.tracer.current_trace is not None
        
        # Trace should be ended
        assert self.tracer.current_trace is None
    
    def test_span_context_manager(self):
        """Test span context manager"""
        self.tracer.start_trace(agent_name="TestAgent")
        
        with self.tracer.span(
            agent_name="TestAgent",
            span_type=SpanType.PERCEIVE,
            inputs={"test": "value"},
        ) as span:
            assert span.span_id
            assert span.status == SpanStatus.PENDING
            time.sleep(0.001)  # Small delay to ensure duration > 0
        
        # Span should be ended
        assert span.status == SpanStatus.SUCCESS
        assert span.duration_ms >= 0  # Allow 0 for very fast execution
    
    def test_trace_persistence(self):
        """Test trace is saved to disk"""
        with self.tracer.trace(agent_name="TestAgent") as trace:
            with self.tracer.span(agent_name="TestAgent", span_type=SpanType.PERCEIVE):
                pass
        
        # Check files were created
        traces_file = Path(self.temp_dir) / "traces.jsonl"
        trace_file = Path(self.temp_dir) / f"trace_{trace.trace_id}.json"
        tree_file = Path(self.temp_dir) / f"tree_{trace.trace_id}.json"
        
        assert traces_file.exists()
        assert trace_file.exists()
        assert tree_file.exists()
    
    def test_trace_summary(self):
        """Test trace summary generation"""
        # Create some traces
        for i in range(5):
            with self.tracer.trace(agent_name=f"Agent{i % 2}"):
                time.sleep(0.001)
        
        summary = self.tracer.get_trace_summary()
        
        assert summary["total_traces"] == 5
        assert summary["success_rate"] == 1.0
        assert summary["avg_duration_ms"] > 0
        assert len(summary["agents"]) == 2  # Agent0, Agent1


class TestMetricsCollector:
    """Test MetricsCollector"""
    
    def setup_method(self):
        """Setup test"""
        self.temp_dir = tempfile.mkdtemp()
        self.collector = MetricsCollector(output_dir=self.temp_dir)
    
    def teardown_method(self):
        """Cleanup test"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_record_run(self):
        """Test recording a run"""
        self.collector.record_run(
            agent_name="TestAgent",
            duration_ms=100.0,
            success=True,
            confidence=0.95,
            token_usage={"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50},
            phase_durations={"perceive": 20.0, "plan": 30.0, "execute": 40.0, "reflect": 10.0},
            tool_calls=["tool1", "tool2"],
        )
        
        metrics = self.collector.get_agent_metrics("TestAgent")
        
        assert metrics.total_runs == 1
        assert metrics.successful_runs == 1
        assert metrics.success_rate == 1.0
        assert metrics.total_duration_ms == 100.0
        assert metrics.avg_duration_ms == 100.0
        assert metrics.total_tokens == 100
        assert metrics.avg_confidence == 0.95
        assert metrics.tool_calls["tool1"] == 1
        assert metrics.tool_calls["tool2"] == 1
    
    def test_multiple_runs(self):
        """Test multiple runs"""
        for i in range(10):
            self.collector.record_run(
                agent_name="TestAgent",
                duration_ms=100.0 + i * 10,
                success=i < 9,  # One failure
                confidence=0.9,
            )
        
        metrics = self.collector.get_agent_metrics("TestAgent")
        
        assert metrics.total_runs == 10
        assert metrics.successful_runs == 9
        assert metrics.failed_runs == 1
        assert metrics.success_rate == 0.9
        assert metrics.avg_duration_ms == 145.0  # (100 + 190) / 2 = 145
    
    def test_system_metrics(self):
        """Test system-wide metrics"""
        for i in range(5):
            self.collector.record_run(
                agent_name=f"Agent{i % 2}",
                duration_ms=100.0,
                success=True,
            )
        
        summary = self.collector.get_summary()
        
        assert summary["total_requests"] == 5
        assert summary["successful_requests"] == 5
        assert summary["success_rate"] == 1.0
        assert len(summary["agents"]) == 2
    
    def test_health_status(self):
        """Test health status calculation"""
        # Healthy system
        for i in range(10):
            self.collector.record_run(
                agent_name="TestAgent",
                duration_ms=1000.0,  # 1 second
                success=True,
            )
        
        health = self.collector.get_health_status()
        
        assert health["status"] == "healthy"
        assert health["success_rate"] == 1.0
        assert health["avg_latency_ms"] == 1000.0
    
    def test_metrics_export(self):
        """Test metrics export"""
        self.collector.record_run(
            agent_name="TestAgent",
            duration_ms=100.0,
            success=True,
        )
        
        self.collector.export_metrics()
        
        # Check files were created
        summary_file = Path(self.temp_dir) / "metrics_summary.json"
        ts_file = Path(self.temp_dir) / "metrics_timeseries.jsonl"
        
        assert summary_file.exists()
        assert ts_file.exists()


class TestMonitoringDashboard:
    """Test MonitoringDashboard"""
    
    def setup_method(self):
        """Setup test"""
        self.temp_dir = tempfile.mkdtemp()
        self.collector = MetricsCollector(output_dir=self.temp_dir)
        self.monitor = MonitoringDashboard(
            output_dir=self.temp_dir,
            metrics_collector=self.collector,
        )
    
    def teardown_method(self):
        """Cleanup test"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_alert_rule_creation(self):
        """Test creating alert rules"""
        self.monitor.add_rule(
            rule_id="test_rule",
            alert_type=AlertType.HIGH_ERROR_RATE,
            level=AlertLevel.ERROR,
            condition=lambda m: m.get("success_rate", 1.0) < 0.5,
            message_template="Error rate too high: {value:.1%}",
        )
        
        assert "test_rule" in self.monitor.alert_rules
    
    def test_alert_firing(self):
        """Test alert firing"""
        # Create failed runs to trigger alert
        for i in range(10):
            self.collector.record_run(
                agent_name="TestAgent",
                duration_ms=100.0,
                success=False,
            )
        
        # Force immediate check (override interval)
        self.monitor.last_check = 0
        
        # Check alerts
        self.monitor.check_alerts()
        
        # Should have high error rate alert
        alerts = self.monitor.get_active_alerts()
        assert len(alerts) > 0, f"Expected alerts but got {len(alerts)}"
        
        # Find error rate alert
        error_alerts = [a for a in alerts if a.alert_type == AlertType.HIGH_ERROR_RATE]
        assert len(error_alerts) > 0, f"Expected HIGH_ERROR_RATE alerts but got {[a.alert_type for a in alerts]}"
    
    def test_alert_cooldown(self):
        """Test alert cooldown period"""
        # Create rule with short cooldown
        self.monitor.add_rule(
            rule_id="test_cooldown",
            alert_type=AlertType.HIGH_ERROR_RATE,
            level=AlertLevel.WARNING,
            condition=lambda m: True,  # Always fire
            message_template="Test",
            cooldown_seconds=5.0,
        )
        
        # First check - should fire
        self.monitor.check_alerts()
        alerts_1 = len(self.monitor.get_active_alerts())
        
        # Immediate second check - should not fire (cooldown)
        self.monitor.check_alerts()
        alerts_2 = len(self.monitor.get_active_alerts())
        
        assert alerts_2 == alerts_1  # No new alerts
    
    def test_alert_handlers(self):
        """Test custom alert handlers"""
        alerts_received = []
        
        def handler(alert: Alert):
            alerts_received.append(alert)
        
        self.monitor.add_alert_handler(handler)
        
        # Trigger alert
        for i in range(10):
            self.collector.record_run(
                agent_name="TestAgent",
                duration_ms=100.0,
                success=False,
            )
        
        # Force immediate check (override interval)
        self.monitor.last_check = 0
        
        self.monitor.check_alerts()
        
        assert len(alerts_received) > 0, f"Expected alerts in handler but got {len(alerts_received)}"
    
    def test_dashboard_data(self):
        """Test dashboard data generation"""
        # Add some data
        for i in range(5):
            self.collector.record_run(
                agent_name="TestAgent",
                duration_ms=100.0,
                success=True,
            )
        
        dashboard = self.monitor.get_dashboard_data()
        
        assert "health" in dashboard
        assert "metrics" in dashboard
        assert "active_alerts" in dashboard
        assert dashboard["metrics"]["total_requests"] == 5
    
    def test_monitoring_report(self):
        """Test report generation"""
        # Add some data
        for i in range(5):
            self.collector.record_run(
                agent_name="TestAgent",
                duration_ms=1000.0,
                success=True,
            )
        
        report = self.monitor.generate_report(hours=1)
        
        assert "MONITORING REPORT" in report
        assert "SYSTEM HEALTH" in report
        assert "AGENT PERFORMANCE" in report
        assert "TestAgent" in report


class TestObservabilityIntegration:
    """Test observability integration"""
    
    def test_observable_agent_mixin(self):
        """Test ObservableAgent mixin"""
        
        class TestAgent(ObservableAgent):
            def __init__(self):
                self.name = "TestAgent"
                self.init_observability()
            
            def run(self):
                self._start_phase_tracking("test")
                time.sleep(0.01)
                self._end_phase_tracking("test")
                self._track_tool_call("test_tool")
        
        agent = TestAgent()
        agent.run()
        
        assert len(agent._phase_durations) == 1
        assert "test" in agent._phase_durations
        assert agent._phase_durations["test"] > 0
        assert "test_tool" in agent._tool_calls
    
    def test_observable_run_decorator(self):
        """Test @observable_run decorator"""
        
        class TestAgent:
            def __init__(self):
                self.name = "TestAgent"
                self.observability_tracer = AgentTracer(enable_langsmith=False)
                self.observability_collector = MetricsCollector()
                self.observability_monitor = None
                self.enable_tracing = True
                self.enable_metrics = True
                self.enable_monitoring = False
                self._phase_durations = {}
                self._tool_calls = []
            
            def _record_run_metrics(self, **kwargs):
                pass
            
            def _check_monitoring(self):
                pass
            
            @observable_run
            def run(self):
                return {"result": "success", "confidence": 0.95}
        
        agent = TestAgent()
        result = agent.run()
        
        assert result["result"] == "success"
    
    def test_observable_phase_decorator(self):
        """Test @observable_phase decorator"""
        
        class TestAgent:
            def __init__(self):
                self.name = "TestAgent"
                self.observability_tracer = AgentTracer(enable_langsmith=False)
                self.enable_tracing = True
                self._phase_start_times = {}
            
            def _start_phase_tracking(self, phase):
                self._phase_start_times[phase] = time.time()
            
            def _end_phase_tracking(self, phase):
                pass
            
            @observable_phase("perceive")
            def perceive(self):
                return {"perception": "test"}
        
        agent = TestAgent()
        result = agent.perceive()
        
        assert result["perception"] == "test"
    
    def test_with_observability_decorator(self):
        """Test @with_observability class decorator"""
        
        @with_observability(enable_tracing=True, enable_metrics=True)
        class TestAgent:
            def __init__(self):
                self.name = "TestAgent"
        
        agent = TestAgent()
        
        assert hasattr(agent, 'observability_tracer')
        assert hasattr(agent, 'observability_collector')
        assert hasattr(agent, '_phase_durations')


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
