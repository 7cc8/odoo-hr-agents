"""
Monitoring Dashboard & Alert System
Provides real-time monitoring and alerting capabilities.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
import json


class AlertLevel(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of alerts"""
    HIGH_ERROR_RATE = "high_error_rate"
    HIGH_LATENCY = "high_latency"
    LOW_CONFIDENCE = "low_confidence"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    ANOMALY_DETECTED = "anomaly_detected"
    AGENT_FAILURE = "agent_failure"
    THRESHOLD_BREACH = "threshold_breach"


@dataclass
class Alert:
    """An alert instance"""
    alert_id: str
    alert_type: AlertType
    level: AlertLevel
    agent_name: Optional[str]
    message: str
    timestamp: float
    
    # Context
    value: Optional[float] = None
    threshold: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Status
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AlertRule:
    """Configuration for an alert rule"""
    rule_id: str
    alert_type: AlertType
    level: AlertLevel
    condition: Callable[[Dict[str, Any]], bool]
    message_template: str
    cooldown_seconds: float = 300.0  # 5 minutes
    
    # Last fired
    last_fired: Optional[float] = None
    
    def should_fire(self, metrics: Dict[str, Any]) -> bool:
        """Check if alert should fire"""
        # Check cooldown
        if self.last_fired and (time.time() - self.last_fired) < self.cooldown_seconds:
            return False
        
        # Check condition
        return self.condition(metrics)
    
    def fire(self, agent_name: Optional[str], value: Optional[float], threshold: Optional[float]) -> Alert:
        """Fire the alert"""
        self.last_fired = time.time()
        
        import uuid
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            alert_type=self.alert_type,
            level=self.level,
            agent_name=agent_name,
            message=self.message_template.format(
                agent=agent_name or "system",
                value=value,
                threshold=threshold,
            ),
            timestamp=time.time(),
            value=value,
            threshold=threshold,
        )
        
        return alert


class MonitoringDashboard:
    """
    Monitoring Dashboard & Alert System
    
    Features:
    - Real-time monitoring
    - Custom alert rules
    - Alert history
    - Health checks
    - Auto-remediation hooks
    """
    
    def __init__(
        self,
        output_dir: str = "monitoring",
        metrics_collector: Optional[Any] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Metrics collector reference
        self.metrics_collector = metrics_collector
        
        # Alert rules
        self.alert_rules: Dict[str, AlertRule] = {}
        self._setup_default_rules()
        
        # Active alerts
        self.active_alerts: Dict[str, Alert] = {}
        
        # Alert history
        self.alert_history: List[Alert] = []
        
        # Alert handlers (callbacks)
        self.alert_handlers: List[Callable[[Alert], None]] = []
        
        # Monitoring enabled
        self.enabled = True
        
        # Last check time
        self.last_check = time.time()
        self.check_interval = 30.0  # Check every 30 seconds
    
    def _setup_default_rules(self):
        """Setup default alert rules"""
        
        # High error rate
        self.add_rule(
            rule_id="high_error_rate",
            alert_type=AlertType.HIGH_ERROR_RATE,
            level=AlertLevel.ERROR,
            condition=lambda m: m.get("success_rate", 1.0) < 0.90,
            message_template="High error rate detected for {agent}: {value:.1%} (threshold: {threshold:.1%})",
        )
        
        # High latency
        self.add_rule(
            rule_id="high_latency",
            alert_type=AlertType.HIGH_LATENCY,
            level=AlertLevel.WARNING,
            condition=lambda m: m.get("avg_duration_ms", 0) > 5000,
            message_template="High latency detected for {agent}: {value:.0f}ms (threshold: {threshold:.0f}ms)",
        )
        
        # Low confidence
        self.add_rule(
            rule_id="low_confidence",
            alert_type=AlertType.LOW_CONFIDENCE,
            level=AlertLevel.WARNING,
            condition=lambda m: m.get("avg_confidence", 1.0) < 0.70,
            message_template="Low confidence scores for {agent}: {value:.2f} (threshold: {threshold:.2f})",
        )
        
        # Agent failure (consecutive failures)
        self.add_rule(
            rule_id="agent_failure",
            alert_type=AlertType.AGENT_FAILURE,
            level=AlertLevel.CRITICAL,
            condition=lambda m: m.get("recent_error_count", 0) >= 5,
            message_template="Agent {agent} has {value:.0f} consecutive failures",
        )
    
    def add_rule(
        self,
        rule_id: str,
        alert_type: AlertType,
        level: AlertLevel,
        condition: Callable[[Dict[str, Any]], bool],
        message_template: str,
        cooldown_seconds: float = 300.0,
    ):
        """Add a custom alert rule"""
        rule = AlertRule(
            rule_id=rule_id,
            alert_type=alert_type,
            level=level,
            condition=condition,
            message_template=message_template,
            cooldown_seconds=cooldown_seconds,
        )
        self.alert_rules[rule_id] = rule
        print(f"✅ Alert rule added: {rule_id} ({level.value})")
    
    def remove_rule(self, rule_id: str):
        """Remove an alert rule"""
        if rule_id in self.alert_rules:
            del self.alert_rules[rule_id]
            print(f"🗑️ Alert rule removed: {rule_id}")
    
    def add_alert_handler(self, handler: Callable[[Alert], None]):
        """Add a custom alert handler"""
        self.alert_handlers.append(handler)
    
    def check_alerts(self):
        """Check all alert rules"""
        if not self.enabled:
            return
        
        if not self.metrics_collector:
            return
        
        # Check interval
        if time.time() - self.last_check < self.check_interval:
            return
        
        self.last_check = time.time()
        
        # Get current metrics
        summary = self.metrics_collector.get_summary()
        
        # Check system-wide rules
        self._check_system_rules(summary)
        
        # Check per-agent rules
        for agent_name, agent_metrics in summary.get("agents", {}).items():
            self._check_agent_rules(agent_name, agent_metrics)
    
    def _check_system_rules(self, metrics: Dict[str, Any]):
        """Check system-wide alert rules"""
        for rule in self.alert_rules.values():
            if rule.should_fire(metrics):
                # Determine value and threshold based on rule type
                value, threshold = self._get_rule_values(rule, metrics, None)
                
                alert = rule.fire(
                    agent_name=None,
                    value=value,
                    threshold=threshold,
                )
                
                self._handle_alert(alert)
    
    def _check_agent_rules(self, agent_name: str, metrics: Dict[str, Any]):
        """Check per-agent alert rules"""
        for rule in self.alert_rules.values():
            if rule.should_fire(metrics):
                value, threshold = self._get_rule_values(rule, metrics, agent_name)
                
                alert = rule.fire(
                    agent_name=agent_name,
                    value=value,
                    threshold=threshold,
                )
                
                self._handle_alert(alert)
    
    def _get_rule_values(
        self,
        rule: AlertRule,
        metrics: Dict[str, Any],
        agent_name: Optional[str],
    ) -> tuple[Optional[float], Optional[float]]:
        """Extract value and threshold for a rule"""
        
        if rule.alert_type == AlertType.HIGH_ERROR_RATE:
            return metrics.get("success_rate", 1.0), 0.90
        
        elif rule.alert_type == AlertType.HIGH_LATENCY:
            return metrics.get("avg_duration_ms", 0), 5000.0
        
        elif rule.alert_type == AlertType.LOW_CONFIDENCE:
            confidence_data = metrics.get("confidence_scores", {})
            return confidence_data.get("avg", 1.0), 0.70
        
        elif rule.alert_type == AlertType.AGENT_FAILURE:
            recent_errors = metrics.get("recent_errors", [])
            return float(len(recent_errors)), 5.0
        
        else:
            return None, None
    
    def _handle_alert(self, alert: Alert):
        """Handle a new alert"""
        # Add to active alerts
        self.active_alerts[alert.alert_id] = alert
        
        # Add to history
        self.alert_history.append(alert)
        
        # Save to disk
        self._save_alert(alert)
        
        # Call handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                print(f"⚠️ Alert handler failed: {e}")
        
        # Print alert
        self._print_alert(alert)
    
    def _print_alert(self, alert: Alert):
        """Print alert to console"""
        emoji_map = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨",
        }
        
        emoji = emoji_map.get(alert.level, "🔔")
        timestamp = datetime.fromtimestamp(alert.timestamp).strftime("%H:%M:%S")
        
        print(f"\n{emoji} [{alert.level.value.upper()}] {timestamp}")
        print(f"   {alert.message}")
        if alert.agent_name:
            print(f"   Agent: {alert.agent_name}")
        print()
    
    def _save_alert(self, alert: Alert):
        """Save alert to disk"""
        try:
            # Save to JSONL
            alerts_file = self.output_dir / "alerts.jsonl"
            with open(alerts_file, "a", encoding="utf-8") as f:
                json.dump(alert.to_dict(), f)
                f.write("\n")
        except Exception as e:
            print(f"⚠️ Failed to save alert: {e}")
    
    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            print(f"✅ Alert acknowledged: {alert_id}")
    
    def resolve_alert(self, alert_id: str):
        """Resolve an alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = time.time()
            del self.active_alerts[alert_id]
            print(f"✅ Alert resolved: {alert_id}")
    
    def get_active_alerts(
        self,
        level: Optional[AlertLevel] = None,
        agent_name: Optional[str] = None,
    ) -> List[Alert]:
        """Get active alerts"""
        alerts = list(self.active_alerts.values())
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        if agent_name:
            alerts = [a for a in alerts if a.agent_name == agent_name]
        
        return alerts
    
    def get_alert_history(
        self,
        hours: int = 24,
        level: Optional[AlertLevel] = None,
        agent_name: Optional[str] = None,
    ) -> List[Alert]:
        """Get alert history"""
        cutoff_time = time.time() - (hours * 3600)
        
        alerts = [
            a for a in self.alert_history
            if a.timestamp >= cutoff_time
        ]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        if agent_name:
            alerts = [a for a in alerts if a.agent_name == agent_name]
        
        return alerts
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data"""
        if not self.metrics_collector:
            return {"error": "No metrics collector"}
        
        summary = self.metrics_collector.get_summary()
        health = self.metrics_collector.get_health_status()
        
        # Count alerts by level
        alert_counts = defaultdict(int)
        for alert in self.active_alerts.values():
            alert_counts[alert.level.value] += 1
        
        return {
            "timestamp": time.time(),
            "health": health,
            "metrics": summary,
            "active_alerts": {
                "total": len(self.active_alerts),
                "by_level": dict(alert_counts),
                "alerts": [a.to_dict() for a in self.get_active_alerts()],
            },
            "recent_alerts": [
                a.to_dict() for a in self.get_alert_history(hours=1)
            ],
        }
    
    def export_dashboard(self):
        """Export dashboard data to file"""
        try:
            dashboard_file = self.output_dir / "dashboard.json"
            with open(dashboard_file, "w", encoding="utf-8") as f:
                json.dump(self.get_dashboard_data(), f, indent=2)
            print("📊 Dashboard exported")
        except Exception as e:
            print(f"⚠️ Failed to export dashboard: {e}")
    
    def generate_report(
        self,
        hours: int = 24,
        output_file: Optional[str] = None,
    ) -> str:
        """Generate monitoring report"""
        if not self.metrics_collector:
            return "No metrics collector configured"
        
        summary = self.metrics_collector.get_summary()
        health = self.metrics_collector.get_health_status()
        alerts = self.get_alert_history(hours=hours)
        
        # Build report
        lines = []
        lines.append("=" * 80)
        lines.append("MONITORING REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Period: Last {hours} hours")
        lines.append("")
        
        # Health status
        lines.append("SYSTEM HEALTH")
        lines.append("-" * 80)
        lines.append(f"Status: {health['status'].upper()}")
        lines.append(f"Success Rate: {health['success_rate']:.1%}")
        lines.append(f"Avg Latency: {health['avg_latency_ms']:.0f}ms")
        lines.append(f"P95 Latency: {health['p95_latency_ms']:.0f}ms")
        lines.append(f"Uptime: {health['uptime_seconds'] / 3600:.1f} hours")
        lines.append(f"Total Requests: {health['total_requests']}")
        lines.append("")
        
        # Agent stats
        lines.append("AGENT PERFORMANCE")
        lines.append("-" * 80)
        for agent_name, agent_stats in health.get("agents_status", {}).items():
            lines.append(f"{agent_name}:")
            lines.append(f"  Success Rate: {agent_stats['success_rate']:.1%}")
            lines.append(f"  Avg Duration: {agent_stats['avg_duration_ms']:.0f}ms")
            lines.append(f"  Total Runs: {agent_stats['total_runs']}")
        lines.append("")
        
        # Alerts
        lines.append(f"ALERTS (Last {hours} hours)")
        lines.append("-" * 80)
        
        if not alerts:
            lines.append("No alerts in this period")
        else:
            # Group by level
            alerts_by_level = defaultdict(list)
            for alert in alerts:
                alerts_by_level[alert.level].append(alert)
            
            for level in [AlertLevel.CRITICAL, AlertLevel.ERROR, AlertLevel.WARNING, AlertLevel.INFO]:
                level_alerts = alerts_by_level.get(level, [])
                if level_alerts:
                    lines.append(f"\n{level.value.upper()} ({len(level_alerts)}):")
                    for alert in level_alerts[:10]:  # Show first 10
                        timestamp = datetime.fromtimestamp(alert.timestamp).strftime("%H:%M:%S")
                        lines.append(f"  [{timestamp}] {alert.message}")
        
        lines.append("")
        lines.append("=" * 80)
        
        report = "\n".join(lines)
        
        # Save to file if requested
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"📄 Report saved to {output_file}")
        
        return report
    
    def start_monitoring(self):
        """Start monitoring (enable alert checking)"""
        self.enabled = True
        print("🟢 Monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring (disable alert checking)"""
        self.enabled = False
        print("🔴 Monitoring stopped")


# Global monitor instance
_global_monitor: Optional[MonitoringDashboard] = None


def get_monitor() -> MonitoringDashboard:
    """Get global monitor instance"""
    global _global_monitor
    if _global_monitor is None:
        from .metrics import get_collector
        _global_monitor = MonitoringDashboard(metrics_collector=get_collector())
    return _global_monitor


def set_monitor(monitor: MonitoringDashboard):
    """Set global monitor instance"""
    global _global_monitor
    _global_monitor = monitor
