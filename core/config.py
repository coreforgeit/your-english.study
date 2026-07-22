from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict

from ai.enums import TranscriptionModel


class Settings(BaseSettings):
    debug: bool = False
    db_name: str
    db_user: str
    db_password: str
    db_host: str = 'db'
    db_port: int = 5432
    redis_host: str = 'redis'
    redis_port: int = 6379
    redis_db: int = 0
    rabbitmq_host: str = 'rabbitmq'
    rabbitmq_port: int = 5672
    rabbitmq_user: str = 'english'
    rabbitmq_password: str = 'change_me'
    bot_token: str = ''
    api_host: str = '0.0.0.0'
    api_port: int = 8000
    site_url: str = 'https://your-english.study'
    www_url: str = 'https://www.your-english.study'
    app_url: str = 'https://app.your-english.study'
    api_url: str = 'https://api.your-english.study'
    log_level: str = 'INFO'
    open_ai_api_key: str = ''
    open_ai_transcription_model: TranscriptionModel = TranscriptionModel.GPT_4O_MINI_TRANSCRIBE
    # open_ai_transcription_model: TranscriptionModel = TranscriptionModel.GPT_4O_TRANSCRIBE

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    @property
    def async_database_url(self) -> str:
        return (
            f'postgresql+asyncpg://{self.db_user}:{self.db_password}'
            f'@{self.db_host}:{self.db_port}/{self.db_name}'
        )

    @property
    def redis_url(self) -> str:
        return f'redis://{self.redis_host}:{self.redis_port}/{self.redis_db}'

    @property
    def rabbitmq_url(self) -> str:
        return (
            f'amqp://{quote(self.rabbitmq_user, safe="")}:'
            f'{quote(self.rabbitmq_password, safe="")}'
            f'@{self.rabbitmq_host}:{self.rabbitmq_port}/'
        )

    @property
    def cors_origins(self) -> list[str]:
        return [
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            self.site_url,
            self.www_url,
            self.app_url,
        ]


settings = Settings()
