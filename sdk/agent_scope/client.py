"""
TraceCollector — 异步 Trace 上报客户端

特性:
  - httpx 异步连接池
  - 攒批上报（攒够 10 条或 5 秒超时自动 flush）
  - 失败重试（最多 3 次）
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from agent_scope.models import Trace

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_ENDPOINT = "http://localhost:8000/api/v1/sdk/traces"
DEFAULT_BATCH_SIZE = 10
DEFAULT_FLUSH_INTERVAL = 5  # 秒
DEFAULT_MAX_RETRIES = 3


class TraceCollector:
    """异步 Trace 收集与上报器"""

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
    ):
        """
        Args:
            endpoint:      Trace 上报 API 地址
            api_key:       API Key（agev_ 前缀）
            project_id:    默认项目 UUID
            agent_id:      默认 Agent UUID
            batch_size:    攒批大小
            flush_interval: 定时刷新间隔（秒）
        """
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.default_project_id = project_id
        self.default_agent_id = agent_id
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # 缓冲区
        self._buffer: list[Trace] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None

        # httpx 异步客户端（惰性创建）
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_http(self) -> httpx.AsyncClient:
        """获取或创建 httpx 客户端"""
        if self._http is None:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            self._http = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(30.0),
            )
            # 启动定时 flush 任务
            self._flush_task = asyncio.create_task(self._background_flush())
        return self._http

    # ==================== 上报方法 ====================

    async def report_trace(self, trace: Trace) -> None:
        """
        异步上报单条 Trace（加入缓冲区，不阻塞调用方）

        Args:
            trace: Trace 数据对象
        """
        # 填充默认值
        if not trace.project_id and self.default_project_id:
            trace.project_id = self.default_project_id
        if not trace.agent_id and self.default_agent_id:
            trace.agent_id = self.default_agent_id

        async with self._lock:
            self._buffer.append(trace)
            if len(self._buffer) >= self.batch_size:
                await self._do_flush()

    async def flush(self) -> None:
        """强制刷新缓冲区"""
        async with self._lock:
            await self._do_flush()

    # ==================== 内部方法 ====================

    async def _do_flush(self) -> None:
        """执行一次 flush（需在 _lock 内调用）"""
        if not self._buffer:
            return

        batch = self._buffer.copy()
        self._buffer.clear()

        # 在锁外发送请求
        await self._send_batch(batch)

    async def _send_batch(self, batch: list[Trace]) -> None:
        """发送批量 Trace 到服务端"""
        if not batch:
            return

        http = await self._get_http()
        url = f"{self.endpoint}/batch" if self.endpoint.endswith("/traces") else f"{self.endpoint}/traces/batch"

        payload = [t.to_dict() for t in batch]

        for attempt in range(DEFAULT_MAX_RETRIES):
            try:
                response = await http.post(url, json=payload)
                response.raise_for_status()
                logger.debug(f"Trace 批量上报成功: {len(batch)} 条")
                return
            except httpx.HTTPStatusError as e:
                logger.warning(f"Trace 上报失败 (HTTP {e.response.status_code}), 尝试 {attempt + 1}/{DEFAULT_MAX_RETRIES}")
                if attempt < DEFAULT_MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.warning(f"Trace 上报异常: {e}, 尝试 {attempt + 1}/{DEFAULT_MAX_RETRIES}")
                if attempt < DEFAULT_MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)

        logger.error(f"Trace 上报最终失败, 丢弃 {len(batch)} 条数据")

    async def _background_flush(self) -> None:
        """后台定时 flush"""
        while True:
            await asyncio.sleep(self.flush_interval)
            async with self._lock:
                await self._do_flush()

    # ==================== 生命周期 ====================

    async def close(self) -> None:
        """关闭客户端，flush 剩余数据"""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        await self.flush()

        if self._http:
            await self._http.aclose()
            self._http = None