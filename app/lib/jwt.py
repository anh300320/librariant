from datetime import UTC, datetime, timedelta

from jose import jwt

from app.settings.auth import AuthSettings


def create_access_token(
    *,
    subject: str,
    settings: AuthSettings,
    extra_claims: dict | None = None,
) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes,
    )
    payload = {
        "sub": subject,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
