"""
AgentScope Python SDK — 企业级 AI Agent 评测与可观测性

快速开始:
    from agent_scope import TraceCollector, trace, trace_context, set_collector

    # 1. 初始化
    collector = TraceCollector(
        endpoint="http://localhost:8000/api/v1/sdk/traces",
        api_key="agev_xxxxxxxx",
        project_id="your-project-uuid",
        agent_id="your-agent-uuid",
    )
    set_collector(collector)

    # 2. 使用上下文管理器
    async with trace_context("my_agent", session_id="sess_1"):
        await run_agent()

    # 3. 使用装饰器
    @trace(span_type="llm_call")
    async def call_llm(prompt: str) -> str:
        ...

    # 4. LangChain 集成
    from agent_scope.langchain_hook import AgentScopeCallbackHandler
    handler = AgentScopeCallbackHandler()
    executor = AgentExecutor(..., callbacks=[handler])

    # 5. 关闭
    await collector.close()
"""
from agent_scope.client import TraceCollector
from agent_scope.context import set_collector, trace_context
from agent_scope.decorators import trace
from agent_scope.models import Span, SpanType, SpanStatus, Trace

__all__ = [
    "TraceCollector",
    "trace",
    "trace_context",
    "set_collector",
    "Span",
    "SpanType",
    "SpanStatus",
    "Trace",
]

__version__ = "0.1.0"