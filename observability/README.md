# 📊 Observability & Monitoring System

نظام مراقبة شامل للوكلاء الذكية مع تتبع كامل، مقاييس أداء، وتنبيهات تلقائية.

## 🎯 الميزات

### 1. Tracing (التتبع)
- **Hierarchical Spans**: تتبع متداخل لكل عملية (perceive → plan → execute → reflect)
- **LangSmith Integration**: تكامل اختياري مع LangSmith
- **Local Storage**: حفظ Traces محلياً كـ JSON/JSONL
- **Span Tree**: عرض شجري للعمليات المتداخلة
- **Context Managers**: استخدام سهل مع `with` statements

### 2. Metrics (المقاييس)
- **Agent Performance**: latency, success rate, confidence scores
- **Token Usage**: تتبع استخدام LLM tokens
- **Tool Calls**: إحصائيات Tool usage
- **Phase Timing**: duration لكل phase (perceive/plan/execute/reflect)
- **Time Series**: بيانات زمنية لتحليل الاتجاهات
- **System Health**: مؤشرات صحة النظام (P95/P99 latency)

### 3. Monitoring (المراقبة)
- **Alert Rules**: قواعد تنبيه قابلة للتخصيص
- **Alert Levels**: INFO / WARNING / ERROR / CRITICAL
- **Auto-Detection**: كشف تلقائي للمشاكل
- **Dashboard**: لوحة معلومات شاملة
- **Reports**: تقارير دورية
- **Custom Handlers**: callbacks مخصصة للتنبيهات

## 📦 التثبيت

```bash
# لا توجد مكتبات إضافية مطلوبة (Pure Python)

# اختياري: LangSmith integration
pip install langchain langsmith

# اختياري: Prometheus integration
pip install prometheus-client
```

## 🚀 الاستخدام السريع

### الطريقة 1: Mixin Pattern

```python
from observability.integration import ObservableAgent, observable_run, observable_phase
from agents.base_agent import BaseAgent, AgentGoal

class MyAgent(ObservableAgent, BaseAgent):
    def __init__(self):
        BaseAgent.__init__(self, name="MyAgent")
        self.init_observability()
    
    @observable_run
    def run(self, goal: AgentGoal):
        perception = self.perceive(goal)
        plan = self.plan(perception)
        result = self.execute(plan)
        reflection = self.reflect(result)
        return result
    
    @observable_phase("perceive")
    def perceive(self, goal: AgentGoal):
        # Your perceive logic
        return perception
    
    @observable_phase("plan")
    def plan(self, perception):
        # Your plan logic
        return plan
    
    @observable_phase("execute")
    def execute(self, plan):
        # Your execute logic
        self._track_tool_call("odoo_query")  # Track tool usage
        return result
    
    @observable_phase("reflect")
    def reflect(self, result):
        # Your reflect logic
        return reflection
```

### الطريقة 2: Class Decorator

```python
from observability.integration import with_observability

@with_observability(enable_tracing=True, enable_metrics=True)
class MyAgent(BaseAgent):
    def __init__(self):
        BaseAgent.__init__(self, name="MyAgent")
        # Observability auto-initialized!
    
    # Your methods...
```

### الطريقة 3: Manual Integration

```python
from observability.tracer import get_tracer
from observability.metrics import get_collector

class MyAgent:
    def __init__(self):
        self.tracer = get_tracer()
        self.collector = get_collector()
    
    def run(self, goal):
        with self.tracer.trace(agent_name="MyAgent", session_id="session_123"):
            
            with self.tracer.span(agent_name="MyAgent", span_type="perceive"):
                # Perceive logic
                pass
            
            with self.tracer.span(agent_name="MyAgent", span_type="plan"):
                # Plan logic
                pass
        
        # Record metrics
        self.collector.record_run(
            agent_name="MyAgent",
            duration_ms=100.0,
            success=True,
            confidence=0.95,
        )
```

## 📊 عرض Metrics

### الحصول على ملخص

```python
from observability.metrics import get_collector

collector = get_collector()
summary = collector.get_summary()

print(f"Total Requests: {summary['total_requests']}")
print(f"Success Rate: {summary['success_rate']:.1%}")
print(f"Avg Latency: {summary['latency']['avg_ms']:.0f}ms")

# Per-agent metrics
for agent, metrics in summary['agents'].items():
    print(f"\n{agent}:")
    print(f"  Success Rate: {metrics['success_rate']:.1%}")
    print(f"  Avg Duration: {metrics['avg_duration_ms']:.0f}ms")
    print(f"  Total Runs: {metrics['total_runs']}")
```

### Health Check

```python
health = collector.get_health_status()

print(f"Status: {health['status']}")  # healthy / degraded / unhealthy
print(f"Success Rate: {health['success_rate']:.1%}")
print(f"P95 Latency: {health['p95_latency_ms']:.0f}ms")
```

### Time Series Data

```python
# Get latency over last hour
points = collector.get_time_series(
    agent_name="MyAgent",
    metric_name="duration_ms",
    window_minutes=60
)

# Plot with matplotlib
import matplotlib.pyplot as plt

timestamps = [p[0] for p in points]
values = [p[1] for p in points]

plt.plot(timestamps, values)
plt.xlabel("Time")
plt.ylabel("Duration (ms)")
plt.title("Agent Latency Over Time")
plt.show()
```

## 🔔 Alert System

### القواعد الافتراضية

تأتي مع 4 قواعد افتراضية:
1. **High Error Rate**: success_rate < 90% → ERROR
2. **High Latency**: avg_duration > 5000ms → WARNING
3. **Low Confidence**: avg_confidence < 0.70 → WARNING
4. **Agent Failure**: 5+ consecutive failures → CRITICAL

### إضافة قواعد مخصصة

```python
from observability.monitor import get_monitor, AlertType, AlertLevel

monitor = get_monitor()

# Custom rule: High token usage
monitor.add_rule(
    rule_id="high_token_usage",
    alert_type=AlertType.THRESHOLD_BREACH,
    level=AlertLevel.WARNING,
    condition=lambda m: m.get("avg_tokens_per_run", 0) > 1000,
    message_template="High token usage for {agent}: {value:.0f} tokens/run",
    cooldown_seconds=300.0,  # 5 minutes
)
```

### Alert Handlers

```python
def slack_notifier(alert):
    """Send alert to Slack"""
    import requests
    
    webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    
    message = {
        "text": f"🚨 {alert.level.upper()}: {alert.message}",
        "username": "Agent Monitor",
    }
    
    requests.post(webhook_url, json=message)

monitor.add_alert_handler(slack_notifier)
```

### Dashboard & Reports

```python
# Get dashboard data
dashboard = monitor.get_dashboard_data()
print(f"Active Alerts: {dashboard['active_alerts']['total']}")

# Generate report
report = monitor.generate_report(hours=24)
print(report)

# Export to file
monitor.generate_report(hours=24, output_file="daily_report.txt")

# Export dashboard JSON
monitor.export_dashboard()  # Saves to monitoring/dashboard.json
```

## 🔍 عرض Traces

### تصفح Traces

```python
from observability.tracer import get_tracer

tracer = get_tracer()

# Get recent traces
traces = tracer.get_traces(agent_name="MyAgent", limit=10)

for trace in traces:
    print(f"Trace {trace['trace_id']}")
    print(f"  Agent: {trace['root_agent']}")
    print(f"  Duration: {trace['duration_ms']:.1f}ms")
    print(f"  Success: {trace['success']}")
    print(f"  Spans: {len(trace['spans'])}")
```

### عرض Span Tree

```python
import json

# Load trace
trace_file = f"traces/trace_{trace_id}.json"
with open(trace_file) as f:
    trace_data = json.load(f)

# Load span tree
tree_file = f"traces/tree_{trace_id}.json"
with open(tree_file) as f:
    tree = json.load(f)

# Pretty print
print(json.dumps(tree, indent=2))
```

### Trace Summary

```python
summary = tracer.get_trace_summary()

print(f"Total Traces: {summary['total_traces']}")
print(f"Success Rate: {summary['success_rate']:.1%}")
print(f"Avg Duration: {summary['avg_duration_ms']:.1f}ms")

# Per-agent breakdown
for agent, stats in summary['agents'].items():
    print(f"\n{agent}:")
    print(f"  Count: {stats['count']}")
    print(f"  Success Rate: {stats['success_rate']:.1%}")
    print(f"  Avg Duration: {stats['avg_duration_ms']:.1f}ms")
```

## 🔗 LangSmith Integration

```python
from observability.tracer import AgentTracer

# Enable LangSmith
tracer = AgentTracer(
    enable_langsmith=True,
    langsmith_api_key="your_api_key",  # or set LANGCHAIN_API_KEY env var
    langsmith_project="your_project",  # or set LANGCHAIN_PROJECT env var
)

# Now all traces will be sent to LangSmith automatically!
```

## 📁 File Structure

```
observability/
├── __init__.py           # Package exports
├── tracer.py             # AgentTracer, Span, Trace
├── metrics.py            # MetricsCollector, AgentMetrics
├── monitor.py            # MonitoringDashboard, Alert
├── integration.py        # ObservableAgent, decorators
├── requirements.txt      # Optional dependencies
└── README.md            # This file

# Generated data
traces/
├── traces.jsonl          # All traces (one per line)
├── trace_{id}.json       # Individual trace
└── tree_{id}.json        # Span tree

metrics/
├── metrics_summary.json  # Latest summary
└── metrics_timeseries.jsonl  # Time series data

monitoring/
├── alerts.jsonl          # Alert history
└── dashboard.json        # Latest dashboard
```

## 🔧 Configuration

### Environment Variables

```bash
# LangSmith (optional)
export LANGCHAIN_API_KEY="your_api_key"
export LANGCHAIN_PROJECT="your_project"
export LANGCHAIN_TRACING_V2="true"

# Custom output directories
export OBSERVABILITY_TRACES_DIR="./my_traces"
export OBSERVABILITY_METRICS_DIR="./my_metrics"
export OBSERVABILITY_MONITORING_DIR="./my_monitoring"
```

### Programmatic Config

```python
from observability import AgentTracer, MetricsCollector, MonitoringDashboard
from observability import set_tracer, set_collector, set_monitor

# Custom configuration
tracer = AgentTracer(
    output_dir="custom_traces",
    enable_langsmith=True,
    langsmith_api_key="...",
    langsmith_project="...",
)

collector = MetricsCollector(output_dir="custom_metrics")
monitor = MonitoringDashboard(
    output_dir="custom_monitoring",
    metrics_collector=collector,
)

# Set as global instances
set_tracer(tracer)
set_collector(collector)
set_monitor(monitor)
```

## 🎓 أمثلة متقدمة

### Example 1: Full Integration

```python
from observability.integration import ObservableAgent, observable_run, observable_phase
from agents.base_agent import BaseAgent, AgentGoal

class FahasAgent(ObservableAgent, BaseAgent):
    def __init__(self):
        BaseAgent.__init__(self, name="Fahas")
        self.init_observability()
    
    @observable_run
    def run(self, goal: AgentGoal):
        # Full agentic loop with auto-tracing
        perception = self.perceive(goal)
        plan = self.plan(perception)
        result = self.execute(plan)
        reflection = self.reflect(result)
        return reflection
    
    @observable_phase("perceive")
    def perceive(self, goal: AgentGoal):
        # Perceive logic
        return {"query": goal.query, "context": goal.context}
    
    @observable_phase("plan")
    def plan(self, perception):
        # Plan logic
        return {"strategy": "complex_query"}
    
    @observable_phase("execute")
    def execute(self, plan):
        # Execute with tool tracking
        self._track_tool_call("odoo_search")
        results = self._query_odoo(plan["strategy"])
        
        self._track_tool_call("format_results")
        formatted = self._format_results(results)
        
        return {"results": formatted}
    
    @observable_phase("reflect")
    def reflect(self, result):
        # Reflect logic
        confidence = self._calculate_confidence(result)
        return {
            "result": result,
            "confidence": confidence,
            "lessons": ["Query successful"],
        }
```

### Example 2: Custom Metrics

```python
from observability.metrics import get_collector

def process_large_batch():
    collector = get_collector()
    
    start_time = time.time()
    success_count = 0
    
    for item in batch:
        try:
            result = process_item(item)
            success_count += 1
        except Exception as e:
            collector.record_error(
                agent_name="BatchProcessor",
                error=str(e),
            )
    
    duration_ms = (time.time() - start_time) * 1000
    
    collector.record_run(
        agent_name="BatchProcessor",
        duration_ms=duration_ms,
        success=success_count == len(batch),
        confidence=success_count / len(batch),
        metadata={"batch_size": len(batch)},
    )
```

### Example 3: Real-time Monitoring

```python
import threading
import time
from observability.monitor import get_monitor

def monitoring_loop():
    """Background monitoring thread"""
    monitor = get_monitor()
    
    while True:
        try:
            # Check alerts
            monitor.check_alerts()
            
            # Export dashboard every minute
            monitor.export_dashboard()
            
            time.sleep(30)  # Check every 30 seconds
        
        except Exception as e:
            print(f"Monitoring error: {e}")

# Start monitoring in background
monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
monitor_thread.start()
```

## 🧪 Testing

```bash
# Run all observability tests
pytest test_observability.py -v

# Run specific test
pytest test_observability.py::TestAgentTracer::test_trace_creation -v

# With coverage
pytest test_observability.py --cov=observability --cov-report=html
```

## 🤝 المساهمة

- إضافة exporters جديدة (Prometheus, Grafana, Datadog)
- تحسين Alert rules
- Dashboard UI (Web interface)
- Real-time streaming

## 📝 License

MIT License - نفس ترخيص المشروع الأساسي

---

**Built with ❤️ for Odoo HR Agents**
