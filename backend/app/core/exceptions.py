"""
自定义异常类

使用方式:
    raise AppException(code=ResponseCode.NOT_FOUND, message="用户不存在")
    raise NotFoundException("用户")  # 快捷异常
"""
from app.schemas.common import ResponseCode


class AppException(Exception):
    """应用基础异常，所有业务异常继承此类"""

    def __init__(self, code: ResponseCode, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# ==================== 快捷异常子类 ====================

class ValidationException(AppException):
    """参数校验失败 (40001)"""
    def __init__(self, message: str = "参数校验失败"):
        super().__init__(ResponseCode.VALIDATION_ERROR, message)


class UnauthorizedException(AppException):
    """未认证 (40101)"""
    def __init__(self, message: str = "未登录，请先登录"):
        super().__init__(ResponseCode.UNAUTHORIZED, message)


class TokenExpiredException(AppException):
    """Token 过期 (40102)"""
    def __init__(self, message: str = "Token 已过期，请重新登录"):
        super().__init__(ResponseCode.TOKEN_EXPIRED, message)


class ForbiddenException(AppException):
    """无权限 (40301)"""
    def __init__(self, message: str = "无权限访问该资源"):
        super().__init__(ResponseCode.FORBIDDEN, message)


class NotFoundException(AppException):
    """资源不存在 (40401)"""
    def __init__(self, resource: str = "资源"):
        super().__init__(ResponseCode.NOT_FOUND, f"{resource}不存在")


class ConflictException(AppException):
    """资源冲突 (40901)"""
    def __init__(self, message: str = "资源已存在"):
        super().__init__(ResponseCode.CONFLICT, message)


class FileTooLargeException(AppException):
    """文件过大 (41301)"""
    def __init__(self, max_size_mb: int = 10):
        super().__init__(ResponseCode.FILE_TOO_LARGE, f"文件大小超过限制 ({max_size_mb}MB)")


class InternalErrorException(AppException):
    """服务器内部错误 (50001)"""
    def __init__(self, message: str = "服务器内部错误"):
        super().__init__(ResponseCode.INTERNAL_ERROR, message)


class ServiceUnavailableException(AppException):
    """服务不可用 (50002)"""
    def __init__(self, message: str = "服务暂时不可用，请稍后重试"):
        super().__init__(ResponseCode.SERVICE_UNAVAILABLE, message)