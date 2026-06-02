from app.db.repository.user import get_by_username, get_by_email, create_user
from app.db.session import get_db_sess
from app.lib.jwt import create_access_token
from app.lib.password import hash_password, verify_password
from app.models.user import UserModel
from app.settings.auth import AuthSettings

DEFAULT_USER_ROLE = "user"


class AuthService:
    def __init__(
        self,
        settings: AuthSettings,
    ) -> None:
        self._settings = settings

    async def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
    ) -> tuple[UserModel, str]:
        async with get_db_sess() as db_sess:
            if await get_by_username(db_sess, username):
                raise ValueError("Username already registered")
            if await get_by_email(db_sess, email):
                raise ValueError("Email already registered")

            user = await create_user(
                db_sess,
                username=username,
                email=email,
                hashed_password=hash_password(password),
                role=DEFAULT_USER_ROLE,
            )
            token = self._create_token(user)
            return user, token

    async def login(self, *, username: str, password: str) -> tuple[UserModel, str]:
        async with get_db_sess() as db_sess:
            user = await get_by_username(db_sess, username)

        if user is None or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid username or password")

        token = self._create_token(user)
        return user, token

    def _create_token(self, user: UserModel) -> str:
        return create_access_token(
            subject=str(user.id),
            settings=self._settings,
            extra_claims={
                "username": user.username,
                "role": user.role,
            },
        )
