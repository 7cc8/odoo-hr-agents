"""Entry point for `langgraph dev` (the dev server supplies its own checkpointer)."""
from dotenv import load_dotenv
load_dotenv()  # ✅ تحميل .env قبل أي شيء

from graph.build_graph import build_graph

# P3: When running with langgraph dev, persistence is handled by the platform
# Do not pass a custom checkpointer - it will be ignored
graph = build_graph(checkpointer=None)
