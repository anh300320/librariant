from pydantic import Field
from pydantic_settings import BaseSettings


class ElasticsearchSettings(BaseSettings):
    url: str = Field(default="http://localhost:9200")
    index: str


elasticsearch_settings = ElasticsearchSettings()