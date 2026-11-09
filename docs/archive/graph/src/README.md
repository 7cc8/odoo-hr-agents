# Seraj LangGraph skeleton

Additive only: no legacy file is modified. The legacy `SerajLLMService.chat_turn` keeps working.

## Install (separate venv recommended)
```
pip install -r requirements-langgraph.txt
```

## Run in Studio
```
langgraph dev
```

## Run from Python
```python
from langgraph.checkpoint.memory import MemorySaver
from graph.build_graph import build_graph

g = build_graph(MemorySaver())
out = g.invoke(
    {"chat_id": "t1", "user_query": "كم عدد الموظفين؟"},
    config={"configurable": {"thread_id": "t1"}},
)
print(out["answer"])
```

## Phases
- Phase 1 (this branch): read path only, same behaviour as `_run_tool_calling_loop` (max 5 turns).
- Phase 3: structured intent classification, unified Plan, real policy_gate/katib/verify/sijil.
- Write path is OFF unless `ENABLE_WRITE_PATH=1`, and its nodes are stubs.

## Rules
- The LLM never gets a write tool.
- Writes only in `katib_execute`, after `policy_gate` and `human_approval`.
- Approval must match the same `plan_id`.
