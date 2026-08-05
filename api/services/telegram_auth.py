import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def get_telegram_user_id(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 300,
) -> int | None:
    if not init_data or not bot_token:
        return None

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None

    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        return None

    data = dict(pairs)
    received_hash = data.pop('hash', None)
    if not received_hash:
        return None

    data_check_string = '\n'.join(f'{key}={value}' for key, value in sorted(data.items()))
    secret_key = hmac.new(
        key=b'WebAppData',
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    try:
        auth_date = int(data['auth_date'])
    except (KeyError, TypeError, ValueError):
        return None

    now = int(time.time())
    if not now - max_age_seconds <= auth_date <= now + 30:
        return None

    try:
        user = json.loads(data['user'])
        return int(user['id'])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 300,
) -> bool:
    return get_telegram_user_id(
        init_data,
        bot_token,
        max_age_seconds=max_age_seconds,
    ) is not None
