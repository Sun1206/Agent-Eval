"""
Agent 路由 — 注册 / 列表 / 详情 / 更新 / 删除
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate
from app.schemas.common import BaseResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/projects/{project_id}/agents", tags=["Agent 管理"])


@router.post("", response_model=BaseResponse[AgentResponse])
async def create_agent(
    project_id: str,
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """注册 Agent"""
    from uuid import UUID
    result = await AgentService.create(db, UUID(project_id), data, current_user)
    return BaseResponse.ok(result, "Agent 注册成功")


@router.get("", response_model=BaseResponse[list[AgentResponse]])
async def list_agents(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Agent 列表"""
    from uuid import UUID
    result = await AgentService.list_by_project(db, UUID(project_id), current_user)
    return BaseResponse.ok(result)


@router.get("/{agent_id}", response_model=BaseResponse[AgentResponse])
async def get_agent(
    project_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Agent 详情"""
    from uuid import UUID
    result = await AgentService.get_by_id(
        db, UUID(project_id), UUID(agent_id), current_user
    )
    return BaseResponse.ok(result)


@router.put("/{agent_id}", response_model=BaseResponse[AgentResponse])
async def update_agent(
    project_id: str,
    agent_id: str,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 Agent"""
    from uuid import UUID
    result = await AgentService.update(
        db, UUID(project_id), UUID(agent_id), data, current_user
    )
    return BaseResponse.ok(result, "Agent 更新成功")


@router.delete("/{agent_id}", response_model=BaseResponse[None])
async def delete_agent(
    project_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 Agent"""
    from uuid import UUID
    await AgentService.delete(db, UUID(project_id), UUID(agent_id), current_user)
    return BaseResponse.ok(None, "Agent 已删除")