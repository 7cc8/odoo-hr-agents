"""Entry point for `langgraph dev` (the dev server supplies its own checkpointer)."""
from dotenv import load_dotenv
load_dotenv()  # ✅ تحميل .env قبل أي شيء

from graph.build_graph import build_graph

graph = build_graph()
