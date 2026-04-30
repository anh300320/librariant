from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_sess
from app.schema.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.schema.base import BaseResponse
from app.service.auth import AuthService
from app.settings.auth import auth_settings

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    db_sess: AsyncSession = Depends(get_db_sess),
) -> AuthService:
    return AuthService(db_sess, auth_settings)


def _to_auth_response(user, token: str) -> AuthResponse:
    return AuthResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
        ),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> BaseResponse:
    try:
        user, token = await auth_service.register(
            username=body.username,
            email=body.email,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return BaseResponse(
        status="201",
        data=_to_auth_response(user, token),
    )


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> BaseResponse:
    try:
        user, token = await auth_service.login(
            username=body.username,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return BaseResponse(
        status="200",
        data=_to_auth_response(user, token),
    )
