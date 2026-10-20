from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .adapters import AdapterError, Held
from .adapters.ai import AI
from .adapters.drive import Drive
from .adapters.media import Downloader, Media, file_hashes, local_file
from .adapters.telegram import Telegram
from .adapters.repliz import PLATFORMS, Repliz, WIB, iso, remote_id, schedule_evidence
from .config import validate_config
from .secrets import SecretStore


def identifier():
    return uuid.uuid4().hex


def schedule_time(stamp, config):
    local = datetime.fromtimestamp(stamp, WIB) + timedelta(seconds=90)
    start = int(config.get('workflow', {}).get('window_start', 8))
    end = int(config.get('workflow', {}).get('window_end', 23))
    if local.hour >= end:
        local = (local + timedelta(days=1)).replace(hour=start, minute=0, second=0, microsecond=0)
    elif local.hour < start:
        local = local.replace(hour=start, minute=0, second=0, microsecond=0)
    return local.timestamp()


class Worker:
    def __init__(self, store, *, repliz=None, drive=None, downloader=None, media=None, ai=None, telegram=None, clock=time.time, command_handlers=None):
        self.store, self.clock = store, clock
        self.worker_id = identifier()
        self.instance_id = store.get_meta('instance_id')
        self.injected = {'repliz': repliz, 'drive': drive, 'downloader': downloader, 'media': media, 'ai': ai, 'telegram': telegram}
        self.command_handlers = command_handlers or {}
        self.secret_store = SecretStore(store.data_dir)
        self.clients = {}
        self.stopping = False

    def config(self):
        version = self.store.get_meta('applied_version', 0)
        return self.store.config_at(version or self.store.get_meta('desired_version', 1))

    def adapter(self, name, config):
        if self.injected.get(name) is not None:
            return self.injected[name]
        version = config.get('credentials', {}).get(name, 0)
        key = (name, version, json.dumps(config.get(name if name != 'media' else 'video', {}), sort_keys=True))
        if key not in self.clients:
            credentials = self.secret_store.get(name, version) if name in {'repliz', 'drive', 'ai', 'telegram'} and version else {}
            factories = {'telegram': lambda: Telegram(credentials), 'repliz': lambda: Repliz(credentials), 'drive': lambda: Drive(credentials), 'downloader': Downloader, 'media': lambda: Media(config.get('video', {})), 'ai': lambda: AI(config.get('ai', {}), credentials)}
            self.clients[key] = factories[name]()
        return self.clients[key]

    def heartbeat(self):
        self.store.set_meta('worker_heartbeat', self.clock())
        self.store.set_meta('worker_state', 'paused' if self.store.get_meta('processing_paused', False) else 'running')
        self.store.set_meta('worker_id', self.worker_id)
        self.store.set_meta('paused', self.store.get_meta('processing_paused', False))
        self.store.set_meta('reply_enabled', self.config().get('reply', {}).get('enabled', False) and not self.store.get_meta('reply_paused', False))

    async def run(self, *, interval=2, stop_event=None):
        from .locks import DataLock
        with DataLock(self.store.data_dir, 'worker'):
            self.recover()
            async def pulse():
                while not self.stopping:
                    self.heartbeat()
                    await asyncio.sleep(5)
            heartbeat = asyncio.create_task(pulse())
            try:
                while not self.stopping and not (stop_event and stop_event.is_set()):
                    try:
                        await self.tick()
                    except Exception as exc:
                        self.store.event('worker.error', payload={'code': getattr(exc, 'code', 'worker_internal'), 'message': 'Siklus worker tertunda; periksa halaman aktivitas.'})
                    await asyncio.sleep(interval)
            finally:
                self.stopping = True
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
                for client in self.clients.values():
                    if hasattr(client, 'close'):
                        await client.close()
                self.store.set_meta('worker_state', 'stopped')
                self.store.set_meta('worker_heartbeat', self.clock())

    def recover(self):
        from .locks import DataLock
        directory = self.store.data_dir / 'journals'
        with DataLock(self.store.data_dir, 'journal-snapshot', blocking=True):
            with self.store.connect() as db:
                for path in directory.glob('*-intent.json'):
                    intent = json.loads(path.read_text('utf-8'))
                    stamp = intent['created_at']
                    db.execute("INSERT OR IGNORE INTO attempts(id,delivery_id,operation,request_key,state,payload,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", (intent['id'], intent.get('delivery_id'), intent['operation'], intent['request_key'], 'unknown', json.dumps(intent['payload']), stamp, stamp))
                    results = [json.loads(p.read_text('utf-8')) for p in directory.glob(intent['id'] + '-*-result.json')]
                    if results:
                        latest = max(results, key=lambda record: record['at'])
                        if latest.get('state') == 'accepted' and latest.get('remote_id'):
                            db.execute("UPDATE attempts SET state='accepted',remote_id=?,updated_at=? WHERE id=?", (latest['remote_id'], latest['at'], intent['id']))
                db.execute("UPDATE attempts SET state='unknown',updated_at=? WHERE state IN ('sending','prepared')", (self.clock(),))
                for attempt in db.execute("SELECT * FROM attempts WHERE operation='schedule'").fetchall():
                    if attempt['remote_id']:
                        db.execute("UPDATE deliveries SET state='scheduled',remote_id=?,updated_at=? WHERE id=? AND state IN ('pending','submitting','unknown')", (attempt['remote_id'], self.clock(), attempt['delivery_id']))
                    elif attempt['state'] == 'unknown':
                        db.execute("UPDATE deliveries SET state='unknown',error='Hasil pengiriman perlu diperiksa setelah restart.',updated_at=? WHERE id=? AND state NOT IN ('published','failed')", (self.clock(), attempt['delivery_id']))
                for attempt in db.execute("SELECT * FROM attempts WHERE operation='reply'").fetchall():
                    payload = json.loads(attempt['payload'])
                    db.execute("UPDATE comments SET state=?,remote_reply_id=?,updated_at=? WHERE id=? AND state IN ('pending','sending','unknown')", ('replied' if attempt['remote_id'] else 'unknown', attempt['remote_id'], self.clock(), payload.get('comment_id')))
                db.execute("UPDATE commands SET status='pending' WHERE status='running'")
                db.execute('UPDATE assets SET lease_owner=NULL,lease_until=NULL')
        self.store.event('worker.recovered')

    async def tick(self):
        self.heartbeat()
        if not self.store.get_meta('applied_version', 0):
            self.store.command('apply_configuration', {'version': self.store.get_meta('desired_version')}, 'bootstrap-configuration')
        await self.commands()
        if self.stopping:
            return
        if not self.store.get_meta('applied_version', 0):
            self.store.set_meta('worker_state', 'waiting_configuration')
            return
        config = self.config()
        if self.injected['repliz'] or config.get('credentials', {}).get('repliz', 0):
            last = self.store.get_meta('account_sync_attempt', 0)
            if self.clock() - last >= 300:
                self.store.set_meta('account_sync_attempt', self.clock())
                try:
                    await self.sync_accounts(config)
                except AdapterError as exc:
                    self.store.event('accounts.held', payload={'code': exc.code, 'message': str(exc)})
        if config.get('telegram', {}).get('enabled'):
            await self.telegram_cycle(config)
        await self.monitor(config)
        if not self.store.get_meta('processing_paused', False):
            await self.process_asset()
            await self.deliver(config)
        if config.get('reply', {}).get('enabled') and not self.store.get_meta('reply_paused', False):
            await self.reply_cycle(config)
        if config.get('reports', {}).get('enabled') and not self.store.get_meta('reports_paused', False):
            await self.report_cycle(config)
        self.heartbeat()

    async def commands(self):
        with self.store.connect() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM commands WHERE status='pending' ORDER BY created_at LIMIT 20")]
        for command in rows:
            with self.store.connect() as db:
                if db.execute("UPDATE commands SET status='running',updated_at=? WHERE id=? AND status='pending'", (self.clock(), command['id'])).rowcount != 1:
                    continue
            payload, kind = json.loads(command['payload']), command['kind']
            try:
                result = await self.command(kind, payload)
                status = 'succeeded'
            except (AdapterError, ValueError) as exc:
                result, status = {'code': getattr(exc, 'code', 'command_invalid'), 'message': str(exc) if isinstance(exc, AdapterError) else 'Perintah belum dapat diterapkan.'}, 'failed'
            except Exception:
                result, status = {'code': 'command_failed', 'message': 'Perintah gagal; konfigurasi aktif tetap dipertahankan.'}, 'failed'
            with self.store.connect() as db:
                db.execute('UPDATE commands SET status=?,result=?,updated_at=? WHERE id=?', (status, json.dumps(result or {}), self.clock(), command['id']))
            self.store.event('command.' + status, command['id'], {'kind': kind, **(result or {})})

    async def command(self, kind, payload):
        if kind == 'apply_configuration':
            version = int(payload['version'])
            if version < self.store.get_meta('applied_version', 0):
                return {'version': version, 'status': 'superseded'}
            config = self.store.config_at(version)
            validation = validate_config(config, self.store.data_dir)
            valid = validation.get('valid') if isinstance(validation, dict) else not validation
            if not valid:
                raise Held('configuration_invalid', 'Konfigurasi belum valid; periksa formulir pengaturan.')
            bank = Path(config['storage']['bank_directory']).expanduser()
            if not bank.is_absolute():
                bank = self.store.data_dir / bank
            bank.mkdir(parents=True, exist_ok=True)
            if bank.is_symlink() or not os.access(bank, os.W_OK):
                raise Held('bank_unwritable', 'Folder bank konten tidak dapat ditulis.')
            previous_version = self.store.get_meta('applied_version', 0)
            previous = self.store.config_at(previous_version) if previous_version else {}
            from .adapters import test_connection
            for provider, credential_version in config.get('credentials', {}).items():
                changed = credential_version != previous.get('credentials', {}).get(provider, 0)
                if provider == 'drive' and config.get('drive') != previous.get('drive'):
                    changed = True
                if provider == 'ai' and config.get('ai') != previous.get('ai'):
                    changed = True
                if changed and credential_version:
                    credentials = self.secret_store.get(provider, credential_version)
                    await asyncio.wait_for(test_connection(provider, credentials, config), timeout=45)
            self.store.set_meta('applied_version', version)
            self.store.event('configuration.applied', str(version), {'version': version})
            return {'version': version, 'status': 'applied'}
        switches = {'pause_processing': ('processing_paused', True), 'resume_processing': ('processing_paused', False), 'pause_reply': ('reply_paused', True), 'resume_reply': ('reply_paused', False), 'pause_reports': ('reports_paused', True), 'resume_reports': ('reports_paused', False)}
        if kind in switches:
            key, value = switches[kind]
            self.store.set_meta(key, value)
            return {'state': 'paused' if value else 'running'}
        if kind == 'sync_accounts':
            await self.sync_accounts(self.config())
            return {'snapshot_at': self.store.get_meta('accounts_snapshot_at')}
        if kind == 'reconcile_delivery':
            await self.reconcile(payload.get('delivery_id'), self.config())
            return {'checked': True}
        if kind == 'retry_delivery_caption':
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                delivery = db.execute('SELECT state,remote_id FROM deliveries WHERE id=?', (payload.get('delivery_id'),)).fetchone()
                attempted = db.execute('SELECT 1 FROM attempts WHERE delivery_id=? LIMIT 1', (payload.get('delivery_id'),)).fetchone()
                if not delivery or delivery['state'] != 'held' or delivery['remote_id'] or attempted:
                    raise Held('retry_unsafe', 'Caption hanya boleh diulang sebelum ada intent atau hasil pengiriman.')
                db.execute("UPDATE deliveries SET state='pending',error=NULL,updated_at=? WHERE id=?", (self.clock(), payload['delivery_id']))
            return {'queued': True, 'publication_requires_live_gates': True}
        if kind == 'retry_asset':
            with self.store.connect() as db:
                asset = db.execute('SELECT * FROM assets WHERE id=?', (payload.get('asset_id'),)).fetchone()
                if not asset or asset['state'] not in {'failed', 'held', 'waiting'}:
                    raise Held('retry_unavailable', 'Konten ini belum memenuhi syarat mencoba ulang.')
                if db.execute('SELECT 1 FROM attempts WHERE delivery_id IN (SELECT id FROM deliveries WHERE asset_id=?)', (asset['id'],)).fetchone():
                    raise Held('retry_unsafe', 'Sudah ada intent pengiriman; periksa hasil tujuan terlebih dahulu.')
                db.execute("UPDATE assets SET state='processing',error=NULL,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE id=?", (self.clock(), asset['id']))
            return {'queued': True}
        if kind in self.command_handlers:
            result = self.command_handlers[kind](self.store, payload)
            return await result if asyncio.iscoroutine(result) else result
        if kind == 'stop_worker':
            self.stopping = True
            return {'state': 'stopping'}
        if kind == 'backup':
            from .backup import create_backup
            return create_backup(self.store)
        if kind == 'cleanup_plan':
            from .cleanup import cleanup_plan
            return cleanup_plan(self.store)
        if kind == 'cleanup':
            from .cleanup import apply_cleanup
            return apply_cleanup(self.store)
        raise Held('command_unsupported', 'Perintah ini belum tersedia pada worker.')

    def artifact(self, asset_id, kind, path, **extra):
        path = Path(path)
        values = {'id': identifier(), 'asset_id': asset_id, 'kind': kind, 'path': str(path), 'sha256': file_hashes(path)['sha256'], 'size': path.stat().st_size, 'created_at': self.clock(), **extra}
        with self.store.connect() as db:
            columns = ','.join(values)
            db.execute(f'INSERT INTO artifacts({columns}) VALUES ({",".join("?" for _ in values)}) ON CONFLICT(asset_id,kind) DO UPDATE SET path=excluded.path,sha256=excluded.sha256,size=excluded.size', tuple(values.values()))

    def asset_update(self, asset_id, **values):
        with self.store.connect() as db:
            db.execute(f'UPDATE assets SET {",".join(key+"=?" for key in values)},updated_at=? WHERE id=?', (*values.values(), self.clock(), asset_id))

    async def process_asset(self):
        if self.store.get_meta('restore_requires_reconciliation', False):
            return
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM assets WHERE state IN ('queued','processing','waiting') AND (lease_until IS NULL OR lease_until<?) AND (state!='waiting' OR updated_at<?) ORDER BY created_at LIMIT 1", (self.clock(), self.clock() - 30)).fetchone()
            if not row:
                return
            asset = dict(row)
            db.execute('UPDATE assets SET lease_owner=?,lease_until=? WHERE id=?', (self.worker_id, self.clock() + 1800, asset['id']))
        start = self.clock()
        stage = asset['stage']
        try:
            config = self.store.config_at(asset['config_version'])
            if asset['config_version'] > self.store.get_meta('applied_version', 0):
                raise Held('configuration_pending', 'Konten menunggu konfigurasi diterapkan.')
            context = json.loads(asset['context'])
            work = self.store.data_dir / 'work' / asset['id']
            work.mkdir(parents=True, exist_ok=True)
            if stage in {'queued', 'download'}:
                self.asset_update(asset['id'], state='processing', stage='download', progress=None, total=None, error=None)
                result = await self.adapter('downloader', config).download(asset['source_url'], work)
                if not result.get('verified') or not result.get('username'):
                    raise Held('source_owner_unverified', 'Pemilik sumber belum terverifikasi.')
                path = local_file(result['path'], work)
                self.artifact(asset['id'], 'source', path)
                context.update({key: value for key, value in result.items() if key != 'path'})
                self.asset_update(asset['id'], state='processing', stage='inspect', source_username=result['username'], source_verified=1, context=json.dumps(context), error=None)
            elif stage == 'inspect':
                source = self.get_artifact(asset['id'], 'source')
                info = await self.adapter('media', config).probe(source['path'])
                frames = await self.adapter('media', config).frames(source['path'], work, info)
                for index, path in enumerate(frames):
                    self.artifact(asset['id'], 'frame-' + str(index + 1), path)
                context.update({'duration': info['duration'], 'width': info['width'], 'height': info['height'], 'frames': frames})
                if config.get('ai', {}).get('transcription_enabled'):
                    transcription_settings = dict(config['ai'])
                    model_path = Path(transcription_settings['whisper_model']).expanduser()
                    if not model_path.is_absolute():
                        transcription_settings['whisper_model'] = str(self.store.data_dir / model_path)
                    transcript = await self.adapter('media', config).transcribe(source['path'], work, transcription_settings)
                    context.update({'transcript': transcript['text'], 'transcript_status': transcript['status']})
                    if transcript.get('path'):
                        self.artifact(asset['id'], 'transcript', transcript['path'])
                else:
                    context['transcript_status'] = 'disabled'
                self.asset_update(asset['id'], stage='draft', state='processing', context=json.dumps(context), error=None)
            elif stage == 'draft':
                result = await self.adapter('ai', config).draft(context, context.get('frames', []))
                context.update({'facts': result.get('facts', []), 'ai_used': result.get('ai_used', False), 'usage': result.get('usage', {})})
                context.update({key: result[key] for key in ('copy_version', 'copy_origin', 'copy_diagnostics') if key in result})
                caption = self.attribution(result['caption'], asset['source_username'])
                self.asset_update(asset['id'], stage='render', state='processing', hook=result['hook'], caption=caption, context=json.dumps(context), error=None)
            elif stage == 'render':
                last_progress = [0.0]
                def render_progress(completed, total):
                    current = time.monotonic()
                    if current - last_progress[0] >= .5 or completed >= total:
                        self.asset_update(asset['id'], progress=completed, total=total)
                        last_progress[0] = current
                with self.store.connect() as db:
                    already_rendered = db.execute("SELECT 1 FROM artifacts WHERE asset_id=? AND kind='render'", (asset['id'],)).fetchone()
                if already_rendered:
                    result = self.get_artifact(asset['id'], 'render')
                else:
                    source = self.get_artifact(asset['id'], 'source')
                    result = await self.adapter('media', config).render(source['path'], work / 'rendered.mp4', asset['hook'], on_progress=render_progress)
                    if result.get('layout'):
                        context['hook_layout'] = result['layout']
                        self.asset_update(asset['id'], context=json.dumps(context))
                    self.artifact(asset['id'], 'render', result['path'])
                bank = Path(config['storage']['bank_directory']).expanduser()
                if not bank.is_absolute():
                    bank = self.store.data_dir / bank
                bank.mkdir(parents=True, exist_ok=True)
                target = bank / (asset['id'] + '.mp4')
                pending = bank / (asset['id'] + '.partial')
                shutil.copyfile(result['path'], pending)
                if file_hashes(pending)['sha256'] != result['sha256']:
                    raise Held('bank_copy', 'Salinan bank konten belum cocok.')
                os.replace(pending, target)
                self.artifact(asset['id'], 'bank', target)
                if config['application']['mode'] == 'shadow' and not config.get('drive', {}).get('folder_url'):
                    self.shadow_ready(asset['id'])
                else:
                    self.asset_update(asset['id'], stage='drive', state='processing', error=None)
            elif stage == 'drive':
                bank = self.get_artifact(asset['id'], 'bank')
                result = await self.adapter('drive', config).verify(bank['path'], config['drive']['folder_url'])
                with self.store.connect() as db:
                    db.execute("UPDATE artifacts SET drive_id=?,drive_url=?,verified_at=? WHERE asset_id=? AND kind='bank'", (result['id'], result['url'], self.clock(), asset['id']))
                if config['application']['mode'] == 'shadow':
                    self.shadow_ready(asset['id'])
                else:
                    self.asset_update(asset['id'], stage='delivery', state='ready', error=None)
            self.store.event('asset.stage', asset['id'], {'stage': stage, 'duration_seconds': max(0, self.clock() - start)})
        except Held as exc:
            self.asset_update(asset['id'], state='waiting' if exc.code.startswith(('drive_', 'configuration_')) else 'held', error=str(exc), progress=None, total=None)
            self.store.event('asset.held', asset['id'], {'stage': stage, 'code': exc.code, 'message': str(exc)})
        except Exception as exc:
            self.asset_update(asset['id'], state='failed', error='Pengolahan terhenti. Periksa rincian tahap lalu coba ulang.', progress=None, total=None)
            self.store.event('asset.failed', asset['id'], {'stage': stage, 'code': getattr(exc, 'code', 'processing_failed')})
        finally:
            with self.store.connect() as db:
                db.execute('UPDATE assets SET lease_owner=NULL,lease_until=NULL WHERE id=? AND lease_owner=?', (asset['id'], self.worker_id))

    def shadow_ready(self, asset_id):
        self.asset_update(asset_id, stage='preview', state='preview_ready', progress=None, total=None, error=None)
        with self.store.connect() as db:
            db.execute("UPDATE deliveries SET state='shadow',updated_at=? WHERE asset_id=? AND state='pending'", (self.clock(), asset_id))
        self.store.event('asset.preview_ready', asset_id, {'published': False})

    def get_artifact(self, asset_id, kind):
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM artifacts WHERE asset_id=? AND kind=?', (asset_id, kind)).fetchone()
        if not row:
            raise Held('artifact_missing', 'File tahap sebelumnya belum tersedia.')
        path = Path(row['path'])
        if not path.is_file() or path.is_symlink() or file_hashes(path)['sha256'] != row['sha256']:
            raise Held('artifact_changed', 'File berubah setelah diperiksa; proses ditahan.')
        return dict(row)

    @staticmethod
    def attribution(caption, username):
        import re
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.]{1,30}', username):
            raise Held('source_owner_unverified', 'Username sumber belum terverifikasi.')
        lines = [line for line in str(caption).splitlines() if not re.match(r'^\s*source\s*:', line, flags=re.I)]
        return '\n'.join(lines).strip() + '\n\nsource: @' + username

    async def sync_accounts(self, config):
        provider = self.adapter('repliz', config)
        accounts = await provider.accounts()
        scheduled = schedule_time(self.clock(), config)
        local = datetime.fromtimestamp(scheduled, WIB)
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        schedules = await provider.schedules(midnight.timestamp(), (midnight + timedelta(days=1)).timestamp())
        day = midnight.date().isoformat()
        normalized, usage, remote_ids = [], {}, set()
        for item in schedules:
            rid, account_id = remote_id(item), item.get('accountId')
            if not isinstance(account_id, str) or item.get('status') not in {'pending', 'process', 'success', 'error'}:
                raise Held('quota_snapshot_incomplete', 'Snapshot kuota belum lengkap.')
            usage[account_id] = usage.get(account_id, 0) + 1
            remote_ids.add(rid)
        scope = config.get('ownership', {})
        excluded = set(scope.get('excluded_account_ids', []))
        owned = set(scope.get('account_ids', [])) if scope.get('acknowledged') else set()
        for item in accounts:
            account_id = remote_id(item)
            platform = item.get('type')
            if platform not in PLATFORMS:
                continue
            if type(item.get('isConnected')) is not bool or not isinstance(item.get('username'), str) or not item['username'].strip():
                raise Held('identity_snapshot_incomplete', 'Identitas dan koneksi akun belum lengkap.')
            supplied_limit = item.get('dailyLimit', 20)
            if type(supplied_limit) is not int or not 0 <= supplied_limit <= 10000:
                raise Held('quota_snapshot_incomplete', 'Batas kuota akun belum dapat dibaca.')
            capabilities = {'post': True, 'reply': True, 'like': platform != 'youtube', 'source': 'repliz_public_contract', 'snapshot_complete': True}
            normalized.append((account_id, platform, item['username'].strip(), str(item.get('name', '')), int(item['isConnected']), json.dumps(capabilities), min(20, config['workflow']['daily_video_limit'], supplied_limit), usage.get(account_id, 0), day, self.clock(), int(item['isConnected'] and account_id in owned and account_id not in excluded), self.instance_id if account_id in owned else None))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE accounts SET enabled=0,connected=0')
            db.executemany('INSERT INTO accounts(id,platform,username,name,connected,capabilities,quota_limit,quota_used,quota_day,snapshot_at,enabled,ownership_instance) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET platform=excluded.platform,username=excluded.username,name=excluded.name,connected=excluded.connected,capabilities=excluded.capabilities,quota_limit=excluded.quota_limit,quota_used=excluded.quota_used,quota_day=excluded.quota_day,snapshot_at=excluded.snapshot_at,enabled=excluded.enabled,ownership_instance=excluded.ownership_instance', normalized)
            for rid in remote_ids:
                db.execute("UPDATE reservations SET state='observed' WHERE delivery_id IN (SELECT id FROM deliveries WHERE remote_id=?)", (rid,))
        self.store.set_meta('accounts_snapshot_at', self.clock())
        self.store.set_meta('accounts_snapshot_day', day)
        self.store.event('accounts.synced', payload={'count': len(normalized), 'quota_day': day})

    def live_allowed(self, config, *, module="processing"):
        if self.store.get_meta("restore_requires_reconciliation", False):
            return False
        current = self.config()
        for settings in (config, current):
            if settings.get('application', {}).get('mode') != 'live' or not settings.get('application', {}).get('publish_enabled') or not settings.get('ownership', {}).get('acknowledged'):
                return False
        if module == 'reply':
            return all(settings.get('reply', {}).get('enabled') for settings in (config, current)) and not self.store.get_meta('reply_paused', False)
        return not self.store.get_meta('processing_paused', False)

    async def deliver(self, config):
        if not self.live_allowed(config):
            return
        config_version = self.store.get_meta('applied_version', 0)
        with self.store.connect() as db:
            row = db.execute("SELECT d.*,a.config_version,a.hook,a.caption,a.source_username,a.source_verified FROM deliveries d JOIN assets a ON d.asset_id=a.id WHERE d.state='pending' AND a.state='ready' AND (d.error IS NULL OR d.updated_at<?) ORDER BY d.created_at LIMIT 1", (self.clock() - 30,)).fetchone()
        if not row:
            return
        delivery = dict(row)
        asset_config = self.store.config_at(delivery['config_version'])
        if not self.live_allowed(asset_config):
            return
        try:
            bank = self.get_artifact(delivery['asset_id'], 'bank')
            if not bank['verified_at'] or not bank['drive_id'] or not delivery['source_verified']:
                raise Held('delivery_proof_missing', 'Bukti Drive atau identitas sumber belum lengkap.')
            # Verify remote bytes again immediately before creating the durable send intent.
            verified = await self.adapter('drive', asset_config).verify(bank['path'], asset_config['drive']['folder_url'])
            if verified.get('id') != bank['drive_id'] or verified.get('sha256') != bank['sha256']:
                raise Held('drive_identity_changed', 'Identitas atau checksum file Drive berubah setelah verifikasi awal.')
            scheduled = schedule_time(self.clock(), config)
            day = datetime.fromtimestamp(scheduled, WIB).date().isoformat()
            account = self.reserve(delivery, day, config)
            provider = self.adapter('repliz', config)
            identity = await provider.account(account['id'])
            if remote_id(identity) != account['id'] or identity.get('username', '').strip() != account['username'] or identity.get('type') != delivery['platform'] or identity.get('isConnected') is not True:
                raise Held('account_identity', 'Identitas akun berubah; lakukan sinkronisasi ulang.')
            caption = delivery['caption']
            persona = self.persona(account['id'])
            if persona and asset_config.get('ai', {}).get('enabled'):
                with self.store.connect() as db:
                    context = json.loads(db.execute('SELECT context FROM assets WHERE id=?', (delivery['asset_id'],)).fetchone()[0])
                context.update(rendered_hook=delivery['hook'], base_caption=caption)
                try:
                    draft = await self.adapter('ai', asset_config).draft(context, context.get('frames', []), persona['style'])
                except AdapterError as exc:
                    raise Held('caption_review', 'Caption akun belum siap. Periksa pengaturan AI dan konteks, lalu pilih ulangi caption untuk melanjutkan.') from exc
                caption = draft['caption']
                self.store.event('delivery.persona', delivery['id'], {'persona_id': persona['id'], 'version': persona['version']})
            payload = {'title': (caption or '').splitlines()[0][:90], 'description': self.attribution(caption, delivery['source_username']), 'type': 'reel' if delivery['platform'] == 'facebook' else 'video', 'medias': [{'type': 'video', 'url': bank['drive_url']}], 'accountId': account['id'], 'scheduleAt': iso(scheduled)}
            scheduled = schedule_time(self.clock(), config)
            if datetime.fromtimestamp(scheduled, WIB).date().isoformat() != day:
                raise Held('schedule_day_changed', 'Hari kuota berubah saat draft disiapkan; reservasi akan diperiksa ulang.')
            payload['scheduleAt'] = iso(scheduled)
            if not self.live_allowed(asset_config):
                raise Held('publishing_paused', 'Pengiriman dijeda sebelum intent dibuat.')
            attempt = self.intent(delivery['id'], 'schedule', 'schedule:' + delivery['id'], payload, config_version=config_version)
            with self.store.connect() as db:
                db.execute("UPDATE deliveries SET state='submitting',scheduled_at=?,updated_at=? WHERE id=?", (scheduled, self.clock(), delivery['id']))
            try:
                result = await provider.create_schedule(payload)
                rid = remote_id(result)
                if result.get('accountId') != account['id']:
                    raise AdapterError('schedule_identity', 'Identitas hasil jadwal belum cocok.', ambiguous=True)
            except Exception as exc:
                self.finish_attempt(attempt, 'unknown', None)
                with self.store.connect() as db:
                    db.execute("UPDATE deliveries SET state='unknown',error='Hasil pengiriman belum diketahui; periksa sebelum mencoba lagi.',updated_at=? WHERE id=?", (self.clock(), delivery['id']))
                self.store.event('delivery.unknown', delivery['id'], {'code': getattr(exc, 'code', 'send_interrupted')})
                return
            self.finish_attempt(attempt, 'accepted', rid)
            with self.store.connect() as db:
                db.execute("UPDATE deliveries SET state='scheduled',remote_id=?,error=NULL,updated_at=? WHERE id=?", (rid, self.clock(), delivery['id']))
            self.store.event('delivery.scheduled', delivery['id'])
        except Held as exc:
            with self.store.connect() as db:
                db.execute('UPDATE deliveries SET error=?,updated_at=? WHERE id=?', (str(exc), self.clock(), delivery['id']))
                if exc.code == 'caption_review':
                    db.execute("UPDATE deliveries SET state='held' WHERE id=?", (delivery['id'],))
                    db.execute("DELETE FROM reservations WHERE delivery_id=? AND state='reserved'", (delivery['id'],))
            self.store.event('delivery.held', delivery['id'], {'code': exc.code, 'message': str(exc)})

    def reserve(self, delivery, day, config):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM attempts WHERE request_key=?', ('schedule:' + delivery['id'],)).fetchone():
                raise Held('intent_exists', 'Intent pengiriman sudah ada; gunakan pemeriksaan hasil.')
            existing = db.execute('SELECT * FROM reservations WHERE delivery_id=?', (delivery['id'],)).fetchone()
            scope = config.get('ownership', {})
            owned, excluded = set(scope.get('account_ids', [])), set(scope.get('excluded_account_ids', []))
            rows = db.execute("SELECT a.*, (SELECT COUNT(*) FROM reservations r WHERE r.account_id=a.id AND r.day=? AND r.state='reserved') AS reserved FROM accounts a WHERE a.platform=? AND a.enabled=1 AND a.connected=1 AND a.quota_day=? AND a.snapshot_at>? AND a.ownership_instance=? ORDER BY (a.quota_used+(SELECT COUNT(*) FROM reservations r WHERE r.account_id=a.id AND r.day=? AND r.state='reserved')),a.id", (day, delivery['platform'], day, self.clock() - 300, self.instance_id, day)).fetchall()
            candidates = [dict(row) for row in rows if row['id'] in owned and row['id'] not in excluded and json.loads(row['capabilities']).get('snapshot_complete') and json.loads(row['capabilities']).get('post')]
            if existing:
                selected = next((a for a in candidates if a['id'] == existing['account_id'] and existing['day'] == day), None)
                if selected and selected['quota_used'] + selected['reserved'] <= min(20, config['workflow']['daily_video_limit'], selected['quota_limit']):
                    return selected
                db.execute('DELETE FROM reservations WHERE delivery_id=?', (delivery['id'],))
                for candidate in candidates:
                    if candidate['id'] == existing['account_id'] and existing['day'] == day:
                        candidate['reserved'] = max(0, candidate['reserved'] - 1)
            selected = next((a for a in candidates if a['quota_used'] + a['reserved'] < min(20, config['workflow']['daily_video_limit'], a['quota_limit'])), None)
            if not selected:
                raise Held('quota_or_account_wait', 'Menunggu akun siap, snapshot segar, atau kuota harian.')
            db.execute('INSERT INTO reservations(id,account_id,delivery_id,day) VALUES (?,?,?,?)', (identifier(), selected['id'], delivery['id'], day))
            db.execute('UPDATE deliveries SET account_id=? WHERE id=?', (selected['id'], delivery['id']))
            return selected

    def journal(self, record, suffix):
        directory = self.store.data_dir / 'journals'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = directory / (record['id'] + '-' + suffix + '.json')
        with path.open('x', encoding='utf-8') as stream:
            os.chmod(path, 0o600)
            json.dump(record, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != 'nt':
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return path

    def intent(self, delivery_id, operation, key, payload, *, config_version=None):
        from .locks import DataLock
        version = self.store.get_meta('applied_version', 0) if config_version is None else config_version
        if type(version) is not int or version < 1:
            raise Held('intent_config_missing', 'Konfigurasi intent belum diterapkan; pengiriman ditahan.')
        self.store.config_at(version)
        # Local metadata must never become part of a provider request body.
        stored_payload = {**payload, '_arker_config_version': version}
        record = {'id': identifier(), 'delivery_id': delivery_id, 'operation': operation, 'request_key': key, 'state': 'sending', 'payload': stored_payload, 'created_at': self.clock()}
        with DataLock(self.store.data_dir, 'journal-snapshot', blocking=True):
            # The file is durable before the database row and network call; orphan intent files also block retry.
            for path in (self.store.data_dir / 'journals').glob('*-intent.json'):
                if json.loads(path.read_text('utf-8')).get('request_key') == key:
                    raise Held('intent_exists', 'Jurnal intent sudah ada; periksa hasil terlebih dahulu.')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT 1 FROM attempts WHERE request_key=?', (key,)).fetchone():
                    raise Held('intent_exists', 'Intent sudah ada; pengiriman tidak diulang.')
                self.journal(record, 'intent')
                db.execute('INSERT INTO attempts(id,delivery_id,operation,request_key,state,payload,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)', (record['id'], delivery_id, operation, key, 'sending', json.dumps(stored_payload), self.clock(), self.clock()))
        return record['id']

    def finish_attempt(self, attempt_id, state, remote):
        from .locks import DataLock
        with DataLock(self.store.data_dir, 'journal-snapshot', blocking=True):
            with self.store.connect() as db:
                row = db.execute('SELECT * FROM attempts WHERE id=?', (attempt_id,)).fetchone()
                if not row:
                    raise Held('journal_missing', 'Intent tidak ditemukan.')
                self.journal({'id': attempt_id, 'state': state, 'remote_id': remote, 'at': self.clock()}, identifier() + '-result')
                db.execute('UPDATE attempts SET state=?,remote_id=?,updated_at=? WHERE id=?', (state, remote, self.clock(), attempt_id))

    async def monitor(self, config):
        with self.store.connect() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM deliveries WHERE state IN ('scheduled','unknown') AND remote_id IS NOT NULL AND updated_at<? ORDER BY updated_at LIMIT 10", (self.clock() - 30,))]
        for delivery in rows:
            try:
                await self.reconcile(delivery['id'], config)
            except AdapterError as exc:
                self.store.event('delivery.reconcile_held', delivery['id'], {'code': exc.code, 'message': str(exc)})

    async def reconcile(self, delivery_id, config):
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM deliveries WHERE id=?', (delivery_id,)).fetchone()
            attempt = db.execute("SELECT * FROM attempts WHERE delivery_id=? AND operation='schedule'", (delivery_id,)).fetchone()
        if not row or not attempt:
            raise Held('reconcile_missing', 'Pengiriman belum mempunyai intent yang bisa diperiksa.')
        delivery, attempt = dict(row), dict(attempt)
        payload = json.loads(attempt['payload'])
        version = payload.get('_arker_config_version')
        if type(version) is not int or version < 1:
            raise Held('reconcile_config_missing', 'Versi konfigurasi intent tidak tercatat; pemeriksaan otomatis ditahan.')
        try:
            pinned_config = self.store.config_at(version)
            provider = self.adapter('repliz', pinned_config)
        except (ValueError, OSError):
            raise Held('reconcile_credentials_unavailable', 'Konfigurasi atau credential asal intent tidak tersedia; pemeriksaan ditahan.') from None
        rid = delivery['remote_id'] or attempt['remote_id']
        if not rid:
            stamp = datetime.fromisoformat(payload['scheduleAt'].replace('Z', '+00:00')).timestamp()
            candidates = await provider.schedules(stamp - 1, stamp + 1)
            matches = [item for item in candidates if all(item.get(key) == payload.get(key) for key in ('accountId', 'description', 'scheduleAt', 'medias'))]
            if len(matches) != 1:
                raise Held('reconcile_ambiguous', 'Belum ada satu hasil provider yang cocok. Pengiriman tetap ditahan.')
            rid = remote_id(matches[0])
        data = await provider.schedule(rid)
        evidence = schedule_evidence(data, rid, delivery['account_id'], delivery['platform'])
        self.finish_attempt(attempt['id'], 'accepted', rid)
        with self.store.connect() as db:
            db.execute('UPDATE deliveries SET state=?,remote_id=?,post_url=?,published_at=?,error=?,updated_at=? WHERE id=?', (evidence['state'], rid, evidence['post_url'], self.clock() if evidence['state'] == 'published' else None, 'Provider gagal menerbitkan jadwal; periksa di provider.' if evidence['state'] == 'failed' else None, self.clock(), delivery_id))
            unfinished = db.execute("SELECT COUNT(*) FROM deliveries WHERE asset_id=? AND state!='published'", (delivery['asset_id'],)).fetchone()[0]
            if unfinished == 0:
                db.execute("UPDATE assets SET state='published',stage='complete',updated_at=? WHERE id=?", (self.clock(), delivery['asset_id']))
        self.store.event('delivery.' + evidence['state'], delivery_id)

    async def reply_cycle(self, config):
        if not self.live_allowed(config, module='reply') or self.clock() - self.store.get_meta('reply_poll_at', 0) < 120:
            return
        config_version = self.store.get_meta('applied_version', 0)
        self.store.set_meta('reply_poll_at', self.clock())
        try:
            provider = self.adapter('repliz', config)
            comments = await provider.comments()
            for item in comments:
                comment_id = remote_id(item)
                comment, content = item.get('comment', {}), item.get('content', {})
                with self.store.connect() as db:
                    delivery = db.execute("SELECT d.*,a.context FROM deliveries d JOIN assets a ON a.id=d.asset_id WHERE d.state='published' AND d.account_id=? AND d.post_url=?", (item.get('accountId'), content.get('url'))).fetchone()
                    if not delivery or not isinstance(comment.get('text'), str) or content.get('hasAutomation') is not False:
                        continue
                    db.execute('INSERT OR IGNORE INTO comments(id,account_id,post_id,asset_id,parent_id,text,author,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)', (comment_id, delivery['account_id'], content.get('id'), delivery['asset_id'], comment.get('parentId'), comment['text'], str(comment.get('owner', {}).get('name', '')), self.clock(), self.clock()))
            with self.store.connect() as db:
                row = db.execute("SELECT c.*,a.context FROM comments c JOIN assets a ON a.id=c.asset_id WHERE c.state='pending' ORDER BY c.created_at LIMIT 1").fetchone()
            if not row:
                return
            comment = dict(row)
            day_start = datetime.fromtimestamp(self.clock(), WIB).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
            with self.store.connect() as db:
                quota = db.execute("SELECT COUNT(*) FROM attempts WHERE operation='reply' AND created_at>=? AND json_extract(payload,'$.account_id')=?", (day_start, comment['account_id'])).fetchone()[0]
                account = db.execute('SELECT * FROM accounts WHERE id=? AND enabled=1 AND connected=1 AND ownership_instance=? AND snapshot_at>?', (comment['account_id'], self.instance_id, self.clock() - 300)).fetchone()
                thread = [dict(row) for row in db.execute('SELECT text,reply FROM comments WHERE post_id=? AND id!=? ORDER BY created_at LIMIT 20', (comment['post_id'], comment['id']))]
            if not account or not json.loads(account['capabilities']).get('reply') or quota >= config['reply']['daily_limit']:
                return
            persona = self.persona(comment['account_id'])
            reply = await self.adapter('ai', config).reply(json.loads(comment['context']), comment['text'], thread, persona['style'] if persona else 'Santai, jelas, sesuai fakta video.')
            if reply is None:
                with self.store.connect() as db:
                    db.execute("UPDATE comments SET state='skipped',updated_at=? WHERE id=?", (self.clock(), comment['id']))
                return
            if any(previous.get('reply') == reply for previous in thread):
                with self.store.connect() as db:
                    db.execute("UPDATE comments SET state='skipped',updated_at=? WHERE id=?", (self.clock(), comment['id']))
                return
            identity = await provider.account(comment['account_id'])
            if remote_id(identity) != account['id'] or identity.get('username', '').strip() != account['username'] or identity.get('isConnected') is not True:
                raise Held('reply_identity', 'Identitas akun balasan berubah; sinkronisasi ulang diperlukan.')
            scope = self.config().get('ownership', {})
            if comment['account_id'] not in scope.get('account_ids', []) or comment['account_id'] in scope.get('excluded_account_ids', []):
                raise Held('reply_ownership', 'Akun tidak berada dalam scope balasan instalasi ini.')
            if not self.live_allowed(config, module='reply'):
                return
            attempt = self.intent(None, 'reply', 'reply:' + comment['id'], {'comment_id': comment['id'], 'account_id': comment['account_id'], 'text': reply}, config_version=config_version)
            with self.store.connect() as db:
                db.execute("UPDATE comments SET state='sending',reply=?,updated_at=? WHERE id=?", (reply, self.clock(), comment['id']))
            try:
                rid = await provider.reply(comment['id'], reply)
            except Exception:
                self.finish_attempt(attempt, 'unknown', None)
                with self.store.connect() as db:
                    db.execute("UPDATE comments SET state='unknown',updated_at=? WHERE id=?", (self.clock(), comment['id']))
                return
            self.finish_attempt(attempt, 'accepted', rid)
            with self.store.connect() as db:
                db.execute("UPDATE comments SET state='replied',remote_reply_id=?,updated_at=? WHERE id=?", (rid, self.clock(), comment['id']))
            self.store.event('comment.replied', comment['id'])
        except AdapterError as exc:
            self.store.event('reply.held', payload={'code': exc.code, 'message': str(exc)})

    def persona(self, account_id):
        with self.store.connect() as db:
            row = db.execute('SELECT p.* FROM account_personas b JOIN personas p ON p.id=b.persona_id AND p.version=b.persona_version WHERE b.account_id=?', (account_id,)).fetchone()
        return dict(row) if row else None

    async def report_cycle(self, config):
        if self.clock() - self.store.get_meta('report_poll_at', 0) < 3600:
            return
        self.store.set_meta('report_poll_at', self.clock())
        try:
            provider = self.adapter('repliz', config)
            with self.store.connect() as db:
                accounts = [dict(row) for row in db.execute('SELECT id FROM accounts WHERE connected=1')]
            sampled = 0
            for account in accounts:
                try:
                    data = await provider.statistic(account['id'])
                    metrics = {key: value for key, value in data.items() if key in {'followersCount', 'followingCount', 'totalLikes', 'videosCount', 'views', 'comments', 'likes', 'shares', 'subscribers', 'subscriberCount'} and type(value) in (int, float) and math.isfinite(value)}
                    if not metrics:
                        self.store.event('report.unavailable', account['id'], {'message': 'Provider belum menyediakan metrik yang dikenali; tidak dianggap nol.'})
                        continue
                    with self.store.connect() as db:
                        db.executemany('INSERT INTO metrics(account_id,kind,value,sampled_at) VALUES (?,?,?,?)', [(account['id'], kind, value, self.clock()) for kind, value in metrics.items()])
                    sampled += 1
                except AdapterError as exc:
                    self.store.event('report.held', account['id'], {'code': exc.code})
            self.store.event('report.collected', payload={'sampled_accounts': sampled, 'requested_accounts': len(accounts)})
        except AdapterError as exc:
            self.store.event('report.held', payload={'code': exc.code, 'message': str(exc)})

    async def notify(self, config, chat_id, text, key):
        with self.store.connect() as db:
            if db.execute('SELECT 1 FROM attempts WHERE request_key=?', (key,)).fetchone():
                return
        attempt = self.intent(None, 'telegram', key, {'chat_id': str(chat_id), 'text': text})
        try:
            result = await self.adapter('telegram', config).send(chat_id, text)
            self.finish_attempt(attempt, 'accepted', result)
        except AdapterError as exc:
            self.finish_attempt(attempt, 'unknown', None)
            self.store.event('notification.unknown', payload={'code': exc.code, 'message': 'Hasil kirim pemberitahuan belum diketahui; tidak dikirim ulang otomatis.'})

    async def telegram_cycle(self, config):
        import re
        from .ingest import intake
        if self.clock() - self.store.get_meta('telegram_poll_at', 0) < 5:
            return
        self.store.set_meta('telegram_poll_at', self.clock())
        try:
            provider = self.adapter('telegram', config)
            updates = await provider.updates(self.store.get_meta('telegram_offset', 0))
            for update in updates:
                update_id = update.get('update_id')
                if type(update_id) is not int:
                    raise Held('telegram_shape', 'Pesan Telegram belum memiliki identitas update.')
                message = update.get('message', {})
                sender = str(message.get('from', {}).get('id', ''))
                chat = message.get('chat', {})
                # Group chats never receive private batch details or admin controls.
                if chat.get('type') == 'private' and sender and str(chat.get('id')) == sender and not message.get('from', {}).get('is_bot'):
                    is_admin = sender == str(config['telegram'].get('admin_id'))
                    text = str(message.get('text') or '')
                    reply = None
                    if text.strip() in {'/pause', '/resume'} and is_admin:
                        kind = 'pause_processing' if text.strip() == '/pause' else 'resume_processing'
                        self.store.command(kind, {}, 'telegram-command:' + str(update_id))
                        reply = 'Perintah diterima. Worker akan mengonfirmasi perubahan melalui panel.'
                    elif text.strip() in {'/start', '/help'}:
                        reply = 'Kirim satu atau beberapa link Reel Instagram. Satu video memiliki tiga tujuan: TikTok, Facebook, dan YouTube. Rincian batch hanya untuk pengirim dan admin.'
                    elif config['telegram'].get('public_ingest', True) or is_admin:
                        urls = re.findall(r'https://(?:www\.)?instagram\.com/[^\s<>]+', text)
                        if urls:
                            result = intake(self.store, urls, source='telegram:' + sender)
                            reply = f"Link diterima: {len(result['accepted'])}\nSudah pernah masuk: {len(result['duplicates'])}\nBelum diterima: {len(result['rejected'])}\nMode: {config['application']['mode']}"
                    if reply:
                        await self.notify(config, chat['id'], reply, 'telegram-update:' + str(update_id))
                self.store.set_meta('telegram_offset', update_id + 1)
            cursor = self.store.get_meta('telegram_event_cursor', 0)
            with self.store.connect() as db:
                events = [dict(row) for row in db.execute("SELECT e.*,b.source FROM events e JOIN assets a ON a.id=e.entity_id JOIN batches b ON b.id=a.batch_id WHERE e.id>? AND e.kind IN ('asset.preview_ready','asset.failed','asset.held') ORDER BY e.id LIMIT 30", (cursor,))]
            for event in events:
                if event['source'].startswith('telegram:'):
                    chat_id = event['source'].split(':', 1)[1]
                    descriptions = {'asset.preview_ready': 'Preview video sudah siap. Mode shadow: belum dipublikasikan.', 'asset.failed': 'Pengolahan video terhenti. Buka panel untuk melihat tahap dan penyebabnya.', 'asset.held': 'Video menunggu pemeriksaan. Buka panel untuk melihat syarat yang belum lengkap.'}
                    await self.notify(config, chat_id, descriptions[event['kind']] + '\nKonten: ' + event['entity_id'], 'telegram-event:' + str(event['id']))
                self.store.set_meta('telegram_event_cursor', event['id'])
        except (AdapterError, ValueError) as exc:
            self.store.event('telegram.held', payload={'code': getattr(exc, 'code', 'telegram_input'), 'message': 'Telegram menunggu koneksi atau input yang valid.'})
