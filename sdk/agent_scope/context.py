"""
TraceContext 上下文管理器 — 管理 Trace/Span 生命周期

支持:
  - trace_context() 创建一次 Trace（顶层上下文）
  - 嵌套 TraceContext → 自动建立父子 Span 关系
  - 使用 contextvars 实现协程安全的上下文栈
"""
import contextvars
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from agent_scope.client import TraceCollector
from agent_scope.models import Span, SpanStatus, SpanType, Trace

logger = logging.getLogger(__name__)

# contextvars：协程安全的上下文变量
_current_context: contextvars.ContextVar[Optional[Span]] = contextvars.ContextVar(
    "_trace_current_span", default=None
)
_active_trace: contextvars.ContextVar[Optional[Trace]] = contextvars.ContextVar(
    "_trace_active_trace", default=None
)
_collector: contextvars.ContextVar[Optional[TraceCollector]] = contextvars.ContextVar(
    "_trace_collector", default=None
)


def set_collector(collector: TraceCollector) -> None:
    """设置全局 TraceCollector（SDK 初始化时调用）"""
    _collector.set(collector)


@asynccontextmanager
async def trace_context(
    name: str,
    span_type: str = SpanType.CHAIN,
    metadata: dict | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    auto_report: bool = True,
) -> AsyncGenerator[Span, None]:
    """
    创建一次 Trace 上下文

    用法:
        async with trace_context("my_agent", session_id="sess_1") as span:
            await do_something()  # 内部的 @trace 装饰器自动添加到当前 Trace

    Args:
        name:        根 Span 名称
        span_type:   Span 类型
        metadata:    附加元数据
        session_id:  会话 ID
        user_id:     终端用户 ID
        auto_report: 退出时是否自动上报

    Yields:
        根 Span 对象
    """
    collector = _collector.get()
    span = Span(name=name, type=span_type)
    if metadata:
        span.metadata.update(metadata)
    t_start = time.monotonic()
    span.start_time = datetime.now(timezone.utc)

    # 确定父 Span：嵌套时自动关联
    parent = _current_context.get()
    if parent is not None:
        span.parent_span_id = parent.span_id

    # 是否创建新 Trace（顶层上下文）
    trace_obj = _active_trace.get()
    is_root = trace_obj is None
    if is_root:
        trace_obj = Trace(
            session_id=session_id,
            user_id=user_id,
        )
        _active_trace.set(trace_obj)

    trace_obj.spans.append(span)

    # 设置当前 Span 为活跃 Span
    token = _current_context.set(span)

    try:
        yield span
        span.status = SpanStatus.SUCCESS
    except Exception:
        span.status = SpanStatus.ERROR
        raise
    finally:
        span.end_time = datetime.now(timezone.utc)
        span.metadata["duration_ms"] = int((time.monotonic() - t_start) * 1000)
        _current_context.reset(token)

        # 顶层上下文退出时，上报整个 Trace
        if is_root and auto_report and collector is not None:
            trace_obj.start_time = span.start_time
            trace_obj.end_time = span.end_time
            trace_obj.duration_ms = span.metadata.get("duration_ms")
            # 汇总 token 用量
            for s in trace_obj.spans:
                usage = s.metadata.get("token_usage", {})
                trace_obj.total_tokens += usage.get("total", 0)
                trace_obj.total_cost += s.metadata.get("cost", 0.0)

            await collector.report_trace(trace_obj)
            _active_trace.set(None)