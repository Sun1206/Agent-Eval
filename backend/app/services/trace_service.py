"""
Trace 写入服务 — 单条/批量写入 ClickHouse

性能优化要点:
  - 所有 ClickHouse 操作通过 asyncio.to_thread 包装，避免阻塞事件循环
  - ClickHouse 客户端是同步的，直接在 async 函数中调用会串行化所有请求
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.core.clickhouse import get_clickhouse
from app.core.exceptions import ValidationException
from app.schemas.trace import TraceReportRequest, TraceListResponse, TraceResponse, SpanSchema

logger = logging.getLogger(__name__)

# 批量写入单次上限
BATCH_MAX_SIZE = 100


class TraceService:
    """Trace 写入服务"""

    @staticmethod
    async def ingest_trace(trace: TraceReportRequest) -> None:
        """写入单条 Trace 到 ClickHouse（异步，不阻塞事件循环）"""
        ch = get_clickhouse()
        row = _trace_to_row(trace)
        await asyncio.to_thread(ch.insert_trace, row)
        logger.debug(f"Trace 写入成功: trace_id={trace.trace_id}")

    @staticmethod
    async def ingest_traces_batch(traces: list[TraceReportRequest]) -> dict:
        """
        批量写入 Trace 到 ClickHouse（异步，不阻塞事件循环）

        单次最多 100 条，超过自动分批。

        Returns:
            {"total": N, "batches": M} 统计信息
        """
        if not traces:
            return {"total": 0, "batches": 0}

        ch = get_clickhouse()
        rows = [_trace_to_row(t) for t in traces]
        total = len(rows)
        batch_count = 0

        # 分批写入
        for i in range(0, total, BATCH_MAX_SIZE):
            batch = rows[i : i + BATCH_MAX_SIZE]
            await asyncio.to_thread(ch.insert_traces_batch, batch)
            batch_count += 1

        logger.info(f"批量 Trace 写入完成: {total} 条, {batch_count} 批")
        return {"total": total, "batches": batch_count}

    # ==================== 查询方法 ====================

    # sort_by 白名单
    _ALLOWED_SORT_FIELDS = {"start_time", "duration_ms"}
    _ALLOWED_SORT_ORDERS = {"DESC", "ASC"}

    @staticmethod
    async def query_traces(
        project_id: UUID,
        filters: Optional[dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "start_time",
        sort_order: str = "DESC",
    ) -> tuple[list[TraceListResponse], int]:
        """
        分页查询 Trace 列表（不含完整 spans）

        Args:
            project_id:  项目 UUID
            filters:     可选筛选条件
                - agent_id:    Agent UUID
                - session_id:  会话 ID
                - user_id:     终端用户 ID
                - status:      状态 (SUCCESS/ERROR)
                - start_time_from: 开始时间起始
                - start_time_to:   开始时间截止
                - keyword:     关键词搜索 (input/output)
            page:        页码
            page_size:   每页条数
            sort_by:     排序字段 (start_time / duration_ms)
            sort_order:  排序方向 (DESC / ASC)

        Returns:
            (items: list[TraceListResponse], total: int)
        """
        # 白名单校验
        if sort_by not in TraceService._ALLOWED_SORT_FIELDS:
            raise ValidationException(f"不支持的排序字段: {sort_by}")
        if sort_order.upper() not in TraceService._ALLOWED_SORT_ORDERS:
            raise ValidationException(f"不支持的排序方向: {sort_order}")

        filters = filters or {}

        # ClickHouse 不可用时优雅降级，返回空列表
        try:
            ch = get_clickhouse()
        except Exception as e:
            logger.warning(f"ClickHouse 不可用，返回空结果: {e}")
            return [], 0

        where_parts = ["project_id = {project_id:String}"]
        params: dict[str, Any] = {"project_id": str(project_id)}

        # 动态拼接 WHERE 条件（参数化防注入）
        for field, param_type in [
            ("agent_id", "String"),
            ("session_id", "String"),
            ("user_id", "String"),
            ("status", "String"),
        ]:
            value = filters.get(field)
            if value:
                where_parts.append(f"{field} = {{{field}:{param_type}}}")
                params[field] = str(value) if value else ""

        if "start_time_from" in filters:
            where_parts.append("start_time >= {start_time_from:DateTime}")
            params["start_time_from"] = filters["start_time_from"]

        if "start_time_to" in filters:
            where_parts.append("start_time <= {start_time_to:DateTime}")
            params["start_time_to"] = filters["start_time_to"]

        # 关键词搜索
        keyword = filters.get("keyword")
        if keyword:
            where_parts.append(
                "(input  LIKE {keyword:String} OR output LIKE {keyword:String})"
            )
            params["keyword"] = f"%{keyword}%"

        where_clause = " AND ".join(where_parts)

        # 串行执行 count + data 查询（clickhouse_connect 不支持同一客户端并发查询）
        offset = (page - 1) * page_size
        count_sql = f"SELECT count() AS cnt FROM traces WHERE {where_clause}"
        data_sql = (
            f"SELECT "
            f"  id, trace_id, project_id, agent_id, session_id, user_id, "
            f"  input, output, start_time, end_time, duration_ms, "
            f"  total_tokens, total_cost, status, "
            f"  JSONLength(spans) AS span_count, "
            f"  tags, metadata, created_at "
            f"FROM traces "
            f"WHERE {where_clause} "
            f"ORDER BY {sort_by} {sort_order.upper()} "
            f"LIMIT {page_size} OFFSET {offset}"
        )
        try:
            count_result = await asyncio.to_thread(ch._ch.query, count_sql, parameters=params)
            data_result = await asyncio.to_thread(ch._ch.query, data_sql, parameters=params)
        except Exception as e:
            logger.warning(f"ClickHouse 查询失败，返回空结果: {e}")
            return [], 0
        total = count_result.first_item["cnt"]

        items = []
        for row in data_result.named_results():
            # ClickHouse 空字符串需转为 None，否则 UUID("") 会抛 ValueError
            end_time_val = row.get("end_time")
            # ClickHouse 中 end_time 默认为 epoch(1970)，转为 None
            if end_time_val and hasattr(end_time_val, 'year') and end_time_val.year <= 1970:
                end_time_val = None
            items.append(TraceListResponse(
                id=row.get("id") or None,
                trace_id=row.get("trace_id"),
                project_id=row.get("project_id") or None,
                agent_id=row.get("agent_id") or None,
                session_id=row.get("session_id") or None,
                user_id=row.get("user_id") or None,
                input=row.get("input"),
                output=row.get("output"),
                start_time=row.get("start_time"),
                end_time=end_time_val,
                duration_ms=row.get("duration_ms"),
                total_tokens=row.get("total_tokens", 0),
                total_cost=float(row.get("total_cost", 0)),
                status=row.get("status", "SUCCESS"),
                span_count=row.get("span_count", 0),
                tags=_parse_json_list(row.get("tags", "[]")),
                created_at=row.get("created_at"),
            ))

        return items, total

    @staticmethod
    async def get_trace_detail(trace_id: UUID) -> Optional[TraceResponse]:
        """
        查询单条 Trace 完整数据（含完整 spans 反序列化）

        Args:
            trace_id: Trace UUID

        Returns:
            TraceResponse 或 None
        """
        # ClickHouse 不可用时优雅降级
        try:
            ch = get_clickhouse()
        except Exception as e:
            logger.warning(f"ClickHouse 不可用，无法查询 Trace 详情: {e}")
            return None
        try:
            result = await asyncio.to_thread(
                ch._ch.query,
                "SELECT * FROM traces WHERE trace_id = {trace_id:String}",
                parameters={"trace_id": str(trace_id)},
            )
        except Exception as e:
            logger.warning(f"ClickHouse 查询失败，无法获取 Trace 详情: {e}")
            return None
        rows = list(result.named_results())
        if not rows:
            return None

        row = rows[0]

        # 反序列化 spans JSON 字符串
        spans_raw = row.get("spans", "[]")
        spans = _deserialize_spans(spans_raw)

        # 反序列化 tags / metadata
        tags = _parse_json_list(row.get("tags", "[]"))
        metadata = _parse_json_dict(row.get("metadata", "{}"))

        return TraceResponse(
            id=row.get("id") or None,
            trace_id=row.get("trace_id"),
            project_id=row.get("project_id") or None,
            agent_id=row.get("agent_id") or None,
            session_id=row.get("session_id") or None,
            user_id=row.get("user_id") or None,
            input=row.get("input"),
            output=row.get("output"),
            start_time=row.get("start_time"),
            end_time=row.get("end_time") if row.get("end_time") and hasattr(row.get("end_time"), 'year') and row.get("end_time").year > 1970 else None,
            duration_ms=row.get("duration_ms"),
            total_tokens=row.get("total_tokens", 0),
            total_cost=float(row.get("total_cost", 0)),
            status=row.get("status", "SUCCESS"),
            spans=spans,
            tags=tags,
            metadata=metadata,
            created_at=row.get("created_at"),
        )


# ==================== 辅助函数 ====================

def _deserialize_spans(spans_raw: str) -> list[SpanSchema]:
    """将 JSON 字符串反序列化为 SpanSchema 列表"""
    try:
        data = json.loads(spans_raw) if isinstance(spans_raw, str) else spans_raw
        if isinstance(data, list):
            return [SpanSchema(**s) for s in data]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return []


def _parse_json_list(raw: str) -> list[str]:
    """安全解析 JSON 数组为字符串列表"""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_json_dict(raw: str) -> dict:
    """安全解析 JSON 对象为 dict"""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _trace_to_row(trace: TraceReportRequest) -> dict:
    """将 TraceReportRequest 转为 ClickHouse 行 dict"""
    # spans 序列化为 JSON 字符串
    spans_json = json.dumps(
        [s.model_dump(mode="json") for s in trace.spans],
        ensure_ascii=False,
    )

    # tags 序列化为 JSON 字符串
    tags_json = json.dumps(trace.tags, ensure_ascii=False)

    # metadata 序列化为 JSON 字符串
    metadata_json = json.dumps(trace.metadata, ensure_ascii=False)

    return {
        "id": str(trace.trace_id),
        "trace_id": str(trace.trace_id),
        "project_id": str(trace.project_id),
        "agent_id": str(trace.agent_id) if trace.agent_id else "",
        "session_id": trace.session_id or "",
        "user_id": trace.user_id or "",
        "input": trace.input or "",
        "output": trace.output or "",
        "start_time": trace.start_time,
        "end_time": trace.end_time,
        "duration_ms": trace.duration_ms or 0,
        "total_tokens": trace.total_tokens,
        "total_cost": trace.total_cost,
        "status": trace.status,
        "spans": spans_json,
        "tags": tags_json,
        "metadata": metadata_json,
        "created_at": None,  # ClickHouse 自动使用 now()
    }
