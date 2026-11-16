import enum
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator


class IdempotencyStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass
class ClaimResult:
    # True if this caller owns the task (fresh claim, or re-claim of a
    # FAILED / lease-expired record) and must do the work.
    success: bool
    # Status of the record after the claim attempt. For a duplicate, this is
    # the current owner's status: SUCCEEDED -> safe to ack, PROCESSING -> retry later.
    status: IdempotencyStatus
    # Fencing token identifying this claim; only the holder may finalize it.
    token: int | None = None


class IdempotencyManager[T](ABC):

    @asynccontextmanager
    async def idempotent(self, idempotency_key: T) -> AsyncIterator[ClaimResult]:
        claim = await self._claim(idempotency_key)
        try:
            yield claim
        except BaseException:
            # Only the owner may mark the task failed; a duplicate must never
            # touch another worker's record.
            if claim.success:
                await self._on_fail(idempotency_key, claim)
            raise
        else:
            if claim.success:
                await self._on_success(idempotency_key, claim)

    @abstractmethod
    async def _claim(self, idempotency_key: T) -> ClaimResult:
        raise NotImplementedError

    @abstractmethod
    async def _on_success(self, idempotency_key: T, claim: ClaimResult) -> None:
        raise NotImplementedError

    @abstractmethod
    async def _on_fail(self, idempotency_key: T, claim: ClaimResult) -> None:
        raise NotImplementedError
