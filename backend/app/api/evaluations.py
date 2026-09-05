"""
评测路由 — 评测任务 CRUD + 取消
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import BaseResponse, PaginationData
from app.schemas.evaluation import (
    EvalRunCreate,
    EvalRunDetail,
    EvalRunListItem,
    EvalResultItem,
    EvalStatsResponse,
    EvalProgressResponse,
)
from app.services.eval_service import EvalService

router = APIRouter(prefix="/projects/{project_id}/evaluations", tags=["评测管理"])


@router.post("", response_model=BaseResponse[dict])
async def create_eval_run(
    project_id: str,
    data: EvalRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建评测任务"""
    detail = await EvalService.create_eval_run(
        UUID(project_id), data, db, current_user
    )
    return BaseResponse.ok(
        detail.model_dump(mode="json"),
        f"评测任务创建成功，共 {detail.total_items} 条用例",
    )


@router.get("", response_model=BaseResponse[PaginationData])
async def list_eval_runs(
    project_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """评测任务列表"""
    items, total = await EvalService.get_eval_runs(
        UUID(project_id), db, page, page_size
    )
    return BaseResponse.paginated(
        [item.model_dump(mode="json") for item in items],
        total, page, page_size,
    )


@router.get("/{run_id}", response_model=BaseResponse[dict])
async def get_eval_run_detail(
    project_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """评测任务详情（含 judge_config）"""
    detail = await EvalService.get_eval_run_detail(UUID(run_id), db)
    return BaseResponse.ok(detail.model_dump(mode="json"))


@router.post("/{run_id}/cancel", response_model=BaseResponse[dict])
async def cancel_eval_run(
    project_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消评测任务（仅 RUNNING 状态可取消）"""
    detail = await EvalService.cancel_eval_run(UUID(run_id), db)
    return BaseResponse.ok(
        detail.model_dump(mode="json"),
        "评测任务已取消",
    )


@router.post("/{run_id}/retry", response_model=BaseResponse[dict])
async def retry_eval_run(
    project_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重试评测任务（仅 FAILED/CANCELLED 状态可重试）"""
    detail = await EvalService.retry_eval_run(UUID(run_id), db)
    return BaseResponse.ok(
        detail.model_dump(mode="json"),
        "评测任务已重新开始",
    )


@router.delete("/{run_id}", response_model=BaseResponse[None])
async def delete_eval_run(
    project_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除评测任务（运行中不可删除）"""
    await EvalService.delete_eval_run(UUID(run_id), db)
    return BaseResponse.ok(None, "评测任务已删除")


# ==================== 结果查询路由 ====================

@router.get("/{run_id}/results", response_model=BaseResponse[PaginationData])
async def list_eval_results(
    project_id: str,
    run_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: str | None = Query(None, description="筛选状态: SUCCESS/FAILURE/ERROR/TIMEOUT"),
    sort_by: str = Query("sort_order", description="排序: total_score/duration_ms/sort_order"),
    sort_order: str = Query("asc", description="排序方向: asc/desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """评测结果分页列表"""
    items, total = await EvalService.get_eval_results(
        UUID(run_id), db, page, page_size, status, sort_by, sort_order,
    )
    return BaseResponse.paginated(
        [item.model_dump(mode="json") for item in items],
        total, page, page_size,
    )


@router.get("/{run_id}/stats", response_model=BaseResponse[dict])
async def get_eval_stats(
    project_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """评测统计摘要"""
    stats = await EvalService.get_eval_stats(UUID(run_id), db)
    return BaseResponse.ok(stats.model_dump(mode="json"))


@router.get("/{run_id}/progress", response_model=BaseResponse[dict])
async def get_eval_progress(
    project_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """评测进度查询"""
    progress = await EvalService.get_eval_progress(UUID(run_id), db)
    return BaseResponse.ok(progress.model_dump(mode="json"))


@router.post("/{run_id}/results/{result_id}/retry", response_model=BaseResponse[dict])
async def retry_eval_result(
    project_id: str,
    run_id: str,
    result_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重试单条评测结果（仅 ERROR/TIMEOUT/FAILURE 可重试）"""
    result = await EvalService.retry_eval_result(UUID(result_id), db)
    return BaseResponse.ok(result.model_dump(mode="json"), "结果重试已开始")