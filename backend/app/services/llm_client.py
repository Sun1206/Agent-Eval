"""
LLM 客户端抽象层 — 多 Provider 统一接口

支持 Provider:
  - DASHSCOPE: 通义千问（DashScope API）
  - DEEPSEEK:  DeepSeek（OpenAI 兼容协议）

用法:
    from app.services.llm_client import LLMProvider, get_llm_client

    client = get_llm_client(LLMProvider.DEEPSEEK, api_key="sk-xxx")
    result = await client.chat_completion(messages=[...], model="deepseek-chat")
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# 默认超时 + 重试配置
DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 2
RETRY_DELAY_BASE = 1.0


class LLMProvider(str, Enum):
    """LLM 提供商枚举"""
    DASHSCOPE = "dashscope"
    DEEPSEEK = "deepseek"
    OPENAI = "openai"


# ==================== 抽象基类 ====================

class BaseLLMClient(ABC):
    """LLM 客户端抽象基类"""

    def __init__(self, api_key: str, base_url: str = "", model: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = model
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_http(self) -> httpx.AsyncClient:
        """惰性创建 httpx 客户端"""
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(DEFAULT_TIMEOUT))
        return self._http

    @abstractmethod
    def _build_request(self, messages: list[dict], model: str, temperature: float, **kwargs) -> dict:
        """构建请求体（子类实现）"""
        ...

    @abstractmethod
    def _get_headers(self) -> dict:
        """构建请求头（子类实现）"""
        ...

    @abstractmethod
    def _get_url(self) -> str:
        """获取 API 端点 URL（子类实现）"""
        ...

    @abstractmethod
    def _parse_response(self, response_data: dict) -> str:
        """从响应中提取文本内容（子类实现）"""
        ...

    async def chat_completion(
        self,
        messages: list[dict],
        model: str = "",
        temperature: float = 0.3,
        response_format: Optional[dict] = None,
    ) -> str:
        """
        调用 LLM 聊天补全（含重试）

        Args:
            messages:        消息列表 [{"role": "system", "content": "..."}, ...]
            model:           模型名（为空时使用默认模型）
            temperature:     温度参数
            response_format: 响应格式，如 {"type": "json_object"} 强制 JSON 输出

        Returns:
            LLM 返回的文本内容
        """
        model = model or self.default_model
        request_body = self._build_request(messages, model, temperature, response_format=response_format)

        http = await self._get_http()
        url = self._get_url()
        headers = self._get_headers()

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await http.post(url, json=request_body, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = self._parse_response(data)
                return content
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"LLM 调用失败 (provider={self.__class__.__name__}, "
                    f"status={e.response.status_code}), "
                    f"尝试 {attempt + 1}/{MAX_RETRIES + 1}"
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
            except Exception as e:
                logger.warning(
                    f"LLM 调用异常 (provider={self.__class__.__name__}): {e}, "
                    f"尝试 {attempt + 1}/{MAX_RETRIES + 1}"
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))

        raise Exception(f"LLM 调用最终失败 ({self.__class__.__name__}), 已重试 {MAX_RETRIES} 次")

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._http:
            await self._http.aclose()
            self._http = None


# ==================== DashScope 客户端（通义千问） ====================

class DashScopeClient(BaseLLMClient):
    """通义千问 DashScope API 客户端"""

    DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    def __init__(self, api_key: str = "", model: str = "qwen-plus"):
        settings = get_settings()
        api_key = api_key or settings.dashscope_api_key or ""
        super().__init__(api_key=api_key, base_url=self.DASHSCOPE_URL, model=model)

    def _get_url(self) -> str:
        return self.DASHSCOPE_URL

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_request(self, messages: list[dict], model: str, temperature: float, **kwargs) -> dict:
        return {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

    def _parse_response(self, response_data: dict) -> str:
        choices = response_data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""


# ==================== DeepSeek 客户端（OpenAI 兼容协议） ====================

class DeepSeekClient(BaseLLMClient):
    """DeepSeek API 客户端（OpenAI 兼容协议）"""

    def __init__(self, api_key: str = "", model: str = "deepseek-chat"):
        settings = get_settings()
        api_key = api_key or settings.deepseek_api_key or ""
        base_url = settings.deepseek_base_url
        super().__init__(api_key=api_key, base_url=base_url, model=model)

    def _get_url(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_request(self, messages: list[dict], model: str, temperature: float, **kwargs) -> dict:
        return {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

    def _parse_response(self, response_data: dict) -> str:
        choices = response_data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""


# ==================== OpenAI 客户端 ====================

class OpenAIClient(BaseLLMClient):
    """OpenAI API 客户端（支持 gpt-4o-mini 等模型，兼容第三方代理）"""

    def __init__(self, api_key: str = "", model: str = ""):
        settings = get_settings()
        api_key = api_key or settings.openai_api_key or ""
        base_url = settings.openai_base_url.rstrip("/")
        model = model or settings.openai_default_model
        super().__init__(api_key=api_key, base_url=base_url, model=model)

    def _get_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_request(self, messages: list[dict], model: str, temperature: float, **kwargs) -> dict:
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        # OpenAI 支持 response_format 强制 JSON 输出
        response_format = kwargs.get("response_format")
        if response_format:
            body["response_format"] = response_format
        return body

    def _parse_response(self, response_data: dict) -> str:
        choices = response_data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""


# ==================== 工厂函数 ====================

_PROVIDER_MAP = {
    LLMProvider.DASHSCOPE: DashScopeClient,
    LLMProvider.DEEPSEEK: DeepSeekClient,
    LLMProvider.OPENAI: OpenAIClient,
}

# 客户端缓存池：按 (provider, model) 缓存实例，避免每次评分新建客户端+连接泄漏
_client_pool: dict[tuple, BaseLLMClient] = {}
_MAX_POOL_SIZE = 20  # 池大小上限，防止无限增长


def get_llm_client(
    provider: LLMProvider | str,
    api_key: str = "",
    model: str = "",
) -> BaseLLMClient:
    """
    获取 LLM 客户端实例（池化，按 provider+model 缓存）

    Args:
        provider: 提供商 (dashscope / deepseek)
        api_key:  API Key（为空时从配置读取）
        model:    模型名（为空时使用默认模型）

    Returns:
        BaseLLMClient 子类实例

    Raises:
        ValueError: 不支持的 provider
    """
    if isinstance(provider, str):
        provider = LLMProvider(provider)

    client_cls = _PROVIDER_MAP.get(provider)
    if client_cls is None:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")

    # 池化 key：同一 provider + model 复用同一客户端
    cache_key = (provider, model or "")
    cached = _client_pool.get(cache_key)
    if cached is not None and isinstance(cached, client_cls):
        return cached

    # 池满时，关闭最早创建的客户端并移除
    if len(_client_pool) >= _MAX_POOL_SIZE:
        oldest_key = next(iter(_client_pool))
        oldest_client = _client_pool.pop(oldest_key)
        try:
            import asyncio
            asyncio.get_event_loop().create_task(oldest_client.close())
        except Exception:
            pass

    client = client_cls(api_key=api_key, model=model)
    _client_pool[cache_key] = client
    return client


async def close_all_llm_clients() -> None:
    """关闭所有缓存的 LLM 客户端（应用关闭时调用）"""
    for key, client in _client_pool.items():
        try:
            await client.close()
        except Exception as e:
            logger.warning(f"关闭 LLM 客户端失败 (key={key}): {e}")
    _client_pool.clear()