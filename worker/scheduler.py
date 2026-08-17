import logging
from collections.abc import Awaitable, Callable
from datetime import UTC

from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from taskiq import TaskiqEvents, TaskiqState

from core.config import settings
from worker.broker import broker


logger = logging.getLogger(__name__)

SchedulerInitializer = Callable[[], Awaitable[None]]
_scheduler_initializers: list[SchedulerInitializer] = []

scheduler = AsyncIOScheduler(
    jobstores={
        'default': RedisJobStore(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            jobs_key='english_practice_bot:scheduler:jobs',
            run_times_key='english_practice_bot:scheduler:run_times',
        ),
    },
    timezone=UTC,
)


def register_scheduler_initializer(
    initializer: SchedulerInitializer,
) -> None:
    _scheduler_initializers.append(initializer)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def start_scheduler(_: TaskiqState) -> None:
    if scheduler.running:
        return

    scheduler.start(paused=True)
    try:
        for initializer in _scheduler_initializers:
            await initializer()
    except Exception:
        scheduler.shutdown(wait=False)
        logger.exception(f'Не удалось подготовить планировщик')
        raise

    scheduler.resume()
    logger.info(f'Планировщик запущен')


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def stop_scheduler(_: TaskiqState) -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info(f'Планировщик остановлен')
