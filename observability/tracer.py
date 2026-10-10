"""
Agent Tracing System
Provides comprehensive tracing for agent execution with LangSmith integration.
"""

import json
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class SpanType(str, Enum):
    """Types of trace spans"""
    AGENT_RUN = "agent_run"
    PERCEIVE = "perceive"
    PLAN = "plan"
    EXECUTE = "execute"
    REFLECT = "reflect"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    MEMORY_ACCESS = "memory_access"


class SpanStatus(str, Enum):
    """Status of a span"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PENDING = "pending"


@dataclass
class Span:
    """A single trace span"""
    span_id: str
    parent_id: Optional[str]
    trace_id: str
    agent_name: str
    span_type: SpanType
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: SpanStatus = SpanStatus.PENDING
    
    # Input/Output
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # Metrics
    token_usage: Optional[Dict[str, int]] = None
    confidence: Optional[float] = None
    
    def finish(self, status: SpanStatus = SpanStatus.SUCCESS, error: Optional[str] = None):
        """Finish the span"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        if error:
            self.error = error
            self.status = SpanStatus.ERROR
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert enums to strings
        data["span_type"] = self.span_type.value
        data["status"] = self.status.value
        return data


@dataclass
class Trace:
    """A complete trace for an agent execution"""
    trace_id: str
    session_id: Optional[str]
    root_agent: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: SpanStatus = SpanStatus.PENDING
    
    # Spans
    spans: List[Span] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # Results
    success: bool = False
    error: Optional[str] = None
    
    def add_span(self, span: Span):
        """Add a span to the trace"""
        self.spans.append(span)
    
    def finish(self, success: bool = True, error: Optional[str] = None):
        """Finish the trace"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error = error
        self.status = SpanStatus.SUCCESS if success else SpanStatus.ERROR
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "root_agent": self.root_agent,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "spans": [span.to_dict() for span in self.spans],
            "metadata": self.metadata,
            "tags": self.tags,
            "success": self.success,
            "error": self.error,
        }
    
    def get_span_tree(self) -> Dict[str, Any]:
        """Get hierarchical span tree"""
        # Build a map of span_id -> span
        span_map = {span.span_id: span for span in self.spans}
        
        # Find root spans (no parent)
        root_spans = [span for span in self.spans if not span.parent_id]
        
        def build_tree(span: Span) -> Dict[str, Any]:
            children = [s for s in self.spans if s.parent_id == span.span_id]
            return {
                "span": span.to_dict(),
                "children": [build_tree(child) for child in children]
            }
        
        return {
            "trace_id": self.trace_id,
            "root_spans": [build_tree(span) for span in root_spans]
        }


class TracingContext:
    """Context for nested tracing"""
    
    def __init__(
        self,
        tracer: "AgentTracer",
        agent_name: str,
        span_type: SpanType,
        parent_span: Optional[Span] = None,
        inputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ):
        self.tracer = tracer
        self.agent_name = agent_name
        self.span_type = span_type
        self.parent_span = parent_span
        self.inputs = inputs or {}
        self.metadata = metadata or {}
        self.tags = tags or []
        self.span: Optional[Span] = None
    
    def __enter__(self) -> Span:
        """Start the span"""
        self.span = self.tracer.start_span(
            agent_name=self.agent_name,
            span_type=self.span_type,
            parent_span=self.parent_span,
            inputs=self.inputs,
            metadata=self.metadata,
            tags=self.tags,
        )
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End the span"""
        if exc_type:
            self.tracer.end_span(
                self.span,
                status=SpanStatus.ERROR,
                error=str(exc_val)
            )
            return False  # Re-raise exception
        else:
            self.tracer.end_span(self.span, status=SpanStatus.SUCCESS)
            return True


class AgentTracer:
    """
    Agent Tracing System
    
    Provides comprehensive tracing for agent execution:
    - Hierarchical spans (perceive -> plan -> execute -> reflect)
    - LangSmith integration
    - Local trace storage
    - Performance metrics
    - Error tracking
    """
    
    def __init__(
        self,
        output_dir: str = "traces",
        enable_langsmith: bool = False,
        langsmith_api_key: Optional[str] = None,
        langsmith_project: Optional[str] = None,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Current trace
        self.current_trace: Optional[Trace] = None
        self.current_span: Optional[Span] = None
        
        # Trace stack for nested contexts
        self.span_stack: List[Span] = []
        
        # LangSmith config
        self.enable_langsmith = enable_langsmith
        self.langsmith_api_key = langsmith_api_key
        self.langsmith_project = langsmith_project
        
        if self.enable_langsmith:
            self._init_langsmith()
    
    def _init_langsmith(self):
        """Initialize LangSmith integration"""
        try:
            import os
            if self.langsmith_api_key:
                os.environ["LANGCHAIN_API_KEY"] = self.langsmith_api_key
            if self.langsmith_project:
                os.environ["LANGCHAIN_PROJECT"] = self.langsmith_project
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            
            print(f"✅ LangSmith tracing enabled (project: {self.langsmith_project})")
        except Exception as e:
            print(f"⚠️ Failed to initialize LangSmith: {e}")
            self.enable_langsmith = False
    
    def start_trace(
        self,
        agent_name: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Trace:
        """Start a new trace"""
        trace = Trace(
            trace_id=str(uuid.uuid4()),
            session_id=session_id,
            root_agent=agent_name,
            start_time=time.time(),
            metadata=metadata or {},
            tags=tags or [],
        )
        self.current_trace = trace
        return trace
    
    def start_span(
        self,
        agent_name: str,
        span_type: SpanType,
        parent_span: Optional[Span] = None,
        inputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Span:
        """Start a new span"""
        if not self.current_trace:
            # Auto-create trace if not exists
            self.start_trace(agent_name=agent_name)
        
        # Use current span as parent if not specified
        if parent_span is None and self.span_stack:
            parent_span = self.span_stack[-1]
        
        span = Span(
            span_id=str(uuid.uuid4()),
            parent_id=parent_span.span_id if parent_span else None,
            trace_id=self.current_trace.trace_id,
            agent_name=agent_name,
            span_type=span_type,
            start_time=time.time(),
            inputs=inputs or {},
            metadata=metadata or {},
            tags=tags or [],
        )
        
        self.current_trace.add_span(span)
        self.span_stack.append(span)
        self.current_span = span
        
        return span
    
    def end_span(
        self,
        span: Span,
        status: SpanStatus = SpanStatus.SUCCESS,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None,
        confidence: Optional[float] = None,
    ):
        """End a span"""
        span.finish(status=status, error=error)
        
        if outputs:
            span.outputs = outputs
        if token_usage:
            span.token_usage = token_usage
        if confidence is not None:
            span.confidence = confidence
        
        # Pop from stack
        if self.span_stack and self.span_stack[-1].span_id == span.span_id:
            self.span_stack.pop()
        
        # Update current span
        self.current_span = self.span_stack[-1] if self.span_stack else None
    
    def end_trace(
        self,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """End the current trace"""
        if not self.current_trace:
            return
        
        self.current_trace.finish(success=success, error=error)
        
        # Save trace
        self._save_trace(self.current_trace)
        
        # Send to LangSmith if enabled
        if self.enable_langsmith:
            self._send_to_langsmith(self.current_trace)
        
        # Clear current trace
        self.current_trace = None
        self.current_span = None
        self.span_stack.clear()
    
    @contextmanager
    def trace(
        self,
        agent_name: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ):
        """Context manager for full trace"""
        trace = self.start_trace(
            agent_name=agent_name,
            session_id=session_id,
            metadata=metadata,
            tags=tags,
        )
        try:
            yield trace
            self.end_trace(success=True)
        except Exception as e:
            self.end_trace(success=False, error=str(e))
            raise
    
    @contextmanager
    def span(
        self,
        agent_name: str,
        span_type: SpanType,
        parent_span: Optional[Span] = None,
        inputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ):
        """Context manager for span"""
        ctx = TracingContext(
            tracer=self,
            agent_name=agent_name,
            span_type=span_type,
            parent_span=parent_span,
            inputs=inputs,
            metadata=metadata,
            tags=tags,
        )
        with ctx as span:
            yield span
    
    def _save_trace(self, trace: Trace):
        """Save trace to local storage"""
        try:
            # Save as JSONL (one line per trace)
            traces_file = self.output_dir / "traces.jsonl"
            with open(traces_file, "a", encoding="utf-8") as f:
                json.dump(trace.to_dict(), f)
                f.write("\n")
            
            # Also save individual trace as JSON for easy viewing
            trace_file = self.output_dir / f"trace_{trace.trace_id}.json"
            with open(trace_file, "w", encoding="utf-8") as f:
                json.dump(trace.to_dict(), f, indent=2)
            
            # Save span tree
            tree_file = self.output_dir / f"tree_{trace.trace_id}.json"
            with open(tree_file, "w", encoding="utf-8") as f:
                json.dump(trace.get_span_tree(), f, indent=2)
            
            print(f"📝 Trace saved: {trace.trace_id} ({trace.duration_ms:.1f}ms)")
        
        except Exception as e:
            print(f"⚠️ Failed to save trace: {e}")
    
    def _send_to_langsmith(self, trace: Trace):
        """Send trace to LangSmith"""
        try:
            # LangSmith integration happens automatically via environment variables
            # when using LangChain's tracing decorators
            # This is a placeholder for custom implementation if needed
            pass
        except Exception as e:
            print(f"⚠️ Failed to send to LangSmith: {e}")
    
    def get_traces(
        self,
        agent_name: Optional[str] = None,
        status: Optional[SpanStatus] = None,
        limit: int = 100,
    ) -> List[Trace]:
        """Load traces from storage"""
        traces = []
        traces_file = self.output_dir / "traces.jsonl"
        
        if not traces_file.exists():
            return traces
        
        try:
            with open(traces_file, "r", encoding="utf-8") as f:
                for line in f:
                    trace_dict = json.loads(line)
                    
                    # Filter by agent_name
                    if agent_name and trace_dict["root_agent"] != agent_name:
                        continue
                    
                    # Filter by status
                    if status and trace_dict["status"] != status.value:
                        continue
                    
                    traces.append(trace_dict)
                    
                    if len(traces) >= limit:
                        break
        
        except Exception as e:
            print(f"⚠️ Failed to load traces: {e}")
        
        return traces
    
    def get_trace_summary(self) -> Dict[str, Any]:
        """Get summary of all traces"""
        traces = self.get_traces(limit=10000)
        
        if not traces:
            return {
                "total_traces": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
            }
        
        total = len(traces)
        successes = sum(1 for t in traces if t["success"])
        total_duration = sum(t["duration_ms"] for t in traces if t["duration_ms"])
        
        # Agent breakdown
        agents = {}
        for trace in traces:
            agent = trace["root_agent"]
            if agent not in agents:
                agents[agent] = {"count": 0, "successes": 0, "total_duration": 0}
            agents[agent]["count"] += 1
            if trace["success"]:
                agents[agent]["successes"] += 1
            if trace["duration_ms"]:
                agents[agent]["total_duration"] += trace["duration_ms"]
        
        return {
            "total_traces": total,
            "success_rate": successes / total if total > 0 else 0.0,
            "avg_duration_ms": total_duration / total if total > 0 else 0.0,
            "agents": {
                name: {
                    "count": stats["count"],
                    "success_rate": stats["successes"] / stats["count"] if stats["count"] > 0 else 0.0,
                    "avg_duration_ms": stats["total_duration"] / stats["count"] if stats["count"] > 0 else 0.0,
                }
                for name, stats in agents.items()
            }
        }


# Global tracer instance
_global_tracer: Optional[AgentTracer] = None


def get_tracer() -> AgentTracer:
    """Get global tracer instance"""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = AgentTracer()
    return _global_tracer


def set_tracer(tracer: AgentTracer):
    """Set global tracer instance"""
    global _global_tracer
    _global_tracer = tracer
