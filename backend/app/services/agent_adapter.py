"""
Agent 调用适配层 — HTTP 调用被评测 Agent + 超时控制 + 重试

特性:
  - 从数据库加载 Agent 配置（endpoint_url + config）
  - HTTP POST 调用 Agent 服务
  - 120s 超时 + 指数退避重试（最多 2 次）
  - 连通性健康检查

异常类型:
  - AgentTimeoutError:     超时
  - AgentConnectionError:  连接失败
  - AgentResponseError:    响应异常（非 200 或无 output）

用法:
    from app.services.agent_adapter import AgentAdapter

    result = await AgentAdapter.call_agent(agent_id, input_text, db)
    # {"output": "...", "trace_id": "...", "duration_ms": 1234, "token_usage": {}}
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent

logger = logging.getLogger(__name__)

# 配置常量
DEFAULT_TIMEOUT = 120.0       # 默认超时（秒）
MAX_RETRIES = 2               # 最大重试次数
RETRY_BASE_DELAY = 1.0        # 基础退避延迟（秒）: 1s → 3s
RETRY_DELAY_MULTIPLIER = 3.0  # 退避倍率


# ==================== 异常类 ====================

class AgentError(Exception):
    """Agent 调用基础异常"""
    pass


class AgentTimeoutError(AgentError):
    """Agent 调用超时"""
    def __init__(self, agent_id: UUID, endpoint_url: str, timeout: float):
        self.agent_id = agent_id
        self.endpoint_url = endpoint_url
        self.timeout = timeout
        super().__init__(f"Agent 调用超时 ({timeout}s): agent_id={agent_id}, url={endpoint_url}")


class AgentConnectionError(AgentError):
    """Agent 连接失败"""
    def __init__(self, agent_id: UUID, endpoint_url: str, original_error: str = ""):
        self.agent_id = agent_id
        self.endpoint_url = endpoint_url
        self.original_error = original_error
        super().__init__(
            f"Agent 连接失败: agent_id={agent_id}, url={endpoint_url}, error={original_error}"
        )


class AgentResponseError(AgentError):
    """Agent 响应异常（非 200 或无 output）"""
    def __init__(
        self,
        agent_id: UUID,
        endpoint_url: str,
        status_code: int = 0,
        message: str = "",
    ):
        self.agent_id = agent_id
        self.endpoint_url = endpoint_url
        self.status_code = status_code
        super().__init__(
            f"Agent 响应异常 (HTTP {status_code}): agent_id={agent_id}, {message}"
        )


# ==================== 返回数据结构 ====================

@dataclass
class AgentCallResult:
    """Agent 调用返回结构"""
    output: str
    trace_id: Optional[str] = None
    duration_ms: int = 0
    token_usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "output": self.output,
            "trace_id": self.trace_id,
            "duration_ms": self.duration_ms,
            "token_usage": self.token_usage,
        }


# ==================== 适配器 ====================

class AgentAdapter:
    """Agent 调用适配器"""

    # 模块级共享 httpx 客户端，复用 TCP 连接
    _shared_client: Optional[httpx.AsyncClient] = None

    @classmethod
    async def _get_client(cls, timeout: float = DEFAULT_TIMEOUT) -> httpx.AsyncClient:
        """获取或创建共享 httpx 客户端"""
        if cls._shared_client is None or cls._shared_client.is_closed:
            cls._shared_client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
            )
        return cls._shared_client

    @classmethod
    async def close_client(cls) -> None:
        """关闭共享客户端（应用关闭时调用）"""
        if cls._shared_client and not cls._shared_client.is_closed:
            await cls._shared_client.aclose()
            cls._shared_client = None

    @staticmethod
    async def call_agent(
        agent_id: UUID,
        input_text: str,
        db: AsyncSession,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> AgentCallResult:
        """
        调用被评测 Agent

        Args:
            agent_id:   Agent UUID
            input_text: 发送给 Agent 的输入文本
            db:         数据库 session
            timeout:    超时时间（秒）

        Returns:
            AgentCallResult

        Raises:
            AgentTimeoutError:     超时
            AgentConnectionError:  连接失败
            AgentResponseError:    响应异常
        """
        # 1. 查询 Agent 配置
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is None:
            raise AgentResponseError(
                agent_id=agent_id,
                endpoint_url="未知",
                message="Agent 不存在",
            )

        endpoint_url = agent.endpoint_url
        if not endpoint_url:
            raise AgentResponseError(
                agent_id=agent_id,
                endpoint_url="未配置",
                message="Agent 的 endpoint_url 未配置",
            )

        # 2. 构造请求体（去除 auth 等内部字段，避免泄露鉴权信息）
        payload: dict = {"input": input_text}
        if agent.config:
            safe_config = {k: v for k, v in agent.config.items() if k != "auth"}
            if safe_config:
                payload["config"] = safe_config

        # 3. 从 config.auth 提取鉴权头
        headers = AgentAdapter._build_auth_headers(agent.config)

        # 4. HTTP 调用（含重试）
        return await AgentAdapter._call_with_retry(
            agent_id=agent_id,
            endpoint_url=endpoint_url,
            payload=payload,
            timeout=timeout,
            headers=headers,
        )

    @staticmethod
    def _build_auth_headers(config: Optional[dict]) -> dict[str, str]:
        """
        从 Agent config 中提取鉴权头

        支持的 config.auth 格式:
          {
            "auth": {
              "type": "bearer",          # Bearer Token 鉴权
              "token": "xxx"
            }
          }
          {
            "auth": {
              "type": "api_key",         # API Key 鉴权
              "key": "xxx",
              "header_name": "X-API-Key"  # 可选，默认 X-API-Key
            }
          }
          {
            "auth": {
              "type": "custom",          # 自定义请求头
              "headers": {"X-Custom": "value"}
            }
          }
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

    @staticmethod
    async def health_check_agent(
        agent_id: UUID,
        db: AsyncSession,
    ) -> dict:
        """
        Agent 连通性健康检查

        Args:
            agent_id: Agent UUID
            db:       数据库 session

        Returns:
            {"healthy": True/False, "latency_ms": 123, "error": None/"..."}
        """
        result_data = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result_data.scalar_one_or_none()
        if agent is None:
            return {"healthy": False, "latency_ms": None, "error": "Agent 不存在"}

        endpoint_url = agent.endpoint_url
        if not endpoint_url:
            return {"healthy": False, "latency_ms": None, "error": "endpoint_url 未配置"}

        t_start = time.monotonic()
        try:
            client = await AgentAdapter._get_client(timeout=10.0)
            response = await client.get(endpoint_url)
            response.raise_for_status()
            latency_ms = int((time.monotonic() - t_start) * 1000)
            return {"healthy": True, "latency_ms": latency_ms, "error": None}
        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            return {"healthy": False, "latency_ms": latency_ms, "error": "连接超时"}
        except Exception as e:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            return {"healthy": False, "latency_ms": latency_ms, "error": str(e)[:200]}

    # ==================== 内部方法 ====================

    @staticmethod
    async def _call_with_retry(
        agent_id: UUID,
        endpoint_url: str,
        payload: dict,
        timeout: float,
        headers: Optional[dict[str, str]] = None,
    ) -> AgentCallResult:
        """带重试的 HTTP 调用"""
        last_error: Optional[Exception] = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                return await AgentAdapter._do_call(
                    agent_id, endpoint_url, payload, timeout, headers
                )
            except AgentTimeoutError as e:
                last_error = e
                logger.warning(
                    f"Agent 超时: agent_id={agent_id}, "
                    f"尝试 {attempt + 1}/{MAX_RETRIES + 1}"
                )
            except AgentConnectionError as e:
                last_error = e
                logger.warning(
                    f"Agent 连接失败: agent_id={agent_id}, "
                    f"尝试 {attempt + 1}/{MAX_RETRIES + 1}, error={e.original_error}"
                )
            except AgentResponseError as e:
                # 4xx 不重试（如 400/404），5xx 重试
                if 400 <= e.status_code < 500:
                    raise
                last_error = e
                logger.warning(
                    f"Agent 响应异常 (HTTP {e.status_code}): agent_id={agent_id}, "
                    f"尝试 {attempt + 1}/{MAX_RETRIES + 1}"
                )

            # 指数退避
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (RETRY_DELAY_MULTIPLIER ** attempt)
                logger.debug(f"Agent 重试等待 {delay}s...")
                await asyncio.sleep(delay)

        # 所有重试失败
        if last_error:
            raise last_error
        raise AgentConnectionError(
            agent_id=agent_id,
            endpoint_url=endpoint_url,
            original_error="重试耗尽",
        )

    @staticmethod
    async def _do_call(
        agent_id: UUID,
        endpoint_url: str,
        payload: dict,
        timeout: float,
        headers: Optional[dict[str, str]] = None,
    ) -> AgentCallResult:
        """执行单次 HTTP 调用（复用共享 httpx 客户端）"""
        t_start = time.monotonic()

        try:
            client = await AgentAdapter._get_client(timeout)
            response = await client.post(endpoint_url, json=payload, headers=headers)
        except httpx.TimeoutException:
            duration_ms = int((time.monotonic() - t_start) * 1000)
            raise AgentTimeoutError(agent_id, endpoint_url, timeout)
        except httpx.ConnectError as e:
            duration_ms = int((time.monotonic() - t_start) * 1000)
            raise AgentConnectionError(agent_id, endpoint_url, str(e))
        except httpx.RequestError as e:
            duration_ms = int((time.monotonic() - t_start) * 1000)
            raise AgentConnectionError(agent_id, endpoint_url, str(e))

        duration_ms = int((time.monotonic() - t_start) * 1000)

        # 检查 HTTP 状态码
        if response.status_code >= 400:
            body_preview = response.text[:300] if response.text else "无响应体"
            raise AgentResponseError(
                agent_id=agent_id,
                endpoint_url=endpoint_url,
                status_code=response.status_code,
                message=f"{response.reason_phrase}: {body_preview}",
            )

        # 解析 JSON 响应
        try:
            data = response.json()
        except Exception:
            raise AgentResponseError(
                agent_id=agent_id,
                endpoint_url=endpoint_url,
                status_code=response.status_code,
                message="响应体不是有效的 JSON",
            )

        # 校验 output 字段
        output = data.get("output") or data.get("result") or data.get("response")
        if output is None:
            raise AgentResponseError(
                agent_id=agent_id,
                endpoint_url=endpoint_url,
                status_code=response.status_code,
                message="响应中缺少 output 字段",
            )

        return AgentCallResult(
            output=str(output),
            trace_id=str(data.get("trace_id")) if data.get("trace_id") else None,
            duration_ms=duration_ms,
            token_usage=data.get("token_usage") or {},
        )