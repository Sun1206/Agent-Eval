"""
SDK 专用路由 — API Key 认证的 Trace 上报 + 健康检查
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_from_api_key
from app.models.user import User
from app.schemas.common import BaseResponse
from app.schemas.trace import TraceReportRequest
from app.services.trace_service import TraceService

router = APIRouter(prefix="/sdk", tags=["SDK 接口"])


@router.get("/health", response_model=BaseResponse[dict])
async def sdk_health(
    current_user: User = Depends(get_current_user_from_api_key),
):
    """
    SDK 健康检查（X-API-Key 认证）

    Header: X-API-Key: agev_xxxxxxxx...
    用于 SDK 检测后端连通性和 API Key 有效性。
    """
    return BaseResponse.ok(
        {"status": "ok", "user_id": str(current_user.id)},
        "SDK 连接正常",
    )


@router.post("/traces", response_model=BaseResponse[dict])
async def sdk_ingest_trace(
    trace: TraceReportRequest,
    current_user: User = Depends(get_current_user_from_api_key),
):
    """
    SDK 上报 Trace（X-API-Key 认证）

    Header: X-API-Key: agev_xxxxxxxx...
    """
    await TraceService.ingest_trace(trace)
    return BaseResponse.ok(
        {"trace_id": str(trace.trace_id)},
        "Trace 上报成功",
    )


@router.post("/traces/batch", response_model=BaseResponse[dict])
async def sdk_ingest_traces_batch(
    body: list[TraceReportRequest],
    current_user: User = Depends(get_current_user_from_api_key),
):
    """
    SDK 批量上报 Trace（单次最多 100 条）

    Header: X-API-Key: agev_xxxxxxxx...
    """
    if not body:
        from app.core.exceptions import ValidationException
        raise ValidationException("上报数据不能为空")

    result = await TraceService.ingest_traces_batch(body)
    return BaseResponse.ok(result, f"批量上报完成，共 {result['total']} 条")