from pydantic import Field
from pydantic_settings import BaseSettings


class S3Settings(BaseSettings):
    endpoint_url: str = Field(default="http://localhost:9000")
    access_key_id: str = Field(default="minioadmin")
    secret_access_key: str = Field(default="minioadmin")
    region: str = Field(default="us-east-1")
    bucket_name: str = Field(default="librariant-files")

    class Config:
        env_file = ".env"
        case_sensitive = True

s3_settings = S3Settings()
