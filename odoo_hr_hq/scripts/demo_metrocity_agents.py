"""
تشغيل محاكاة حية للوكلاء الثمانية داخل مكتب MetroCity (pixel-agents)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.pixel_office_bridge import MetroCityBridge, METROCITY_AGENTS

def run_live_office_demo():
    bridge = MetroCityBridge()
    print(f"🏢 بث أحداث الوكلاء الثمانية إلى المسار:\n   {bridge.sessions_dir}\n")

    # 1. دخول جميع الوكلاء الثمانية إلى مكاتبهم
    for agent_id, info in METROCITY_AGENTS.items():
        print(f"🚶 دخول {info['name_ar']} إلى مكتبه...")
        bridge.spawn_agent(agent_id, f"بدء مناوبة العمل لـ {info['name_ar']}")
        time.sleep(0.4)

    # 2. تفعيل أنيميشن العمل بالتسلسل (سراج -> فاحص -> مدقق -> مصلح -> حارس -> كاتب -> سجل)
    workflow = [
        ("seraj",    "توزيع مهام فحص العقود وتصفية نهاية الخدمة على الفريق", "Task"),
        ("fahas",    "استعلام Odoo عن العقود النشطة للموظف #104", "Grep"),
        ("mudaqqiq", "تدقيق حساب نهاية الخدمة وفق المادة 85 من نظام العمل", "Read"),
        ("musleh",   "تنظيف تواريخ المباشرة في قالب الإكسل (Dry-Run)", "Edit"),
        ("muwaffaq", "مطابقة المسميات الوظيفية والأقسام بنسبة 96%", "Glob"),
        ("hares",    "فحص صلاحيات الكتابة وطلب موافقة المالك (Needs you)", "Bash"),
        ("katib",    "الاستعداد لكتابة تسوية نهاية الخدمة في Odoo", "Write"),
        ("sijil",    "توثيق التقارير ذات الـ 5 أسطر وحساب نقاط XP", "Read"),
    ]

    active_tools = {}
    for agent_id, desc, tool in workflow:
        print(f"⌨️  {METROCITY_AGENTS[agent_id]['name_ar']} يعمل الآن: {desc}")
        active_tools[agent_id] = bridge.start_working(agent_id, desc, tool_override=tool)
        time.sleep(1.5)

    print("\n⏳ الوكلاء الثمانية يكتبون ويعملون الآن في المكتب لمدة 10 ثوانٍ...")
    time.sleep(10)

    # 3. إنهاء المهام لكل الوكلاء ما عدا (حارس وكاتب) يبقيان بانتظار موافقة المالك
    for agent_id, tool_id in active_tools.items():
        if agent_id in ("hares", "katib"):
            print(f"⚠️  {METROCITY_AGENTS[agent_id]['name_ar']} بقي في حالة انتظار موافقة المالك (Needs you)!")
            continue
        bridge.finish_working(agent_id, tool_id, "تم إنجاز المهمة وإرسال التقرير لسراج")
        print(f"✅ أنهى {METROCITY_AGENTS[agent_id]['name_ar']} مهمته وأخذ استراحة.")
        time.sleep(0.5)

if __name__ == "__main__":
    run_live_office_demo()
