"""
مقارنة فعلية: Service القديم vs Agent الجديد
يشغل نفس الأسئلة على النظامين ويقارن النتائج
"""

import time
import sys
from typing import Dict, Any, List, Tuple
from datetime import datetime

# القديم
from fahas_service import FahasAgent as FahasService

# الجديد
from agents.fahas_agent import FahasAgent, create_fahas_query_goal
from agents.base_agent import AgentGoal


class ComparisonRunner:
    """مشغل المقارنة"""
    
    def __init__(self):
        # النظام القديم
        self.old_fahas = FahasService()
        
        # النظام الجديد
        self.new_fahas = FahasAgent()
    
    def run_old_system(self, query: str, context: Dict = None) -> Dict[str, Any]:
        """تشغيل النظام القديم"""
        print(f"\n{'='*80}")
        print(f"🔵 OLD SYSTEM: {query}")
        print(f"{'='*80}")
        
        start_time = time.time()
        llm_calls = 0
        
        try:
            # النظام القديم يحتاج task_type محدد
            # دعني أحاول تحويل السؤال إلى task
            
            if "شركات" in query and "المتاحة" in query:
                task_type = "list_companies"
                params = {}
            elif "عدد الموظفين" in query:
                task_type = "count_employees"
                params = {}
                
                # استخراج اسم الشركة إن وجد
                if "النخبة" in query:
                    params["company_filter"] = "النخبة"
                elif "كل الشركات" in query or "النظام ككل" in query:
                    params["all_companies"] = True
            elif "وزع" in query or "وزّع" in query:
                task_type = "distribute_employees"
                params = {}
            else:
                task_type = "search_employees"
                params = {}
            
            print(f"Task Type: {task_type}")
            print(f"Params: {params}")
            
            # تنفيذ
            result = self.old_fahas.execute_query_task(task_type, params)
            
            duration = time.time() - start_time
            
            print(f"\n📤 Result:")
            print(result)
            print(f"\n⏱️  Time: {duration:.2f}s")
            print(f"🔢 LLM Calls: {llm_calls} (Service لا يستخدم LLM)")
            
            return {
                "result": result,
                "llm_calls": llm_calls,
                "duration": duration,
                "success": True,
            }
        
        except Exception as e:
            duration = time.time() - start_time
            print(f"\n❌ Error: {e}")
            print(f"⏱️  Time: {duration:.2f}s")
            
            return {
                "result": None,
                "error": str(e),
                "llm_calls": llm_calls,
                "duration": duration,
                "success": False,
            }
    
    def run_new_system(self, query: str, context: Dict = None) -> Dict[str, Any]:
        """تشغيل النظام الجديد"""
        print(f"\n{'='*80}")
        print(f"🟢 NEW SYSTEM (Agent): {query}")
        print(f"{'='*80}")
        
        start_time = time.time()
        
        # عد استدعاءات LLM
        original_call_llm = self.new_fahas._call_llm
        llm_calls = [0]  # استخدام list للتعديل في nested function
        
        def counting_call_llm(*args, **kwargs):
            llm_calls[0] += 1
            print(f"  📞 LLM Call #{llm_calls[0]}")
            return original_call_llm(*args, **kwargs)
        
        self.new_fahas._call_llm = counting_call_llm
        
        try:
            # إنشاء الهدف
            goal = create_fahas_query_goal(query, context or {})
            
            print(f"Goal: {goal.objective}")
            
            # تشغيل الوكيل
            result = self.new_fahas.run(goal)
            
            duration = time.time() - start_time
            
            print(f"\n📤 Result:")
            print(result)
            print(f"\n⏱️  Time: {duration:.2f}s")
            print(f"🔢 LLM Calls: {llm_calls[0]}")
            print(f"🔄 Iterations: {self.new_fahas.iteration_count}")
            
            # استعادة الدالة الأصلية
            self.new_fahas._call_llm = original_call_llm
            
            return {
                "result": result,
                "llm_calls": llm_calls[0],
                "iterations": self.new_fahas.iteration_count,
                "duration": duration,
                "success": True,
            }
        
        except Exception as e:
            duration = time.time() - start_time
            print(f"\n❌ Error: {e}")
            print(f"⏱️  Time: {duration:.2f}s")
            print(f"🔢 LLM Calls: {llm_calls[0]}")
            
            # استعادة الدالة الأصلية
            self.new_fahas._call_llm = original_call_llm
            
            return {
                "result": None,
                "error": str(e),
                "llm_calls": llm_calls[0],
                "duration": duration,
                "success": False,
            }
    
    def run_comparison(self, questions: List[str]) -> List[Dict]:
        """تشغيل المقارنة الكاملة"""
        results = []
        
        print("\n" + "="*80)
        print("🔬 COMPARISON TEST: Old Service vs New Agent")
        print("="*80)
        print(f"Questions: {len(questions)}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        for i, question in enumerate(questions, 1):
            print(f"\n\n{'#'*80}")
            print(f"# Question {i}/{len(questions)}: {question}")
            print(f"{'#'*80}")
            
            # تشغيل القديم
            old_result = self.run_old_system(question)
            
            # تشغيل الجديد
            new_result = self.run_new_system(question)
            
            # المقارنة
            comparison = {
                "question": question,
                "old": old_result,
                "new": new_result,
                "speedup": old_result["duration"] / new_result["duration"] if new_result["duration"] > 0 else 0,
            }
            
            results.append(comparison)
            
            # ملخص
            print(f"\n{'─'*80}")
            print(f"📊 COMPARISON SUMMARY:")
            print(f"  Old: {old_result['duration']:.2f}s, {old_result['llm_calls']} LLM calls")
            print(f"  New: {new_result['duration']:.2f}s, {new_result['llm_calls']} LLM calls, {new_result.get('iterations', 0)} iterations")
            print(f"  Speed: {'Old' if comparison['speedup'] > 1 else 'New'} is {abs(comparison['speedup']):.1f}x faster")
            print(f"{'─'*80}")
        
        return results
    
    def print_final_report(self, results: List[Dict]):
        """طباعة التقرير النهائي"""
        print(f"\n\n{'='*80}")
        print("📋 FINAL REPORT")
        print(f"{'='*80}")
        
        total_old_time = sum(r["old"]["duration"] for r in results)
        total_new_time = sum(r["new"]["duration"] for r in results)
        total_old_llm = sum(r["old"]["llm_calls"] for r in results)
        total_new_llm = sum(r["new"]["llm_calls"] for r in results)
        
        print(f"\nTotal Time:")
        print(f"  Old System: {total_old_time:.2f}s")
        print(f"  New System: {total_new_time:.2f}s")
        print(f"  Difference: {abs(total_old_time - total_new_time):.2f}s")
        
        print(f"\nTotal LLM Calls:")
        print(f"  Old System: {total_old_llm}")
        print(f"  New System: {total_new_llm}")
        
        print(f"\nSuccess Rate:")
        old_success = sum(1 for r in results if r["old"]["success"]) / len(results) * 100
        new_success = sum(1 for r in results if r["new"]["success"]) / len(results) * 100
        print(f"  Old System: {old_success:.0f}%")
        print(f"  New System: {new_success:.0f}%")
        
        print(f"\nPer-Question Breakdown:")
        print(f"{'─'*80}")
        print(f"{'#':<3} {'Question':<40} {'Old (s)':<10} {'New (s)':<10} {'LLM Δ':<8}")
        print(f"{'─'*80}")
        
        for i, r in enumerate(results, 1):
            q_short = r["question"][:37] + "..." if len(r["question"]) > 40 else r["question"]
            old_time = r["old"]["duration"]
            new_time = r["new"]["duration"]
            llm_delta = r["new"]["llm_calls"] - r["old"]["llm_calls"]
            
            print(f"{i:<3} {q_short:<40} {old_time:<10.2f} {new_time:<10.2f} +{llm_delta:<7}")
        
        print(f"{'─'*80}")


def main():
    """النقطة الرئيسية"""
    
    # الأسئلة المطلوبة
    questions = [
        "ما الشركات المتاحة لي؟",
        "كم عدد الموظفين في شركة النخبة الذكية؟",
        "كم عدد الموظفين؟",
        "والشركة الثانية؟",
        "كم عدد الموظفين في كل الشركات؟",
        "كم عدد الموظفين في النظام ككل؟",
        "وزّع الموظفين على الشركات",
    ]
    
    runner = ComparisonRunner()
    results = runner.run_comparison(questions)
    runner.print_final_report(results)
    
    # الأسئلة المطلوبة
    print(f"\n\n{'='*80}")
    print("❓ ANSWERS TO SPECIFIC QUESTIONS")
    print(f"{'='*80}")
    
    print("\n1. هل وقع خطأ «الفرق بين 13 و14 يعني أن الشركات الأخرى فارغة»?")
    print("   → سيظهر من النتائج الفعلية")
    
    print("\n2. هل تجاوز أي سؤال حد الخطوات؟")
    max_iterations = max(r["new"].get("iterations", 0) for r in results)
    print(f"   → Max iterations: {max_iterations}")
    
    print("\n3. هل run() في fahas_agent يستدعي fahas_service تحته أم يستبدله؟")
    print("   → يستبدله - Agent جديد تماماً، لا يستدعي Service")
    
    print("\n4. كم استدعاء نموذج لكل سؤال، وما الزمن الكلي؟")
    print("   → انظر الجدول أعلاه")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
