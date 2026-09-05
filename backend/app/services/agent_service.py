"""
Agent 业务逻辑 — CRUD + 名称版本唯一性校验
"""
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentResponse, AgentUpdate
from app.services.project_service import _get_project_and_check_member


class AgentService:
    """Agent 服务"""

    @staticmethod
    async def create(
        db: AsyncSession, project_id: UUID, data: AgentCreate, user: User
    ) -> AgentResponse:
        """注册 Agent"""
        await _get_project_and_check_member(db, project_id, user.id)

        # 检查同项目下名称+版本唯一性
        existing = await db.execute(
            select(Agent).where(
                and_(
                    Agent.project_id == project_id,
                    Agent.name == data.name,
                    Agent.version == data.version,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException(f"Agent '{data.name}' 版本 '{data.version}' 已存在")

        agent = Agent(
            project_id=project_id,
            name=data.name,
            version=data.version,
            description=data.description,
            endpoint_url=data.endpoint_url,
            config=data.config,
        )
        db.add(agent)
        await db.flush()
        await db.refresh(agent)  # 刷新对象，获取数据库自动生成的字段
        return AgentResponse.model_validate(agent)

    @staticmethod
    async def list_by_project(
        db: AsyncSession, project_id: UUID, user: User
    ) -> list[AgentResponse]:
        """获取项目下的 Agent 列表"""
        await _get_project_and_check_member(db, project_id, user.id)

        result = await db.execute(
            select(Agent)
            .where(Agent.project_id == project_id)
            .order_by(Agent.created_at.desc())
        )
        agents = result.scalars().all()
        return [AgentResponse.model_validate(a) for a in agents]

    @staticmethod
    async def get_by_id(
        db: AsyncSession, project_id: UUID, agent_id: UUID, user: User
    ) -> AgentResponse:
        """获取 Agent 详情"""
        await _get_project_and_check_member(db, project_id, user.id)

        agent = await _get_agent_or_404(db, agent_id, project_id)
        return AgentResponse.model_validate(agent)

    @staticmethod
    async def update(
        db: AsyncSession, project_id: UUID, agent_id: UUID,
        data: AgentUpdate, user: User,
    ) -> AgentResponse:
        """更新 Agent"""
        await _get_project_and_check_member(db, project_id, user.id)

        agent = await _get_agent_or_404(db, agent_id, project_id)

        # 如果修改了名称或版本，检查唯一性
        new_name = data.name or agent.name
        new_version = data.version or agent.version
        if data.name or data.version:
            existing = await db.execute(
                select(Agent).where(
                    and_(
                        Agent.project_id == project_id,
                        Agent.name == new_name,
                        Agent.version == new_version,
                        Agent.id != agent_id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise ConflictException(
                    f"Agent '{new_name}' 版本 '{new_version}' 已存在"
                )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)

        db.add(agent)
        await db.flush()
        await db.refresh(agent)  # 刷新对象，获取数据库自动生成的字段
        return AgentResponse.model_validate(agent)

    @staticmethod
    async def delete(
        db: AsyncSession, project_id: UUID, agent_id: UUID, user: User
    ) -> None:
        """删除 Agent"""
        await _get_project_and_check_member(db, project_id, user.id)

        agent = await _get_agent_or_404(db, agent_id, project_id)

        # 检查是否有关联的评测任务
        from app.models.evaluation import EvalRun
        eval_count = await db.execute(
            select(func.count()).select_from(EvalRun).where(EvalRun.agent_id == agent_id)
        )
        if eval_count.scalar() > 0:
            raise ValidationException("该 Agent 已关联评测任务，无法删除")

        await db.delete(agent)
        await db.flush()


async def _get_agent_or_404(
    db: AsyncSession, agent_id: UUID, project_id: UUID
) -> Agent:
    """查询 Agent，加项目隔离"""
    result = await db.execute(
        select(Agent).where(
            and_(Agent.id == agent_id, Agent.project_id == project_id)
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise NotFoundException("Agent")
    return agent