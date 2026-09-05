"""
Trace 路由 — 项目级 Trace 上报 + 查询（JWT 认证）
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.core.exceptions import ValidationException, NotFoundException
from app.models.user import User
from app.schemas.common import BaseResponse, PaginationData
from app.schemas.trace import TraceReportRequest, TraceListResponse, TraceResponse
from app.services.trace_service import TraceService

router = APIRouter(prefix="/projects/{project_id}/traces", tags=["Trace 管理"])


@router.post("", response_model=BaseResponse[dict])
async def ingest_trace(
    project_id: str,
    trace: TraceReportRequest,
    current_user: User = Depends(get_current_user),
):
    """上报单条 Trace"""
    from uuid import UUID
    # 校验 project_id 一致性
    if str(trace.project_id) != project_id:
        from app.core.exceptions import ValidationException
        raise ValidationException("Trace 的 project_id 与 URL 不一致")

    await TraceService.ingest_trace(trace)
    return BaseResponse.ok(
        {"trace_id": str(trace.trace_id)},
        "Trace 上报成功",
    )


@router.post("/batch", response_model=BaseResponse[dict])
async def ingest_traces_batch(
    project_id: str,
    body: list[TraceReportRequest],
    current_user: User = Depends(get_current_user),
):
    """批量上报 Trace（单次最多 100 条）"""
    if not body:
        from app.core.exceptions import ValidationException
        raise ValidationException("上报数据不能为空")

    # 校验 project_id 一致性
    for trace in body:
        if str(trace.project_id) != project_id:
            from app.core.exceptions import ValidationException
            raise ValidationException(
                f"Trace {trace.trace_id} 的 project_id 与 URL 不一致"
            )

    result = await TraceService.ingest_traces_batch(body)
    return BaseResponse.ok(result, f"批量上报完成，共 {result['total']} 条")


# ==================== 查询路由 ====================

@router.get("", response_model=BaseResponse[PaginationData])
async def list_traces(
    project_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    agent_id: str | None = Query(None, description="Agent ID"),
    session_id: str | None = Query(None, description="会话 ID"),
    user_id: str | None = Query(None, description="终端用户 ID"),
    status: str | None = Query(None, description="状态: SUCCESS/ERROR"),
    start_time_from: datetime | None = Query(None, description="开始时间（起始）"),
    start_time_to: datetime | None = Query(None, description="开始时间（截止）"),
    keyword: str | None = Query(None, description="关键词搜索"),
    sort_by: str = Query("start_time", description="排序: start_time / duration_ms"),
    sort_order: str = Query("DESC", description="排序方向: DESC / ASC"),
    current_user: User = Depends(get_current_user),
):
    """
    Trace 列表查询（不含完整 spans）

    Query 参数支持多条件筛选 + 排序 + 关键词搜索。
    """
    filters = {}
    if agent_id:
        filters["agent_id"] = agent_id
    if session_id:
        filters["session_id"] = session_id
    if user_id:
        filters["user_id"] = user_id
    if status:
        filters["status"] = status.upper()
    if start_time_from:
        filters["start_time_from"] = start_time_from
    if start_time_to:
        filters["start_time_to"] = start_time_to
    if keyword:
        filters["keyword"] = keyword.strip()

    items, total = await TraceService.query_traces(
        project_id=UUID(project_id),
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return BaseResponse.paginated(
        [item.model_dump(mode="json") for item in items],
        total, page, page_size,
    )


@router.get("/{trace_id}", response_model=BaseResponse[TraceResponse])
async def get_trace_detail(
    project_id: str,
    trace_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Trace 详情（含完整 spans）
    """
    detail = await TraceService.get_trace_detail(UUID(trace_id))
    if detail is None:
        raise NotFoundException("Trace")
    return BaseResponse.ok(detail)