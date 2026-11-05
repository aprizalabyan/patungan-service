from fastapi import APIRouter, Request, Response

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services import auth as auth_service
from app.core.config import get_settings
from app.core.errors import ApiError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession, request: Request, response: Response):
    result, refresh_token = auth_service.login(
        db, body.email, body.password,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    _set_cookie(response, refresh_token)
    return result


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(settings.refresh_token_cookie_name, token, max_age=settings.refresh_token_expire_days * 86400,
                        httponly=True, secure=settings.cookie_secure, samesite=settings.cookie_samesite,
                        domain=settings.cookie_domain, path="/api/v1/auth")


def _clear_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.refresh_token_cookie_name, path="/api/v1/auth", domain=settings.cookie_domain,
                           secure=settings.cookie_secure, httponly=True, samesite=settings.cookie_samesite)


def _check_origin(request: Request) -> None:
    settings = get_settings()
    origin = request.headers.get("origin")
    if not origin or origin.rstrip("/") not in settings.cors_origins:
        raise ApiError(403, "csrf_origin_invalid", "Request origin is not allowed")


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: DbSession):
    _check_origin(request)
    settings = get_settings()
    raw = request.cookies.get(settings.refresh_token_cookie_name)
    result, new_token = auth_service.refresh(
        db, raw, request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    _set_cookie(response, new_token)
    return result


@router.post("/logout")
def logout(request: Request, response: Response, db: DbSession):
    _check_origin(request)
    settings = get_settings()
    auth_service.logout(db, request.cookies.get(settings.refresh_token_cookie_name))
    _clear_cookie(response)
    return {"code": 200, "success": True, "data": {"message": "Logged out"}}


@router.post("/logout-all")
def logout_all(request: Request, response: Response, db: DbSession, user: CurrentUser):
    _check_origin(request)
    auth_service.logout_all(db, user.id)
    _clear_cookie(response)
    return {"code": 200, "success": True, "data": {"message": "Logged out from all devices"}}


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser):
    return user
