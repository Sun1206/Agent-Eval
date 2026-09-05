"""
评测服务 — 创建 / 列表 / 详情 / 取消
"""
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.core.exceptions import NotFoundException, ValidationException
from app.models.dataset import Dataset, DatasetItem
from app.models.evaluation import EvalRun, EvalResult
from app.models.user import User
from app.schemas.evaluation import (
    EvalRunCreate,
    EvalRunDetail,
    EvalRunListItem,
    EvalResultItem,
    EvalStatsResponse,
    EvalProgressResponse,
    JudgeConfigSchema,
)

logger = logging.getLogger(__name__)

# 合法状态流转规则
VALID_CANCEL_STATUSES = {"RUNNING"}


class EvalService:
    """评测任务服务"""

    # ==================== 创建 ====================

    @staticmethod
    async def create_eval_run(
        project_id: UUID,
        data: EvalRunCreate,
        db: AsyncSession,
        current_user: User,
    ) -> EvalRunDetail:
        """创建评测任务"""
        # 并行校验 dataset + 统计条目数 + 校验 agent（3 次查询并行化）
        from app.models.agent import Agent

        dataset_stmt = select(Dataset).where(
            and_(
                Dataset.id == data.dataset_id,
                Dataset.project_id == project_id,
            )
        )
        count_stmt = select(func.count()).where(
            DatasetItem.dataset_id == data.dataset_id,
        )
        agent_stmt = select(Agent).where(
            and_(
                Agent.id == data.agent_id,
                Agent.project_id == project_id,
            )
        )

        dataset_result, count_result, agent_result = await asyncio.gather(
            db.execute(dataset_stmt),
            db.execute(count_stmt),
            db.execute(agent_stmt),
        )

        dataset = dataset_result.scalar_one_or_none()
        if dataset is None:
            raise NotFoundException("数据集")

        total_items = count_result.scalar() or 0
        if total_items == 0:
            raise ValidationException("数据集无可用条目，无法创建评测任务")

        agent = agent_result.scalar_one_or_none()
        if agent is None:
            raise NotFoundException("Agent")

        # 生成名称
        name = data.name or f"评测-{dataset.name}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        run = EvalRun(
            project_id=project_id,
            dataset_id=data.dataset_id,
            agent_id=data.agent_id,
            name=name,
            status="PENDING",
            judge_config=data.judge_config.model_dump(),
            concurrency=data.concurrency,
            total_items=total_items,
            completed_items=0,
            failed_items=0,
            created_by=current_user.id,
        )
        db.add(run)
        await db.flush()
        await db.refresh(run)

        # 异步启动评测执行（后台任务）
        _schedule_eval_execution(run.id, None)

        return EvalRunDetail.model_validate(run)

    # ==================== 列表 ====================

    @staticmethod
    async def get_eval_runs(
        project_id: UUID,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[EvalRunListItem], int]:
        """分页查询评测任务列表"""
        # 并行执行 count + data 查询（列表页排除 judge_config/error_message 大字段）
        offset = (page - 1) * page_size
        count_stmt = select(func.count()).where(EvalRun.project_id == project_id)
        data_stmt = (
            select(EvalRun)
            .options(load_only(
                EvalRun.id,
                EvalRun.project_id,
                EvalRun.dataset_id,
                EvalRun.agent_id,
                EvalRun.name,
                EvalRun.status,
                EvalRun.concurrency,
                EvalRun.total_items,
                EvalRun.completed_items,
                EvalRun.failed_items,
                EvalRun.avg_score,
                EvalRun.pass_rate,
                EvalRun.created_at,
                EvalRun.started_at,
                EvalRun.completed_at,
                EvalRun.created_by,
            ))
            .where(EvalRun.project_id == project_id)
            .order_by(EvalRun.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        total_result, data_result = await asyncio.gather(
            db.scalar(count_stmt),
            db.execute(data_stmt),
        )
        total = total_result or 0
        runs = data_result.scalars().all()

        items = [EvalRunListItem.model_validate(r) for r in runs]
        return items, total

    # ==================== 详情 ====================

    @staticmethod
    async def get_eval_run_detail(
        run_id: UUID,
        db: AsyncSession,
    ) -> EvalRunDetail:
        """查询评测任务详情"""
        result = await db.execute(
            select(EvalRun).where(EvalRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundException("评测任务")

        return EvalRunDetail.model_validate(run)

    # ==================== 取消 ====================

    @staticmethod
    async def cancel_eval_run(
        run_id: UUID,
        db: AsyncSession,
    ) -> EvalRunDetail:
        """
        取消评测任务

        仅有 RUNNING 状态可以取消。
        """
        result = await db.execute(
            select(EvalRun).where(EvalRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundException("评测任务")

        if run.status not in VALID_CANCEL_STATUSES:
            raise ValidationException(
                f"仅允许取消运行中的评测任务，当前状态: {run.status}"
            )

        run.status = "CANCELLED"
        run.completed_at = datetime.now(timezone.utc)

        await db.flush()
        await db.refresh(run)

        return EvalRunDetail.model_validate(run)

    # ==================== 重试 ====================

    # 允许重试的状态
    _RETRYABLE_STATUSES = {"FAILED", "CANCELLED", "PENDING"}

    @staticmethod
    async def retry_eval_run(
        run_id: UUID,
        db: AsyncSession,
    ) -> EvalRunDetail:
        """
        重试评测任务（仅 FAILED/CANCELLED 状态可重试）

        重置进度和状态，删除旧结果，重新调度后台执行。
        """
        result = await db.execute(
            select(EvalRun).where(EvalRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundException("评测任务")

        if run.status not in EvalService._RETRYABLE_STATUSES:
            raise ValidationException(
                f"仅允许重试失败或已取消的评测任务，当前状态: {run.status}"
            )

        # 删除旧结果
        from app.models.evaluation import EvalResult
        await db.execute(
            EvalResult.__table__.delete().where(EvalResult.eval_run_id == run_id)
        )

        # 重置状态
        run.status = "PENDING"
        run.completed_items = 0
        run.failed_items = 0
        run.avg_score = None
        run.pass_rate = None
        run.started_at = None
        run.completed_at = None
        run.error_message = None

        await db.flush()
        await db.refresh(run)

        # 重新调度后台任务
        _schedule_eval_execution(run.id, None)

        return EvalRunDetail.model_validate(run)

    # ==================== 单条结果重试 ====================

    @staticmethod
    async def retry_eval_result(
        result_id: UUID,
        db: AsyncSession,
    ) -> EvalResultItem:
        """
        重试单条评测结果

        仅 ERROR/TIMEOUT/FAILURE 状态可重试。
        删除旧结果，重新调度该条目的后台执行。
        """
        result = await db.get(EvalResult, result_id)
        if result is None:
            raise NotFoundException("评测结果")

        if result.status not in ("ERROR", "TIMEOUT", "FAILURE"):
            raise ValidationException(
                f"仅允许重试失败/错误/超时的结果，当前状态: {result.status}"
            )

        run_id = result.eval_run_id
        sort_order = result.sort_order
        dataset_item_id = result.dataset_item_id

        # 删除旧结果
        await db.delete(result)

        # 更新进度计数（completed_items 不变，failed_items 减 1）
        run = await db.get(EvalRun, run_id)
        if run and run.failed_items and run.failed_items > 0:
            run.failed_items -= 1
            # 回退 completed_items，因为重试后会重新 +1
            if run.completed_items and run.completed_items > 0:
                run.completed_items -= 1
            # 状态改回 RUNNING
            run.status = "RUNNING"
            run.completed_at = None
            run.avg_score = None
            run.pass_rate = None

        await db.flush()

        # 调度单条重试的后台任务
        _schedule_single_item_retry(run_id, dataset_item_id, sort_order)

        # 返回被删除的 result 的基本信息（前端需要知道操作成功）
        return EvalResultItem.model_validate(result)

    # ==================== 删除 ====================

    @staticmethod
    async def delete_eval_run(
        run_id: UUID,
        db: AsyncSession,
    ) -> None:
        """删除评测任务及其结果"""
        result = await db.execute(
            select(EvalRun).where(EvalRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundException("评测任务")

        if run.status == "RUNNING":
            raise ValidationException("运行中的评测任务无法删除，请先取消")

        # 删除关联的评测结果
        from app.models.evaluation import EvalResult
        await db.execute(
            EvalResult.__table__.delete().where(EvalResult.eval_run_id == run_id)
        )

        # 删除评测任务
        await db.delete(run)

    # ==================== 评测结果查询 ====================

    _ALLOWED_RESULT_SORT_FIELDS = {"total_score", "duration_ms", "sort_order"}
    _ALLOWED_SORT_ORDERS = {"asc", "desc"}

    @staticmethod
    async def get_eval_results(
        run_id: UUID,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        sort_by: str = "sort_order",
        sort_order: str = "asc",
    ) -> tuple[list[EvalResultItem], int]:
        """
        分页查询评测结果列表

        Args:
            run_id:     评测任务 ID
            db:         数据库 session
            page:       页码
            page_size:  每页条数
            status:     筛选状态 (SUCCESS/FAILURE/ERROR/TIMEOUT)
            sort_by:    排序字段 (total_score/duration_ms/sort_order)
            sort_order: 排序方向 (asc/desc)
        """
        # 校验评测任务存在
        run = await db.get(EvalRun, run_id)
        if run is None:
            raise NotFoundException("评测任务")

        # 白名单校验
        if sort_by not in EvalService._ALLOWED_RESULT_SORT_FIELDS:
            raise ValidationException(f"不支持的排序字段: {sort_by}")
        if sort_order.lower() not in EvalService._ALLOWED_SORT_ORDERS:
            raise ValidationException(f"不支持的排序方向: {sort_order}")

        # 构建查询条件
        conditions = [EvalResult.eval_run_id == run_id]
        if status:
            conditions.append(EvalResult.status == status.upper())

        # 并行执行 count + data 查询
        offset = (page - 1) * page_size
        sort_col = getattr(EvalResult, sort_by)
        order = sort_col.asc() if sort_order.lower() == "asc" else sort_col.desc()

        count_stmt = select(func.count()).where(and_(*conditions))
        data_stmt = (
            select(EvalResult)
            .where(and_(*conditions))
            .order_by(order)
            .limit(page_size)
            .offset(offset)
        )
        total_result, data_result = await asyncio.gather(
            db.scalar(count_stmt),
            db.execute(data_stmt),
        )
        total = total_result or 0
        rows = data_result.scalars().all()

        items = [EvalResultItem.model_validate(r) for r in rows]
        return items, total

    @staticmethod
    async def get_eval_stats(
        run_id: UUID,
        db: AsyncSession,
    ) -> EvalStatsResponse:
        """
        查询评测统计摘要（单条 SQL 聚合，避免多次查询）
        """
        # 校验评测任务存在
        run = await db.get(EvalRun, run_id)
        if run is None:
            raise NotFoundException("评测任务")

        # 合并为单条 SQL：基础统计 + 通过率 + 得分分布
        stats_result = await db.execute(
            select(
                func.count().label("total_items"),
                func.sum(
                    case((EvalResult.status == "SUCCESS", 1), else_=0)
                ).label("success_items"),
                func.sum(
                    case(
                        (EvalResult.status.in_(["FAILURE", "ERROR", "TIMEOUT"]), 1),
                        else_=0,
                    )
                ).label("failure_items"),
                func.avg(EvalResult.total_score).label("avg_score"),
                func.avg(EvalResult.duration_ms).label("avg_duration_ms"),
                # 通过率（总分 >= 60）
                func.sum(
                    case((EvalResult.total_score >= 60, 1), else_=0)
                ).label("pass_count"),
                # 得分分布
                func.sum(
                    case(
                        (and_(EvalResult.total_score >= 0, EvalResult.total_score <= 20), 1),
                        else_=0,
                    )
                ).label("range_0_20"),
                func.sum(
                    case(
                        (and_(EvalResult.total_score >= 21, EvalResult.total_score <= 40), 1),
                        else_=0,
                    )
                ).label("range_21_40"),
                func.sum(
                    case(
                        (and_(EvalResult.total_score >= 41, EvalResult.total_score <= 60), 1),
                        else_=0,
                    )
                ).label("range_41_60"),
                func.sum(
                    case(
                        (and_(EvalResult.total_score >= 61, EvalResult.total_score <= 80), 1),
                        else_=0,
                    )
                ).label("range_61_80"),
                func.sum(
                    case(
                        (and_(EvalResult.total_score >= 81, EvalResult.total_score <= 100), 1),
                        else_=0,
                    )
                ).label("range_81_100"),
            ).where(EvalResult.eval_run_id == run_id)
        )
        stats = stats_result.one()

        total = stats.total_items or 0
        success = stats.success_items or 0
        failure = stats.failure_items or 0
        pass_count = stats.pass_count or 0
        pass_rate = round(pass_count / total, 4) if total > 0 else 0.0

        return EvalStatsResponse(
            total_items=total,
            success_items=success,
            failure_items=failure,
            pass_rate=pass_rate,
            avg_score=round(float(stats.avg_score), 2) if stats.avg_score else None,
            dimension_avgs={},  # 维度评分在 JSONB 中，暂不聚合
            score_distribution={
                "0-20": stats.range_0_20 or 0,
                "21-40": stats.range_21_40 or 0,
                "41-60": stats.range_41_60 or 0,
                "61-80": stats.range_61_80 or 0,
                "81-100": stats.range_81_100 or 0,
            },
            avg_duration_ms=round(float(stats.avg_duration_ms), 2) if stats.avg_duration_ms else None,
        )

    @staticmethod
    async def get_eval_progress(
        run_id: UUID,
        db: AsyncSession,
    ) -> EvalProgressResponse:
        """查询评测进度"""
        run = await db.get(EvalRun, run_id)
        if run is None:
            raise NotFoundException("评测任务")

        avg_score = float(run.avg_score) if run.avg_score is not None else None
        pass_rate = float(run.pass_rate) if run.pass_rate is not None else None

        return EvalProgressResponse(
            status=run.status,
            total_items=run.total_items or 0,
            completed_items=run.completed_items or 0,
            failed_items=run.failed_items or 0,
            avg_score=avg_score,
            pass_rate=pass_rate,
        )


# ==================== 后台任务调度 ====================

def _schedule_eval_execution(run_id: UUID, session_factory=None) -> None:
    """
    调度评测后台任务（asyncio.create_task）

    在 FastAPI 事件循环中创建后台任务，不阻塞请求响应。
    """
    from app.services.eval_executor import execute_eval_run

    async def _runner():
        try:
            await execute_eval_run(run_id, session_factory)
        except Exception as e:
            logger.error(f"评测后台任务异常: run_id={run_id}, error={e}")
            # 后台异常时更新状态为 FAILED
            try:
                from app.core.database import get_session_factory
                factory = session_factory or get_session_factory()
                async with factory() as db:
                    run = await db.get(EvalRun, run_id)
                    if run and run.status == "RUNNING":
                        run.status = "FAILED"
                        run.error_message = f"后台执行异常: {str(e)[:500]}"
                        run.completed_at = datetime.now(timezone.utc)
                        await db.commit()
            except Exception as inner_e:
                logger.error(f"更新 FAILED 状态失败: {inner_e}")

    task = asyncio.create_task(_runner())
    logger.info(f"评测后台任务已调度: run_id={run_id}, task={task.get_name()}")


def _schedule_single_item_retry(
    run_id: UUID,
    dataset_item_id: UUID,
    sort_order: int,
    session_factory=None,
) -> None:
    """
    调度单条评测结果的重试任务
    """
    from app.services.eval_executor import execute_single_item

    async def _runner():
        try:
            await execute_single_item(run_id, dataset_item_id, sort_order, session_factory)
        except Exception as e:
            logger.error(f"单条重试异常: run_id={run_id}, item_id={dataset_item_id}, error={e}")

    task = asyncio.create_task(_runner())
    logger.info(f"单条重试已调度: run_id={run_id}, item_id={dataset_item_id}, task={task.get_name()}")