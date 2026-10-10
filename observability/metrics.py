"""
Metrics Collection System
Provides real-time metrics for agent performance monitoring.
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import json


class MetricType(str, Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricPoint:
    """A single metric data point"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentMetrics:
    """Metrics for a single agent"""
    agent_name: str
    
    # Execution metrics
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    
    # Performance metrics
    total_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    max_duration_ms: float = 0.0
    
    # Phase metrics (perceive, plan, execute, reflect)
    phase_durations: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    # Token usage (for LLM calls)
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    
    # Confidence scores
    confidence_scores: List[float] = field(default_factory=list)
    
    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    # Tool usage
    tool_calls: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Last update
    last_update: float = field(default_factory=time.time)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_runs == 0:
            return 0.0
        return self.successful_runs / self.total_runs
    
    @property
    def avg_duration_ms(self) -> float:
        """Calculate average duration"""
        if self.total_runs == 0:
            return 0.0
        return self.total_duration_ms / self.total_runs
    
    @property
    def avg_confidence(self) -> float:
        """Calculate average confidence"""
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores) / len(self.confidence_scores)
    
    @property
    def avg_tokens_per_run(self) -> float:
        """Calculate average tokens per run"""
        if self.total_runs == 0:
            return 0.0
        return self.total_tokens / self.total_runs
    
    def get_phase_avg_duration(self, phase: str) -> float:
        """Get average duration for a specific phase"""
        durations = self.phase_durations.get(phase, [])
        if not durations:
            return 0.0
        return sum(durations) / len(durations)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_name": self.agent_name,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": self.success_rate,
            "total_duration_ms": self.total_duration_ms,
            "avg_duration_ms": self.avg_duration_ms,
            "min_duration_ms": self.min_duration_ms if self.min_duration_ms != float('inf') else 0.0,
            "max_duration_ms": self.max_duration_ms,
            "phase_durations": {
                phase: {
                    "count": len(durations),
                    "avg": sum(durations) / len(durations) if durations else 0.0,
                    "min": min(durations) if durations else 0.0,
                    "max": max(durations) if durations else 0.0,
                }
                for phase, durations in self.phase_durations.items()
            },
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "avg_tokens_per_run": self.avg_tokens_per_run,
            "confidence_scores": {
                "count": len(self.confidence_scores),
                "avg": self.avg_confidence,
                "min": min(self.confidence_scores) if self.confidence_scores else 0.0,
                "max": max(self.confidence_scores) if self.confidence_scores else 0.0,
            },
            "recent_errors": self.errors[-10:],  # Last 10 errors
            "tool_calls": dict(self.tool_calls),
            "last_update": self.last_update,
        }


@dataclass
class SystemMetrics:
    """System-wide metrics"""
    
    # Overall stats
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Time-series data (rolling window)
    request_rate_window: deque = field(default_factory=lambda: deque(maxlen=100))
    latency_window: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    # Agent metrics
    agent_metrics: Dict[str, AgentMetrics] = field(default_factory=dict)
    
    # Start time
    start_time: float = field(default_factory=time.time)
    
    @property
    def uptime_seconds(self) -> float:
        """Calculate uptime"""
        return time.time() - self.start_time
    
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def requests_per_minute(self) -> float:
        """Calculate requests per minute (last 100 requests)"""
        if len(self.request_rate_window) < 2:
            return 0.0
        
        time_span = self.request_rate_window[-1] - self.request_rate_window[0]
        if time_span == 0:
            return 0.0
        
        return (len(self.request_rate_window) / time_span) * 60
    
    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency"""
        if not self.latency_window:
            return 0.0
        return sum(self.latency_window) / len(self.latency_window)
    
    @property
    def p95_latency_ms(self) -> float:
        """Calculate 95th percentile latency"""
        if not self.latency_window:
            return 0.0
        sorted_latencies = sorted(self.latency_window)
        index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[index]
    
    @property
    def p99_latency_ms(self) -> float:
        """Calculate 99th percentile latency"""
        if not self.latency_window:
            return 0.0
        sorted_latencies = sorted(self.latency_window)
        index = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[index]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "uptime_seconds": self.uptime_seconds,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "requests_per_minute": self.requests_per_minute,
            "latency": {
                "avg_ms": self.avg_latency_ms,
                "p95_ms": self.p95_latency_ms,
                "p99_ms": self.p99_latency_ms,
            },
            "agents": {
                name: metrics.to_dict()
                for name, metrics in self.agent_metrics.items()
            }
        }


class MetricsCollector:
    """
    Metrics Collection System
    
    Collects and aggregates metrics for:
    - Agent performance (latency, success rate, confidence)
    - Token usage
    - Tool calls
    - Error rates
    - System health
    """
    
    def __init__(self, output_dir: str = "metrics"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # System metrics
        self.system_metrics = SystemMetrics()
        
        # Time-series storage
        self.metrics_history: deque = deque(maxlen=10000)  # Last 10k metrics
        
        # Export interval (seconds)
        self.export_interval = 60.0  # Export every minute
        self.last_export = time.time()
    
    def get_agent_metrics(self, agent_name: str) -> AgentMetrics:
        """Get or create metrics for an agent"""
        if agent_name not in self.system_metrics.agent_metrics:
            self.system_metrics.agent_metrics[agent_name] = AgentMetrics(agent_name=agent_name)
        return self.system_metrics.agent_metrics[agent_name]
    
    def record_run(
        self,
        agent_name: str,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
        confidence: Optional[float] = None,
        token_usage: Optional[Dict[str, int]] = None,
        phase_durations: Optional[Dict[str, float]] = None,
        tool_calls: Optional[List[str]] = None,
    ):
        """Record a complete agent run"""
        # System-level metrics
        self.system_metrics.total_requests += 1
        if success:
            self.system_metrics.successful_requests += 1
        else:
            self.system_metrics.failed_requests += 1
        
        self.system_metrics.request_rate_window.append(time.time())
        self.system_metrics.latency_window.append(duration_ms)
        
        # Agent-level metrics
        metrics = self.get_agent_metrics(agent_name)
        metrics.total_runs += 1
        metrics.last_update = time.time()
        
        if success:
            metrics.successful_runs += 1
        else:
            metrics.failed_runs += 1
            if error:
                metrics.errors.append({
                    "timestamp": time.time(),
                    "error": error,
                })
        
        # Duration metrics
        metrics.total_duration_ms += duration_ms
        metrics.min_duration_ms = min(metrics.min_duration_ms, duration_ms)
        metrics.max_duration_ms = max(metrics.max_duration_ms, duration_ms)
        
        # Phase durations
        if phase_durations:
            for phase, phase_duration in phase_durations.items():
                metrics.phase_durations[phase].append(phase_duration)
        
        # Token usage
        if token_usage:
            metrics.total_tokens += token_usage.get("total_tokens", 0)
            metrics.prompt_tokens += token_usage.get("prompt_tokens", 0)
            metrics.completion_tokens += token_usage.get("completion_tokens", 0)
        
        # Confidence
        if confidence is not None:
            metrics.confidence_scores.append(confidence)
        
        # Tool calls
        if tool_calls:
            for tool in tool_calls:
                metrics.tool_calls[tool] += 1
        
        # Store in history
        self.metrics_history.append({
            "timestamp": time.time(),
            "agent_name": agent_name,
            "duration_ms": duration_ms,
            "success": success,
            "error": error,
            "confidence": confidence,
            "token_usage": token_usage,
            "phase_durations": phase_durations,
            "tool_calls": tool_calls,
        })
        
        # Auto-export if interval passed
        if time.time() - self.last_export >= self.export_interval:
            self.export_metrics()
    
    def record_phase(
        self,
        agent_name: str,
        phase: str,
        duration_ms: float,
    ):
        """Record a single phase execution"""
        metrics = self.get_agent_metrics(agent_name)
        metrics.phase_durations[phase].append(duration_ms)
    
    def record_tool_call(
        self,
        agent_name: str,
        tool_name: str,
    ):
        """Record a tool call"""
        metrics = self.get_agent_metrics(agent_name)
        metrics.tool_calls[tool_name] += 1
    
    def record_error(
        self,
        agent_name: str,
        error: str,
    ):
        """Record an error"""
        metrics = self.get_agent_metrics(agent_name)
        metrics.errors.append({
            "timestamp": time.time(),
            "error": error,
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get current metrics summary"""
        return self.system_metrics.to_dict()
    
    def get_agent_summary(self, agent_name: str) -> Dict[str, Any]:
        """Get metrics for a specific agent"""
        metrics = self.get_agent_metrics(agent_name)
        return metrics.to_dict()
    
    def get_time_series(
        self,
        agent_name: Optional[str] = None,
        metric_name: str = "duration_ms",
        window_minutes: int = 60,
    ) -> List[Tuple[float, float]]:
        """Get time series data for a metric"""
        cutoff_time = time.time() - (window_minutes * 60)
        
        points = []
        for entry in self.metrics_history:
            if entry["timestamp"] < cutoff_time:
                continue
            
            if agent_name and entry["agent_name"] != agent_name:
                continue
            
            value = entry.get(metric_name)
            if value is not None:
                points.append((entry["timestamp"], value))
        
        return points
    
    def export_metrics(self):
        """Export metrics to file"""
        try:
            # Export summary as JSON
            summary_file = self.output_dir / "metrics_summary.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(self.get_summary(), f, indent=2)
            
            # Export time series as JSONL
            ts_file = self.output_dir / "metrics_timeseries.jsonl"
            with open(ts_file, "a", encoding="utf-8") as f:
                for entry in self.metrics_history:
                    if entry.get("_exported"):
                        continue
                    json.dump(entry, f)
                    f.write("\n")
                    entry["_exported"] = True
            
            self.last_export = time.time()
            print(f"📊 Metrics exported ({self.system_metrics.total_requests} total requests)")
        
        except Exception as e:
            print(f"⚠️ Failed to export metrics: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status"""
        # Calculate health indicators
        success_rate = self.system_metrics.success_rate
        avg_latency = self.system_metrics.avg_latency_ms
        p95_latency = self.system_metrics.p95_latency_ms
        
        # Determine health status
        is_healthy = (
            success_rate >= 0.95 and
            avg_latency < 5000 and  # < 5 seconds
            p95_latency < 10000      # < 10 seconds
        )
        
        is_degraded = (
            success_rate >= 0.90 and
            avg_latency < 10000 and
            p95_latency < 20000
        )
        
        if is_healthy:
            status = "healthy"
        elif is_degraded:
            status = "degraded"
        else:
            status = "unhealthy"
        
        return {
            "status": status,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "uptime_seconds": self.system_metrics.uptime_seconds,
            "total_requests": self.system_metrics.total_requests,
            "agents_status": {
                name: {
                    "success_rate": metrics.success_rate,
                    "avg_duration_ms": metrics.avg_duration_ms,
                    "total_runs": metrics.total_runs,
                }
                for name, metrics in self.system_metrics.agent_metrics.items()
            }
        }
    
    def reset_metrics(self):
        """Reset all metrics (for testing)"""
        self.system_metrics = SystemMetrics()
        self.metrics_history.clear()
        print("🔄 Metrics reset")


# Global collector instance
_global_collector: Optional[MetricsCollector] = None


def get_collector() -> MetricsCollector:
    """Get global collector instance"""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def set_collector(collector: MetricsCollector):
    """Set global collector instance"""
    global _global_collector
    _global_collector = collector
