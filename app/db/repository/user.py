from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.entities.user import User
from app.models.user import UserModel


async def create_user(
    db_sess: AsyncSession,
    *,
    username: str,
    email: str,
    hashed_password: str,
    role: str,
) -> UserModel:
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=role,
    )
    db_sess.add(user)
    await db_sess.flush()
    await db_sess.refresh(user)

    return _convert_to_user_model(user)

async def get_by_username(db_sess: AsyncSession, username: str) -> UserModel | None:
    result = await db_sess.execute(
        select(User).where(User.username == username),
    )
    return _convert_to_user_model(
        result.scalar_one_or_none(),
        include_password=True,
    )

async def get_by_email(db_sess: AsyncSession, email: str) -> UserModel | None:
    result = await db_sess.execute(
        select(User).where(User.email == email),
    )
    return _convert_to_user_model(result.scalar_one_or_none())

async def get_by_id(db_sess: AsyncSession, user_id: int) -> UserModel | None:
    result = await db_sess.execute(
        select(User).where(User.id == user_id),
    )
    return _convert_to_user_model(result.scalar_one_or_none())


def _convert_to_user_model(
    user: User | None,
    include_password: bool = False,
) -> UserModel | None:
    if user is None:
        return None

    hashed_password = None
    if include_password:
        hashed_password = user.hashed_password

    return UserModel(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        hashed_password=hashed_password,
    )