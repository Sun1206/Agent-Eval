"""
统一响应 Schema + 错误码枚举

所有 API 返回格式:
  成功单体: { "code": 0, "data": {...}, "message": "ok" }
  成功分页: { "code": 0, "data": { "items": [...], "total": N, "page": N, "page_size": N }, "message": "ok" }
  错误:     { "code": 40001, "data": null, "message": "错误描述" }
"""
from enum import IntEnum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field


# ==================== 错误码枚举 ====================

class ResponseCode(IntEnum):
    """统一错误码"""
    # 成功
    SUCCESS = 0

    # 客户端错误 - 参数
    VALIDATION_ERROR = 40001  # 参数校验失败

    # 客户端错误 - 认证
    UNAUTHORIZED = 40101       # 未认证
    TOKEN_EXPIRED = 40102      # Token 过期

    # 客户端错误 - 权限
    FORBIDDEN = 40301          # 无权限

    # 客户端错误 - 资源
    NOT_FOUND = 40401          # 资源不存在
    CONFLICT = 40901           # 资源冲突

    # 客户端错误 - 文件
    FILE_TOO_LARGE = 41301     # 文件过大

    # 服务端错误
    INTERNAL_ERROR = 50001     # 服务器内部错误
    SERVICE_UNAVAILABLE = 50002  # 服务不可用


# ==================== 分页数据 ====================

class PaginationData(BaseModel):
    """分页数据结构"""
    items: list[Any] = Field(default_factory=list, description="数据列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")


# ==================== 统一响应 ====================

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """统一响应基类"""
    code: int = Field(default=ResponseCode.SUCCESS, description="业务状态码")
    data: Optional[T] = Field(default=None, description="响应数据")
    message: str = Field(default="ok", description="提示信息")

    @classmethod
    def ok(cls, data: T, message: str = "ok") -> "BaseResponse[T]":
        """成功响应（单体数据）"""
        return cls(code=ResponseCode.SUCCESS, data=data, message=message)

    @classmethod
    def paginated(
        cls,
        items: list[Any],
        total: int,
        page: int,
        page_size: int,
        message: str = "ok",
    ) -> "BaseResponse[PaginationData]":
        """成功响应（分页数据）"""
        return cls(
            code=ResponseCode.SUCCESS,
            data=PaginationData(items=items, total=total, page=page, page_size=page_size),
            message=message,
        )

    @classmethod
    def error(cls, code: ResponseCode, message: str) -> "BaseResponse[None]":
        """错误响应"""
        return cls(code=code, data=None, message=message)