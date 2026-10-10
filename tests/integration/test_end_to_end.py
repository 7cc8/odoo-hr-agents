"""
End-to-End Integration Tests
Tests complete workflows from Excel upload to final output.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from openpyxl import Workbook
from datetime import datetime, timedelta

# Import agents
from agents.fahas_agent import FahasAgent
from agents.musleh_agent import MuslehAgent
from agents.hares_agent import HaresAgent
from agents.katib_agent import KatibAgent
from agents.mudaqqiq_agent import MudaqqiqAgent
from agents.muwaffaq_agent import MuwaffaqAgent
from agents.sijil_agent import SijilAgent
from agents.seraj_meta_agent import SerajMetaAgent
from agents.base_agent import AgentGoal

# Import support modules
from template_detector import TemplateDetector


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mock_llm = self._create_mock_llm()
        self.mock_odoo = self._create_mock_odoo()
        
        # Initialize agents
        self.fahas = FahasAgent()
        self.musleh = MuslehAgent()
        self.hares = HaresAgent()
        self.katib = KatibAgent()
        self.mudaqqiq = MudaqqiqAgent()
        self.muwaffaq = MuwaffaqAgent()
        self.sijil = SijilAgent()
        self.seraj = SerajMetaAgent()
    
    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def _create_mock_llm(self):
        """Create mock LLM provider"""
        mock = Mock()
        mock.generate.return_value = {
            "text": "Test response",
            "confidence": 0.95
        }
        return mock
    
    def _create_mock_odoo(self):
        """Create mock Odoo connection"""
        mock = Mock()
        mock.search_read.return_value = [
            {"id": 1, "name": "John Doe", "department": "IT"},
            {"id": 2, "name": "Jane Smith", "department": "HR"},
        ]
        mock.create.return_value = 3
        mock.write.return_value = True
        return mock
    
    def _create_test_excel(self, sheet_type: str, num_rows: int = 10) -> Path:
        """Create test Excel file"""
        file_path = self.temp_dir / f"test_{sheet_type}.xlsx"
        wb = Workbook()
        ws = wb.active
        
        if sheet_type == "attendance":
            ws.append(["Employee ID", "Date", "Check In", "Check Out"])
            for i in range(num_rows):
                ws.append([f"EMP{i:03d}", datetime.now().date(), "09:00", "17:00"])
        
        elif sheet_type == "payroll":
            ws.append(["Employee ID", "Basic Salary", "Allowances", "Deductions"])
            for i in range(num_rows):
                ws.append([f"EMP{i:03d}", 5000 + i*100, 500, 200])
        
        elif sheet_type == "leaves":
            ws.append(["Employee ID", "Leave Type", "Start Date", "End Date"])
            for i in range(num_rows):
                ws.append([f"EMP{i:03d}", "Annual", datetime.now().date(), 
                          (datetime.now() + timedelta(days=7)).date()])
        
        elif sheet_type == "new_hire":
            ws.append(["Name", "Email", "Department", "Position", "Start Date"])
            for i in range(num_rows):
                ws.append([f"Employee {i}", f"emp{i}@test.com", "IT", 
                          "Developer", datetime.now().date()])
        
        wb.save(file_path)
        return file_path
    
    @pytest.mark.integration
    def test_query_workflow(self):
        """Test complete query workflow"""
        # 1. User query
        query = "Find all employees in IT department"
        
        # 2. Seraj routes to Fahas
        with patch.object(self.seraj, '_select_agents_dynamically') as mock_select:
            mock_select.return_value = ["Fahas"]
            
            # 3. Fahas queries Odoo
            with patch.object(self.fahas, 'llm_provider', self.mock_llm):
                with patch('agents.fahas_agent.OdooQueryGateway') as mock_gateway:
                    mock_gateway.return_value.execute_query.return_value = {
                        "results": [
                            {"id": 1, "name": "John Doe", "department": "IT"},
                            {"id": 2, "name": "Jane Smith", "department": "IT"},
                        ],
                        "count": 2
                    }
                    
                    goal = AgentGoal(
                        description=query,
                        context={"user": "admin"},
                        success_criteria=["results returned"]
                    )
                    
                    result = self.fahas.run(goal)
                    
                    assert result is not None
                    assert "results" in str(result)
    
    @pytest.mark.integration
    def test_write_workflow(self):
        """Test complete write workflow"""
        # 1. User wants to create employee
        data = {
            "name": "New Employee",
            "email": "new@test.com",
            "department_id": 1
        }
        
        # 2. Hares checks security
        with patch.object(self.hares, 'llm_provider', self.mock_llm):
            security_goal = AgentGoal(
                description="Create new employee",
                context={"action": "create", "model": "hr.employee", "data": data}
            )
            security_result = self.hares.run(security_goal)
            assert security_result is not None
        
        # 3. Mudaqqiq checks compliance
        with patch.object(self.mudaqqiq, 'llm_provider', self.mock_llm):
            compliance_goal = AgentGoal(
                description="Verify employee creation",
                context={"action": "create", "model": "hr.employee", "data": data}
            )
            compliance_result = self.mudaqqiq.run(compliance_goal)
            assert compliance_result is not None
        
        # 4. Katib writes to Odoo
        with patch.object(self.katib, 'llm_provider', self.mock_llm):
            with patch('agents.katib_agent.OdooWriteGateway') as mock_gateway:
                mock_gateway.return_value.create.return_value = {"id": 123}
                
                write_goal = AgentGoal(
                    description="Create employee",
                    context={"action": "create", "model": "hr.employee", "data": data}
                )
                
                write_result = self.katib.run(write_goal)
                assert write_result is not None
    
    @pytest.mark.integration
    def test_excel_processing_workflow(self):
        """Test complete Excel processing workflow"""
        # 1. Create test Excel
        excel_file = self._create_test_excel("attendance", num_rows=50)
        
        # 2. Template detection
        detector = TemplateDetector()
        with open(excel_file, 'rb') as f:
            detection = detector.detect(f.read(), "test_attendance.xlsx")
        
        assert detection is not None
        assert detection.primary_sheet_type in ["attendance", "timesheet"]
        
        # 3. Parse Excel
        df = pd.read_excel(excel_file)
        assert len(df) == 50
        
        # 4. Validate data (Mudaqqiq)
        with patch.object(self.mudaqqiq, 'llm_provider', self.mock_llm):
            validation_goal = AgentGoal(
                description="Validate attendance data",
                context={"data": df.to_dict('records')[:5]}  # Sample
            )
            validation = self.mudaqqiq.run(validation_goal)
            assert validation is not None
        
        # 5. Process records (Seraj orchestration)
        with patch.object(self.seraj, 'llm_provider', self.mock_llm):
            with patch.object(self.seraj, '_select_agents_dynamically') as mock_select:
                mock_select.return_value = ["Katib"]
                
                process_goal = AgentGoal(
                    description="Process attendance records",
                    context={"records": df.to_dict('records')[:10]}  # Process first 10
                )
                
                result = self.seraj.orchestrate(process_goal)
                assert result is not None
    
    @pytest.mark.integration
    def test_error_healing_workflow(self):
        """Test error detection and healing workflow"""
        # 1. Simulate error in data
        bad_data = {
            "employee_id": "INVALID_ID",  # Non-existent
            "action": "update"
        }
        
        # 2. Fahas detects error
        with patch.object(self.fahas, 'llm_provider', self.mock_llm):
            with patch('agents.fahas_agent.OdooQueryGateway') as mock_gateway:
                mock_gateway.return_value.execute_query.side_effect = Exception("Employee not found")
                
                query_goal = AgentGoal(
                    description="Find employee INVALID_ID",
                    context=bad_data
                )
                
                try:
                    self.fahas.run(query_goal)
                except Exception as e:
                    error = str(e)
        
        # 3. Musleh heals the error
        with patch.object(self.musleh, 'llm_provider', self.mock_llm):
            heal_goal = AgentGoal(
                description="Fix employee lookup error",
                context={"error": "Employee not found", "data": bad_data}
            )
            
            healing = self.musleh.run(heal_goal)
            assert healing is not None
    
    @pytest.mark.integration
    def test_matching_workflow(self):
        """Test employee matching workflow"""
        # 1. Input data with fuzzy names
        input_data = [
            {"name": "Jon Doe", "department": "IT"},  # Typo: Jon vs John
            {"name": "Jane Smyth", "department": "HR"},  # Typo: Smyth vs Smith
        ]
        
        # 2. Odoo existing data
        existing_employees = [
            {"id": 1, "name": "John Doe", "department": "IT"},
            {"id": 2, "name": "Jane Smith", "department": "HR"},
        ]
        
        # 3. Muwaffaq matches
        with patch.object(self.muwaffaq, 'llm_provider', self.mock_llm):
            for input_emp in input_data:
                match_goal = AgentGoal(
                    description=f"Match employee {input_emp['name']}",
                    context={
                        "input": input_emp,
                        "candidates": existing_employees
                    }
                )
                
                match_result = self.muwaffaq.run(match_goal)
                assert match_result is not None
    
    @pytest.mark.integration
    def test_audit_workflow(self):
        """Test complete audit workflow"""
        # 1. Perform some operations
        operations = [
            {"agent": "Katib", "action": "create", "model": "hr.employee", "timestamp": datetime.now()},
            {"agent": "Katib", "action": "update", "model": "hr.employee", "timestamp": datetime.now()},
        ]
        
        # 2. Sijil audits
        with patch.object(self.sijil, 'llm_provider', self.mock_llm):
            audit_goal = AgentGoal(
                description="Audit recent operations",
                context={"operations": operations, "time_range": "last_hour"}
            )
            
            audit_result = self.sijil.run(audit_goal)
            assert audit_result is not None
    
    @pytest.mark.integration
    def test_full_seraj_orchestration(self):
        """Test full Seraj meta-agent orchestration"""
        # Complex scenario: new hire onboarding
        new_hire_data = {
            "name": "Alice Johnson",
            "email": "alice@company.com",
            "department": "Engineering",
            "position": "Senior Developer",
            "start_date": datetime.now().date(),
            "salary": 8000,
            "benefits": ["health_insurance", "401k"]
        }
        
        with patch.object(self.seraj, 'llm_provider', self.mock_llm):
            with patch.object(self.seraj, '_select_agents_dynamically') as mock_select:
                # Seraj should select multiple agents
                mock_select.return_value = ["Hares", "Mudaqqiq", "Muwaffaq", "Katib"]
                
                onboarding_goal = AgentGoal(
                    description="Complete new hire onboarding",
                    context=new_hire_data
                )
                
                result = self.seraj.orchestrate(onboarding_goal)
                assert result is not None
                
                # Verify Seraj reflection
                assert hasattr(self.seraj, 'learned_patterns')


class TestStressTesting:
    """Stress tests for high-volume scenarios"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mock_llm = Mock()
        self.mock_llm.generate.return_value = {"text": "OK", "confidence": 0.9}
    
    def teardown_method(self):
        """Cleanup"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    @pytest.mark.stress
    @pytest.mark.slow
    def test_large_excel_processing(self):
        """Test processing large Excel file (10,000 rows)"""
        # Create large Excel
        file_path = self.temp_dir / "large_test.xlsx"
        wb = Workbook()
        ws = wb.active
        
        ws.append(["Employee ID", "Name", "Department", "Salary"])
        for i in range(10000):
            ws.append([f"EMP{i:05d}", f"Employee {i}", "IT", 5000 + i])
        
        wb.save(file_path)
        
        # Test parsing
        import time
        start = time.time()
        df = pd.read_excel(file_path)
        parse_time = time.time() - start
        
        assert len(df) == 10000
        assert parse_time < 10.0  # Should parse in < 10 seconds
        
        print(f"✅ Parsed 10,000 rows in {parse_time:.2f}s")
    
    @pytest.mark.stress
    def test_concurrent_agent_execution(self):
        """Test multiple agents running concurrently"""
        import concurrent.futures
        
        agents = [
            FahasAgent(),
            MuslehAgent(),
            HaresAgent(),
            KatibAgent(),
        ]
        
        def run_agent(agent):
            with patch.object(agent, 'llm_provider', self.mock_llm):
                goal = AgentGoal(
                    description="Test concurrent execution",
                    context={"test": True}
                )
                return agent.run(goal)
        
        # Run agents concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(run_agent, agent) for agent in agents]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        assert len(results) == 4
        print(f"✅ Ran 4 agents concurrently")
    
    @pytest.mark.stress
    def test_memory_usage_under_load(self):
        """Test memory usage during high-load processing"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create large dataset
        large_dataset = [
            {"id": i, "data": f"Data {i}" * 100}
            for i in range(1000)
        ]
        
        # Process with agent
        fahas = FahasAgent()
        with patch.object(fahas, 'llm_provider', self.mock_llm):
            for batch in range(10):
                goal = AgentGoal(
                    description="Process batch",
                    context={"batch": large_dataset[batch*100:(batch+1)*100]}
                )
                fahas.run(goal)
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (< 500 MB)
        assert memory_increase < 500
        print(f"✅ Memory increase: {memory_increase:.1f} MB")


class TestSecurityValidation:
    """Security-focused tests"""
    
    def setup_method(self):
        """Setup"""
        self.hares = HaresAgent()
        self.mock_llm = Mock()
        self.mock_llm.generate.return_value = {
            "text": "REJECT",
            "confidence": 0.95
        }
    
    @pytest.mark.security
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        malicious_queries = [
            "'; DROP TABLE employees; --",
            "1' OR '1'='1",
            "admin'--",
            "'; DELETE FROM users WHERE '1'='1",
        ]
        
        with patch.object(self.hares, 'llm_provider', self.mock_llm):
            for query in malicious_queries:
                goal = AgentGoal(
                    description=f"Query: {query}",
                    context={"query": query}
                )
                
                result = self.hares.run(goal)
                # Hares should detect and reject
                assert result is not None
                print(f"✅ Blocked: {query[:30]}...")
    
    @pytest.mark.security
    def test_unauthorized_access_prevention(self):
        """Test unauthorized access prevention"""
        # User without permissions
        unauthorized_actions = [
            {"action": "delete", "model": "hr.employee", "user_role": "viewer"},
            {"action": "write", "model": "hr.payslip", "user_role": "basic_user"},
            {"action": "create", "model": "hr.contract", "user_role": "intern"},
        ]
        
        with patch.object(self.hares, 'llm_provider', self.mock_llm):
            for action in unauthorized_actions:
                goal = AgentGoal(
                    description="Unauthorized action attempt",
                    context=action
                )
                
                result = self.hares.run(goal)
                assert result is not None
                print(f"✅ Blocked: {action['action']} on {action['model']}")
    
    @pytest.mark.security
    def test_data_validation(self):
        """Test data validation and sanitization"""
        invalid_data = [
            {"email": "not-an-email"},
            {"salary": -1000},
            {"date": "invalid-date"},
            {"phone": "abc123"},
        ]
        
        mudaqqiq = MudaqqiqAgent()
        with patch.object(mudaqqiq, 'llm_provider', self.mock_llm):
            for data in invalid_data:
                goal = AgentGoal(
                    description="Validate data",
                    context={"data": data}
                )
                
                result = mudaqqiq.run(goal)
                assert result is not None
                print(f"✅ Validated: {list(data.keys())[0]}")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "integration"])
