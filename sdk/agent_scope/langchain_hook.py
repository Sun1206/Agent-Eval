"""
LangChain 自动 Hook — 基于 BaseCallbackHandler 拦截 LLM/Tool 调用

工作原理:
  - 实现 LangChain 的 BaseCallbackHandler 接口
  - 注册到 LLM Chain / Agent Executor 的 callbacks 列表
  - 自动为每次 LLM 调用生成 llm_call Span
  - 自动为每次 Tool 调用生成 tool_call Span
  - Span 自动关联到当前激活的 TraceContext

兼容性:
  - LangChain >= 0.1.0（BaseCallbackHandler 稳定接口）
  - LangChain v0.3.x 通过 BaseCallbackHandler 兼容
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from agent_scope.context import _active_trace, _current_context
from agent_scope.models import Span, SpanStatus

logger = logging.getLogger(__name__)

# 尝试导入 LangChain Callback 基类
try:
    from langchain.callbacks.base import BaseCallbackHandler

    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False

    class BaseCallbackHandler:  # type: ignore
        """占位类，LangChain 未安装时不影响导入"""
        pass


class AgentScopeCallbackHandler(BaseCallbackHandler):
    """
    LangChain Callback Handler — 自动将 LLM/Tool 调用记录为 Span

    用法:
        from langchain.agents import AgentExecutor
        from agent_scope.langchain_hook import AgentScopeCallbackHandler

        handler = AgentScopeCallbackHandler()
        executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=tools,
            callbacks=[handler],
        )
    """

    def __init__(self):
        super().__init__()
        # Span ID 映射: LangChain run_id → 我们的 span_id
        self._span_map: dict[UUID, Span] = {}
        self._start_times: dict[UUID, float] = {}

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用开始"""
        span = Span(
            span_id=uuid4(),
            type="llm_call",
            name=f"LLM: {serialized.get('name', serialized.get('id', ['unknown']))[-1] if isinstance(serialized.get('id'), list) else serialized.get('name', 'unknown')}",
            start_time=datetime.now(timezone.utc),
        )

        # 关联父 Span
        ctx = _current_context.get()
        if ctx is not None:
            span.parent_span_id = ctx.span_id

        span.input = {
            "prompts": prompts,
            "model": serialized.get("name", "unknown"),
        }

        span.metadata["kwargs"] = {
            k: str(v)[:200] for k, v in kwargs.items()
            if k in ("temperature", "max_tokens", "model_name")
        }

        self._span_map[run_id] = span
        self._start_times[run_id] = time.monotonic()

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用结束"""
        span = self._span_map.pop(run_id, None)
        if span is None:
            return

        t_now = datetime.now(timezone.utc)
        span.end_time = t_now
        span.status = SpanStatus.SUCCESS

        # 提取 LLM 响应
        if hasattr(response, "generations"):
            generations = response.generations
            if generations and generations[0]:
                gen = generations[0][0]
                span.output = {
                    "text": getattr(gen, "text", str(gen)),
                }
                # Token 用量
                if hasattr(response, "llm_output") and response.llm_output:
                    usage = response.llm_output.get("token_usage", {})
                    span.metadata["token_usage"] = usage

        span.metadata["duration_ms"] = _calc_duration_ms(run_id, self._start_times)

        _append_to_trace(span)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用出错"""
        span = self._span_map.pop(run_id, None)
        if span is None:
            return

        span.end_time = datetime.now(timezone.utc)
        span.status = SpanStatus.ERROR
        span.output = {"error": str(error)}
        span.metadata["duration_ms"] = _calc_duration_ms(run_id, self._start_times)
        _append_to_trace(span)

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Tool 调用开始"""
        span = Span(
            span_id=uuid4(),
            type="tool_call",
            name=f"Tool: {serialized.get('name', 'unknown')}",
            start_time=datetime.now(timezone.utc),
        )

        ctx = _current_context.get()
        if ctx is not None:
            span.parent_span_id = ctx.span_id

        span.input = {"input": input_str}
        self._span_map[run_id] = span
        self._start_times[run_id] = time.monotonic()

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Tool 调用结束"""
        span = self._span_map.pop(run_id, None)
        if span is None:
            return

        span.end_time = datetime.now(timezone.utc)
        span.status = SpanStatus.SUCCESS
        span.output = {"result": output}
        span.metadata["duration_ms"] = _calc_duration_ms(run_id, self._start_times)
        _append_to_trace(span)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Tool 调用出错"""
        span = self._span_map.pop(run_id, None)
        if span is None:
            return

        span.end_time = datetime.now(timezone.utc)
        span.status = SpanStatus.ERROR
        span.output = {"error": str(error)}
        span.metadata["duration_ms"] = _calc_duration_ms(run_id, self._start_times)
        _append_to_trace(span)


def _append_to_trace(span: Span) -> None:
    """将 Span 附加到当前激活的 Trace"""
    trace_obj = _active_trace.get()
    if trace_obj is not None:
        trace_obj.spans.append(span)


def _calc_duration_ms(run_id: UUID, start_times: dict[UUID, float]) -> int:
    """计算执行耗时（毫秒）"""
    t_start = start_times.pop(run_id, None)
    if t_start is not None:
        return int((time.monotonic() - t_start) * 1000)
    return 0