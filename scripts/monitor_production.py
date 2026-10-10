#!/usr/bin/env python3
"""
Production Monitoring Script
Continuously monitors production system and alerts on issues.
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from observability.tracer import get_tracer
from observability.metrics import get_collector
from observability.monitor import get_monitor


class ProductionMonitor:
    """Production monitoring and alerting"""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.tracer = get_tracer()
        self.collector = get_collector()
        self.monitor = get_monitor()
        self.running = True
    
    def start(self):
        """Start monitoring loop"""
        print("="*80)
        print("🔍 PRODUCTION MONITORING STARTED")
        print("="*80)
        print(f"Check interval: {self.check_interval}s")
        print("Press Ctrl+C to stop")
        print()
        
        try:
            while self.running:
                self.check_system()
                time.sleep(self.check_interval)
        
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped by user")
            self.stop()
    
    def check_system(self):
        """Run system checks"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{timestamp}] Checking system...")
        
        # Get health status
        health = self.collector.get_health_status()
        
        # Display key metrics
        print(f"  Status: {self._get_status_emoji(health['status'])} {health['status'].upper()}")
        print(f"  Success Rate: {health['success_rate']:.1%}")
        print(f"  Avg Latency: {health['avg_latency_ms']:.0f}ms")
        print(f"  P95 Latency: {health['p95_latency_ms']:.0f}ms")
        print(f"  Total Requests: {health['total_requests']}")
        
        # Check alerts
        self.monitor.check_alerts()
        active_alerts = self.monitor.get_active_alerts()
        
        if active_alerts:
            print(f"\n  ⚠️  {len(active_alerts)} ACTIVE ALERTS:")
            for alert in active_alerts[:5]:  # Show first 5
                print(f"     [{alert.level.upper()}] {alert.message}")
        else:
            print(f"  ✅ No active alerts")
        
        # Agent breakdown
        agents_status = health.get('agents_status', {})
        if agents_status:
            print(f"\n  Agents:")
            for agent_name, agent_health in list(agents_status.items())[:5]:
                print(f"     {agent_name:12} - Success: {agent_health['success_rate']:.1%}, "
                      f"Latency: {agent_health['avg_duration_ms']:.0f}ms")
        
        # Export metrics
        if health['total_requests'] % 10 == 0:  # Every 10 requests
            self.collector.export_metrics()
            self.monitor.export_dashboard()
    
    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for status"""
        return {
            "healthy": "🟢",
            "degraded": "🟡",
            "unhealthy": "🔴",
        }.get(status, "⚪")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        
        # Final export
        self.collector.export_metrics()
        self.monitor.export_dashboard()
        
        # Generate report
        report = self.monitor.generate_report(hours=24)
        report_file = Path("monitoring") / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_file, "w") as f:
            f.write(report)
        
        print(f"\n📄 Final report saved: {report_file}")
        print("\n✅ Monitoring stopped cleanly")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor production system")
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Check interval in seconds (default: 30)"
    )
    
    args = parser.parse_args()
    
    monitor = ProductionMonitor(check_interval=args.interval)
    monitor.start()


if __name__ == "__main__":
    main()
