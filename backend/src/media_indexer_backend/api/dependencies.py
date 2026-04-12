from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from media_indexer_backend.core.auth import verify_session_token
from media_indexer_backend.core.config import get_settings
from media_indexer_backend.db.session import get_db_session
from media_indexer_backend.models.enums import UserRole, UserStatus
from media_indexer_backend.models.tables import User
from media_indexer_backend.schemas.auth import AuthCapabilities
from media_indexer_backend.services.user_service import capabilities_for_user, enforce_user_status


def get_session(session: Session = Depends(get_db_session)) -> Session:
    return session


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
    authorization: str | None = Header(default=None),
) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    user_id = verify_session_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return enforce_user_status(session, user)


def get_current_capabilities(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AuthCapabilities:
    return capabilities_for_user(session, current_user)


def require_authenticated(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return current_user


def require_collection_manager(
    current_user: User = Depends(get_current_user),
    capabilities: AuthCapabilities = Depends(get_current_capabilities),
) -> User:
    if not capabilities.can_manage_collections:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Collection management access required.")
    return current_user


def require_upload_access(
    current_user: User = Depends(get_current_user),
    capabilities: AuthCapabilities = Depends(get_current_capabilities),
) -> User:
    if not capabilities.can_upload_assets:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Upload access required.")
    return current_user


def user_can_access_source(capabilities: AuthCapabilities, source_id) -> bool:
    if capabilities.allowed_source_ids == "all":
        return True
    return str(source_id) in {str(value) for value in capabilities.allowed_source_ids}
