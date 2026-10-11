"""Entry point for `langgraph dev` (the dev server supplies its own checkpointer)."""
from dotenv import load_dotenv
load_dotenv()  # ✅ تحميل .env قبل أي شيء

from graph.build_graph import build_graph
from graph.checkpointer import get_checkpointer_for_environment

# P3: persistent checkpointer for durable state management
checkpointer = get_checkpointer_for_environment()
graph = build_graph(checkpointer=checkpointer)
