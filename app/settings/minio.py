from pydantic import Field
from pydantic_settings import BaseSettings


class MinioSettings(BaseSettings):
    endpoint: str = Field(default="http://minio:3000")
    access_key: str
    secret_key: str
    bucket: str


minio_settings = MinioSettings()