"""
اختبارات الوكلاء الذكية الجديدة
================================
"""
import unittest
from agents.base_agent import create_agent_goal
from agents.fahas_agent import FahasAgent, create_fahas_query_goal


class TestFahasAgent(unittest.TestCase):
    """اختبارات وكيل فاحص الذكي"""
    
    def setUp(self):
        self.agent = FahasAgent()
    
    def test_perceive_simple_query(self):
        """اختبار: فهم استعلام بسيط"""
        goal = create_fahas_query_goal("كم عدد الموظفين؟")
        perception = self.agent.perceive(goal)
        
        self.assertIn("operation", perception)
        self.assertEqual(perception["operation"], "count")
        self.assertEqual(perception["model"], "hr.employee")
    
    def test_perceive_complex_query(self):
        """اختبار: فهم استعلام معقد"""
        goal = create_fahas_query_goal("أعطني أسماء الموظفين في قسم المبيعات")
        perception = self.agent.perceive(goal)
        
        self.assertEqual(perception["operation"], "search")
        self.assertIn("domain", perception)
        self.assertIn("fields", perception)
    
    def test_plan_single_step(self):
        """اختبار: خطة بسيطة"""
        goal = create_fahas_query_goal("عدد الموظفين")
        perception = {"operation": "count", "model": "hr.employee"}
        plan = self.agent.plan(goal, perception)
        
        self.assertGreater(len(plan.steps), 0)
        self.assertEqual(plan.steps[0]["action"], "query")
    
    def test_full_run_count(self):
        """اختبار: تشغيل كامل لاستعلام count"""
        goal = create_fahas_query_goal("كم موظف عندنا؟")
        result = self.agent.run(goal)
        
        # يجب أن ينجح أو يفشل بشكل واضح
        self.assertIn(result["status"], ["success", "failed", "error"])
        
        if result["status"] == "success":
            self.assertIn("result", result)
            self.assertIn("reflection", result)
    
    def test_reflection_on_empty_results(self):
        """اختبار: التأمل عند عدم وجود نتائج"""
        goal = create_fahas_query_goal("موظف غير موجود")
        # محاكاة تنفيذ فاشل
        plan = self.agent.plan(goal, {"operation": "search", "model": "hr.employee"})
        result = {"status": "no_results", "data": []}
        
        reflection = self.agent.reflect(goal, plan, result)
        
        # يجب أن يقترح إعادة المحاولة
        self.assertTrue(reflection.should_retry or not reflection.success)
    
    def test_memory_working(self):
        """اختبار: ذاكرة العمل"""
        self.agent.memory.add_to_working({"test": "data"})
        context = self.agent.memory.get_context_window(limit=1)
        
        self.assertEqual(len(context), 1)
        self.assertEqual(context[0]["test"], "data")
    
    def test_memory_episodic(self):
        """اختبار: الذاكرة الطويلة"""
        self.agent.memory.add_episode({
            "query": "test query",
            "result": "test result",
        })
        
        self.assertEqual(len(self.agent.memory.episodic_memory), 1)


class TestBaseAgent(unittest.TestCase):
    """اختبارات الفئة الأساسية"""
    
    def test_agent_goal_creation(self):
        """اختبار: إنشاء هدف"""
        goal = create_agent_goal(
            objective="Test objective",
            constraints=["constraint1"],
            success_criteria=["success1"],
        )
        
        self.assertEqual(goal.objective, "Test objective")
        self.assertEqual(len(goal.constraints), 1)
        self.assertEqual(goal.max_iterations, 10)


# TODO: إضافة اختبارات لبقية الوكلاء


if __name__ == "__main__":
    unittest.main()
