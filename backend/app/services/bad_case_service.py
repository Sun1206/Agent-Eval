"""
Bad Case 服务 — 标记 / 更新 / 列表 / 详情

状态流转规则:
  open → in_progress → resolved
  任一状态 → closed
  不允许从 closed 回到其他状态
  不允许跳过中间状态（open → resolved 不允许）
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.models.bad_case import BadCase
from app.models.user import User
from app.schemas.bad_case import (
    BadCaseCreate,
    BadCaseResponse,
    BadCaseTag,
    BadCaseStatus,
    BadCaseUpdate,
)

logger = logging.getLogger(__name__)

# 合法状态流转映射（源状态 → 允许的目标状态集合）
VALID_TRANSITIONS: dict[BadCaseStatus, set[BadCaseStatus]] = {
    BadCaseStatus.OPEN: {BadCaseStatus.IN_PROGRESS, BadCaseStatus.CLOSED},
    BadCaseStatus.IN_PROGRESS: {BadCaseStatus.RESOLVED, BadCaseStatus.CLOSED},
    BadCaseStatus.RESOLVED: {BadCaseStatus.CLOSED},
    BadCaseStatus.CLOSED: set(),  # 不允许从 closed 转到任何状态
}


class BadCaseService:
    """Bad Case 服务"""

    # ==================== 标记 ====================

    @staticmethod
    async def mark_bad_case(
        project_id: UUID,
        data: BadCaseCreate,
        db: AsyncSession,
        current_user: User,
    ) -> BadCaseResponse:
        """标记一个 Bad Case"""
        now = datetime.now(timezone.utc)

        bad_case = BadCase(
            project_id=project_id,
            trace_id=data.trace_id,
            tag=data.tag.value,
            description=data.description,
            status=BadCaseStatus.OPEN.value,
            assignee_id=data.assignee_id,
            marked_by=current_user.id,
            marked_at=now,
        )
        db.add(bad_case)
        await db.flush()
        await db.refresh(bad_case)

        return BadCaseResponse.model_validate(bad_case)

    # ==================== 更新 ====================

    @staticmethod
    async def update_bad_case(
        case_id: UUID,
        data: BadCaseUpdate,
        db: AsyncSession,
    ) -> BadCaseResponse:
        """更新 Bad Case（状态/负责人/解决方案）"""
        bad_case = await db.get(BadCase, case_id)
        if bad_case is None:
            raise NotFoundException("Bad Case")

        # 状态流转校验
        if data.status is not None:
            _validate_transition(
                BadCaseStatus(bad_case.status),
                data.status,
            )
            bad_case.status = data.status.value

            # resolved 时自动记录 resolved_at
            if data.status == BadCaseStatus.RESOLVED:
                bad_case.resolved_at = datetime.now(timezone.utc)

        # 更新负责人
        if data.assignee_id is not None:
            bad_case.assignee_id = data.assignee_id

        # 更新解决方案
        if data.resolution is not None:
            bad_case.resolution = data.resolution

        await db.flush()
        await db.refresh(bad_case)

        return BadCaseResponse.model_validate(bad_case)

    # ==================== 列表 ====================

    @staticmethod
    async def get_bad_cases(
        project_id: UUID,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        assignee_id: Optional[UUID] = None,
    ) -> tuple[list[BadCaseResponse], int]:
        """分页查询 Bad Case 列表"""
        conditions = [BadCase.project_id == project_id]

        if status:
            conditions.append(BadCase.status == status)
        if tag:
            conditions.append(BadCase.tag == tag)
        if assignee_id:
            conditions.append(BadCase.assignee_id == assignee_id)

        # 并行执行 count + data 查询
        offset = (page - 1) * page_size
        count_stmt = select(func.count()).where(and_(*conditions))
        data_stmt = (
            select(BadCase)
            .where(and_(*conditions))
            .order_by(BadCase.marked_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        total_result, data_result = await asyncio.gather(
            db.scalar(count_stmt),
            db.execute(data_stmt),
        )
        total = total_result or 0
        rows = data_result.scalars().all()

        items = [BadCaseResponse.model_validate(r) for r in rows]
        return items, total

    # ==================== 详情 ====================

    @staticmethod
    async def get_bad_case_detail(
        case_id: UUID,
        db: AsyncSession,
    ) -> BadCaseResponse:
        """查询 Bad Case 详情"""
        bad_case = await db.get(BadCase, case_id)
        if bad_case is None:
            raise NotFoundException("Bad Case")

        return BadCaseResponse.model_validate(bad_case)

    # ==================== 统计 ====================

    @staticmethod
    async def get_bad_case_stats(
        project_id: UUID,
        db: AsyncSession,
    ) -> dict:
        """
        查询 Bad Case 统计（按状态 + 按标签分布）

        优化: 总数 + 状态分组合并为一条 SQL，标签分组单独一条，共 2 次查询（原 3 次）
        """
        # 并行执行按状态分组 + 按标签分组（两次 GROUP BY 独立，可并行）
        status_stmt = select(
            BadCase.status,
            func.count().label("cnt"),
        ).where(BadCase.project_id == project_id).group_by(BadCase.status)

        tag_stmt = select(
            BadCase.tag,
            func.count().label("cnt"),
        ).where(BadCase.project_id == project_id).group_by(BadCase.tag)

        status_result, tag_result = await asyncio.gather(
            db.execute(status_stmt),
            db.execute(tag_stmt),
        )

        by_status: dict[str, int] = {}
        total = 0
        for row in status_result:
            by_status[row.status] = row.cnt
            total += row.cnt

        # 未出现在数据库中的状态补 0
        for s in ("open", "in_progress", "resolved", "closed"):
            by_status.setdefault(s, 0)

        by_tag: dict[str, int] = {}
        for row in tag_result:
            by_tag[row.tag] = row.cnt

        # 未出现在数据库中的标签补 0
        for t in ("hallucination", "error", "omission", "timeout", "other"):
            by_tag.setdefault(t, 0)

        return {
            "total": total,
            "by_status": by_status,
            "by_tag": by_tag,
        }


# ==================== 内部工具 ====================

def _validate_transition(
    from_status: BadCaseStatus,
    to_status: BadCaseStatus,
) -> None:
    """校验状态流转合法性"""
    allowed = VALID_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise ValidationException(
            f"不允许的状态流转: {from_status.value} → {to_status.value}"
        )