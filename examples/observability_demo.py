"""
Observability System Demo
Demonstrates full observability capabilities with FahasAgent.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
import random
from dataclasses import dataclass
from typing import Any, Dict

# Observability imports
from observability.integration import ObservableAgent, observable_run, observable_phase, observable_tool
from observability.tracer import get_tracer
from observability.metrics import get_collector
from observability.monitor import get_monitor

# Base agent (simplified for demo)
@dataclass
class AgentGoal:
    """Agent goal"""
    query: str
    context: Dict[str, Any]


class DemoAgent(ObservableAgent):
    """
    Demo Agent with Full Observability
    
    Shows:
    - Automatic tracing (perceive -> plan -> execute -> reflect)
    - Metrics collection (latency, success rate, confidence)
    - Tool call tracking
    - Phase timing
    - Error handling
    """
    
    def __init__(self, name: str = "DemoAgent"):
        self.name = name
        self.init_observability()
        print(f"✅ {name} initialized with observability")
    
    @observable_run
    def run(self, goal: AgentGoal) -> Dict[str, Any]:
        """Run full agentic loop with automatic tracing"""
        print(f"\n{'='*60}")
        print(f"🤖 {self.name} starting execution")
        print(f"Query: {goal.query}")
        print(f"{'='*60}\n")
        
        # Full agentic loop
        perception = self.perceive(goal)
        plan = self.plan(perception)
        result = self.execute(plan)
        reflection = self.reflect(result)
        
        return reflection
    
    @observable_phase("perceive")
    def perceive(self, goal: AgentGoal) -> Dict[str, Any]:
        """Perceive phase - analyze the goal"""
        print("👁️  Perceiving...")
        time.sleep(0.1)  # Simulate work
        
        perception = {
            "query": goal.query,
            "query_type": "search" if "find" in goal.query.lower() else "complex",
            "context": goal.context,
            "complexity": random.choice(["simple", "medium", "complex"]),
        }
        
        print(f"   Perceived complexity: {perception['complexity']}")
        return perception
    
    @observable_phase("plan")
    def plan(self, perception: Dict[str, Any]) -> Dict[str, Any]:
        """Plan phase - create execution strategy"""
        print("📋 Planning...")
        time.sleep(0.1)
        
        # Determine strategy based on complexity
        complexity = perception["complexity"]
        
        if complexity == "simple":
            strategy = "direct_query"
            steps = ["search", "format"]
        elif complexity == "medium":
            strategy = "filtered_query"
            steps = ["search", "filter", "format"]
        else:
            strategy = "multi_step_query"
            steps = ["search", "analyze", "filter", "aggregate", "format"]
        
        plan = {
            "strategy": strategy,
            "steps": steps,
            "estimated_time": len(steps) * 0.1,
        }
        
        print(f"   Strategy: {strategy} ({len(steps)} steps)")
        return plan
    
    @observable_phase("execute")
    def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute phase - run the plan"""
        print("⚙️  Executing...")
        
        results = []
        
        for step in plan["steps"]:
            print(f"   → {step}")
            
            # Simulate step execution with tool tracking
            if step == "search":
                data = self._tool_search(plan["strategy"])
                results.append(data)
            
            elif step == "filter":
                filtered = self._tool_filter(results[-1])
                results.append(filtered)
            
            elif step == "analyze":
                analyzed = self._tool_analyze(results[-1])
                results.append(analyzed)
            
            elif step == "aggregate":
                aggregated = self._tool_aggregate(results[-1])
                results.append(aggregated)
            
            elif step == "format":
                formatted = self._tool_format(results[-1] if results else {})
                results.append(formatted)
            
            time.sleep(0.05)  # Simulate work
        
        return {
            "results": results[-1],
            "steps_completed": len(plan["steps"]),
        }
    
    @observable_phase("reflect")
    def reflect(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Reflect phase - evaluate results"""
        print("🤔 Reflecting...")
        time.sleep(0.05)
        
        # Calculate confidence
        steps_completed = result["steps_completed"]
        confidence = min(0.95, 0.6 + (steps_completed * 0.1))
        
        # Simulate occasional low confidence
        if random.random() < 0.1:
            confidence = random.uniform(0.4, 0.6)
        
        reflection = {
            "result": result["results"],
            "confidence": confidence,
            "success": confidence > 0.5,
            "lessons": [
                f"Completed {steps_completed} steps",
                f"Confidence: {confidence:.2f}",
            ],
        }
        
        print(f"   Confidence: {confidence:.2%}")
        print(f"   Success: {reflection['success']}")
        
        return reflection
    
    # Tool methods with tracking
    
    @observable_tool("search")
    def _tool_search(self, strategy: str) -> Dict[str, Any]:
        """Search tool"""
        self._track_tool_call("odoo_search")
        return {"data": f"Search results for {strategy}", "count": random.randint(10, 100)}
    
    @observable_tool("filter")
    def _tool_filter(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter tool"""
        self._track_tool_call("data_filter")
        original_count = data.get("count", 0)
        filtered_count = int(original_count * random.uniform(0.3, 0.7))
        return {"data": "Filtered results", "count": filtered_count}
    
    @observable_tool("analyze")
    def _tool_analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analysis tool"""
        self._track_tool_call("data_analyzer")
        return {"data": "Analyzed data", "insights": ["pattern1", "pattern2"]}
    
    @observable_tool("aggregate")
    def _tool_aggregate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregation tool"""
        self._track_tool_call("data_aggregator")
        return {"data": "Aggregated results", "summary": "Summary of data"}
    
    @observable_tool("format")
    def _tool_format(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format tool"""
        self._track_tool_call("result_formatter")
        return {"formatted": True, "output": str(data)}


def run_demo():
    """Run complete observability demo"""
    print("\n" + "="*80)
    print("🚀 OBSERVABILITY SYSTEM DEMO")
    print("="*80)
    
    # Initialize components
    tracer = get_tracer()
    collector = get_collector()
    monitor = get_monitor()
    
    print("\n✅ Observability components initialized:")
    print(f"   - Tracer: {tracer.output_dir}")
    print(f"   - Metrics: {collector.output_dir}")
    print(f"   - Monitor: {monitor.output_dir}")
    
    # Create agent
    agent = DemoAgent(name="Fahas")
    
    # Run multiple executions
    print("\n" + "="*80)
    print("📊 Running 10 executions...")
    print("="*80)
    
    queries = [
        "Find all employees in IT department",
        "Get employee count by department",
        "Find employees hired in last 30 days",
        "Get salary statistics",
        "Find employees with pending leaves",
    ]
    
    for i in range(10):
        query = random.choice(queries)
        
        goal = AgentGoal(
            query=query,
            context={"user": "admin", "department": "HR"}
        )
        
        try:
            # Simulate occasional failures
            if random.random() < 0.1:  # 10% failure rate
                raise Exception("Simulated failure")
            
            result = agent.run(goal)
            print(f"✅ Execution {i+1}/10 completed")
        
        except Exception as e:
            print(f"❌ Execution {i+1}/10 failed: {e}")
        
        time.sleep(0.2)  # Small delay between runs
    
    # Check monitoring
    monitor.check_alerts()
    
    # Display results
    print("\n" + "="*80)
    print("📊 METRICS SUMMARY")
    print("="*80)
    
    summary = collector.get_summary()
    
    print(f"\n🌐 System-wide:")
    print(f"   Total Requests: {summary['total_requests']}")
    print(f"   Success Rate: {summary['success_rate']:.1%}")
    print(f"   Avg Latency: {summary['latency']['avg_ms']:.0f}ms")
    print(f"   P95 Latency: {summary['latency']['p95_ms']:.0f}ms")
    print(f"   P99 Latency: {summary['latency']['p99_ms']:.0f}ms")
    print(f"   Requests/min: {summary['requests_per_minute']:.1f}")
    
    print(f"\n🤖 Agent: Fahas")
    agent_metrics = summary['agents']['Fahas']
    print(f"   Total Runs: {agent_metrics['total_runs']}")
    print(f"   Successful: {agent_metrics['successful_runs']}")
    print(f"   Failed: {agent_metrics['failed_runs']}")
    print(f"   Success Rate: {agent_metrics['success_rate']:.1%}")
    print(f"   Avg Duration: {agent_metrics['avg_duration_ms']:.0f}ms")
    print(f"   Min Duration: {agent_metrics['min_duration_ms']:.0f}ms")
    print(f"   Max Duration: {agent_metrics['max_duration_ms']:.0f}ms")
    print(f"   Avg Confidence: {agent_metrics['confidence_scores']['avg']:.2f}")
    
    # Phase breakdown
    print(f"\n⏱️  Phase Timings:")
    for phase, stats in agent_metrics['phase_durations'].items():
        print(f"   {phase:12} - Avg: {stats['avg']:6.1f}ms  Min: {stats['min']:6.1f}ms  Max: {stats['max']:6.1f}ms")
    
    # Tool usage
    print(f"\n🔧 Tool Usage:")
    for tool, count in sorted(agent_metrics['tool_calls'].items(), key=lambda x: x[1], reverse=True):
        print(f"   {tool:20} - {count:3} calls")
    
    # Traces
    print("\n" + "="*80)
    print("🔍 TRACE SUMMARY")
    print("="*80)
    
    trace_summary = tracer.get_trace_summary()
    
    print(f"\n📝 Traces:")
    print(f"   Total: {trace_summary['total_traces']}")
    print(f"   Success Rate: {trace_summary['success_rate']:.1%}")
    print(f"   Avg Duration: {trace_summary['avg_duration_ms']:.1f}ms")
    
    # Alerts
    print("\n" + "="*80)
    print("🔔 ALERTS")
    print("="*80)
    
    active_alerts = monitor.get_active_alerts()
    
    if active_alerts:
        print(f"\n⚠️  Active Alerts: {len(active_alerts)}")
        for alert in active_alerts:
            print(f"   [{alert.level.upper()}] {alert.message}")
    else:
        print("\n✅ No active alerts")
    
    # Health status
    print("\n" + "="*80)
    print("🏥 SYSTEM HEALTH")
    print("="*80)
    
    health = collector.get_health_status()
    
    status_emoji = {
        "healthy": "🟢",
        "degraded": "🟡",
        "unhealthy": "🔴",
    }
    
    print(f"\n{status_emoji.get(health['status'], '⚪')} Status: {health['status'].upper()}")
    print(f"   Uptime: {health['uptime_seconds'] / 60:.1f} minutes")
    print(f"   Success Rate: {health['success_rate']:.1%}")
    print(f"   Avg Latency: {health['avg_latency_ms']:.0f}ms")
    print(f"   P95 Latency: {health['p95_latency_ms']:.0f}ms")
    
    # Export data
    print("\n" + "="*80)
    print("💾 EXPORTING DATA")
    print("="*80)
    
    collector.export_metrics()
    monitor.export_dashboard()
    
    # Generate report
    report_file = monitor.output_dir / "demo_report.txt"
    monitor.generate_report(hours=1, output_file=str(report_file))
    print(f"\n📄 Report saved to: {report_file}")
    
    # Show file locations
    print("\n" + "="*80)
    print("📁 OUTPUT FILES")
    print("="*80)
    
    print(f"\n🔍 Traces:")
    print(f"   {tracer.output_dir}/traces.jsonl")
    print(f"   {tracer.output_dir}/trace_*.json")
    print(f"   {tracer.output_dir}/tree_*.json")
    
    print(f"\n📊 Metrics:")
    print(f"   {collector.output_dir}/metrics_summary.json")
    print(f"   {collector.output_dir}/metrics_timeseries.jsonl")
    
    print(f"\n🔔 Monitoring:")
    print(f"   {monitor.output_dir}/dashboard.json")
    print(f"   {monitor.output_dir}/alerts.jsonl")
    print(f"   {monitor.output_dir}/demo_report.txt")
    
    print("\n" + "="*80)
    print("✅ DEMO COMPLETE")
    print("="*80)
    print("\nCheck the output directories for detailed data!")
    print()


if __name__ == "__main__":
    run_demo()
