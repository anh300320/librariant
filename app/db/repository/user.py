from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.entities.user import User


async def create_user(
    db_sess: AsyncSession,
    *,
    username: str,
    email: str,
    hashed_password: str,
    role: str,
) -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=role,
    )
    db_sess.add(user)
    await db_sess.flush()
    await db_sess.refresh(user)
    return user

async def get_by_username(db_sess: AsyncSession, username: str) -> User | None:
    result = await db_sess.execute(
        select(User).where(User.username == username),
    )
    return result.scalar_one_or_none()

async def get_by_email(db_sess: AsyncSession, email: str) -> User | None:
    result = await db_sess.execute(
        select(User).where(User.email == email),
    )
    return result.scalar_one_or_none()

async def get_by_id(db_sess: AsyncSession, user_id: int) -> User | None:
    result = await db_sess.execute(
        select(User).where(User.id == user_id),
    )
    return result.scalar_one_or_none()
