from fastapi import APIRouter, Depends, HTTPException, status

from app.exception.node import NodeBaseError
from app.models.user import UserModel
from app.router.dependencies import get_folder_service
from app.schema.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.schema.base import BaseResponse
from app.service.auth import AuthService
from app.service.folder import FolderService
from app.settings.auth import auth_settings

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service() -> AuthService:
    return AuthService(auth_settings)


def _to_auth_response(user: UserModel, token: str, home_folder_id: int) -> AuthResponse:
    return AuthResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            home_folder_id=home_folder_id
        ),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
    folder_service: FolderService = Depends(get_folder_service),
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
    else:
        user_folder = await folder_service.create_user_directory(user)

    return BaseResponse(
        status="201",
        data=_to_auth_response(
            user,
            token,
            home_folder_id=user_folder.id,
        ),
    )


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    folder_service: FolderService = Depends(get_folder_service),
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

    try:
        user_root_folder = await folder_service.get_user_home_folder(user)
    except NodeBaseError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return BaseResponse(
        status="200",
        data=_to_auth_response(
            user,
            token,
            user_root_folder.id,
        ),
    )
