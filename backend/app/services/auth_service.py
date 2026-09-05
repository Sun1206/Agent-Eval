"""
认证业务逻辑 — 注册 / 登录 / Token 刷新 / API Key 管理
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    hash_password,
    hash_password_async,
    verify_password_async,
)
from app.models.user import ApiKey, User
from app.schemas.auth import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    TokenRefreshResponse,
    UserResponse,
)


class AuthService:
    """认证服务"""

    @staticmethod
    async def register(db: AsyncSession, data: RegisterRequest) -> LoginResponse:
        """用户注册"""
        # 合并用户名+邮箱唯一性检查为一次查询
        existing = await db.execute(
            select(User).where((User.username == data.username) | (User.email == data.email))
        )
        found = existing.scalar_one_or_none()
        if found:
            if found.username == data.username:
                raise ConflictException("用户名已存在")
            raise ConflictException("邮箱已被注册")

        # 创建用户
        user = User(
            username=data.username,
            email=data.email,
            password_hash=hash_password(data.password),
            display_name=data.display_name,
        )
        db.add(user)
        await db.flush()  # 获取 user.id

        # 生成 Token
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    async def login(db: AsyncSession, data: LoginRequest) -> LoginResponse:
        """用户登录"""
        # 支持用户名或邮箱登录
        user = await _find_user_by_login(db, data.login)
        if user is None:
            raise UnauthorizedException("用户名或密码错误")

        if not user.is_active:
            raise UnauthorizedException("用户已被禁用")

        if not await verify_password_async(data.password, user.password_hash):
            raise UnauthorizedException("用户名或密码错误")

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    async def refresh(db: AsyncSession, refresh_token_str: str) -> TokenRefreshResponse:
        """刷新 Token"""
        payload = decode_token(refresh_token_str)
        if payload is None:
            raise UnauthorizedException("Refresh Token 无效或已过期")

        if payload.get("type") != "refresh":
            raise UnauthorizedException("请使用 Refresh Token")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Token 内容无效")

        # 确认用户存在且活跃
        result = await db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise UnauthorizedException("用户不存在或已被禁用")

        return TokenRefreshResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    @staticmethod
    async def get_me(user: User) -> UserResponse:
        """获取当前用户信息（user 由依赖注入提供）"""
        return UserResponse.model_validate(user)

    # ==================== API Key 管理 ====================

    @staticmethod
    async def create_api_key(
        db: AsyncSession, user_id: UUID, data: ApiKeyCreateRequest
    ) -> ApiKeyCreateResponse:
        """创建 API Key"""
        full_key, prefix, key_hash = generate_api_key()

        api_key = ApiKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=prefix,
            name=data.name,
            expires_at=data.expires_at,
        )
        db.add(api_key)
        await db.flush()

        return ApiKeyCreateResponse(
            id=api_key.id,
            name=api_key.name,
            key_prefix=prefix,
            full_key=full_key,
            is_active=api_key.is_active,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
        )

    @staticmethod
    async def list_api_keys(
        db: AsyncSession, user_id: UUID
    ) -> list[ApiKeyResponse]:
        """列出当前用户的 API Key（不返回完整 Key）"""
        result = await db.execute(
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
        )
        keys = result.scalars().all()

        return [
            ApiKeyResponse(
                id=k.id,
                name=k.name,
                key_prefix=k.key_prefix + "...",
                is_active=k.is_active,
                last_used_at=k.last_used_at,
                expires_at=k.expires_at,
                created_at=k.created_at,
            )
            for k in keys
        ]

    @staticmethod
    async def revoke_api_key(db: AsyncSession, user_id: UUID, key_id: UUID):
        """吊销 API Key（软删除）"""
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id,
                ApiKey.user_id == user_id,
            )
        )
        key = result.scalar_one_or_none()
        if key is None:
            raise NotFoundException("API Key")

        key.is_active = False
        db.add(key)


async def _find_user_by_login(db: AsyncSession, login: str) -> User | None:
    """根据用户名或邮箱查找用户"""
    # 判断是邮箱还是用户名
    if "@" in login:
        return (
            await db.execute(select(User).where(User.email == login))
        ).scalar_one_or_none()
    else:
        return (
            await db.execute(select(User).where(User.username == login))
        ).scalar_one_or_none()