from pydantic_settings import BaseSettings


class KafkaSettings(BaseSettings):
    address: str = "localhost"
    port: int = 9092
    consumer_group: str = "librariant"
    outbox_scan_interval_sec: float = 1.0
    outbox_batch_size: int = 100


kafka_settings = KafkaSettings()
