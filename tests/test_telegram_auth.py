import hashlib
import hmac
import time
import unittest
from urllib.parse import urlencode

from api.services.telegram_auth import (
    get_telegram_user_id,
    validate_telegram_init_data,
)


BOT_TOKEN = '123456:test-token'


def build_init_data(*, auth_date: int, user_id: int = 42) -> str:
    data = {
        'auth_date': str(auth_date),
        'query_id': 'test-query',
        'user': f'{{"id":{user_id},"first_name":"Test"}}',
    }
    data_check_string = '\n'.join(
        f'{key}={value}'
        for key, value in sorted(data.items())
    )
    secret_key = hmac.new(
        b'WebAppData',
        BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()
    data['hash'] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(data)


class ValidateTelegramInitDataTest(unittest.TestCase):
    def test_accepts_valid_fresh_data(self):
        init_data = build_init_data(auth_date=int(time.time()))

        self.assertTrue(validate_telegram_init_data(init_data, BOT_TOKEN))
        self.assertEqual(get_telegram_user_id(init_data, BOT_TOKEN), 42)

    def test_rejects_modified_data(self):
        init_data = build_init_data(auth_date=int(time.time())).replace(
            '%22id%22%3A42',
            '%22id%22%3A43',
        )

        self.assertFalse(validate_telegram_init_data(init_data, BOT_TOKEN))

    def test_rejects_expired_data(self):
        init_data = build_init_data(auth_date=int(time.time()) - 301)

        self.assertFalse(validate_telegram_init_data(init_data, BOT_TOKEN))

    def test_rejects_missing_bot_token(self):
        init_data = build_init_data(auth_date=int(time.time()))

        self.assertFalse(validate_telegram_init_data(init_data, ''))


if __name__ == '__main__':
    unittest.main()
