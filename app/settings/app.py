from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    timezone: str = "UTC"


app_settings = AppSettings()
