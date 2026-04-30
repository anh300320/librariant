from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    host: str = Field(default="localhost")
    port: int = Field(default=5432)
    user: str = Field(default="librariant")
    password: str = Field(default="librariant")
    name: str = Field(default="librariant")
    pool_size: int = Field(default=10),
    max_overflow: int = Field(default=20),
    pool_timeout: int = Field(default=30),
    pool_recycle: int = Field(default=1800),

    @property
    def url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


database_settings = DatabaseSettings()
