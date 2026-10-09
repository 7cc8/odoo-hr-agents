"""Entry point for `langgraph dev` (the dev server supplies its own checkpointer)."""
from graph.build_graph import build_graph

graph = build_graph()
