from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from . import AdapterError, Held

UTC = timezone.utc
WIB = timezone(timedelta(hours=7))
PLATFORMS = {'tiktok', 'facebook', 'youtube'}


def remote_id(value):
    if not isinstance(value, dict):
        raise Held('provider_shape', 'Bentuk respons provider belum dikenali.')
    identifier = value.get('id') or value.get('_id')
    if not isinstance(identifier, str) or not identifier or len(identifier) > 200:
        raise Held('provider_identity', 'Identitas dari provider belum lengkap.')
    return identifier


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, UTC).isoformat().replace('+00:00', 'Z')


class Repliz:
    """Public API contract: docs.repliz.com/api; mutation retries are deliberately absent."""

    def __init__(self, credentials, *, transport=None, interval=0.5):
        if not credentials.get('access_key') or not credentials.get('secret_key'):
            raise Held('repliz_credentials', 'Isi kredensial Repliz terlebih dahulu.')
        self.client = httpx.AsyncClient(
            base_url='https://api.repliz.com',
            auth=(credentials['access_key'], credentials['secret_key']),
            timeout=httpx.Timeout(35, connect=10), follow_redirects=False, transport=transport,
        )
        self.interval, self.next_start = interval, 0.0
        self.lock = asyncio.Lock()
        self.slots = asyncio.Semaphore(2)
        self.mutations = asyncio.Lock()

    async def close(self):
        await self.client.aclose()

    async def request(self, method, path, **kwargs):
        async with self.slots:
            async with self.lock:
                delay = self.next_start - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                self.next_start = time.monotonic() + self.interval
            try:
                response = await self.client.request(method, path, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                raise AdapterError('provider_unreachable', 'Koneksi provider terputus. Periksa hasil sebelum mengirim ulang.', ambiguous=method != 'GET') from exc
            if response.status_code == 429:
                try:
                    delay = max(1, min(300, int(response.headers.get('retry-after', '30'))))
                except ValueError:
                    delay = 30
                self.next_start = max(self.next_start, time.monotonic() + delay)
            if not 200 <= response.status_code < 300:
                raise AdapterError(f'provider_http_{response.status_code}', f'Provider mengembalikan HTTP {response.status_code}.', ambiguous=method != 'GET' and response.status_code >= 500)
            try:
                data = response.json()
            except ValueError as exc:
                raise AdapterError('provider_json', 'Respons provider tidak dapat dibaca.', ambiguous=method != 'GET') from exc
            if not isinstance(data, dict):
                raise AdapterError('provider_shape', 'Bentuk respons provider belum dikenali.', ambiguous=method != 'GET')
            return data

    async def pages(self, path, params=None):
        found, identifiers, expected = [], set(), None
        for page in range(1, 501):
            data = await self.request('GET', path, params={**(params or {}), 'page': page, 'limit': 100})
            docs, total = data.get('docs'), data.get('totalDocs')
            if not isinstance(docs, list) or type(total) is not int or total < 0 or data.get('page') != page:
                raise Held('snapshot_incomplete', 'Snapshot provider belum lengkap; daftar akun lama tetap dipertahankan.')
            if expected is None:
                expected = total
            if total != expected:
                raise Held('snapshot_changed', 'Daftar provider berubah saat dibaca; sinkronisasi akan diulang.')
            for item in docs:
                identifier = remote_id(item)
                if identifier in identifiers:
                    raise Held('snapshot_duplicate', 'Snapshot berisi identitas ganda.')
                identifiers.add(identifier)
                found.append(item)
            if data.get('hasNextPage') is False:
                if len(found) != total:
                    raise Held('snapshot_incomplete', 'Jumlah hasil provider belum lengkap.')
                return found
            if not docs or data.get('hasNextPage') is not True:
                raise Held('snapshot_incomplete', 'Penanda halaman provider belum lengkap.')
        raise Held('snapshot_too_large', 'Snapshot melebihi batas pemeriksaan.')

    async def accounts(self):
        return await self.pages('/public/account')

    async def account(self, identifier):
        return await self.request('GET', '/public/account/' + self._identifier(identifier))

    async def schedules(self, start, end):
        return await self.pages('/public/schedule', {'fromDate': iso(start), 'toDate': iso(end)})

    async def schedule(self, identifier):
        return await self.request('GET', '/public/schedule/' + self._identifier(identifier))

    async def create_schedule(self, payload):
        async with self.mutations:
            return await self.request('POST', '/public/schedule', json=payload)

    async def comments(self):
        return await self.pages('/public/comment', {'status': 'pending'})

    async def reply(self, identifier, text):
        async with self.mutations:
            data = await self.request('POST', '/public/comment/' + self._identifier(identifier), json={'text': text})
        if not isinstance(data.get('commentId'), str) or not data['commentId']:
            raise AdapterError('reply_result_unknown', 'Provider belum memberikan bukti balasan.', ambiguous=True)
        return data['commentId']

    async def statistic(self, identifier):
        return await self.request('GET', '/public/account/' + self._identifier(identifier) + '/statistic')

    @staticmethod
    def _identifier(value):
        if not isinstance(value, str) or not value or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in value):
            raise Held('invalid_remote_id', 'Identitas provider tidak valid.')
        return value


def schedule_evidence(data, identifier, account_id, platform):
    if remote_id(data) != identifier or data.get('accountId') != account_id:
        raise Held('schedule_identity', 'Hasil provider tidak cocok dengan akun atau jadwal yang diminta.')
    status = data.get('status')
    if status in {'pending', 'process'}:
        return {'state': 'scheduled', 'post_url': None}
    if status == 'error':
        return {'state': 'failed', 'post_url': None}
    if status == 'success':
        result = data.get('result') if isinstance(data.get('result'), dict) else {}
        content = data.get('content') if isinstance(data.get('content'), dict) else {}
        url = result.get('url') or content.get('url') or data.get('url')
        parsed = urlparse(url) if isinstance(url, str) else None
        domains = {'tiktok': {'tiktok.com', 'www.tiktok.com'}, 'facebook': {'facebook.com', 'www.facebook.com', 'fb.watch'}, 'youtube': {'youtube.com', 'www.youtube.com', 'youtu.be'}}
        if not parsed or parsed.scheme != 'https' or parsed.hostname not in domains.get(platform, set()) or parsed.path in {'', '/'}:
            raise Held('published_evidence_missing', 'Provider menyatakan selesai, tetapi tautan posting terverifikasi belum tersedia.')
        return {'state': 'published', 'post_url': url}
    raise Held('schedule_status_unknown', 'Status jadwal provider belum dikenali; pengiriman ditahan.')
