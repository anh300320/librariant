from sqlalchemy.ext.asyncio import AsyncSession

from app.db.entities.user import User
from app.db.repository.user import get_by_username, get_by_email, create_user
from app.lib.jwt import create_access_token
from app.lib.password import hash_password, verify_password
from app.settings.auth import AuthSettings

DEFAULT_USER_ROLE = "user"


class AuthService:
    def __init__(
        self,
        db_sess: AsyncSession,
        settings: AuthSettings,
    ) -> None:
        self._db_sess = db_sess
        self._settings = settings

    async def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
    ) -> tuple[User, str]:
        async with self._db_sess.begin():
            if await get_by_username(self._db_sess, username):
                raise ValueError("Username already registered")
            if await get_by_email(self._db_sess, email):
                raise ValueError("Email already registered")

            user = await create_user(
                self._db_sess,
                username=username,
                email=email,
                hashed_password=hash_password(password),
                role=DEFAULT_USER_ROLE,
            )
            token = self._create_token(user)
            return user, token

    async def login(self, *, username: str, password: str) -> tuple[User, str]:
        async with self._db_sess.begin():
            user = await get_by_username(self._db_sess, username)

        if user is None or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid username or password")

        token = self._create_token(user)
        return user, token

    def _create_token(self, user: User) -> str:
        return create_access_token(
            subject=str(user.id),
            settings=self._settings,
            extra_claims={
                "username": user.username,
                "role": user.role,
            },
        )
