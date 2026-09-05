"""
全局异常处理器

将各类异常统一转换为 BaseResponse 错误格式。
"""
import logging
import traceback

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.exceptions import AppException
from app.schemas.common import BaseResponse, ResponseCode

logger = logging.getLogger(__name__)


# ==================== 业务异常处理 ====================

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """处理所有 AppException 及其子类"""
    logger.warning(f"业务异常: code={exc.code}, message={exc.message}, path={request.url.path}")
    response = BaseResponse.error(code=exc.code, message=exc.message)
    return JSONResponse(
        status_code=_get_http_status(exc.code),
        content=response.model_dump(),
    )


# ==================== Pydantic 参数校验异常处理 ====================

async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理 FastAPI 的 RequestValidationError（路径参数/Query/Body 校验失败）"""
    errors = exc.errors()
    # 提取第一个校验错误的 field 和 message
    if errors:
        first_error = errors[0]
        field = " → ".join(str(loc) for loc in first_error.get("loc", []))
        msg = first_error.get("msg", "参数校验失败")
        detail = f"{field}: {msg}"
    else:
        detail = "参数校验失败"

    logger.warning(f"参数校验失败: {detail}, path={request.url.path}")
    response = BaseResponse.error(code=ResponseCode.VALIDATION_ERROR, message=detail)
    return JSONResponse(status_code=422, content=response.model_dump())


async def pydantic_validation_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """处理 Pydantic ValidationError（Service 层手动校验时抛出）"""
    errors = exc.errors()
    if errors:
        first_error = errors[0]
        field = " → ".join(str(loc) for loc in first_error.get("loc", []))
        msg = first_error.get("msg", "参数校验失败")
        detail = f"{field}: {msg}"
    else:
        detail = "参数校验失败"

    logger.warning(f"Pydantic 校验失败: {detail}, path={request.url.path}")
    response = BaseResponse.error(code=ResponseCode.VALIDATION_ERROR, message=detail)
    return JSONResponse(status_code=422, content=response.model_dump())


# ==================== 未知异常兜底 ====================

async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """捕获所有未处理的异常，记录完整堆栈，返回 50001"""
    tb = traceback.format_exc()
    logger.error(f"未处理异常: {type(exc).__name__}: {exc}\n{tb}")

    response = BaseResponse.error(
        code=ResponseCode.INTERNAL_ERROR,
        message="服务器内部错误，请稍后重试",
    )
    return JSONResponse(status_code=500, content=response.model_dump())


# ==================== 辅助函数 ====================

def _get_http_status(code: ResponseCode) -> int:
    """根据业务错误码映射 HTTP 状态码"""
    mapping = {
        ResponseCode.VALIDATION_ERROR: 400,  # 业务校验失败用 400，区别于 FastAPI 的 422
        ResponseCode.UNAUTHORIZED: 401,
        ResponseCode.TOKEN_EXPIRED: 401,
        ResponseCode.FORBIDDEN: 403,
        ResponseCode.NOT_FOUND: 404,
        ResponseCode.CONFLICT: 409,
        ResponseCode.FILE_TOO_LARGE: 413,
        ResponseCode.INTERNAL_ERROR: 500,
        ResponseCode.SERVICE_UNAVAILABLE: 503,
    }
    return mapping.get(code, 400)