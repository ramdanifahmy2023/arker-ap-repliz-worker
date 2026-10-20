from __future__ import annotations

import hmac
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from arker import auth, read_models
from arker.config import bank_path, storage_check, validate_config
from arker.db import Store, now
from arker.ingest import intake
from arker.secrets import PROVIDERS, SecretStore


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Login(Input):
    email: str = Field(max_length=254)
    password: str = Field(max_length=1024)


class Configuration(Input):
    config: dict
    base_version: int = Field(ge=1)


class Validation(Input):
    config: dict


class Intake(Input):
    urls: list[str] = Field(min_length=1, max_length=100)


class Command(Input):
    kind: str = Field(max_length=80)
    payload: dict = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=128)


class Persona(Input):
    name: str = Field(min_length=1, max_length=120)
    style: str = Field(min_length=1, max_length=4000)
    account_id: str | None = Field(default=None, max_length=200)


class StorageCheck(Input):
    bank_directory: str = Field(min_length=1, max_length=4096)
    folder_url: str = Field(default='', max_length=2048)


def create_app(data_dir: str | Path, *, web_dir: Path | None = None, secure_cookies=False, allowed_origins: list[str] | None = None):
    store = Store(data_dir)
    secret_store = SecretStore(store.data_dir)
    app = FastAPI(title='Arker Control API', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.state.secrets = secret_store
    approved_origins = {origin.rstrip('/') for origin in (allowed_origins or [])}
    local_hosts = {'localhost', '127.0.0.1', '::1', 'testserver'}
    if any(urlsplit(origin).hostname not in local_hosts and urlsplit(origin).scheme != 'https' for origin in approved_origins):
        raise ValueError('Akses jarak jauh harus memakai HTTPS.')
    secure_cookies = secure_cookies or any(urlsplit(origin).scheme == 'https' for origin in approved_origins)

    def failure(detail, code, status=400):
        return JSONResponse({'detail': detail, 'code': code}, status_code=status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not return Pydantic's input values: a rejected credential field may be sensitive.
        return JSONResponse({'detail': 'Periksa bentuk dan tipe isian.', 'code': 'invalid_input', 'errors': [{'field': '.'.join(str(v) for v in error['loc'][1:]), 'message': error['msg']} for error in exc.errors()]}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse({'detail': str(exc.detail), 'code': {401: 'authentication_required', 403: 'forbidden', 404: 'not_found', 409: 'conflict'}.get(exc.status_code, 'request_failed')}, status_code=exc.status_code)

    @app.middleware('http')
    async def security(request: Request, call_next):
        if request.url.hostname not in local_hosts and str(request.base_url).rstrip('/') not in approved_origins:
            return failure('Host tidak diizinkan.', 'invalid_host', 400)
        if request.url.path.startswith('/api/'):
            try:
                content_length = int(request.headers.get('content-length', '0'))
            except ValueError:
                return failure('Panjang permintaan tidak valid.', 'invalid_length', 400)
            if content_length < 0:
                return failure('Panjang permintaan tidak valid.', 'invalid_length', 400)
            if content_length > 262144:
                return failure('Ukuran permintaan terlalu besar.', 'body_too_large', 413)
            if request.method not in ('GET', 'HEAD', 'OPTIONS'):
                origin = request.headers.get('origin')
                expected = str(request.base_url).rstrip('/')
                if not origin or (origin != expected and origin not in approved_origins):
                    return failure('Asal permintaan tidak cocok.', 'invalid_origin', 403)
                if request.headers.get('content-type', '').split(';')[0] != 'application/json':
                    return failure('Gunakan data JSON.', 'invalid_content_type', 415)
                chunks, size = [], 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > 262144:
                        return failure('Ukuran permintaan terlalu besar.', 'body_too_large', 413)
                    chunks.append(chunk)
                # Starlette's cached request replays _body to downstream middleware and validation.
                request._body = b''.join(chunks)
            current = auth.session(store, request.cookies.get(auth.COOKIE_NAME))
            request.state.session = current
            public = request.url.path in ('/api/auth/session', '/api/auth/login')
            if not public and current is None:
                return failure('Silakan login terlebih dahulu.', 'authentication_required', 401)
            if not public and request.method not in ('GET', 'HEAD', 'OPTIONS'):
                if not hmac.compare_digest(request.headers.get('x-csrf-token', '').encode(), current['csrf_token'].encode()):
                    return failure('Sesi formulir sudah berubah. Muat ulang halaman.', 'csrf_failed', 403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/auth/session')
    def session(request: Request):
        return request.state.session or {'authenticated': False, 'user': None, 'csrf_token': None, 'setup_required': auth.setup_required(store)}

    @app.post('/api/auth/login')
    def login(body: Login, request: Request, response: Response):
        try:
            token, result = auth.login(store, body.email, body.password, request.client.host if request.client else 'local')
        except PermissionError as exc:
            limited = str(exc) == 'rate_limited'
            return failure('Terlalu banyak percobaan. Coba lagi dalam 15 menit.' if limited else 'Email atau password tidak sesuai.', str(exc), 429 if limited else 401)
        response.set_cookie(auth.COOKIE_NAME, token, httponly=True, secure=secure_cookies, samesite='strict', max_age=auth.SESSION_SECONDS, path='/')
        return result

    @app.post('/api/auth/logout')
    def logout(request: Request, response: Response):
        auth.logout(store, request.cookies.get(auth.COOKIE_NAME))
        response.delete_cookie(auth.COOKIE_NAME, path='/', secure=secure_cookies, httponly=True, samesite='strict')
        return {'authenticated': False}

    @app.get('/api/overview')
    def overview():
        return read_models.overview(store)

    @app.get('/api/health')
    def health():
        return read_models.health(store)

    @app.get('/api/service')
    def service_status():
        from arker.lifecycle import status
        return status(store.data_dir)

    @app.post('/api/service/{action}')
    def service_action(action: str):
        if action not in ('start', 'stop', 'restart'):
            raise HTTPException(422, 'Tindakan layanan tidak didukung.')
        from arker.lifecycle import worker_action
        try:
            result = worker_action(store.data_dir, action)
        except (RuntimeError, ValueError, OSError):
            raise HTTPException(409, 'Kendali worker membutuhkan supervisor Arker yang berjalan dan memiliki proses ini. Periksa status layanan.') from None
        store.event('service.requested', payload={'action': action})
        return result

    @app.get('/api/assets')
    def assets(q: str = '', state: str = '', page: int = 1, limit: int = 25, stage: str = '', date: str = '', scope: str = '', batch_id: str = ''):
        if not 1 <= page <= 100000 or not 1 <= limit <= 100 or len(q) > 200 or len(batch_id) > 100 or scope not in ('', 'active'):
            raise HTTPException(422, 'Parameter halaman tidak valid.')
        try:
            return read_models.assets(store, q, state, page, limit, stage, date, scope, batch_id)
        except ValueError:
            raise HTTPException(422, 'Tanggal harus berformat YYYY-MM-DD.') from None

    @app.get('/api/assets/{identifier}')
    def asset(identifier: str):
        result = read_models.asset_detail(store, identifier)
        if result is None:
            raise HTTPException(404, 'Konten tidak ditemukan.')
        return result

    @app.post('/api/intake')
    def ingest(body: Intake):
        try:
            return intake(store, body.urls)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get('/api/batches')
    def batches(page: int = 1, limit: int = 25):
        if not 1 <= page <= 100000 or not 1 <= limit <= 100:
            raise HTTPException(422, 'Parameter halaman tidak valid.')
        with store.connect() as db:
            items = [dict(row) for row in db.execute('SELECT b.*, (SELECT COUNT(*) FROM assets a WHERE a.batch_id=b.id AND a.state IN (\'completed\',\'published\')) completed FROM batches b ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, (page-1)*limit))]
            total = db.execute('SELECT COUNT(*) FROM batches').fetchone()[0]
        return {'items': items, 'total': total, 'page': page, 'limit': limit}

    @app.get('/api/accounts')
    def accounts():
        versions = store.configuration()
        configuration = store.config_at(versions['applied_version'] or versions['desired_version'])
        scope = configuration['ownership']
        current_time = now()
        instance_id = store.get_meta('instance_id')
        with store.connect() as db:
            items = [read_models.record(row) for row in db.execute('SELECT * FROM accounts ORDER BY platform,name,id')]
            for item in items:
                reserved = db.execute("SELECT COUNT(*) FROM reservations WHERE account_id=? AND day=? AND state='reserved'", (item['id'], item['quota_day'])).fetchone()[0]
                item['quota_reserved'] = reserved
                item['quota_remaining'] = max(0, item['quota_limit'] - item['quota_used'] - reserved)
                item['snapshot_fresh'] = item['snapshot_at'] is not None and current_time - item['snapshot_at'] < 300
                reasons = []
                if not item['connected']:
                    reasons.append('Akun belum terhubung.')
                if not item['snapshot_fresh']:
                    reasons.append('Snapshot akun sudah usang atau belum lengkap.')
                if not scope['acknowledged'] or item['id'] not in scope['account_ids'] or item['ownership_instance'] != instance_id:
                    reasons.append('Scope kepemilikan belum ditetapkan untuk instalasi ini.')
                if item['id'] in scope['excluded_account_ids']:
                    reasons.append('Akun dikecualikan dari rotasi.')
                if not item['capabilities'].get('post') or not item['capabilities'].get('snapshot_complete'):
                    reasons.append('Kemampuan posting belum terverifikasi.')
                if not item['enabled'] and not reasons:
                    reasons.append('Akun belum diaktifkan untuk rotasi.')
                if item['quota_remaining'] <= 0:
                    reasons.append('Kuota pada tanggal snapshot sudah penuh.')
                item['rotation_eligible'] = not reasons
                item['readiness_reasons'] = reasons
        return {'items': items, 'total': len(items), 'snapshot_at': store.get_meta('accounts_snapshot_at')}

    @app.get('/api/deliveries')
    def deliveries(state: str = '', platform: str = '', page: int = 1, limit: int = 100):
        if not 1 <= page <= 100000 or not 1 <= limit <= 100:
            raise HTTPException(422, 'Parameter halaman tidak valid.')
        where, values = [], []
        for name, value in [('state', state), ('platform', platform)]:
            if value:
                where.append(f'{name}=?')
                values.append(value)
        query = ' WHERE ' + ' AND '.join(where) if where else ''
        with store.connect() as db:
            total = db.execute('SELECT COUNT(*) FROM deliveries'+query, values).fetchone()[0]
            items = [read_models.record(row) for row in db.execute('SELECT * FROM deliveries'+query+' ORDER BY created_at DESC LIMIT ? OFFSET ?', [*values, limit, (page-1)*limit])]
            for item in items:
                attempts = db.execute("SELECT COUNT(*) total, COUNT(CASE WHEN operation='schedule' THEN 1 END) schedules FROM attempts WHERE delivery_id=?", (item['id'],)).fetchone()
                item['available_actions'] = read_models.delivery_actions(item, bool(attempts['total']), has_schedule_attempt=bool(attempts['schedules']))
        return {'items': items, 'total': total, 'page': page, 'limit': limit}

    @app.get('/api/comments')
    def comments(q: str = '', state: str = '', page: int = 1, limit: int = 50):
        if not 1 <= page <= 100000 or not 1 <= limit <= 200 or len(q) > 200:
            raise HTTPException(422, 'Parameter halaman komentar tidak valid.')
        clauses, values = [], []
        if q:
            clauses.append('(text LIKE ? OR author LIKE ? OR reply LIKE ?)')
            values.extend([f'%{q}%'] * 3)
        if state:
            clauses.append('state=?')
            values.append(state)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        with store.connect() as db:
            items = [dict(row) for row in db.execute('SELECT * FROM comments'+where+' ORDER BY updated_at DESC,id LIMIT ? OFFSET ?', [*values, limit, (page-1)*limit])]
            total = db.execute('SELECT COUNT(*) FROM comments'+where, values).fetchone()[0]
        return {'items': items, 'total': total, 'page': page, 'limit': limit}

    @app.get('/api/reports')
    def reports():
        with store.connect() as db:
            items = [dict(row) for row in db.execute('SELECT * FROM metrics ORDER BY sampled_at DESC LIMIT 500')]
        return {'items': items, 'metrics': read_models.overview(store)['charts'], 'quality': 'measured' if items else 'no_provider_metrics', 'generated_at': now()}

    @app.get('/api/personas')
    def personas():
        with store.connect() as db:
            items = [dict(row) for row in db.execute('SELECT p.* FROM personas p JOIN (SELECT id,MAX(version) version FROM personas GROUP BY id) latest ON p.id=latest.id AND p.version=latest.version ORDER BY p.name')]
            for item in items:
                item['bindings'] = [dict(row) for row in db.execute('SELECT * FROM account_personas WHERE persona_id=?', (item['id'],))]
        return {'items': items}

    @app.put('/api/personas/{identifier}')
    def persona(identifier: str, body: Persona):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', identifier):
            raise HTTPException(422, 'ID persona tidak valid.')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            version = db.execute('SELECT COALESCE(MAX(version),0)+1 FROM personas WHERE id=?', (identifier,)).fetchone()[0]
            db.execute('INSERT INTO personas VALUES (?,?,?,?,?)', (identifier, version, body.name, body.style, now()))
            if body.account_id:
                if not db.execute('SELECT 1 FROM accounts WHERE id=?', (body.account_id,)).fetchone():
                    raise HTTPException(422, 'Pilih akun yang sudah terbaca dari provider.')
                db.execute('INSERT INTO account_personas VALUES (?,?,?) ON CONFLICT(account_id) DO UPDATE SET persona_id=excluded.persona_id,persona_version=excluded.persona_version', (body.account_id, identifier, version))
        store.event('persona.saved', identifier, {'version': version})
        return {'id': identifier, 'version': version, 'name': body.name, 'style': body.style, 'account_id': body.account_id}

    @app.get('/api/events')
    def events(after: int = 0, before: int = 0, limit: int = 100):
        if after < 0 or before < 0 or (after and before) or not 1 <= limit <= 500:
            raise HTTPException(422, 'Cursor tidak valid.')
        with store.connect() as db:
            if after:
                rows = db.execute('SELECT * FROM events WHERE id>? ORDER BY id LIMIT ?', (after, limit))
            elif before:
                rows = db.execute('SELECT * FROM events WHERE id<? ORDER BY id DESC LIMIT ?', (before, limit))
            else:
                rows = db.execute('SELECT * FROM events ORDER BY id DESC LIMIT ?', (limit,))
            items = [read_models.record(row) for row in rows]
        return {'items': items, 'cursor': max(item['id'] for item in items) if items else after, 'next_before': min(item['id'] for item in items) if len(items) == limit else None}

    @app.get('/api/configuration')
    def configuration():
        return {**store.configuration(), 'credentials': secret_store.status()}

    @app.post('/api/configuration/validate')
    def configuration_validate(body: Validation):
        return validate_application_config(body.config)

    def validate_application_config(config):
        result = validate_config(config, store.data_dir)
        if result['valid'] and store.get_meta('restore_requires_reconciliation', False) and (config['application']['mode'] != 'shadow' or config['application']['publish_enabled'] or config['reply']['enabled'] or config['telegram']['enabled']):
            result['valid'] = False
            result['errors'].append({'field': 'application', 'message': 'Instalasi hasil restore memerlukan rekonsiliasi ownership dan intent sebelum modul eksternal diaktifkan.'})
        return result

    def check_secret_versions(config):
        for provider, version in config['credentials'].items():
            if version:
                try:
                    secret_store.get(provider, version)
                except (ValueError, OSError):
                    raise HTTPException(422, 'Versi credential tidak tersedia.') from None

    @app.put('/api/configuration')
    def configuration_save(body: Configuration, request: Request):
        result = validate_application_config(body.config)
        if not result['valid']:
            return JSONResponse({'detail': 'Periksa pengaturan yang ditandai.', 'code': 'invalid_configuration', **result}, status_code=422)
        check_secret_versions(body.config)
        try:
            version = store.save_configuration(body.config, body.base_version, request.state.session['user']['id'])
        except ValueError:
            raise HTTPException(409, 'Konfigurasi berubah di sesi lain. Muat ulang sebelum menyimpan.') from None
        return {'version': version, 'status': 'pending', 'impact': result['impact']}

    @app.post('/api/credentials/{provider}')
    def credentials(provider: str, body: dict, request: Request):
        if provider not in PROVIDERS:
            raise HTTPException(404, 'Provider tidak dikenal.')
        configuration = store.configuration()
        try:
            version = secret_store.set(provider, body)
        except ValueError:
            raise HTTPException(422, 'Periksa kelengkapan dan nama kolom credential.') from None
        configuration['config']['credentials'][provider] = version
        try:
            config_version = store.save_configuration(configuration['config'], configuration['desired_version'], request.state.session['user']['id'])
        except ValueError:
            raise HTTPException(409, 'Credential tersimpan, tetapi konfigurasi berubah. Muat ulang sebelum menerapkan versi baru.') from None
        store.event('credential.saved', provider, {'version': version})
        return {'configured': True, 'version': version, 'configuration_version': config_version, 'status': 'pending'}

    @app.post('/api/connections/{provider}/test')
    async def connection_test(provider: str):
        if provider not in PROVIDERS:
            raise HTTPException(404, 'Provider tidak dikenal.')
        try:
            secrets = secret_store.get(provider)
        except (ValueError, OSError):
            return {'valid': False, 'status': 'unreadable', 'detail': 'Credential tersimpan tidak dapat dibaca. Isi ulang melalui formulir.'}
        if not secrets:
            return {'valid': False, 'status': 'not_configured', 'detail': 'Isi credential terlebih dahulu.'}
        try:
            from arker.adapters import test_connection
            result = await test_connection(provider, secrets, store.configuration()['config'])
            result = {**result, 'valid': bool(result.get('connected', result.get('valid'))), 'status': 'connected' if result.get('connected', result.get('valid')) else 'unavailable', 'detail': result.get('message', result.get('detail', 'Pemeriksaan selesai.'))}
        except Exception:
            result = {'valid': False, 'status': 'unavailable', 'detail': 'Pemeriksaan layanan gagal. Credential tetap tersimpan; belum ada perubahan pool akun.'}
        store.event('connection.tested', provider, {'valid': bool(result.get('valid')), 'status': result.get('status')})
        return result

    @app.get('/api/storage')
    def storage():
        configuration = store.configuration()
        current = configuration['config']
        check = storage_check(current['storage']['bank_directory'], current['drive']['folder_url'], store.data_dir)
        with store.connect() as db:
            rows = db.execute('SELECT DISTINCT c.version,c.config FROM configurations c JOIN assets a ON a.config_version=c.version ORDER BY c.version').fetchall()
            verification = {'verified': db.execute("SELECT COUNT(*) FROM artifacts WHERE kind='bank' AND verified_at IS NOT NULL").fetchone()[0], 'awaiting': db.execute("SELECT COUNT(*) FROM artifacts WHERE kind='bank' AND verified_at IS NULL").fetchone()[0]}
        profiles = [{'version': configuration['desired_version'], 'bank_directory': current['storage']['bank_directory'], 'folder_url': current['drive']['folder_url'], 'status': 'active' if configuration['desired_version'] == configuration['applied_version'] else 'pending'}]
        profiles.extend({'version': row['version'], 'bank_directory': json.loads(row['config'])['storage']['bank_directory'], 'folder_url': json.loads(row['config'])['drive']['folder_url'], 'status': 'referenced'} for row in rows if row['version'] != configuration['desired_version'])
        return {'profiles': profiles, 'capacity': check['capacity'], 'verification': verification, 'check': check}

    @app.post('/api/storage/check')
    def check_storage(body: StorageCheck):
        return storage_check(body.bank_directory, body.folder_url, store.data_dir)

    @app.get('/api/backups')
    def backups():
        from arker.backup import list_backups
        result = list_backups(store)
        return result if isinstance(result, dict) else {'items': result}

    @app.post('/api/commands')
    def commands(body: Command):
        allowed = {'apply_configuration': {'version'}, 'pause_processing': set(), 'resume_processing': set(), 'pause_reply': set(), 'resume_reply': set(), 'pause_reports': set(), 'resume_reports': set(), 'sync_accounts': set(), 'reconcile_delivery': {'delivery_id'}, 'retry_delivery_caption': {'delivery_id'}, 'retry_asset': {'asset_id'}, 'backup': set(), 'cleanup': set(), 'cleanup_plan': set()}
        if body.kind not in allowed or set(body.payload) != allowed[body.kind]:
            raise HTTPException(422, 'Perintah atau argumennya tidak didukung.')
        with store.connect() as db:
            previous = db.execute('SELECT * FROM commands WHERE idempotency_key=?', (body.idempotency_key,)).fetchone()
        if previous:
            if previous['kind'] != body.kind or json.loads(previous['payload']) != body.payload:
                raise HTTPException(409, 'Kunci perintah sudah digunakan untuk tindakan berbeda.')
            return {'command': read_models.record(previous)}
        if store.get_meta('restore_requires_reconciliation', False) and body.kind in ('resume_processing', 'resume_reply'):
            raise HTTPException(409, 'Rekonsiliasi hasil restore diperlukan sebelum worker dilanjutkan.')
        if any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value) for key, value in body.payload.items() if key != 'version'):
            raise HTTPException(422, 'ID entitas perintah tidak valid.')
        if body.kind == 'apply_configuration':
            if type(body.payload.get('version')) is not int or body.payload['version'] != store.configuration()['desired_version']:
                raise HTTPException(409, 'Terapkan hanya versi konfigurasi terbaru.')
        if body.kind == 'retry_asset':
            detail = read_models.asset_detail(store, body.payload['asset_id'])
            if not detail or detail['asset']['state'] not in ('failed', 'held') or any(d['state'] in ('published','scheduled','accepted','unknown','submit_unknown') for d in detail['deliveries']):
                raise HTTPException(409, 'Konten belum memenuhi syarat ulang proses lokal.')
            with store.connect() as db:
                if db.execute('SELECT 1 FROM attempts WHERE delivery_id IN (SELECT id FROM deliveries WHERE asset_id=?) LIMIT 1', (body.payload['asset_id'],)).fetchone():
                    raise HTTPException(409, 'Periksa hasil kirim terdahulu sebelum mengulang proses.')
        if body.kind in ('reconcile_delivery', 'retry_delivery_caption'):
            with store.connect() as db:
                row = db.execute('SELECT * FROM deliveries WHERE id=?', (body.payload['delivery_id'],)).fetchone()
                attempts = db.execute("SELECT COUNT(*) total, COUNT(CASE WHEN operation='schedule' THEN 1 END) schedules FROM attempts WHERE delivery_id=?", (body.payload['delivery_id'],)).fetchone()
            actions = read_models.delivery_actions(dict(row), bool(attempts['total']), has_schedule_attempt=bool(attempts['schedules'])) if row else []
            if not any(action['kind'] == body.kind for action in actions):
                message = 'Delivery belum memiliki hasil remote yang dapat diperiksa.' if body.kind == 'reconcile_delivery' else 'Caption hanya dapat diulang pada delivery ditahan tanpa intent atau hasil remote.'
                raise HTTPException(409, message)
        try:
            return {'command': store.command(body.kind, body.payload, body.idempotency_key)}
        except ValueError:
            raise HTTPException(409, 'Kunci perintah sudah digunakan untuk tindakan berbeda.') from None

    @app.get('/api/commands/{identifier}')
    def command(identifier: str):
        with store.connect() as db:
            row = db.execute('SELECT * FROM commands WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise HTTPException(404, 'Perintah tidak ditemukan.')
        return {'command': read_models.record(row)}

    @app.get('/api/media/{asset_id}/{artifact}')
    def media(asset_id: str, artifact: str):
        with store.connect() as db:
            row = db.execute('SELECT artifacts.*,assets.config_version FROM artifacts JOIN assets ON assets.id=artifacts.asset_id WHERE asset_id=? AND kind=?', (asset_id, artifact)).fetchone()
        if not row:
            raise HTTPException(404, 'File tidak ditemukan.')
        path = Path(row['path'])
        config = store.config_at(row['config_version'])
        allowed_roots = [bank_path(config['storage']['bank_directory'], store.data_dir), (store.data_dir / 'cache').resolve(), (store.data_dir / 'work').resolve()]
        if not path.is_absolute() or any(parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()) for parent in [path, *path.parents]) or not any(path.resolve().is_relative_to(root) for root in allowed_roots):
            raise HTTPException(403, 'Lokasi file tidak dapat ditampilkan.')
        media_type = mimetypes.guess_type(path.name)[0]
        if media_type not in ('video/mp4','image/jpeg','image/png','image/webp','audio/wav','audio/mpeg') or not path.is_file():
            raise HTTPException(404, 'Preview file tidak tersedia.')
        return FileResponse(path, media_type=media_type)

    if web_dir is not None and Path(web_dir).is_dir():
        app.mount('/', StaticFiles(directory=web_dir, html=True), name='web')
    return app
