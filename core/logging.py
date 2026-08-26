import logging
import sys

from core.config import settings


class SuccessfulHealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not isinstance(record.args, tuple) or len(record.args) < 5:
            return True

        _, method, path, _, status_code = record.args[:5]
        is_successful_health_check = (
            method == 'GET'
            and isinstance(path, str)
            and path.partition('?')[0] == '/health'
            and status_code == 200
        )
        return not is_successful_health_check


def setup_logging() -> None:
    logging.basicConfig(
        level=settings.log_level.upper(),
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    access_logger = logging.getLogger('uvicorn.access')
    access_logger.setLevel(logging.INFO)
    access_logger.addFilter(SuccessfulHealthCheckFilter())
