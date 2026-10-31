"""
اختبار سريع للوكلاء الجدد
============================
نقطة الدخول لتجربة الوكلاء الذكية الجديدة
"""
import os
import sys
from pathlib import Path

# إضافة المشروع للـ path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from agents.fahas_agent import FahasAgent, create_fahas_query_goal
from agents.tool_registry import ToolRegistry, register_all_tools


def test_fahas_simple():
    """اختبار بسيط لفاحص"""
    print("=" * 60)
    print("اختبار وكيل فاحص الذكي")
    print("=" * 60)
    
    # تسجيل الأدوات
    print("\n1. تسجيل الأدوات...")
    # register_all_tools()  # سنفعّله بعد التأكد
    
    # إنشاء الوكيل
    print("2. إنشاء وكيل فاحص...")
    fahas = FahasAgent()
    
    # إنشاء هدف
    print("3. إنشاء هدف استعلام...")
    goal = create_fahas_query_goal(
        "كم عدد الموظفين في النظام؟",
        context={"company_id": 15}
    )
    
    print(f"\nالهدف: {goal.objective}")
    print(f"القيود: {goal.constraints}")
    print(f"معايير النجاح: {goal.success_criteria}")
    
    # تشغيل الوكيل
    print("\n4. تشغيل الوكيل...")
    print("-" * 60)
    
    result = fahas.run(goal)
    
    print("-" * 60)
    print(f"\n5. النتيجة:")
    print(f"   الحالة: {result['status']}")
    print(f"   التكرارات: {result['iterations']}")
    print(f"   المدة: {result.get('duration_seconds', 0):.2f} ثانية")
    
    if result['status'] == 'success':
        reflection = result.get('reflection')
        if reflection:
            print(f"   الثقة: {reflection.confidence:.2%}")
            if reflection.issues:
                print(f"   المشاكل: {reflection.issues}")
    
    print("\n6. Trace Log:")
    for event in result.get('trace', []):
        print(f"   [{event['event']}] {event.get('data', {})}")
    
    print("\n" + "=" * 60)
    return result


def test_integration_with_langgraph():
    """اختبار التكامل مع LangGraph"""
    print("\n" + "=" * 60)
    print("اختبار التكامل مع LangGraph")
    print("=" * 60)
    
    try:
        from graph.build_graph import build_graph
        from langgraph.checkpoint.memory import MemorySaver
        
        print("\n1. بناء Graph مع checkpointer...")
        graph = build_graph(checkpointer=MemorySaver())
        
        print("2. اختبار استعلام عبر Graph...")
        result = graph.invoke(
            {
                "chat_id": "test_1",
                "user_query": "كم عدد الموظفين؟",
                "user_name": "مختبر",
            },
            config={"configurable": {"thread_id": "test_thread_1"}}
        )
        
        print(f"\nالإجابة: {result.get('answer', 'لا توجد إجابة')}")
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"❌ خطأ في التكامل: {e}")
        import traceback
        traceback.print_exc()


def main():
    """النقطة الرئيسية"""
    print("\n🚀 اختبار الوكلاء الذكية الجديدة\n")
    
    # تحقق من بيانات الاتصال
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("⚠️  تحذير: OPENROUTER_API_KEY غير موجود")
        print("   سيعمل الوكيل في وضع fallback\n")
    
    if not os.environ.get("ODOO_URL"):
        print("⚠️  تحذير: ODOO_URL غير موجود")
        print("   لن تعمل الاستعلامات الفعلية\n")
    
    # الاختبارات
    try:
        # 1. اختبار فاحص مباشرة
        result1 = test_fahas_simple()
        
        # 2. اختبار التكامل مع LangGraph
        # test_integration_with_langgraph()  # سنفعّله بعد التأكد
        
        print("\n✅ الاختبارات اكتملت!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  تم الإيقاف من المستخدم")
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
