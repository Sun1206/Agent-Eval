"""
请求日志中间件

记录每个 HTTP 请求的 method、path、状态码和耗时。
使用纯 ASGI 中间件（非 BaseHTTPMiddleware），性能更好。
"""
import logging
import time

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """请求日志 + 耗时记录中间件"""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # 只记录 HTTP 请求，忽略 WebSocket / Lifespan
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.monotonic()
        status_code = 500  # 默认值

        async def wrapped_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            method = scope.get("method", "UNKNOWN")
            path = scope.get("path", "UNKNOWN")

            log_msg = f"{method} {path} → {status_code} ({duration_ms}ms)"
            if status_code >= 500:
                logger.error(log_msg)
            elif status_code >= 400:
                logger.warning(log_msg)
            else:
                logger.info(log_msg)