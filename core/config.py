from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_name: str
    db_user: str
    db_password: str
    db_host: str = 'postgres'
    db_port: int = 5432
    redis_host: str = 'redis'
    redis_port: int = 6379
    redis_db: int = 0
    bot_token: str = ''
    api_host: str = '0.0.0.0'
    api_port: int = 8000

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


settings = Settings()
