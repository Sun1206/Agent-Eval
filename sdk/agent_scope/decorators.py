"""
@trace 装饰器 — 自动记录函数调用为 Span

支持同步和异步函数。自动捕获:
  - 函数名 → Span.name
  - 输入参数(JSON-safe) → Span.input
  - 返回值(JSON-safe) → Span.output
  - 执行耗时 → Span metadata
  - 异常 → Span.status = "error"
"""
import functools
import inspect
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from agent_scope.context import _current_context
from agent_scope.models import Span, SpanStatus, SpanType

logger = logging.getLogger(__name__)


def trace(
    name: str | None = None,
    span_type: str = SpanType.CHAIN,
    metadata: dict | None = None,
):
    """
    自动记录函数调用的装饰器

    Args:
        name:      Span 名称，默认使用函数名
        span_type: Span 类型 (chain/llm_call/tool_call/retrieval/embedding)
        metadata:  附加元数据

    用法:
        @trace(span_type="llm_call")
        async def call_llm(prompt: str) -> str:
            ...
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        if inspect.iscoroutinefunction(func):
            return _wrap_async(func, span_name, span_type, metadata or {})
        else:
            return _wrap_sync(func, span_name, span_type, metadata or {})

    return decorator


def _wrap_sync(func, span_name, span_type, metadata_extra):
    """包装同步函数"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        span = Span(name=span_name, type=span_type)
        span.metadata.update(metadata_extra)
        t_start = time.monotonic()
        span.start_time = datetime.now(timezone.utc)

        # 自动获取父 Span
        ctx = _current_context.get()
        if ctx is not None:
            span.parent_span_id = ctx.span_id

        # 记录输入
        span.input = _safe_serialize_args(args, kwargs)

        try:
            result = func(*args, **kwargs)
            span.status = SpanStatus.SUCCESS
            span.output = {"result": _safe_serialize(result)}
            _append_span_to_active_trace(span)
            return result
        except Exception as e:
            span.status = SpanStatus.ERROR
            span.output = {"error": str(e)}
            _append_span_to_active_trace(span)
            raise
        finally:
            span.end_time = datetime.now(timezone.utc)
            span.metadata["duration_ms"] = int(
                (time.monotonic() - t_start) * 1000
            )

    return wrapper


def _wrap_async(func, span_name, span_type, metadata_extra):
    """包装异步函数"""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        span = Span(name=span_name, type=span_type)
        span.metadata.update(metadata_extra)
        t_start = time.monotonic()
        span.start_time = datetime.now(timezone.utc)

        # 自动获取父 Span
        ctx = _current_context.get()
        if ctx is not None:
            span.parent_span_id = ctx.span_id

        # 记录输入
        span.input = _safe_serialize_args(args, kwargs)

        try:
            result = await func(*args, **kwargs)
            span.status = SpanStatus.SUCCESS
            span.output = {"result": _safe_serialize(result)}
            _append_span_to_active_trace(span)
            return result
        except Exception as e:
            span.status = SpanStatus.ERROR
            span.output = {"error": str(e)}
            _append_span_to_active_trace(span)
            raise
        finally:
            span.end_time = datetime.now(timezone.utc)
            span.metadata["duration_ms"] = int(
                (time.monotonic() - t_start) * 1000
            )

    return wrapper


def _append_span_to_active_trace(span: Span) -> None:
    """将 Span 附加到当前激活的 Trace"""
    from agent_scope.context import _active_trace

    trace_obj = _active_trace.get()
    if trace_obj is not None:
        trace_obj.spans.append(span)


def _safe_serialize(value: Any) -> Any:
    """安全序列化，避免不可 JSON 的对象报错"""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def _safe_serialize_args(args: tuple, kwargs: dict) -> dict:
    """安全序列化函数参数"""
    result = {}
    if args:
        # 跳过 self/cls
        start_idx = 1 if args and hasattr(args[0], "__dict__") else 0
        result["args"] = [_safe_serialize(a) for a in args[start_idx:]]
    if kwargs:
        result["kwargs"] = {k: _safe_serialize(v) for k, v in kwargs.items()}
    return result