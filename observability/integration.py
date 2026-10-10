"""
Observability Integration with BaseAgent
Provides seamless integration of tracing and metrics with agent execution.
"""

import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from .tracer import AgentTracer, SpanType, SpanStatus, get_tracer
from .metrics import MetricsCollector, get_collector
from .monitor import MonitoringDashboard, get_monitor


class ObservableAgent:
    """
    Mixin for adding observability to agents.
    
    Usage:
        class MyAgent(ObservableAgent, BaseAgent):
            def __init__(self, ...):
                BaseAgent.__init__(self, ...)
                self.init_observability()
    """
    
    def init_observability(
        self,
        tracer: Optional[AgentTracer] = None,
        collector: Optional[MetricsCollector] = None,
        monitor: Optional[MonitoringDashboard] = None,
        enable_tracing: bool = True,
        enable_metrics: bool = True,
        enable_monitoring: bool = True,
    ):
        """Initialize observability components"""
        self.observability_tracer = tracer or get_tracer() if enable_tracing else None
        self.observability_collector = collector or get_collector() if enable_metrics else None
        self.observability_monitor = monitor or get_monitor() if enable_monitoring else None
        
        self.enable_tracing = enable_tracing
        self.enable_metrics = enable_metrics
        self.enable_monitoring = enable_monitoring
        
        # Track phase timings
        self._phase_start_times: Dict[str, float] = {}
        self._phase_durations: Dict[str, float] = {}
        self._tool_calls: list[str] = []
    
    def _start_phase_tracking(self, phase: str):
        """Start tracking a phase"""
        self._phase_start_times[phase] = time.time()
    
    def _end_phase_tracking(self, phase: str):
        """End tracking a phase"""
        if phase in self._phase_start_times:
            duration_ms = (time.time() - self._phase_start_times[phase]) * 1000
            self._phase_durations[phase] = duration_ms
            
            # Record in metrics
            if self.enable_metrics and self.observability_collector:
                self.observability_collector.record_phase(
                    agent_name=self.name if hasattr(self, 'name') else self.__class__.__name__,
                    phase=phase,
                    duration_ms=duration_ms,
                )
    
    def _track_tool_call(self, tool_name: str):
        """Track a tool call"""
        self._tool_calls.append(tool_name)
        
        if self.enable_metrics and self.observability_collector:
            self.observability_collector.record_tool_call(
                agent_name=self.name if hasattr(self, 'name') else self.__class__.__name__,
                tool_name=tool_name,
            )
    
    def _record_run_metrics(
        self,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
        confidence: Optional[float] = None,
        token_usage: Optional[Dict[str, int]] = None,
    ):
        """Record full run metrics"""
        if not self.enable_metrics or not self.observability_collector:
            return
        
        self.observability_collector.record_run(
            agent_name=self.name if hasattr(self, 'name') else self.__class__.__name__,
            duration_ms=duration_ms,
            success=success,
            error=error,
            confidence=confidence,
            token_usage=token_usage,
            phase_durations=self._phase_durations.copy(),
            tool_calls=self._tool_calls.copy(),
        )
        
        # Reset for next run
        self._phase_durations.clear()
        self._tool_calls.clear()
    
    def _check_monitoring(self):
        """Trigger monitoring checks"""
        if self.enable_monitoring and self.observability_monitor:
            self.observability_monitor.check_alerts()


def observable_run(method: Callable) -> Callable:
    """
    Decorator for agent run method with full observability.
    
    Usage:
        @observable_run
        def run(self, goal: AgentGoal) -> Any:
            ...
    """
    
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        # Get agent name
        agent_name = self.name if hasattr(self, 'name') else self.__class__.__name__
        
        # Check if observability is initialized
        if not hasattr(self, 'observability_tracer'):
            # Fall back to normal execution
            return method(self, *args, **kwargs)
        
        start_time = time.time()
        success = False
        error = None
        result = None
        
        # Start trace
        tracer = self.observability_tracer
        if tracer and self.enable_tracing:
            trace = tracer.start_trace(
                agent_name=agent_name,
                session_id=kwargs.get('session_id'),
                metadata={
                    "method": method.__name__,
                    "args_count": len(args),
                },
                tags=[agent_name, "run"],
            )
        
        try:
            # Execute method
            result = method(self, *args, **kwargs)
            success = True
            return result
        
        except Exception as e:
            error = str(e)
            raise
        
        finally:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Extract confidence if available
            confidence = None
            if hasattr(result, 'confidence'):
                confidence = result.confidence
            elif isinstance(result, dict) and 'confidence' in result:
                confidence = result['confidence']
            
            # Record metrics
            if hasattr(self, '_record_run_metrics'):
                self._record_run_metrics(
                    duration_ms=duration_ms,
                    success=success,
                    error=error,
                    confidence=confidence,
                )
            
            # End trace
            if tracer and self.enable_tracing:
                tracer.end_trace(success=success, error=error)
            
            # Check monitoring
            if hasattr(self, '_check_monitoring'):
                self._check_monitoring()
    
    return wrapper


def observable_phase(phase_name: str):
    """
    Decorator for agent phase methods with tracing.
    
    Usage:
        @observable_phase("perceive")
        def perceive(self, goal: AgentGoal) -> Perception:
            ...
    """
    
    def decorator(method: Callable) -> Callable:
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            # Get agent name
            agent_name = self.name if hasattr(self, 'name') else self.__class__.__name__
            
            # Check if observability is initialized
            if not hasattr(self, 'observability_tracer'):
                return method(self, *args, **kwargs)
            
            # Start phase tracking
            if hasattr(self, '_start_phase_tracking'):
                self._start_phase_tracking(phase_name)
            
            # Start span
            tracer = self.observability_tracer
            if tracer and self.enable_tracing:
                span = tracer.start_span(
                    agent_name=agent_name,
                    span_type=getattr(SpanType, phase_name.upper(), SpanType.EXECUTE),
                    inputs={"args_count": len(args)},
                    tags=[agent_name, phase_name],
                )
            
            try:
                # Execute phase
                result = method(self, *args, **kwargs)
                
                # End span
                if tracer and self.enable_tracing:
                    outputs = {}
                    if hasattr(result, '__dict__'):
                        outputs = {k: str(v)[:100] for k, v in result.__dict__.items()}
                    elif isinstance(result, dict):
                        outputs = {k: str(v)[:100] for k, v in result.items()}
                    
                    tracer.end_span(
                        span,
                        status=SpanStatus.SUCCESS,
                        outputs=outputs,
                    )
                
                return result
            
            except Exception as e:
                # End span with error
                if tracer and self.enable_tracing:
                    tracer.end_span(
                        span,
                        status=SpanStatus.ERROR,
                        error=str(e),
                    )
                raise
            
            finally:
                # End phase tracking
                if hasattr(self, '_end_phase_tracking'):
                    self._end_phase_tracking(phase_name)
        
        return wrapper
    
    return decorator


def observable_tool(tool_name: str):
    """
    Decorator for tool calls with tracking.
    
    Usage:
        @observable_tool("query_odoo")
        def query_odoo(self, ...):
            ...
    """
    
    def decorator(method: Callable) -> Callable:
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            # Track tool call
            if hasattr(self, '_track_tool_call'):
                self._track_tool_call(tool_name)
            
            # Get agent name
            agent_name = self.name if hasattr(self, 'name') else self.__class__.__name__
            
            # Start span
            tracer = getattr(self, 'observability_tracer', None)
            if tracer and getattr(self, 'enable_tracing', False):
                span = tracer.start_span(
                    agent_name=agent_name,
                    span_type=SpanType.TOOL_CALL,
                    inputs={"tool": tool_name},
                    tags=[agent_name, "tool", tool_name],
                )
            
            try:
                result = method(self, *args, **kwargs)
                
                # End span
                if tracer and getattr(self, 'enable_tracing', False):
                    tracer.end_span(
                        span,
                        status=SpanStatus.SUCCESS,
                        outputs={"result": str(result)[:200]},
                    )
                
                return result
            
            except Exception as e:
                # End span with error
                if tracer and getattr(self, 'enable_tracing', False):
                    tracer.end_span(
                        span,
                        status=SpanStatus.ERROR,
                        error=str(e),
                    )
                raise
        
        return wrapper
    
    return decorator


def with_observability(
    enable_tracing: bool = True,
    enable_metrics: bool = True,
    enable_monitoring: bool = True,
):
    """
    Class decorator to add observability to an agent.
    
    Usage:
        @with_observability()
        class MyAgent(BaseAgent):
            ...
    """
    
    def decorator(cls):
        # Store original __init__
        original_init = cls.__init__
        
        # Wrap __init__
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            
            # Add observability
            if not hasattr(self, 'observability_tracer'):
                self.observability_tracer = get_tracer() if enable_tracing else None
            if not hasattr(self, 'observability_collector'):
                self.observability_collector = get_collector() if enable_metrics else None
            if not hasattr(self, 'observability_monitor'):
                self.observability_monitor = get_monitor() if enable_monitoring else None
            
            self.enable_tracing = enable_tracing
            self.enable_metrics = enable_metrics
            self.enable_monitoring = enable_monitoring
            
            self._phase_start_times = {}
            self._phase_durations = {}
            self._tool_calls = []
        
        cls.__init__ = new_init
        
        # Add helper methods from ObservableAgent
        cls._start_phase_tracking = ObservableAgent._start_phase_tracking
        cls._end_phase_tracking = ObservableAgent._end_phase_tracking
        cls._track_tool_call = ObservableAgent._track_tool_call
        cls._record_run_metrics = ObservableAgent._record_run_metrics
        cls._check_monitoring = ObservableAgent._check_monitoring
        
        return cls
    
    return decorator
