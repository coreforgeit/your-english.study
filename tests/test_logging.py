import logging

from core.logging import SuccessfulHealthCheckFilter


def make_access_record(method: str, path: str, status_code: int) -> logging.LogRecord:
    return logging.LogRecord(
        name='uvicorn.access',
        level=logging.INFO,
        pathname='',
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=('127.0.0.1:12345', method, path, '1.1', status_code),
        exc_info=None,
    )


def test_successful_health_check_is_excluded() -> None:
    record = make_access_record('GET', '/health', 200)

    assert SuccessfulHealthCheckFilter().filter(record) is False


def test_failed_health_check_is_logged() -> None:
    record = make_access_record('GET', '/health', 503)

    assert SuccessfulHealthCheckFilter().filter(record) is True


def test_other_successful_request_is_logged() -> None:
    record = make_access_record('GET', '/api/vocabulary', 200)

    assert SuccessfulHealthCheckFilter().filter(record) is True
