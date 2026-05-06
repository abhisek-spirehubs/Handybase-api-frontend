from typing import Optional
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_access_token
from app.models.user import User, UserRole, UserStatus
from app.core.exceptions import UnauthorizedException, ForbiddenException

security = HTTPBearer(auto_error=True)
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)

    user_id: str = payload.get("sub")
    role: str = payload.get("role")

    if not user_id or not role:
        raise UnauthorizedException("Invalid token payload")

    user = await User.get(user_id)

    if not user:
        raise UnauthorizedException("User not found")
    if user.is_deleted:
        raise UnauthorizedException("Account has been deleted")
    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedException("Account is inactive")

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
) -> Optional[User]:
    """
    Returns current user if token provided and valid.
    Returns None for unauthenticated requests.
    Used on public routes that behave differently for logged-in users.
    """
    if not credentials:
        return None
    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = await User.get(user_id)
        if not user or user.is_deleted or user.status != UserStatus.ACTIVE:
            return None
        return user
    except Exception:
        return None


async def admin_required(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.user_type != UserRole.ADMIN:
        raise ForbiddenException("Admin access required")
    return current_user


async def provider_required(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.user_type != UserRole.PROVIDER:
        raise ForbiddenException("Provider access required")
    return current_user


async def client_required(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.user_type != UserRole.CLIENT:
        raise ForbiddenException("Client access required")
    return current_user


async def client_or_admin_required(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.user_type not in [UserRole.ADMIN, UserRole.CLIENT]:
        raise ForbiddenException("Client or Admin access required")
    return current_user


async def admin_or_provider_required(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.user_type not in [UserRole.ADMIN, UserRole.PROVIDER]:
        raise ForbiddenException("Admin or Provider access required")
    return current_user