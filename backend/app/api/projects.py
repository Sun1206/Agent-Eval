"""
项目路由 — CRUD + 成员管理
"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import BaseResponse
from app.schemas.project import (
    MemberAddRequest,
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["项目管理"])


@router.post("", response_model=BaseResponse[ProjectResponse])
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建项目"""
    result = await ProjectService.create(db, data, current_user)
    return BaseResponse.ok(result, "项目创建成功")


@router.get("", response_model=BaseResponse[list[ProjectResponse]])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目列表（当前用户参与的项目）"""
    result = await ProjectService.list_by_user(db, current_user)
    return BaseResponse.ok(result)


@router.get("/{project_id}", response_model=BaseResponse[ProjectResponse])
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目详情"""
    result = await ProjectService.get_by_id(db, UUID(project_id), current_user)
    return BaseResponse.ok(result)


@router.put("/{project_id}", response_model=BaseResponse[ProjectResponse])
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新项目"""
    result = await ProjectService.update(db, UUID(project_id), data, current_user)
    return BaseResponse.ok(result, "项目更新成功")


@router.delete("/{project_id}", response_model=BaseResponse[None])
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """软删除项目"""
    await ProjectService.soft_delete(db, UUID(project_id), current_user)
    return BaseResponse.ok(None, "项目已删除")


# ==================== 成员管理 ====================

@router.get("/{project_id}/members", response_model=BaseResponse[list[MemberResponse]])
async def list_members(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目成员列表"""
    result = await ProjectService.list_members(db, UUID(project_id), current_user)
    return BaseResponse.ok(result)


@router.post("/{project_id}/members", response_model=BaseResponse[MemberResponse])
async def add_member(
    project_id: str,
    data: MemberAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加项目成员"""
    result = await ProjectService.add_member(db, UUID(project_id), data, current_user)
    return BaseResponse.ok(result, "成员添加成功")


@router.delete("/{project_id}/members/{user_id}", response_model=BaseResponse[None])
async def remove_member(
    project_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """移除项目成员"""
    await ProjectService.remove_member(db, UUID(project_id), UUID(user_id), current_user)
    return BaseResponse.ok(None, "成员已移除")