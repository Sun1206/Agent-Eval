"""
评测执行引擎 — asyncio 后台异步逐条执行

流程:
  PENDING -> RUNNING -> 逐条(Agent调用->Judge评分->结果写入) -> 计算统计 -> COMPLETED/FAILED

性能优化要点:
  - 共享 httpx.AsyncClient，复用 TCP 连接
  - 原子更新进度，避免 N+1 查询
  - SQL 聚合计算统计，避免全量加载到内存
  - 只查询一次 EvalRun，避免重复查询
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import httpx
from sqlalchemy import and_, select, update, func, case
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import load_only

from app.core.database import get_session_factory
from app.models.agent import Agent
from app.models.dataset import DatasetItem
from app.models.evaluation import EvalRun, EvalResult
from app.schemas.evaluation import JudgeConfigSchema
from app.services.judge_service import JudgeService

logger = logging.getLogger(__name__)

# 配置常量
ITEM_TIMEOUT = 120  # 单条用例超时（秒）
MAX_CONSECUTIVE_FAILURES = 5  # 连续失败上限

# ClickHouse 写入锁（clickhouse_connect 不支持同一客户端并发查询）
_ch_lock = asyncio.Lock()


async def execute_eval_run(
    run_id: UUID,
    session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
) -> None:
    """
    主执行函数 — 作为后台任务运行

    Args:
        run_id:          评测任务 ID
        session_factory: db session 工厂（为空则使用全局工厂）
    """
    factory = session_factory or get_session_factory()

    # Step 1: 加载评测任务信息（只查一次）
    async with factory() as db:
        eval_run = await db.get(EvalRun, run_id)
        if eval_run is None:
            logger.error(f"评测任务不存在: {run_id}")
            return

        dataset_id = eval_run.dataset_id
        agent_id = eval_run.agent_id
        project_id = eval_run.project_id
        judge_config_raw = eval_run.judge_config
        concurrency = eval_run.concurrency

        # 加载数据集条目（只加载必要字段，避免加载 tags/metadata 等大字段）
        result = await db.execute(
            select(DatasetItem)
            .options(load_only(
                DatasetItem.id,
                DatasetItem.sort_order,
                DatasetItem.input,
                DatasetItem.expected_output,
                DatasetItem.context,
            ))
            .where(DatasetItem.dataset_id == dataset_id)
            .order_by(DatasetItem.sort_order.asc(), DatasetItem.created_at.asc())
        )
        dataset_items = list(result.scalars().all())

        # 加载 Agent
        agent = await db.get(Agent, agent_id) if agent_id else None

    # Step 2: 更新状态为 RUNNING
    await _update_run_status(factory, run_id, "RUNNING", started_at=datetime.now(timezone.utc))

    total_items = len(dataset_items)

    if total_items == 0:
        await _update_run_status(factory, run_id, "COMPLETED", completed_at=datetime.now(timezone.utc))
        return

    logger.info(f"评测任务开始: run_id={run_id}, total={total_items}, concurrency={concurrency}")

    # Step 3: 逐条执行（共享 httpx 客户端，复用 TCP 连接）
    semaphore = asyncio.Semaphore(concurrency)
    failures = {"consecutive": 0, "total": 0}

    async with httpx.AsyncClient(timeout=httpx.Timeout(100)) as http_client:

        async def process_item(idx: int, item: DatasetItem) -> None:
            """处理单条用例（在 semaphore 控制下并发执行）"""
            order = item.sort_order or idx + 1
            async with semaphore:
                await _process_single_item(
                    factory, run_id, project_id, item, agent, judge_config_raw,
                    order, failures, http_client,
                )

        # 并发处理所有条目
        tasks = [process_item(i, item) for i, item in enumerate(dataset_items)]
        await asyncio.gather(*tasks, return_exceptions=True)

    # Step 4: 计算统计并更新（SQL 聚合，不加载全量数据）
    await _finalize_eval_run(factory, run_id, failures)


async def execute_single_item(
    run_id: UUID,
    dataset_item_id: UUID,
    sort_order: int,
    session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
) -> None:
    """
    单条结果重试 — 重新执行指定条目的评测

    流程: 加载任务信息 -> 调用 Agent -> Judge 评分 -> 写入结果 -> 更新统计
    """
    factory = session_factory or get_session_factory()

    async with factory() as db:
        eval_run = await db.get(EvalRun, run_id)
        if eval_run is None:
            logger.error(f"评测任务不存在: run_id={run_id}")
            return

        project_id = eval_run.project_id
        agent_id = eval_run.agent_id
        judge_config_raw = eval_run.judge_config

        item = await db.get(DatasetItem, dataset_item_id)
        if item is None:
            logger.error(f"数据集条目不存在: item_id={dataset_item_id}")
            return

        agent = await db.get(Agent, agent_id) if agent_id else None

    failures = {"consecutive": 0, "total": 0}

    async with httpx.AsyncClient(timeout=httpx.Timeout(100)) as http_client:
        await _process_single_item(
            factory, run_id, project_id, item, agent, judge_config_raw,
            sort_order, failures, http_client,
        )

    # 重新计算统计
    await _finalize_eval_run(factory, run_id, failures)


# ==================== 单条处理 ====================

async def _process_single_item(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    project_id: UUID,
    item: DatasetItem,
    agent: Optional[Agent],
    judge_config_raw: dict,
    order: int,
    failures: dict,
    http_client: httpx.AsyncClient,
) -> None:
    """
    处理单条评测

    流程: Agent 调用 -> 自动生成 Trace -> Judge 评分 -> 写入结果 -> 原子更新进度
    单条失败不阻塞整体流程。
    """
    result_status = "SUCCESS"
    agent_output = ""
    agent_trace_id = None
    total_score = 0.0
    dimension_scores = {}
    judge_reason = ""
    error_message = None
    duration_ms = 0
    t_start = time.monotonic()
    trace_start_time = datetime.now(timezone.utc)

    try:
        # 1. 调用 Agent（120s 超时），获取 output 和 trace_id
        agent_result = await asyncio.wait_for(
            _call_agent(http_client, agent.endpoint_url if agent else None, item.input, item.context, agent.config if agent else {}),
            timeout=ITEM_TIMEOUT,
        )
        agent_output = agent_result.output
        agent_trace_id = agent_result.trace_id

        # 2. 自动生成 Trace 写入 ClickHouse（无论 Agent 是否返回 trace_id）
        #    使用全局锁串行化 ClickHouse 写入，避免并发查询冲突
        trace_end_time = datetime.now(timezone.utc)
        agent_duration_ms = int((trace_end_time - trace_start_time).total_seconds() * 1000)
        generated_trace_id = agent_trace_id or str(uuid4())
        async with _ch_lock:
            await _write_eval_trace(
                trace_id=generated_trace_id,
                project_id=project_id,
                agent_id=agent.id if agent else None,
                input_text=item.input or "",
                output_text=agent_output,
                start_time=trace_start_time,
                end_time=trace_end_time,
                duration_ms=agent_duration_ms,
                status="SUCCESS",
            )
        # 使用生成的 trace_id（确保始终有值）
        agent_trace_id = generated_trace_id

        # 3. 调用 Judge 评分
        judge_config_obj = JudgeConfigSchema(**judge_config_raw)
        rating = await JudgeService.judge(
            input_text=item.input or "",
            agent_output=agent_output,
            expected_output=item.expected_output or "",
            judge_config=judge_config_obj,
        )
        total_score = rating.total_score
        dimension_scores = rating.dimension_scores
        judge_reason = rating.reason

        logger.info(
            f"用例评分完成: run_id={run_id}, item_id={item.id}, "
            f"total_score={total_score}, dimension_scores={dimension_scores}"
        )

        # 4. 重置连续失败计数
        failures["consecutive"] = 0

    except asyncio.TimeoutError:
        result_status = "TIMEOUT"
        error_message = f"Agent 调用超时（{ITEM_TIMEOUT}s）"
        failures["consecutive"] += 1
        failures["total"] += 1
        logger.warning(f"用例超时: run_id={run_id}, item_id={item.id}")
    except Exception as e:
        result_status = "ERROR"
        error_message = str(e)[:500]
        failures["consecutive"] += 1
        failures["total"] += 1
        logger.warning(f"用例执行失败: run_id={run_id}, item_id={item.id}, error={e}")

    duration_ms = int((time.monotonic() - t_start) * 1000)

    # trace_id 安全解析为 UUID
    trace_id: Optional[UUID] = None
    if agent_trace_id:
        try:
            trace_id = UUID(agent_trace_id)
        except (ValueError, TypeError):
            logger.warning(
                f"Agent 返回的 trace_id 无法解析为 UUID，已忽略: "
                f"run_id={run_id}, item_id={item.id}, trace_id_raw={agent_trace_id}"
            )

    # 5. 写入评测结果 + 原子更新进度（独立 session）
    async with factory() as db:
        eval_result = EvalResult(
            eval_run_id=run_id,
            dataset_item_id=item.id,
            sort_order=order,
            agent_input=item.input or "",
            agent_output=agent_output,
            total_score=total_score,
            dimension_scores=dimension_scores,
            judge_reason=judge_reason,
            status=result_status,
            error_message=error_message,
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
        db.add(eval_result)

        # 原子更新进度（合并为一次 UPDATE，避免失败用例时执行两次 UPDATE）
        update_values: dict = {"completed_items": EvalRun.completed_items + 1}
        if result_status in ("ERROR", "FAILURE", "TIMEOUT"):
            update_values["failed_items"] = EvalRun.failed_items + 1
        await db.execute(
            update(EvalRun)
            .where(EvalRun.id == run_id)
            .values(**update_values)
        )
        await db.commit()

    # 6. 检查是否需要终止（连续失败 > 上限）
    if failures["consecutive"] >= MAX_CONSECUTIVE_FAILURES:
        logger.error(
            f"评测任务终止: run_id={run_id}, "
            f"连续失败 {failures['consecutive']} 次，超过上限 {MAX_CONSECUTIVE_FAILURES}"
        )
        raise _AbortEvaluationException(f"连续失败 {failures['consecutive']} 次")


class _AbortEvaluationException(Exception):
    """内部异常：评测需要终止（被 gather 捕获后处理）"""
    pass


# ==================== Agent 调用结果 ====================

class _AgentCallResult:
    """Agent 调用返回结构（eval_executor 内部使用）"""
    __slots__ = ("output", "trace_id")

    def __init__(self, output: str, trace_id: Optional[str] = None):
        self.output = output
        self.trace_id = trace_id


# ==================== Agent 调用 ====================

async def _call_agent(
    http_client: httpx.AsyncClient,
    endpoint_url: Optional[str],
    input_text: str,
    context: Optional[str],
    config: dict,
) -> _AgentCallResult:
    """调用 Agent 服务获取输出和 trace_id（复用 httpx 客户端）"""
    if not endpoint_url:
        # 无 endpoint 时使用 mock 输出（便于开发调试）
        logger.warning("Agent 无 endpoint_url，返回 mock 输出")
        return _AgentCallResult(
            output=f"[Mock] Agent 对输入 '{input_text[:50]}' 的模拟输出",
        )

    payload = {
        "input": input_text,
    }
    if context:
        payload["context"] = context
    # 去除 auth 等内部字段，避免泄露鉴权信息
    if config:
        safe_config = {k: v for k, v in config.items() if k != "auth"}
        if safe_config:
            payload["config"] = safe_config

    # 从 config.auth 提取鉴权头
    headers = _build_auth_headers(config)

    # 复用传入的 http_client，避免每次新建 TCP 连接
    response = await http_client.post(endpoint_url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()

    # 解析 output
    output = ""
    if "output" in data:
        output = str(data["output"])
    elif "result" in data:
        output = str(data["result"])
    elif "response" in data:
        output = str(data["response"])
    else:
        output = str(data)

    # 提取 trace_id
    trace_id = None
    raw_trace_id = data.get("trace_id")
    if raw_trace_id:
        try:
            trace_id = str(raw_trace_id)
        except (ValueError, TypeError):
            logger.warning(f"Agent 返回的 trace_id 无法解析: {raw_trace_id}")

    return _AgentCallResult(output=output, trace_id=trace_id)


# ==================== 辅助函数 ====================

def _build_auth_headers(config: Optional[dict]) -> dict[str, str]:
    """
    从 Agent config 中提取鉴权头

    支持的 config.auth 格式:
      {"auth": {"type": "bearer", "token": "xxx"}}
      {"auth": {"type": "api_key", "key": "xxx", "header_name": "X-API-Key"}}
      {"auth": {"type": "custom", "headers": {"X-Custom": "value"}}}
    """
    if not config:
        return {}
    auth = config.get("auth")
    if not auth or not isinstance(auth, dict):
        return {}

    auth_type = auth.get("type", "")
    headers: dict[str, str] = {}

    if auth_type == "bearer":
        token = auth.get("token", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "api_key":
        key = auth.get("key", "")
        header_name = auth.get("header_name", "X-API-Key")
        if key:
            headers[header_name] = key
    elif auth_type == "custom":
        custom_headers = auth.get("headers", {})
        if isinstance(custom_headers, dict):
            headers.update(custom_headers)

    return headers


async def _update_run_status(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    status: str,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    error_message: Optional[str] = None,
) -> None:
    """更新评测任务状态（原子 UPDATE，避免读-改-写）"""
    values: dict = {"status": status}
    if started_at:
        values["started_at"] = started_at
    if completed_at:
        values["completed_at"] = completed_at
    if error_message:
        values["error_message"] = error_message

    async with factory() as db:
        await db.execute(
            update(EvalRun).where(EvalRun.id == run_id).values(**values)
        )
        await db.commit()


async def _finalize_eval_run(
    factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    failures: dict,
) -> None:
    """评测完成后的统计汇总（SQL 聚合，不加载全量数据到内存）"""
    async with factory() as db:
        run = await db.get(EvalRun, run_id)
        if run is None:
            return

        # SQL 聚合计算平均分和通过率（避免全量加载）
        stats = await db.execute(
            select(
                func.avg(EvalResult.total_score).label("avg_score"),
                func.count().label("success_count"),
                func.sum(
                    case(
                        (EvalResult.total_score >= 60, 1),
                        else_=0,
                    )
                ).label("pass_count"),
            ).where(
                and_(
                    EvalResult.eval_run_id == run_id,
                    EvalResult.status == "SUCCESS",
                )
            )
        )
        row = stats.one()

        logger.info(
            f"SQL 聚合结果: avg_score={row.avg_score}, success_count={row.success_count}, "
            f"pass_count={row.pass_count}, run_id={run_id}"
        )

        if row.success_count and row.success_count > 0:
            run.avg_score = round(float(row.avg_score or 0), 2)
            run.pass_rate = round(float(row.pass_count or 0) / row.success_count, 4)
        else:
            run.avg_score = 0.0
            run.pass_rate = 0.0

        # 确定最终状态
        if failures.get("consecutive", 0) >= MAX_CONSECUTIVE_FAILURES:
            run.status = "FAILED"
            run.error_message = f"连续失败超过 {MAX_CONSECUTIVE_FAILURES} 次，评测终止"
        else:
            run.status = "COMPLETED"

        run.completed_at = datetime.now(timezone.utc)
        await db.commit()

    logger.info(
        f"评测任务完成: run_id={run_id}, status={run.status}, "
        f"total={run.total_items}, completed={run.completed_items}, "
        f"failed={run.failed_items or 0}, avg_score={run.avg_score}, pass_rate={run.pass_rate}"
    )


# ==================== Trace 自动写入 ====================

async def _write_eval_trace(
    trace_id: str,
    project_id: UUID,
    agent_id: Optional[UUID],
    input_text: str,
    output_text: str,
    start_time: datetime,
    end_time: datetime,
    duration_ms: int,
    status: str,
) -> None:
    """
    评测执行时自动生成 Trace 写入 ClickHouse

    这样即使 Agent 未集成 SDK，评测结果中的 trace_id 也能在 ClickHouse 中找到对应数据。
    如果 Agent 已集成 SDK 并返回了 trace_id，则复用该 ID（ClickHouse ReplacingMergeTree 会去重）。
    """
    try:
        from app.core.clickhouse import get_clickhouse
        ch = get_clickhouse()

        # 构造 span 数据（Agent 调用作为根 span）
        span = {
            "span_id": str(uuid4()),
            "parent_span_id": None,
            "type": "chain",
            "name": "agent_call",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "status": "success" if status == "SUCCESS" else "error",
            "input": {"text": input_text[:2000]} if input_text else None,
            "output": {"text": output_text[:2000]} if output_text else None,
            "metadata": {"model": None, "token_usage": None, "cost": None},
        }

        row = {
            "id": str(trace_id),
            "trace_id": str(trace_id),
            "project_id": str(project_id),
            "agent_id": str(agent_id) if agent_id else "",
            "session_id": "",
            "user_id": "eval_system",
            "input": input_text[:10000],
            "output": output_text[:10000],
            "start_time": start_time,
            "end_time": end_time,
            "duration_ms": duration_ms,
            "total_tokens": 0,
            "total_cost": 0,
            "status": status.lower(),
            "spans": json.dumps([span], ensure_ascii=False),
            "tags": json.dumps(["eval"], ensure_ascii=False),
            "metadata": json.dumps({"source": "eval_auto_trace"}, ensure_ascii=False),
            "created_at": datetime.now(timezone.utc),
        }

        await asyncio.to_thread(ch.insert_trace, row)
        logger.debug(f"评测自动写入 Trace: trace_id={trace_id}")

    except Exception as e:
        # Trace 写入失败不影响评测主流程
        logger.warning(f"评测自动写入 Trace 失败（不影响评测）: {e}")
