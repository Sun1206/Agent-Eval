"""
Bad Case 路由 — 标记 / 更新 / 列表 / 详情
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.bad_case import BadCaseCreate, BadCaseUpdate
from app.schemas.common import BaseResponse, PaginationData
from app.services.bad_case_service import BadCaseService

router = APIRouter(prefix="/projects/{project_id}/bad-cases", tags=["Bad Case 管理"])


@router.post("", response_model=BaseResponse[dict])
async def mark_bad_case(
    project_id: str,
    data: BadCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """标记 Bad Case"""
    result = await BadCaseService.mark_bad_case(
        UUID(project_id), data, db, current_user
    )
    return BaseResponse.ok(
        result.model_dump(mode="json"),
        "Bad Case 标记成功",
    )


@router.get("", response_model=BaseResponse[PaginationData])
async def list_bad_cases(
    project_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status: str | None = Query(None, description="筛选状态: open/in_progress/resolved/closed"),
    tag: str | None = Query(None, description="筛选标签: hallucination/error/omission/timeout/other"),
    assignee_id: str | None = Query(None, description="筛选负责人 ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bad Case 列表"""
    items, total = await BadCaseService.get_bad_cases(
        UUID(project_id),
        db,
        page=page,
        page_size=page_size,
        status=status,
        tag=tag,
        assignee_id=UUID(assignee_id) if assignee_id else None,
    )
    return BaseResponse.paginated(
        [item.model_dump(mode="json") for item in items],
        total, page, page_size,
    )


@router.get("/stats", response_model=BaseResponse[dict])
async def get_bad_case_stats(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bad Case 统计（按状态 + 按标签分布）"""
    stats = await BadCaseService.get_bad_case_stats(UUID(project_id), db)
    return BaseResponse.ok(stats)


@router.get("/{case_id}", response_model=BaseResponse[dict])
async def get_bad_case_detail(
    project_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bad Case 详情"""
    result = await BadCaseService.get_bad_case_detail(UUID(case_id), db)
    return BaseResponse.ok(result.model_dump(mode="json"))


@router.put("/{case_id}", response_model=BaseResponse[dict])
async def update_bad_case(
    project_id: str,
    case_id: str,
    data: BadCaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 Bad Case（状态/负责人/解决方案）"""
    result = await BadCaseService.update_bad_case(UUID(case_id), data, db)
    return BaseResponse.ok(
        result.model_dump(mode="json"),
        "Bad Case 更新成功",
    )