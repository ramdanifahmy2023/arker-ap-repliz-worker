from __future__ import annotations

import re

import httpx

from . import AdapterError, Held


class Telegram:
    def __init__(self, credentials, *, transport=None):
        token = credentials.get('bot_token', '')
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
            raise Held('telegram_credentials', 'Token bot Telegram belum valid.')
        self.client = httpx.AsyncClient(base_url='https://api.telegram.org/bot' + token + '/', timeout=20, transport=transport, follow_redirects=False)

    async def close(self):
        await self.client.aclose()

    async def updates(self, offset):
        data = await self.request('GET', 'getUpdates', params={'offset': offset, 'limit': 50, 'timeout': 0, 'allowed_updates': '["message"]'})
        if not isinstance(data.get('result'), list):
            raise Held('telegram_shape', 'Daftar pesan Telegram belum bisa dibaca.')
        return data['result']

    async def send(self, chat_id, text):
        data = await self.request('POST', 'sendMessage', json={'chat_id': chat_id, 'text': text[:4000], 'link_preview_options': {'is_disabled': True}})
        result = data.get('result', {})
        if not isinstance(result.get('message_id'), int):
            raise AdapterError('telegram_unknown', 'Bukti pengiriman pemberitahuan belum tersedia.', ambiguous=True)
        return str(result['message_id'])

    async def request(self, method, path, **kwargs):
        try:
            response = await self.client.request(method, path, **kwargs)
            if response.status_code != 200:
                raise AdapterError('telegram_http', f'Telegram mengembalikan HTTP {response.status_code}.', ambiguous=method != 'GET')
            result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AdapterError('telegram_connection', 'Koneksi Telegram belum tersedia.', ambiguous=method != 'GET') from exc
        if not isinstance(result, dict) or result.get('ok') is not True:
            raise AdapterError('telegram_response', 'Telegram belum mengonfirmasi permintaan.', ambiguous=method != 'GET')
        return result
