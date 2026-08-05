from pydantic import BaseModel


class TelegramAuthRequest(BaseModel):
    init_data: str
