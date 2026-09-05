"""
项目业务逻辑 — CRUD + 软删除 + 成员管理
"""
import asyncio
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.project import (
    MemberAddRequest,
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)


class ProjectService:
    """项目服务"""

    @staticmethod
    async def create(
        db: AsyncSession, data: ProjectCreate, owner: User
    ) -> ProjectResponse:
        """创建项目，自动设置 owner 并添加为项目成员"""
        project = Project(
            name=data.name,
            description=data.description,
            owner_id=owner.id,
        )
        db.add(project)
        await db.flush()

        # 自动将创建者加入项目成员（role=owner）
        member = ProjectMember(
            project_id=project.id,
            user_id=owner.id,
            role="owner",
        )
        db.add(member)
        await db.flush()
        await db.refresh(project)  # 刷新对象，获取数据库自动生成的字段

        return ProjectResponse.model_validate(project)

    @staticmethod
    async def list_by_user(
        db: AsyncSession, user: User
    ) -> list[ProjectResponse]:
        """获取用户参与的项目列表（排除软删除）"""
        result = await db.execute(
            select(Project)
            .join(ProjectMember, Project.id == ProjectMember.project_id)
            .where(
                and_(
                    ProjectMember.user_id == user.id,
                    Project.is_deleted == False,
                )
            )
            .order_by(Project.created_at.desc())
        )
        projects = result.scalars().all()
        return [ProjectResponse.model_validate(p) for p in projects]

    @staticmethod
    async def get_by_id(
        db: AsyncSession, project_id: UUID, user: User
    ) -> ProjectResponse:
        """获取项目详情（需是项目成员）"""
        project = await _get_project_and_check_member(db, project_id, user.id)
        return ProjectResponse.model_validate(project)

    @staticmethod
    async def update(
        db: AsyncSession, project_id: UUID, data: ProjectUpdate, user: User
    ) -> ProjectResponse:
        """更新项目（仅 owner 可操作）"""
        project = await _get_project_or_404(db, project_id)
        _check_ownership(project, user.id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)

        db.add(project)
        await db.flush()
        await db.refresh(project)  # 刷新对象，获取数据库自动更新的 updated_at
        return ProjectResponse.model_validate(project)

    @staticmethod
    async def soft_delete(
        db: AsyncSession, project_id: UUID, user: User
    ) -> None:
        """软删除项目（仅 owner 可操作）"""
        project = await _get_project_or_404(db, project_id)
        _check_ownership(project, user.id)

        project.is_deleted = True
        db.add(project)

    # ==================== 成员管理 ====================

    @staticmethod
    async def list_members(
        db: AsyncSession, project_id: UUID, user: User
    ) -> list[MemberResponse]:
        """获取项目成员列表（需是项目成员）"""
        await _get_project_and_check_member(db, project_id, user.id)

        result = await db.execute(
            select(ProjectMember, User.username)
            .join(User, ProjectMember.user_id == User.id)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.created_at)
        )
        rows = result.all()
        return [
            MemberResponse(
                id=pm.id,
                project_id=pm.project_id,
                user_id=pm.user_id,
                role=pm.role,
                username=username,
                created_at=pm.created_at,
            )
            for pm, username in rows
        ]

    @staticmethod
    async def add_member(
        db: AsyncSession, project_id: UUID, data: MemberAddRequest, user: User
    ) -> MemberResponse:
        """添加项目成员（仅 owner/admin 可操作）"""
        project = await _get_project_or_404(db, project_id)
        await _check_admin(db, project_id, user.id, project.owner_id)

        # 并行检查用户存在性 + 是否已是成员（两次查询独立，可并行）
        user_stmt = select(User).where(User.id == data.user_id)
        member_stmt = select(ProjectMember).where(
            and_(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == data.user_id,
            )
        )
        user_result, member_result = await asyncio.gather(
            db.execute(user_stmt),
            db.execute(member_stmt),
        )
        target_user = user_result.scalar_one_or_none()
        if target_user is None:
            raise NotFoundException("用户")
        if member_result.scalar_one_or_none() is not None:
            raise ConflictException("该用户已是项目成员")

        member = ProjectMember(
            project_id=project_id,
            user_id=data.user_id,
            role=data.role,
        )
        db.add(member)
        await db.flush()

        return MemberResponse(
            id=member.id,
            project_id=member.project_id,
            user_id=member.user_id,
            role=member.role,
            username=target_user.username,
            created_at=member.created_at,
        )

    @staticmethod
    async def remove_member(
        db: AsyncSession, project_id: UUID, target_user_id: UUID, user: User
    ) -> None:
        """移除项目成员（仅 owner/admin 可操作，不能移除 owner）"""
        project = await _get_project_or_404(db, project_id)
        await _check_admin(db, project_id, user.id, project.owner_id)

        # 不能移除 owner
        if target_user_id == project.owner_id:
            raise ForbiddenException("不能移除项目所有者")

        result = await db.execute(
            select(ProjectMember).where(
                and_(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == target_user_id,
                )
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            raise NotFoundException("项目成员")

        await db.delete(member)


# ==================== 内部辅助函数 ====================

async def _get_project_or_404(db: AsyncSession, project_id: UUID) -> Project:
    """查询项目，排除已软删除的"""
    result = await db.execute(
        select(Project).where(
            and_(Project.id == project_id, Project.is_deleted == False)
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException("项目")
    return project


async def _get_project_and_check_member(
    db: AsyncSession, project_id: UUID, user_id: UUID
) -> Project:
    """查询项目并校验成员身份（合并为一条 JOIN 查询，避免 2 次查询）"""
    result = await db.execute(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            and_(
                Project.id == project_id,
                Project.is_deleted == False,
                ProjectMember.user_id == user_id,
            )
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise ForbiddenException("非项目成员或项目不存在")
    return project


def _check_ownership(project: Project, user_id: UUID) -> None:
    """校验是否为项目所有者"""
    if project.owner_id != user_id:
        raise ForbiddenException("仅项目所有者可执行此操作")


async def _check_membership(
    db: AsyncSession, project_id: UUID, user_id: UUID
) -> None:
    """校验是否为项目成员"""
    result = await db.execute(
        select(ProjectMember).where(
            and_(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
    )
    if result.scalar_one_or_none() is None:
        raise ForbiddenException("非项目成员，无法访问")


async def _check_admin(
    db: AsyncSession, project_id: UUID, user_id: UUID, owner_id: UUID
) -> None:
    """校验是否为项目 owner 或 admin"""
    # owner 直接通过
    if user_id == owner_id:
        return
    result = await db.execute(
        select(ProjectMember).where(
            and_(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
                ProjectMember.role.in_(["admin"]),
            )
        )
    )
    if result.scalar_one_or_none() is None:
        raise ForbiddenException("仅项目所有者或管理员可执行此操作")