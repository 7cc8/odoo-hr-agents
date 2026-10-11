"""Graph assembly.

read : ingest_user_message -> classify_intent -> seraj_think <-> fahas_tools -> finalize
write: prepare_plan -> policy_gate -> human_approval(interrupt) -> katib_execute
       -> fahas_verify -> sijil_log -> finalize_write
excel: parse_excel -> validate -> heal -> dry_run -> approval(interrupt) -> write -> verify -> log
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from graph import nodes as n
from graph import agentic_nodes as an
from graph import excel_nodes as en  # P4: Excel workflow nodes
from graph.state import SerajState


def build_graph(checkpointer=None):
    """
    بناء رسم سراج الرئيسي
    
    Args:
        checkpointer: MemorySaver أو SQLite للحفظ المستمر
                     ضروري للمحادثات الطويلة و human-in-the-loop
    """
    g = StateGraph(SerajState)

    # عقد القراءة (Read Path)
    g.add_node("ingest_user_message", n.ingest_user_message)
    g.add_node("classify_intent", n.classify_intent)
    g.add_node("seraj_meta_orchestration", an.seraj_meta_orchestration)  # ✅ جديد: Meta-Agent
    g.add_node("seraj_think", n.seraj_think)
    g.add_node("fahas_tools", n.fahas_tools)
    # fahas_agentic: حُذفت - نستخدم fahas_tools المُختبر فقط
    g.add_node("seraj_meta_reflect", an.seraj_meta_reflect)  # ✅ جديد: Meta-Agent Reflection
    g.add_node("finalize", n.finalize)

    # عقد الكتابة (Write Path)
    g.add_node("prepare_plan", n.prepare_plan)
    g.add_node("policy_gate", n.policy_gate)
    g.add_node("mudaqqiq_verify", an.mudaqqiq_agentic_verify)  # ✅ جديد: التحقق من الامتثال
    g.add_node("hares_guard", an.hares_agentic_guard)  # ✅ جديد: فحص الأمان
    g.add_node("human_approval", n.human_approval)
    g.add_node("katib_execute", n.katib_execute)  # ✅ عقدة katib واحدة فقط
    g.add_node("fahas_verify", n.fahas_verify)
    g.add_node("sijil_log", n.sijil_log)  # ✅ استخدام sijil_log المُختبر
    g.add_node("finalize_write", n.finalize_write)

    # عقد المعالجة (Processing Path)
    g.add_node("musleh_heal", an.musleh_agentic_heal)  # ✅ جديد: معالجة البيانات المرفوضة
    g.add_node("muwaffaq_match", an.muwaffaq_agentic_match)  # ✅ جديد: المطابقة الذكية

    # P4: عقد مسار Excel (Excel Workflow)
    g.add_node("parse_excel_file", en.parse_excel_file)
    g.add_node("validate_excel_rows", en.validate_excel_rows)
    g.add_node("heal_excel_batch", en.heal_excel_batch)
    g.add_node("generate_dry_run_report", en.generate_dry_run_report)
    g.add_node("create_excel_approval", en.create_excel_approval)

    # مسار القراءة
    g.add_edge(START, "ingest_user_message")
    g.add_conditional_edges("ingest_user_message", n.route_after_ingest, ["classify_intent", "finalize"])
    
    # ✅ جديد: بعد التصنيف، نذهب للـ Meta-Agent أولاً للتخطيط الذكي
    g.add_conditional_edges("classify_intent", n.route_intent, ["seraj_meta_orchestration", "prepare_plan"])
    
    # ✅ Meta-Agent يقرر ثم ننتقل لـ seraj_think
    g.add_edge("seraj_meta_orchestration", "seraj_think")

    g.add_conditional_edges("seraj_think", n.route_after_think, ["fahas_tools", "finalize"])
    g.add_edge("fahas_tools", "seraj_think")
    
    # ✅ جديد: بعد الانتهاء، نذهب للمراجعة الذكية
    g.add_edge("finalize", "seraj_meta_reflect")
    g.add_edge("seraj_meta_reflect", END)

    # مسار الكتابة المحسّن
    g.add_edge("prepare_plan", "mudaqqiq_verify")  # ✅ جديد: التحقق من الامتثال أولاً
    g.add_conditional_edges("mudaqqiq_verify", n.route_after_compliance, ["hares_guard", "musleh_heal", "finalize_write"])
    g.add_conditional_edges("hares_guard", n.route_after_security, ["policy_gate", "finalize_write"])  # ✅ إصلاح
    g.add_conditional_edges("policy_gate", n.route_after_policy, ["human_approval", "finalize_write"])
    # ✅ توحيد مسار الكتابة: عقدة katib واحدة فقط
    g.add_conditional_edges("human_approval", n.route_after_approval, ["katib_execute", "finalize_write"])
    g.add_edge("katib_execute", "fahas_verify")
    g.add_edge("fahas_verify", "sijil_log")
    g.add_edge("sijil_log", "finalize_write")
    
    # ✅ جديد: مسار الكتابة يذهب للمراجعة الذكية أيضاً
    g.add_edge("finalize_write", "seraj_meta_reflect")

    # مسار المعالجة
    g.add_edge("musleh_heal", "mudaqqiq_verify")  # ✅ بعد المعالجة، نعيد التحقق
    
    # مسار المطابقة (يمكن استدعاؤه من أي مكان)
    g.add_edge("muwaffaq_match", "seraj_think")  # ✅ بعد المطابقة، نعود لسراج

    # P4: مسار Excel
    # يمكن الدخول من classify_intent عند رفع ملف Excel
    g.add_conditional_edges("parse_excel_file", en.route_after_excel_parse, ["validate_excel_rows", "finalize"])
    g.add_conditional_edges("validate_excel_rows", en.route_after_validation, ["heal_excel_batch", "finalize"])
    g.add_conditional_edges("heal_excel_batch", en.route_after_healing, ["generate_dry_run_report"])
    g.add_conditional_edges("generate_dry_run_report", en.route_after_dry_run, ["create_excel_approval", "finalize"])
    g.add_conditional_edges("create_excel_approval", en.route_after_excel_approval, ["human_approval"])

    return g.compile(checkpointer=checkpointer)
