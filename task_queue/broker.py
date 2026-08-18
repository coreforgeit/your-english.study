from taskiq_aio_pika import AioPikaBroker

from core.config import settings


broker = AioPikaBroker(settings.rabbitmq_url)
