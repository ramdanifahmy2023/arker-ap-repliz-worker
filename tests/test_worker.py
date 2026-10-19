import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from arker.adapters import AdapterError, Held
from arker.adapters.media import file_hashes
from arker.db import Store
from arker.worker import Worker, schedule_time


STAMP = 1792375200.0


def asset(store, name='fixture', state='queued', stage='queued', version=1):
    with store.connect() as db:
        db.execute('INSERT INTO assets(id,source_url,state,stage,config_version,created_at,updated_at) VALUES (?,?,?,?,?,?,?)', (name, 'https://www.instagram.com/reel/' + name + '/', state, stage, version, STAMP, STAMP))
        for platform in ('tiktok', 'facebook', 'youtube'):
            db.execute('INSERT INTO deliveries(id,asset_id,platform,created_at,updated_at) VALUES (?,?,?,?,?)', (name + '-' + platform, name, platform, STAMP, STAMP))
    return name


class DownloadFixture:
    async def download(self, url, directory):
        path = Path(directory) / 'source.mp4'
        path.write_bytes(b'isolated source fixture')
        return {'path': str(path), 'username': 'fixture_source', 'verified': True, 'description': 'Video fixture'}


class MediaFixture:
    async def probe(self, path):
        return {'duration': 4, 'width': 360, 'height': 640}

    async def frames(self, source, directory, info):
        paths = []
        for index in range(6):
            path = Path(directory) / f'frame-{index}.jpg'
            path.write_bytes(b'fixtureframe')
            paths.append(str(path))
        return paths

    async def render(self, source, destination, hook, **kwargs):
        destination.write_bytes(b'isolated rendered fixture')
        return {'path': str(destination), 'sha256': file_hashes(destination)['sha256'], 'size': destination.stat().st_size}


class ProviderFixture:
    def __init__(self):
        self.created = []
        self.should_timeout = False
        self.remote = []
        self.partial = False

    async def accounts(self):
        if self.partial:
            raise Held('snapshot_incomplete', 'Fixture partial')
        return [{'id': 'account-' + p, 'type': p, 'username': p + '_fixture', 'name': p, 'isConnected': True} for p in ('tiktok', 'facebook', 'youtube')]

    async def schedules(self, start, end):
        return self.remote

    async def account(self, identifier):
        return next(a for a in await self.accounts() if a['id'] == identifier)

    async def create_schedule(self, payload):
        self.created.append(payload)
        if self.should_timeout:
            raise AdapterError('provider_timeout', 'Fixture timeout', ambiguous=True)
        result = {'id': 'remote-' + str(len(self.created)), 'status': 'pending', **payload}
        self.remote.append(result)
        return result

    async def schedule(self, identifier):
        return next(item for item in self.remote if item['id'] == identifier)


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name))
        self.provider = ProviderFixture()
        self.drive = AsyncMock()
        self.drive.verify.return_value = {'id': 'drivefixture12345', 'url': 'https://drive.google.com/uc?id=drivefixture12345'}
        self.worker = Worker(self.store, downloader=DownloadFixture(), media=MediaFixture(), clock=lambda: STAMP)

    def tearDown(self):
        self.temp.cleanup()

    async def test_shadow_pipeline_three_deliveries_and_no_provider_calls(self):
        asset(self.store)
        self.worker.injected['repliz'] = self.provider
        for _ in range(4):
            await self.worker.tick()
        with self.store.connect() as db:
            result = db.execute('SELECT * FROM assets').fetchone()
            states = [row[0] for row in db.execute('SELECT state FROM deliveries')]
            count = db.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0]
        self.assertEqual(result['state'], 'preview_ready')
        self.assertEqual(states, ['shadow'] * 3)
        self.assertIn('source: @fixture_source', result['caption'])
        self.assertEqual(self.provider.created, [])
        self.assertEqual(count, 9)

    async def test_pause_command_and_apply_ack(self):
        asset(self.store)
        self.store.command('pause_processing', {}, 'pause-fixture')
        await self.worker.tick()
        self.assertEqual(self.store.get_meta('applied_version'), 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT stage FROM assets').fetchone()[0], 'queued')
        self.store.command('resume_processing', {}, 'resume-fixture')
        await self.worker.tick()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT stage FROM assets').fetchone()[0], 'inspect')

    async def test_job_keeps_old_bank_configuration(self):
        asset(self.store)
        old_bank = self.store.config_at(1)['storage']['bank_directory']
        config = self.store.config_at(1)
        config['storage']['bank_directory'] = str(self.store.data_dir / 'new-bank')
        self.store.save_configuration(config, 1)
        for _ in range(4):
            await self.worker.tick()
        with self.store.connect() as db:
            bank = db.execute("SELECT path FROM artifacts WHERE kind='bank'").fetchone()[0]
        self.assertEqual(Path(bank).parent, Path(old_bank))
        self.assertEqual(self.store.get_meta('applied_version'), 2)

    async def live(self):
        config = self.store.config_at(1)
        config['application'].update(mode='live', publish_enabled=True)
        config['ownership'] = {'acknowledged': True, 'account_ids': ['account-' + p for p in ('tiktok', 'facebook', 'youtube')], 'excluded_account_ids': []}
        config['drive']['folder_url'] = 'https://drive.google.com/drive/folders/folderfixture12345'
        config['credentials'].update(repliz=1, drive=1)
        version = self.store.save_configuration(config, 1)
        self.store.set_meta('applied_version', version)
        self.worker.injected.update(repliz=self.provider, drive=self.drive)
        await self.worker.sync_accounts(config)
        return config, version

    async def ready(self, version):
        asset(self.store, version=version, state='ready', stage='delivery')
        file = Path(self.temp.name) / 'bank.mp4'
        file.write_bytes(b'fixture')
        self.drive.verify.return_value['sha256'] = file_hashes(file)['sha256']
        self.worker.artifact('fixture', 'bank', file, drive_id='drivefixture12345', drive_url='https://drive.google.com/uc?id=drivefixture12345', verified_at=STAMP)
        with self.store.connect() as db:
            db.execute("UPDATE assets SET caption='Keterangan fixture',source_username='fixture_source',source_verified=1")

    async def test_partial_account_snapshot_never_clears_pool(self):
        config, _ = await self.live()
        self.provider.partial = True
        with self.assertRaises(Held):
            await self.worker.sync_accounts(config)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM accounts WHERE enabled=1').fetchone()[0], 3)

    async def test_shadow_asset_never_promoted_by_live_config(self):
        asset(self.store, state='ready', stage='delivery')
        config, _ = await self.live()
        await self.worker.deliver(config)
        self.assertEqual(self.provider.created, [])

    async def test_ambiguous_send_keeps_intent_and_never_retries(self):
        config, version = await self.live()
        await self.ready(version)
        self.provider.should_timeout = True
        await self.worker.deliver(config)
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM deliveries WHERE state='unknown'").fetchone()
            self.assertIsNotNone(row)
            attempt = db.execute('SELECT * FROM attempts').fetchone()
            self.assertEqual(attempt['state'], 'unknown')
        self.assertEqual(len(self.provider.created), 1)
        with self.assertRaises(Held):
            self.worker.intent(row['id'], 'schedule', 'schedule:' + row['id'], {})
        with self.assertRaises(Held):
            await self.worker.command('retry_asset', {'asset_id': 'fixture'})
        self.worker.recover()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM deliveries WHERE id=?', (row['id'],)).fetchone()[0], 'unknown')

    async def test_accepted_schedule_is_not_published_until_evidence(self):
        config, version = await self.live()
        await self.ready(version)
        await self.worker.deliver(config)
        with self.store.connect() as db:
            row = dict(db.execute("SELECT * FROM deliveries WHERE state='scheduled'").fetchone())
        self.assertIsNone(row['published_at'])
        self.assertIn('source: @fixture_source', self.provider.created[0]['description'])
        self.provider.remote[0]['status'] = 'success'
        with self.assertRaises(Held):
            await self.worker.reconcile(row['id'], config)
        self.provider.remote[0]['url'] = 'https://www.tiktok.com/@fixture/video/123'
        await self.worker.reconcile(row['id'], config)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM deliveries WHERE id=?', (row['id'],)).fetchone()[0], 'published')

    async def test_reconcile_pins_original_credentials_after_rotation_and_recovery(self):
        config, version = await self.live()
        await self.ready(version)
        await self.worker.deliver(config)
        self.assertNotIn('_arker_config_version', self.provider.created[0])
        with self.store.connect() as db:
            attempt = dict(db.execute('SELECT * FROM attempts').fetchone())
        self.assertEqual(json.loads(attempt['payload'])['_arker_config_version'], version)
        journal = json.loads((self.store.data_dir / 'journals' / (attempt['id'] + '-intent.json')).read_text())
        self.assertEqual(journal['payload']['_arker_config_version'], version)
        rotated = self.store.config_at(version)
        rotated['credentials']['repliz'] = 2
        current_version = self.store.save_configuration(rotated, version)
        self.store.set_meta('applied_version', current_version)
        wrong_workspace = AsyncMock()
        def select_provider(name, settings):
            return self.provider if settings['credentials']['repliz'] == 1 else wrong_workspace
        with patch.object(self.worker, 'adapter', side_effect=select_provider) as select:
            await self.worker.reconcile(attempt['delivery_id'], rotated)
            select.assert_called_once_with('repliz', config)
        with self.store.connect() as db:
            db.execute('DELETE FROM attempts WHERE id=?', (attempt['id'],))
            db.execute("UPDATE deliveries SET state='unknown',remote_id=NULL WHERE id=?", (attempt['delivery_id'],))
        self.worker.recover()
        with self.store.connect() as db:
            recovered = json.loads(db.execute('SELECT payload FROM attempts').fetchone()[0])
            self.assertEqual(recovered['_arker_config_version'], version)
            db.execute('UPDATE attempts SET remote_id=NULL WHERE id=?', (attempt['id'],))
            db.execute("UPDATE deliveries SET state='unknown',remote_id=NULL WHERE id=?", (attempt['delivery_id'],))
        with patch.object(self.worker, 'adapter', side_effect=select_provider):
            await self.worker.reconcile(attempt['delivery_id'], rotated)
            self.worker.injected['repliz'] = None
            self.worker.clock = lambda: STAMP + 31
            rotated['credentials']['repliz'] = 0
            await self.worker.monitor(rotated)
        wrong_workspace.schedule.assert_not_awaited()
        wrong_workspace.schedules.assert_not_awaited()

    async def test_reconcile_without_pinned_version_holds_before_provider_access(self):
        config, version = await self.live()
        await self.ready(version)
        await self.worker.deliver(config)
        with self.store.connect() as db:
            attempt = dict(db.execute('SELECT * FROM attempts').fetchone())
            payload = json.loads(attempt['payload'])
            del payload['_arker_config_version']
            db.execute('UPDATE attempts SET payload=? WHERE id=?', (json.dumps(payload), attempt['id']))
        with patch.object(self.worker, 'adapter') as adapter:
            with self.assertRaisesRegex(Held, 'Versi konfigurasi intent'):
                await self.worker.reconcile(attempt['delivery_id'], config)
            adapter.assert_not_called()

    async def test_quota20_reservations_accounted_without_provider_call(self):
        config, version = await self.live()
        day = self.store.get_meta('accounts_snapshot_day')
        for index in range(21):
            name = 'quota' + str(index)
            asset(self.store, name=name, version=version)
            delivery = {'id': name + '-tiktok', 'platform': 'tiktok'}
            if index < 20:
                self.worker.reserve(delivery, day, config)
            else:
                with self.assertRaises(Held):
                    self.worker.reserve(delivery, day, config)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM reservations').fetchone()[0], 20)
        self.assertFalse(self.provider.created)

    async def test_quota_counts_observed_schedule_once_and_keeps_unsent_reservation(self):
        config, version = await self.live()
        await self.ready(version)
        await self.worker.deliver(config)
        for index in range(18):
            self.provider.remote.append({'id': f'existing-{index}', 'accountId': 'account-tiktok', 'status': 'pending'})
        await self.worker.sync_accounts(config)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM reservations').fetchone()[0], 'observed')
            self.assertEqual(db.execute("SELECT quota_used FROM accounts WHERE id='account-tiktok'").fetchone()[0], 19)
        day = self.store.get_meta('accounts_snapshot_day')
        asset(self.store, name='lastslot', version=version)
        self.worker.reserve({'id': 'lastslot-tiktok', 'platform': 'tiktok'}, day, config)
        await self.worker.sync_accounts(config)
        asset(self.store, name='overflow', version=version)
        with self.assertRaises(Held):
            self.worker.reserve({'id': 'overflow-tiktok', 'platform': 'tiktok'}, day, config)
        self.assertEqual(len(self.provider.created), 1)

    async def test_stop_command_halts_tick_before_pipeline(self):
        asset(self.store)
        self.store.command('stop_worker', {}, 'stop-fixture')
        await self.worker.tick()
        self.assertTrue(self.worker.stopping)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM assets').fetchone()[0], 'queued')

    def test_source_credit_replaces_unverified_ai_credit(self):
        self.assertEqual(Worker.attribution('Kalimat\nsource: @guessed\nBaris', 'verified_source'), 'Kalimat\nBaris\n\nsource: @verified_source')
        with self.assertRaises(Held):
            Worker.attribution('caption', 'Display Name')

    async def test_failed_credential_test_preserves_active_version(self):
        from unittest.mock import patch
        await self.worker.tick()
        config = self.store.config_at(1)
        version = self.worker.secret_store.set('repliz', {'access_key': 'fixture-A', 'secret_key': 'fixture-B'})
        config['credentials']['repliz'] = version
        desired = self.store.save_configuration(config, 1)
        with patch('arker.adapters.test_connection', new=AsyncMock(side_effect=Held('credentials_rejected', 'Kredensial fixture ditolak.'))):
            await self.worker.commands()
        self.assertEqual(self.store.get_meta('applied_version'), 1)
        self.assertEqual(self.store.get_meta('desired_version'), desired)

    async def test_journal_only_intent_recovers_unknown_not_resend(self):
        config, version = await self.live()
        await self.ready(version)
        row = {'id': 'fixture-tiktok', 'platform': 'tiktok'}
        self.worker.reserve(row, self.store.get_meta('accounts_snapshot_day'), config)
        self.worker.journal({'id': 'orphan-fixture', 'delivery_id': row['id'], 'operation': 'schedule', 'request_key': 'schedule:' + row['id'], 'state': 'sending', 'payload': {'accountId': 'account-tiktok'}, 'created_at': STAMP}, 'intent')
        self.worker.recover()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM attempts').fetchone()[0], 'unknown')
            self.assertEqual(db.execute('SELECT state FROM deliveries WHERE id=?', (row['id'],)).fetchone()[0], 'unknown')
        with self.assertRaises(Held):
            self.worker.intent(row['id'], 'schedule', 'schedule:' + row['id'], {})

    async def test_result_journal_recovers_remote_identity_after_crash(self):
        config, version = await self.live()
        await self.ready(version)
        row = {'id': 'fixture-tiktok', 'platform': 'tiktok'}
        self.worker.reserve(row, self.store.get_meta('accounts_snapshot_day'), config)
        attempt = self.worker.intent(row['id'], 'schedule', 'schedule:' + row['id'], {'accountId': 'account-tiktok'})
        self.worker.journal({'id': attempt, 'state': 'accepted', 'remote_id': 'remote-fixture', 'at': STAMP}, 'fixture-result')
        self.worker.recover()
        with self.store.connect() as db:
            result = db.execute('SELECT * FROM deliveries WHERE id=?', (row['id'],)).fetchone()
            self.assertEqual(result['state'], 'scheduled')
            self.assertEqual(result['remote_id'], 'remote-fixture')

    async def test_drive_file_swap_blocks_before_intent(self):
        config, version = await self.live()
        await self.ready(version)
        self.drive.verify.return_value['id'] = 'another-drive-file'
        await self.worker.deliver(config)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 0)
        self.assertFalse(self.provider.created)

    async def test_persona_binding_remains_immutable_for_delivery(self):
        config, version = await self.live()
        with self.store.connect() as db:
            db.execute('INSERT INTO personas VALUES (?,?,?,?,?)', ('tone', 1, 'Fixture', 'Gaya pertama', STAMP))
            db.execute('INSERT INTO personas VALUES (?,?,?,?,?)', ('tone', 2, 'Fixture', 'Gaya baru', STAMP))
            db.execute('INSERT INTO account_personas VALUES (?,?,?)', ('account-tiktok', 'tone', 1))
        self.assertEqual(self.worker.persona('account-tiktok')['style'], 'Gaya pertama')

    async def test_reports_missing_data_does_not_become_zero(self):
        config, _ = await self.live()
        self.provider.statistic = AsyncMock(side_effect=[{'followersCount': 42, 'likes': float('inf')}, {'views': float('nan'), 'comments': True}, {'views': None, 'shares': float('-inf')}])
        await self.worker.report_cycle(config)
        with self.store.connect() as db:
            values = [dict(row) for row in db.execute('SELECT * FROM metrics')]
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]['value'], 42)

    async def test_telegram_private_intake_dedup_and_group_privacy(self):
        config = self.store.config_at(1)
        config['telegram'].update(enabled=True, admin_id='123')
        self.store.set_meta('applied_version', 1)
        telegram = AsyncMock()
        telegram.updates.return_value = [
            {'update_id': 1, 'message': {'from': {'id': 456}, 'chat': {'type': 'group', 'id': -100}, 'text': 'https://instagram.com/reel/GroupFixture/'}},
            {'update_id': 2, 'message': {'from': {'id': 456}, 'chat': {'type': 'private', 'id': 456}, 'text': 'https://instagram.com/reel/PrivateFixture/'}},
        ]
        telegram.send.return_value = 'message-fixture'
        self.worker.injected['telegram'] = telegram
        await self.worker.telegram_cycle(config)
        with self.store.connect() as db:
            rows = db.execute('SELECT * FROM assets').fetchall()
            destinations = db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0]
        self.assertEqual(len(rows), 1)
        self.assertEqual(destinations, 3)
        telegram.send.assert_awaited_once()
        self.assertEqual(telegram.send.call_args.args[0], 456)
        self.assertEqual(self.store.get_meta('telegram_offset'), 3)

    async def test_reply_unknown_is_deduplicated_with_separate_quota(self):
        config, version = await self.live()
        config['reply']['enabled'] = True
        with self.store.connect() as db:
            db.execute('UPDATE configurations SET config=? WHERE version=?', (json.dumps(config), version))
        await self.ready(version)
        with self.store.connect() as db:
            db.execute("UPDATE deliveries SET state='published',account_id='account-tiktok',post_url='https://www.tiktok.com/@fixture/video/123' WHERE platform='tiktok'")
        self.provider.comments = AsyncMock(return_value=[{'id': 'comment-fixture', 'accountId': 'account-tiktok', 'comment': {'text': 'Gerakan apa ini?', 'owner': {'name': 'Fixture viewer'}}, 'content': {'id': 'post-fixture', 'url': 'https://www.tiktok.com/@fixture/video/123', 'hasAutomation': False}}])
        self.provider.reply = AsyncMock(side_effect=AdapterError('fixture_timeout', 'Fixture timeout', ambiguous=True))
        ai = AsyncMock()
        ai.reply.return_value = 'Terlihat gerakan di bagian akhir video.'
        self.worker.injected['ai'] = ai
        await self.worker.reply_cycle(config)
        self.assertEqual(self.provider.reply.await_count, 1)
        self.worker.store.set_meta('reply_poll_at', 0)
        await self.worker.reply_cycle(config)
        self.assertEqual(self.provider.reply.await_count, 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM comments').fetchone()[0], 'unknown')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 0)
            self.assertEqual(json.loads(db.execute("SELECT payload FROM attempts WHERE operation='reply'").fetchone()[0])['_arker_config_version'], version)

    async def test_restore_requires_reconciliation_blocks_saved_live_config(self):
        config, version = await self.live()
        await self.ready(version)
        self.store.set_meta('restore_requires_reconciliation', True)
        self.assertFalse(self.worker.live_allowed(config))
        await self.worker.deliver(config)
        self.assertEqual(self.provider.created, [])

    async def test_reply_pause_is_independent_from_processing_pause(self):
        config, version = await self.live()
        config['reply']['enabled'] = True
        with self.store.connect() as db:
            db.execute('UPDATE configurations SET config=? WHERE version=?', (json.dumps(config), version))
        self.store.set_meta('processing_paused', True)
        self.assertFalse(self.worker.live_allowed(config))
        self.assertTrue(self.worker.live_allowed(config, module='reply'))
        self.store.set_meta('reply_paused', True)
        self.assertFalse(self.worker.live_allowed(config, module='reply'))
