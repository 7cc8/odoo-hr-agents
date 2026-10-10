"""
اختبارات وكيل التدقيق والامتثال: مدقق (Mudaqqiq Agentic Compliance Agent Tests)
================================================================================
"""

from agents.mudaqqiq_agent import (
    MudaqqiqAgent,
    ComplianceCategory,
    ComplianceStatus,
    ComplianceDecision,
    get_mudaqqiq_agent,
)


# ============================================================================
# Test Cases
# ============================================================================

def test_mudaqqiq_perceive_labor_law():
    """اختبار مرحلة الإدراك لقواعد نظام العمل"""
    print("\n" + "="*70)
    print("TEST 1: Perceive - Labor Law Compliance Check")
    print("="*70)
    
    agent = MudaqqiqAgent()
    
    # طلب التحقق من راتب موظف
    request = {
        "type": "salary_check",
        "category": ComplianceCategory.LABOR_LAW,
        "context": {"saudi_employee": True},
        "data": {
            "basic_salary": 5000,
            "employee_type": "saudi"
        }
    }
    
    perception = agent.perceive(request)
    
    # التحقق من النتائج
    assert perception["check_type"] == "salary_check"
    assert perception["category"] == ComplianceCategory.LABOR_LAW
    assert len(perception["applicable_rules"]) > 0
    assert perception["sensitivity_level"] in ["low", "medium", "high"]
    
    print(f"✅ Check Type: {perception['check_type']}")
    print(f"✅ Category: {perception['category']}")
    print(f"✅ Applicable Rules: {len(perception['applicable_rules'])}")
    print(f"✅ Sensitivity: {perception['sensitivity_level']}")
    print(f"✅ Legal Risks: {perception['legal_risks']}")
    print("\n✅ TEST PASSED: Perceive correctly analyzed labor law compliance")


def test_mudaqqiq_perceive_gosi():
    """اختبار مرحلة الإدراك لقواعد GOSI"""
    print("\n" + "="*70)
    print("TEST 2: Perceive - GOSI Compliance Check")
    print("="*70)
    
    agent = MudaqqiqAgent()
    
    # طلب التحقق من GOSI
    request = {
        "type": "gosi_check",
        "category": ComplianceCategory.GOSI,
        "context": {"gosi": True},
        "data": {
            "basic_salary": 10000,
            "gosi_contribution": 975,  # 9.75%
        }
    }
    
    perception = agent.perceive(request)
    
    # التحقق من وجود قواعد GOSI
    gosi_rules = [r for r in perception["applicable_rules"] if r.category == ComplianceCategory.GOSI]
    assert len(gosi_rules) > 0
    
    print(f"✅ Check Type: {perception['check_type']}")
    print(f"✅ GOSI Rules Found: {len(gosi_rules)}")
    print(f"✅ Sensitivity: {perception['sensitivity_level']}")
    
    for rule in gosi_rules:
        print(f"   - {rule.title_ar} ({rule.severity})")
    
    print("\n✅ TEST PASSED: GOSI rules identified correctly")


def test_mudaqqiq_plan_compliance_check():
    """اختبار مرحلة التخطيط"""
    print("\n" + "="*70)
    print("TEST 3: Plan - Compliance Verification Strategy")
    print("="*70)
    
    agent = MudaqqiqAgent()
    
    # إنشاء perception
    request = {
        "type": "full_check",
        "category": ComplianceCategory.GENERAL,
        "context": {},
        "data": {}
    }
    
    perception = agent.perceive(request)
    plan = agent.plan(perception)
    
    # التحقق من النتائج
    assert len(plan["verification_steps"]) > 0
    assert plan["expected_duration"] in ["short", "medium", "long"]
    assert len(plan["rules_to_check"]) > 0
    
    print(f"✅ Verification Steps: {len(plan['verification_steps'])}")
    print(f"✅ Expected Duration: {plan['expected_duration']}")
    print(f"✅ Rules to Check: {len(plan['rules_to_check'])}")
    
    # عرض أول 3 خطوات
    print("\n📋 First 3 Steps:")
    for i, step in enumerate(plan["verification_steps"][:3], 1):
        print(f"   {i}. {step['rule_title']} (priority: {step['priority']})")
    
    print("\n✅ TEST PASSED: Verification plan created successfully")


def test_mudaqqiq_execute_compliant():
    """اختبار تنفيذ فحص ممتثل"""
    print("\n" + "="*70)
    print("TEST 4: Execute - Compliant Data")
    print("="*70)
    
    agent = MudaqqiqAgent()
    
    # دورة كاملة: Perceive → Plan → Execute
    request = {
        "type": "salary_check",
        "category": ComplianceCategory.LABOR_LAW,
        "context": {"saudi_employee": True},
        "data": {
            "basic_salary": 5000,  # فوق الحد الأدنى
        }
    }
    
    perception = agent.perceive(request)
    plan = agent.plan(perception)
    result = agent.execute(plan)
    
    # التحقق من النتائج (حالياً كل الفحوصات passed)
    assert result["status"] == ComplianceStatus.COMPLIANT
    assert result["decision"] == ComplianceDecision.APPROVE
    assert result["passed_checks"] == result["total_checks"]
    assert len(result["violations"]) == 0
    
    print(f"✅ Status: {result['status']}")
    print(f"✅ Decision: {result['decision']}")
    print(f"✅ Passed Checks: {result['passed_checks']}/{result['total_checks']}")
    print(f"✅ Violations: {len(result['violations'])}")
    print(f"✅ Warnings: {len(result['warnings'])}")
    
    print("\n✅ TEST PASSED: Compliant data approved")


def test_mudaqqiq_reflect_successful():
    """اختبار مرحلة التأمل بعد فحص ناجح"""
    print("\n" + "="*70)
    print("TEST 5: Reflect - Successful Compliance Check")
    print("="*70)
    
    agent = MudaqqiqAgent()
    
    # دورة كاملة مع Reflection
    request = {
        "type": "contract_check",
        "category": ComplianceCategory.CONTRACTS,
        "context": {},
        "data": {
            "contract_duration_years": 3,  # ضمن الحدود
        }
    }
    
    perception = agent.perceive(request)
    plan = agent.plan(perception)
    result = agent.execute(plan)
    reflection = agent.reflect(perception, plan, result)
    
    # التحقق من النتائج
    assert len(reflection["decision_rationale_ar"]) > 0
    assert reflection["confidence_score"] > 0.8
    assert isinstance(reflection["lessons_learned"], list)
    
    print(f"✅ Decision Rationale: {reflection['decision_rationale_ar']}")
    print(f"✅ Confidence Score: {reflection['confidence_score']:.2f}")
    print(f"✅ Lessons Learned: {reflection['lessons_learned']}")
    print(f"✅ Legal Interpretation: {reflection['legal_interpretation_ar']}")
    
    print("\n✅ TEST PASSED: Reflection completed successfully")


def test_mudaqqiq_full_agentic_loop():
    """اختبار الدورة الذكية الكاملة"""
    print("\n" + "="*70)
    print("TEST 6: Full Agentic Loop (Perceive→Plan→Execute→Reflect)")
    print("="*70)
    
    agent = MudaqqiqAgent()
    
    # طلب فحص شامل
    request = {
        "type": "comprehensive_check",
        "category": ComplianceCategory.GENERAL,
        "context": {
            "gosi": True,
            "salary": True,
            "deduction": True,
        },
        "data": {
            "basic_salary": 8000,
            "gosi_contribution": 780,
            "total_deductions": 3500,
        }
    }
    
    # الدورة الكاملة
    print("\n🔍 Phase 1: PERCEIVE")
    perception = agent.perceive(request)
    print(f"   Applicable Rules: {len(perception['applicable_rules'])}")
    print(f"   Sensitivity: {perception['sensitivity_level']}")
    
    print("\n📋 Phase 2: PLAN")
    plan = agent.plan(perception)
    print(f"   Verification Steps: {len(plan['verification_steps'])}")
    print(f"   Expected Duration: {plan['expected_duration']}")
    
    print("\n⚡ Phase 3: EXECUTE")
    result = agent.execute(plan)
    print(f"   Status: {result['status']}")
    print(f"   Decision: {result['decision']}")
    print(f"   Passed: {result['passed_checks']}/{result['total_checks']}")
    
    print("\n🤔 Phase 4: REFLECT")
    reflection = agent.reflect(perception, plan, result)
    print(f"   Confidence: {reflection['confidence_score']:.2f}")
    print(f"   Rationale: {reflection['decision_rationale_ar'][0] if reflection['decision_rationale_ar'] else 'N/A'}")
    
    # التحقق النهائي
    assert perception["applicable_rules"] is not None
    assert plan["verification_steps"] is not None
    assert result["status"] is not None
    assert reflection["confidence_score"] > 0
    
    print("\n✅ TEST PASSED: Full Agentic Loop completed successfully")


def test_mudaqqiq_public_api():
    """اختبار الواجهة العامة verify_compliance"""
    print("\n" + "="*70)
    print("TEST 7: Public API (verify_compliance)")
    print("="*70)
    
    agent = MudaqqiqAgent()
    
    # استخدام الواجهة العامة
    request = {
        "type": "wps_check",
        "category": ComplianceCategory.WPS,
        "context": {"payment_date": "2026-10-05"},
        "data": {
            "salary_paid_date": "2026-10-05",
            "month_end": "2026-09-30"
        }
    }
    
    result = agent.verify_compliance(request)
    
    # التحقق من الواجهة
    assert "status" in result
    assert "decision" in result
    assert "confidence_score" in result
    assert "timestamp" in result
    
    print(f"✅ Status: {result['status']}")
    print(f"✅ Decision: {result['decision']}")
    print(f"✅ Confidence: {result['confidence_score']:.2f}")
    print(f"✅ Passed Checks: {result['passed_checks']}/{result['total_checks']}")
    print(f"✅ Has Rationale: {len(result['decision_rationale_ar']) > 0}")
    
    print("\n✅ TEST PASSED: Public API working correctly")


def test_mudaqqiq_rules_database():
    """اختبار قاعدة القواعد"""
    print("\n" + "="*70)
    print("TEST 8: Compliance Rules Database")
    print("="*70)
    
    agent = MudaqqiqAgent()
    
    # التحقق من وجود قواعد
    assert len(agent._rules_database) > 0
    
    print(f"✅ Total Rules: {len(agent._rules_database)}")
    
    # عد القواعد حسب الفئة
    categories_count = {}
    for rule in agent._rules_database:
        cat = rule.category
        categories_count[cat] = categories_count.get(cat, 0) + 1
    
    print("\n📊 Rules by Category:")
    for cat, count in categories_count.items():
        print(f"   - {cat}: {count} rules")
    
    # عد القواعد حسب الشدة
    severity_count = {}
    for rule in agent._rules_database:
        sev = rule.severity
        severity_count[sev] = severity_count.get(sev, 0) + 1
    
    print("\n📊 Rules by Severity:")
    for sev, count in severity_count.items():
        print(f"   - {sev}: {count} rules")
    
    print("\n✅ TEST PASSED: Rules database loaded correctly")


def test_mudaqqiq_singleton():
    """اختبار Singleton Factory"""
    print("\n" + "="*70)
    print("TEST 9: Singleton Factory Pattern")
    print("="*70)
    
    agent1 = get_mudaqqiq_agent()
    agent2 = get_mudaqqiq_agent()
    
    assert agent1 is agent2
    assert agent1.name == agent2.name
    assert len(agent1._rules_database) == len(agent2._rules_database)
    
    print(f"✅ Agent 1 Name: {agent1.name}")
    print(f"✅ Agent 2 Name: {agent2.name}")
    print(f"✅ Same Instance: {agent1 is agent2}")
    print(f"✅ Rules Count: {len(agent1._rules_database)}")
    
    print("\n✅ TEST PASSED: Singleton pattern working correctly")


def test_mudaqqiq_multiple_categories():
    """اختبار فحص متعدد الفئات"""
    print("\n" + "="*70)
    print("TEST 10: Multiple Categories Compliance Check")
    print("="*70)
    
    agent = MudaqqiqAgent()
    
    # طلب فحص يشمل عدة فئات
    request = {
        "type": "employee_full_check",
        "category": ComplianceCategory.GENERAL,
        "context": {
            "salary": True,
            "gosi": True,
            "deduction": True,
        },
        "data": {
            "basic_salary": 12000,
            "gosi_employee_contribution": 1170,  # 9.75%
            "total_monthly_deductions": 5000,  # 41.67% - ضمن الحدود
        }
    }
    
    result = agent.verify_compliance(request)
    
    # التحقق من شمولية الفحص
    assert result["total_checks"] > 5  # يجب فحص عدة قواعد
    assert result["status"] is not None
    
    print(f"✅ Total Checks Performed: {result['total_checks']}")
    print(f"✅ Passed Checks: {result['passed_checks']}")
    print(f"✅ Status: {result['status']}")
    print(f"✅ Decision: {result['decision']}")
    print(f"✅ Confidence: {result['confidence_score']:.2f}")
    
    print("\n✅ TEST PASSED: Multiple categories handled correctly")


# ============================================================================
# Run All Tests
# ============================================================================

def run_all_tests():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*70)
    print("MUDAQQIQ AGENT - AGENTIC AI TESTS")
    print("="*70)
    
    tests = [
        test_mudaqqiq_perceive_labor_law,
        test_mudaqqiq_perceive_gosi,
        test_mudaqqiq_plan_compliance_check,
        test_mudaqqiq_execute_compliant,
        test_mudaqqiq_reflect_successful,
        test_mudaqqiq_full_agentic_loop,
        test_mudaqqiq_public_api,
        test_mudaqqiq_rules_database,
        test_mudaqqiq_singleton,
        test_mudaqqiq_multiple_categories,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as exc:
            print(f"\n❌ TEST FAILED: {test_func.__name__}")
            print(f"   Error: {exc}")
            failed += 1
        except Exception as exc:
            print(f"\n❌ TEST ERROR: {test_func.__name__}")
            print(f"   Error: {exc}")
            failed += 1
    
    # النتيجة النهائية
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! MudaqqiqAgent is fully functional!")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review.")
    
    print("="*70)


if __name__ == "__main__":
    run_all_tests()
