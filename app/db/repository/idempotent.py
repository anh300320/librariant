import logging
import uuid
from datetime import timedelta
from typing import AsyncContextManager, Callable

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.entities.idempotency_record import IdempotencyRecord
from app.idempotent.manager import IdempotencyManager, IdempotencyStatus, ClaimResult


_logger = logging.getLogger(__name__)

# How many times to retry the claim if the conflicting record vanishes between
# the claim and the status lookup (e.g. removed by a cleanup job).
_MAX_CLAIM_ATTEMPTS = 3


class DbOpManager(IdempotencyManager[uuid.UUID]):

    def __init__(
        self,
        task_name: str,
        get_db_sess_func: Callable[[], AsyncContextManager[AsyncSession]],
        timeout: timedelta = timedelta(minutes=10),
    ):
        """
        :param get_db_sess_func: session factory (e.g. ``get_db_sess``) that
            commits on exit. Each operation uses its own short-lived session so
            state changes are visible to other workers immediately.
        :param timeout: lease duration; a PROCESSING record whose lease has
            expired is assumed to belong to a crashed worker and can be re-claimed.
        """
        self._task_name = task_name
        self._get_db_sess_func = get_db_sess_func
        self._timeout = timeout

    async def _claim(self, idempotency_key: uuid.UUID) -> ClaimResult:
        for _ in range(_MAX_CLAIM_ATTEMPTS):
            async with self._get_db_sess_func() as db_sess:
                token = await claim_idempotency_record(
                    db_sess, self._task_name, idempotency_key, self._timeout
                )
                if token is not None:
                    return ClaimResult(
                        success=True,
                        status=IdempotencyStatus.PROCESSING,
                        token=token,
                    )

                record = await get_idempotency_record(db_sess, self._task_name, idempotency_key)
                if record is not None:
                    return ClaimResult(
                        success=False,
                        status=IdempotencyStatus(record.status),
                    )
            # The record was deleted between the claim and the lookup: try again.

        raise RuntimeError(
            f"could not claim idempotency record, task={self._task_name}, key={idempotency_key}"
        )

    async def _on_success(self, idempotency_key: uuid.UUID, claim: ClaimResult) -> None:
        await self._finalize(idempotency_key, claim, IdempotencyStatus.SUCCEEDED)

    async def _on_fail(self, idempotency_key: uuid.UUID, claim: ClaimResult) -> None:
        await self._finalize(idempotency_key, claim, IdempotencyStatus.FAILED)

    async def _finalize(
        self,
        idempotency_key: uuid.UUID,
        claim: ClaimResult,
        status: IdempotencyStatus,
    ) -> None:
        async with self._get_db_sess_func() as db_sess:
            updated = await finalize_idempotency_record(
                db_sess, self._task_name, idempotency_key, claim.token, status
            )
        if not updated:
            # Our lease expired and another worker re-claimed the record; its
            # result takes precedence over ours.
            _logger.warning(
                "lost idempotency lease, result not recorded, task=%s, key=%s, status=%s",
                self._task_name,
                idempotency_key,
                status.value,
            )


async def claim_idempotency_record(
    db_sess: AsyncSession,
    task_name: str,
    idempotency_key: uuid.UUID,
    timeout: timedelta,
) -> int | None:
    """
    Atomically claim (task_name, idempotency_key) in a single statement.

    The claim succeeds if the record does not exist yet, or if it exists and is
    re-claimable: FAILED, or PROCESSING with an expired lease (crashed worker).

    Returns the claim's fencing token (the record's ``attempts``) on success,
    or None if another worker owns the record or it already SUCCEEDED.
    """
    locked_until = func.now() + timeout
    stmt = (
        pg_insert(IdempotencyRecord)
        .values(
            task_name=task_name,
            key=idempotency_key,
            status=IdempotencyStatus.PROCESSING.value,
            attempts=1,
            locked_until=locked_until,
        )
        .on_conflict_do_update(
            index_elements=["task_name", "key"],
            set_={
                "status": IdempotencyStatus.PROCESSING.value,
                "attempts": IdempotencyRecord.attempts + 1,
                "locked_until": locked_until,
            },
            where=(
                (IdempotencyRecord.status == IdempotencyStatus.FAILED.value)
                | (
                    (IdempotencyRecord.status == IdempotencyStatus.PROCESSING.value)
                    & (IdempotencyRecord.locked_until < func.now())
                )
            ),
        )
        .returning(IdempotencyRecord.attempts)
    )
    result = await db_sess.execute(stmt)
    return result.scalar_one_or_none()


async def get_idempotency_record(
    db_sess: AsyncSession,
    task_name: str,
    idempotency_key: uuid.UUID,
) -> IdempotencyRecord | None:
    """Return the record for (task_name, idempotency_key), or None if absent."""
    result = await db_sess.execute(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.task_name == task_name,
            IdempotencyRecord.key == idempotency_key,
        )
        # Always reload from the database instead of returning a cached object
        # from the session's identity map.
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def finalize_idempotency_record(
    db_sess: AsyncSession,
    task_name: str,
    idempotency_key: uuid.UUID,
    token: int | None,
    status: IdempotencyStatus,
) -> bool:
    """
    Set the final status and release the lease, but only if the caller still
    owns the claim (record is PROCESSING and ``attempts`` matches the token).

    Returns True if the record was updated, False if the claim was lost.
    """
    result = await db_sess.execute(
        update(IdempotencyRecord)
        .where(
            IdempotencyRecord.task_name == task_name,
            IdempotencyRecord.key == idempotency_key,
            IdempotencyRecord.status == IdempotencyStatus.PROCESSING.value,
            IdempotencyRecord.attempts == token,
        )
        .values(status=status.value, locked_until=None)
    )
    return result.rowcount == 1
