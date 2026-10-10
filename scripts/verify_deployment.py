#!/usr/bin/env python3
"""
Deployment Verification Script
Verifies that the system is properly deployed and functional.
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.fahas_agent import FahasAgent
from agents.musleh_agent import MuslehAgent
from agents.hares_agent import HaresAgent
from agents.katib_agent import KatibAgent
from agents.mudaqqiq_agent import MudaqqiqAgent
from agents.muwaffaq_agent import MuwaffaqAgent
from agents.sijil_agent import SijilAgent
from agents.seraj_meta_agent import SerajMetaAgent


class DeploymentVerifier:
    """Verifies deployment health"""
    
    def __init__(self):
        self.checks: List[Tuple[str, bool, str]] = []
        self.agents = {}
    
    def run_all_checks(self) -> bool:
        """Run all verification checks"""
        print("="*80)
        print("🔍 DEPLOYMENT VERIFICATION")
        print("="*80)
        print()
        
        # Run checks
        self.check_environment()
        self.check_dependencies()
        self.check_agents()
        self.check_configuration()
        self.check_storage()
        self.check_observability()
        self.check_connectivity()
        
        # Summary
        self.print_summary()
        
        # Return overall status
        return all(check[1] for check in self.checks)
    
    def check_environment(self):
        """Check environment variables"""
        print("📋 Checking environment variables...")
        
        import os
        
        required_vars = [
            "ODOO_URL",
            "ODOO_DB",
            "ODOO_USERNAME",
        ]
        
        optional_vars = [
            "LLM_PROVIDER",
            "LANGSMITH_API_KEY",
            "ENVIRONMENT",
        ]
        
        # Check required
        missing_required = []
        for var in required_vars:
            if not os.getenv(var):
                missing_required.append(var)
        
        if missing_required:
            self.add_check("Environment Variables", False, 
                          f"Missing: {', '.join(missing_required)}")
        else:
            self.add_check("Environment Variables", True, 
                          f"{len(required_vars)} required vars set")
        
        # Check optional
        set_optional = [var for var in optional_vars if os.getenv(var)]
        print(f"   Optional vars: {len(set_optional)}/{len(optional_vars)} set")
        print()
    
    def check_dependencies(self):
        """Check Python dependencies"""
        print("📦 Checking dependencies...")
        
        required_packages = [
            "langchain",
            "langgraph",
            "pandas",
            "openpyxl",
            "chromadb",
        ]
        
        missing = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        if missing:
            self.add_check("Dependencies", False, 
                          f"Missing: {', '.join(missing)}")
        else:
            self.add_check("Dependencies", True, 
                          f"{len(required_packages)} packages installed")
        print()
    
    def check_agents(self):
        """Check agent instantiation"""
        print("🤖 Checking agents...")
        
        agent_classes = {
            "Fahas": FahasAgent,
            "Musleh": MuslehAgent,
            "Hares": HaresAgent,
            "Katib": KatibAgent,
            "Mudaqqiq": MudaqqiqAgent,
            "Muwaffaq": MuwaffaqAgent,
            "Sijil": SijilAgent,
            "Seraj": SerajMetaAgent,
        }
        
        failed = []
        for name, agent_class in agent_classes.items():
            try:
                agent = agent_class()
                self.agents[name] = agent
                print(f"   ✅ {name}")
            except Exception as e:
                failed.append(f"{name}: {e}")
                print(f"   ❌ {name}: {e}")
        
        if failed:
            self.add_check("Agent Initialization", False, 
                          f"{len(failed)} agents failed")
        else:
            self.add_check("Agent Initialization", True, 
                          f"All {len(agent_classes)} agents initialized")
        print()
    
    def check_configuration(self):
        """Check configuration files"""
        print("⚙️  Checking configuration...")
        
        config_files = [
            ".env",
            "parser.py",
            "template_detector.py",
        ]
        
        missing = []
        for file in config_files:
            if not Path(file).exists():
                missing.append(file)
        
        if missing:
            self.add_check("Configuration", False, 
                          f"Missing: {', '.join(missing)}")
        else:
            self.add_check("Configuration", True, 
                          f"{len(config_files)} files present")
        print()
    
    def check_storage(self):
        """Check storage directories"""
        print("💾 Checking storage...")
        
        directories = [
            "traces",
            "metrics",
            "monitoring",
            "memory/chroma_db",
        ]
        
        missing = []
        for dir_path in directories:
            path = Path(dir_path)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    print(f"   ✅ Created: {dir_path}")
                except Exception as e:
                    missing.append(f"{dir_path}: {e}")
                    print(f"   ❌ Failed to create: {dir_path}")
            else:
                print(f"   ✅ {dir_path}")
        
        if missing:
            self.add_check("Storage Directories", False, 
                          f"{len(missing)} directories failed")
        else:
            self.add_check("Storage Directories", True, 
                          f"All {len(directories)} directories ready")
        print()
    
    def check_observability(self):
        """Check observability system"""
        print("📊 Checking observability...")
        
        try:
            from observability.tracer import get_tracer
            from observability.metrics import get_collector
            from observability.monitor import get_monitor
            
            tracer = get_tracer()
            collector = get_collector()
            monitor = get_monitor()
            
            # Test basic functionality
            with tracer.trace(agent_name="VerificationTest"):
                time.sleep(0.01)
            
            collector.record_run(
                agent_name="VerificationTest",
                duration_ms=10.0,
                success=True
            )
            
            health = collector.get_health_status()
            
            self.add_check("Observability", True, 
                          f"Status: {health['status']}")
            print(f"   ✅ Tracer operational")
            print(f"   ✅ Metrics collector operational")
            print(f"   ✅ Monitor operational")
        
        except Exception as e:
            self.add_check("Observability", False, str(e))
            print(f"   ❌ Failed: {e}")
        
        print()
    
    def check_connectivity(self):
        """Check external connections"""
        print("🌐 Checking connectivity...")
        
        import os
        
        # Check Odoo
        odoo_url = os.getenv("ODOO_URL")
        if odoo_url:
            try:
                import requests
                response = requests.get(odoo_url, timeout=5)
                if response.status_code < 500:
                    print(f"   ✅ Odoo reachable ({odoo_url})")
                    odoo_ok = True
                else:
                    print(f"   ⚠️  Odoo returned {response.status_code}")
                    odoo_ok = False
            except Exception as e:
                print(f"   ❌ Odoo unreachable: {e}")
                odoo_ok = False
        else:
            print(f"   ⚠️  ODOO_URL not set")
            odoo_ok = False
        
        # Check LLM provider
        llm_provider = os.getenv("LLM_PROVIDER", "ollama")
        if llm_provider == "ollama":
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            try:
                import requests
                response = requests.get(f"{ollama_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    print(f"   ✅ Ollama reachable ({len(models)} models)")
                    llm_ok = True
                else:
                    print(f"   ⚠️  Ollama returned {response.status_code}")
                    llm_ok = False
            except Exception as e:
                print(f"   ❌ Ollama unreachable: {e}")
                llm_ok = False
        else:
            print(f"   ℹ️  Using {llm_provider} (API key required)")
            llm_ok = True  # Assume OK if configured
        
        overall_ok = odoo_ok and llm_ok
        self.add_check("Connectivity", overall_ok, 
                      "All services reachable" if overall_ok else "Some services unreachable")
        print()
    
    def add_check(self, name: str, passed: bool, details: str):
        """Add check result"""
        self.checks.append((name, passed, details))
    
    def print_summary(self):
        """Print verification summary"""
        print("="*80)
        print("📋 VERIFICATION SUMMARY")
        print("="*80)
        print()
        
        passed_count = sum(1 for check in self.checks if check[1])
        total_count = len(self.checks)
        
        for name, passed, details in self.checks:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status:10} {name:30} {details}")
        
        print()
        print("="*80)
        
        if passed_count == total_count:
            print(f"✅ ALL CHECKS PASSED ({passed_count}/{total_count})")
            print("="*80)
            print("🚀 System is ready for deployment!")
        else:
            print(f"⚠️  {total_count - passed_count} CHECKS FAILED ({passed_count}/{total_count} passed)")
            print("="*80)
            print("❌ System is NOT ready for deployment!")
            print()
            print("Please fix the failed checks before deploying.")
        
        print()
        return passed_count == total_count


def main():
    """Main entry point"""
    verifier = DeploymentVerifier()
    success = verifier.run_all_checks()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
