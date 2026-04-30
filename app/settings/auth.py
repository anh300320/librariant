from pydantic import Field
from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    secret_key: str = Field(default="change-me-in-production")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60)


auth_settings = AuthSettings()
