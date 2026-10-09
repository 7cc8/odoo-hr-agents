"""Graph assembly.

read : ingest_user_message -> classify_intent -> seraj_think <-> fahas_tools -> finalize
write: prepare_plan -> policy_gate -> human_approval(interrupt) -> katib_execute
       -> fahas_verify -> sijil_log -> finalize_write
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from graph import nodes as n
from graph.state import SerajState


def build_graph(checkpointer=None):
    g = StateGraph(SerajState)

    g.add_node("ingest_user_message", n.ingest_user_message)
    g.add_node("classify_intent", n.classify_intent)
    g.add_node("seraj_think", n.seraj_think)
    g.add_node("fahas_tools", n.fahas_tools)
    g.add_node("finalize", n.finalize)

    g.add_node("prepare_plan", n.prepare_plan)
    g.add_node("policy_gate", n.policy_gate)
    g.add_node("human_approval", n.human_approval)
    g.add_node("katib_execute", n.katib_execute)
    g.add_node("fahas_verify", n.fahas_verify)
    g.add_node("sijil_log", n.sijil_log)
    g.add_node("finalize_write", n.finalize_write)

    g.add_edge(START, "ingest_user_message")
    g.add_conditional_edges("ingest_user_message", n.route_after_ingest, ["classify_intent", "finalize"])
    g.add_conditional_edges("classify_intent", n.route_intent, ["seraj_think", "prepare_plan"])

    g.add_conditional_edges("seraj_think", n.route_after_think, ["fahas_tools", "finalize"])
    g.add_edge("fahas_tools", "seraj_think")
    g.add_edge("finalize", END)

    g.add_edge("prepare_plan", "policy_gate")
    g.add_conditional_edges("policy_gate", n.route_after_policy, ["human_approval", "finalize_write"])
    g.add_conditional_edges("human_approval", n.route_after_approval, ["katib_execute", "finalize_write"])
    g.add_edge("katib_execute", "fahas_verify")
    g.add_edge("fahas_verify", "sijil_log")
    g.add_edge("sijil_log", "finalize_write")
    g.add_edge("finalize_write", END)

    return g.compile(checkpointer=checkpointer)
