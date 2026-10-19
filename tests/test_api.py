import asyncio
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from arker.api import create_app
from arker.auth import bootstrap_admin
from arker.db import now, uid


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.app = create_app(self.root)
        self.store = self.app.state.store
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        bootstrap_admin(self.store, 'admin@example.test', 'test fixture passphrase only')
        self.client.headers['Origin'] = 'http://testserver'
        response = self.client.post('/api/auth/login', json={'email': 'admin@example.test', 'password': 'test fixture passphrase only'})
        self.assertEqual(response.status_code, 200)
        self.client.headers['X-CSRF-Token'] = response.json()['csrf_token']

    def test_auth_required_on_data_and_media(self):
        unauthenticated = TestClient(self.app)
        self.addCleanup(unauthenticated.close)
        for route in ('/api/overview','/api/assets','/api/configuration','/api/media/a/b'):
            self.assertEqual(unauthenticated.get(route).status_code, 401)
        self.assertFalse(unauthenticated.get('/api/auth/session').json()['authenticated'])

    def test_service_actions_require_auth_csrf_and_fixed_action(self):
        with patch('arker.lifecycle.worker_action', return_value={'accepted':True,'action':'start'}) as action:
            self.assertEqual(self.client.post('/api/service/start', json={}, headers={'X-CSRF-Token':'wrong'}).status_code, 403)
            action.assert_not_called()
            self.assertEqual(self.client.post('/api/service/install', json={}).status_code, 422)
            action.assert_not_called()
            self.assertEqual(self.client.post('/api/service/start', json={}).json()['accepted'], True)
            action.assert_called_once_with(self.store.data_dir, 'start')
        self.assertIn('running', self.client.get('/api/service').json())
        with patch('arker.lifecycle.worker_action', side_effect=RuntimeError('private internal error')):
            result = self.client.post('/api/service/stop', json={})
            self.assertEqual(result.status_code, 409)
            self.assertNotIn('private internal error', result.text)

    def test_csrf_origin_and_content_type_guards(self):
        payload = {'urls':['https://instagram.com/reel/Guard123/']}
        self.assertEqual(self.client.post('/api/intake', json=payload, headers={'X-CSRF-Token': 'wrong'}).status_code, 403)
        self.assertEqual(self.client.post('/api/intake', json=payload, headers={'Origin': 'https://evil.example'}).status_code, 403)
        self.assertEqual(self.client.post('/api/intake', content=json.dumps(payload), headers={'Content-Type':'text/plain'}).status_code, 415)
        self.assertEqual(self.client.post('/api/intake', json=payload).status_code, 200)

    def test_session_logout_expires_and_cookie_flags(self):
        response = self.client.post('/api/auth/login', json={'email':'admin@example.test','password':'test fixture passphrase only'})
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=strict', response.headers['set-cookie'])
        self.client.headers['X-CSRF-Token'] = response.json()['csrf_token']
        self.assertEqual(self.client.post('/api/auth/logout', json={}).status_code, 200)
        self.assertEqual(self.client.get('/api/overview').status_code, 401)

    def test_chunked_body_is_rejected_before_remaining_chunks_are_read(self):
        incoming = [{'type':'http.request','body':b'x'*200000,'more_body':True}, {'type':'http.request','body':b'x'*100000,'more_body':True}, {'type':'http.request','body':b'ignored','more_body':False}]
        consumed, sent = [], []
        async def receive():
            consumed.append(True)
            return incoming.pop(0) if incoming else {'type':'http.disconnect'}
        async def send(message):
            sent.append(message)
        scope = {'type':'http','asgi':{'version':'3.0','spec_version':'2.3'},'http_version':'1.1','method':'POST','scheme':'http','path':'/api/auth/login','raw_path':b'/api/auth/login','root_path':'','query_string':b'','headers':[(b'host',b'testserver'),(b'origin',b'http://testserver'),(b'content-type',b'application/json')],'client':('testclient',1),'server':('testserver',80)}
        asyncio.run(self.app(scope,receive,send))
        self.assertEqual(next(message['status'] for message in sent if message['type']=='http.response.start'), 413)
        self.assertEqual(len(consumed), 2)

    def test_session_expiry_and_oversized_request(self):
        oversized = {'urls':['x' * 270000]}
        self.assertEqual(self.client.post('/api/intake', json=oversized).status_code, 413)
        with self.store.connect() as db:
            db.execute('UPDATE sessions SET expires_at=?', (time.time()-1,))
        self.assertEqual(self.client.get('/api/overview').status_code, 401)

    def test_rate_limit_login_and_generic_response(self):
        for _ in range(10):
            response = self.client.post('/api/auth/login', json={'email':'nobody@example.test','password':'incorrect fixture'})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()['detail'], 'Email atau password tidak sesuai.')
        self.assertEqual(self.client.post('/api/auth/login', json={'email':'admin@example.test','password':'test fixture passphrase only'}).status_code, 429)

    def test_configuration_save_conflict_and_invalid_limits(self):
        config = self.client.get('/api/configuration').json()
        config['config']['workflow']['daily_video_limit'] = 16
        response = self.client.put('/api/configuration', json={'config': config['config'], 'base_version': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'pending')
        self.assertEqual(self.client.put('/api/configuration', json={'config': config['config'], 'base_version': 1}).status_code, 409)
        config['config']['workflow']['daily_video_limit'] = 99
        self.assertEqual(self.client.put('/api/configuration', json={'config': config['config'], 'base_version': 2}).status_code, 422)
        saved = self.client.get('/api/configuration').json()
        self.assertEqual(saved['desired_version'], 2)
        self.assertEqual(saved['applied_version'], 0)

    def test_configuration_cannot_reference_missing_credential_version(self):
        config = self.client.get('/api/configuration').json()['config']
        config['credentials']['repliz'] = 99
        response = self.client.put('/api/configuration', json={'config':config,'base_version':1})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.store.configuration()['desired_version'], 1)

    def test_credentials_no_leaks_and_versioned_application(self):
        fixture = {'access_key':'fixture access value','secret_key':'fixture secret value'}
        response = self.client.post('/api/credentials/repliz', json=fixture)
        self.assertEqual(response.status_code, 200)
        config = self.client.get('/api/configuration').json()
        self.assertEqual(config['config']['credentials']['repliz'], 1)
        self.assertEqual(config['desired_version'], 2)
        for route in ('/api/configuration','/api/events','/api/overview'):
            text = self.client.get(route).text
            for value in fixture.values():
                self.assertNotIn(value, text)
        response = self.client.post('/api/auth/login', json={'email':'admin@example.test','password':fixture,'secret':'hidden fixture'})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('hidden fixture', response.text)
        self.assertNotIn('fixture secret value', response.text)

    def test_command_idempotency_and_unknown_retry_rejected(self):
        command = {'kind':'pause_processing','payload':{},'idempotency_key':'command-fixture-123'}
        first = self.client.post('/api/commands', json=command)
        second = self.client.post('/api/commands', json=command)
        self.assertEqual(first.json()['command']['id'], second.json()['command']['id'])
        command['kind'] = 'resume_processing'
        self.assertEqual(self.client.post('/api/commands', json=command).status_code, 409)
        asset = self.client.post('/api/intake', json={'urls':['https://instagram.com/reel/Unknown123/']}).json()['accepted'][0]['id']
        with self.store.connect() as db:
            db.execute("UPDATE assets SET state='failed' WHERE id=?", (asset,))
            db.execute("UPDATE deliveries SET state='unknown' WHERE asset_id=?", (asset,))
        retry = {'kind':'retry_asset','payload':{'asset_id':asset},'idempotency_key':'retry-fixture-123'}
        self.assertEqual(self.client.post('/api/commands', json=retry).status_code, 409)
        self.assertEqual(self.client.get(f'/api/assets/{asset}').json()['asset']['available_actions'], [])
        retry['payload']['asset_id'] = []
        self.assertEqual(self.client.post('/api/commands', json=retry).status_code, 422)

    def test_unknown_delivery_without_remote_id_can_reconcile_by_intent(self):
        asset = self.client.post('/api/intake', json={'urls':['https://instagram.com/reel/ReconcileFixture123/']}).json()['accepted'][0]['id']
        with self.store.connect() as db:
            delivery = db.execute('SELECT id FROM deliveries WHERE asset_id=? LIMIT 1', (asset,)).fetchone()[0]
            db.execute("UPDATE deliveries SET state='unknown' WHERE id=?", (delivery,))
            db.execute('INSERT INTO attempts(id,delivery_id,operation,request_key,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?)', (uid(),delivery,'schedule','intent-fixture','unknown',now(),now()))
        detail = self.client.get(f'/api/assets/{asset}').json()
        action = next(d for d in detail['deliveries'] if d['id'] == delivery)['available_actions'][0]
        self.assertEqual(action['kind'], 'reconcile_delivery')
        response = self.client.post('/api/commands', json={'kind':action['kind'],'payload':action['payload'],'idempotency_key':'reconcile-fixture'})
        self.assertEqual(response.status_code, 200)

    def test_retry_command_idempotency_survives_entity_state_change(self):
        asset = self.client.post('/api/intake', json={'urls':['https://instagram.com/reel/RetryFixture123/']}).json()['accepted'][0]['id']
        with self.store.connect() as db:
            db.execute("UPDATE assets SET state='failed' WHERE id=?", (asset,))
        command = {'kind':'retry_asset','payload':{'asset_id':asset},'idempotency_key':'same-retry-fixture'}
        first = self.client.post('/api/commands', json=command)
        self.assertEqual(first.status_code, 200)
        with self.store.connect() as db:
            db.execute("UPDATE assets SET state='processing' WHERE id=?", (asset,))
            db.execute("UPDATE commands SET status='succeeded' WHERE id=?", (first.json()['command']['id'],))
        second = self.client.post('/api/commands', json=command)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['command']['id'], second.json()['command']['id'])
        self.assertEqual(second.json()['command']['status'], 'succeeded')

    def test_restore_guard_prevents_module_activation(self):
        self.store.set_meta('restore_requires_reconciliation', True)
        config = self.store.configuration()['config']
        config['telegram']['enabled'] = True
        self.assertFalse(self.client.post('/api/configuration/validate', json={'config':config}).json()['valid'])
        self.assertEqual(self.client.put('/api/configuration', json={'config':config,'base_version':1}).status_code, 422)
        self.assertEqual(self.client.post('/api/commands', json={'kind':'resume_processing','payload':{},'idempotency_key':'restore-resume-fixture'}).status_code, 409)
        self.assertTrue(self.client.get('/api/health').json()['restore_requires_reconciliation'])

    def test_published_asset_is_terminal_and_not_an_active_queue(self):
        self.client.post('/api/intake', json={'urls':['https://instagram.com/reel/TerminalFixture123/']})
        with self.store.connect() as db:
            db.execute("UPDATE assets SET state='published',stage='complete'")
        overview = self.client.get('/api/overview').json()
        self.assertEqual(overview['summary']['assets_active'], 0)
        self.assertEqual(overview['summary']['assets_completed'], 1)
        self.assertEqual(overview['charts']['stages'], [])
        self.assertEqual(overview['active_assets'], [])
        self.assertEqual(self.client.get('/api/assets?scope=active').json()['total'], 0)
        self.assertEqual(self.client.get('/api/batches').json()['items'][0]['completed'], 1)

    def test_overview_units_and_stale_worker(self):
        self.client.post('/api/intake', json={'urls':['https://instagram.com/reel/ChartFixture123/']})
        with self.store.connect() as db:
            db.execute("UPDATE deliveries SET state='scheduled' WHERE platform='tiktok'")
            db.execute("UPDATE deliveries SET state='published',published_at=? WHERE platform='youtube'", (now(),))
        self.store.set_meta('worker_heartbeat', now()-120)
        overview = self.client.get('/api/overview').json()
        self.assertEqual(overview['summary']['assets_total'], 1)
        self.assertEqual(overview['summary']['deliveries_published'], 1)
        self.assertEqual(overview['summary']['deliveries_scheduled'], 1)
        self.assertEqual(sum(item['assets'] for item in overview['charts']['throughput']), 1)
        self.assertEqual(sum(item['deliveries'] for item in overview['charts']['throughput']), 1)
        self.assertFalse(overview['health']['connected'])
        self.assertEqual(overview['health']['state'], 'offline')
        self.assertEqual(overview['charts']['durations'], [])
        self.store.event('asset.stage', payload={'stage':'queued','duration_seconds':2.5})
        self.store.event('asset.stage', payload={'stage':'download','duration_seconds':3.5})
        self.assertEqual(self.client.get('/api/overview').json()['charts']['durations'], [{'stage':'download','seconds':3.0,'samples':2}])

    def test_stage_and_date_filters_match_chart_drilldown(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        asset = self.client.post('/api/intake', json={'urls':['https://instagram.com/reel/FilterFixture123/']}).json()['accepted'][0]['id']
        today = str(datetime.now(ZoneInfo('Asia/Jakarta')).date())
        self.assertEqual(self.client.get('/api/assets', params={'stage':'queued','date':today}).json()['total'], 1)
        self.assertEqual(self.client.get('/api/assets', params={'stage':'render','date':today}).json()['total'], 0)
        self.assertEqual(self.client.get('/api/assets', params={'date':'wrong'}).status_code, 422)

    def test_media_path_boundary_prevents_secret_file_read(self):
        asset = self.client.post('/api/intake', json={'urls':['https://instagram.com/reel/MediaFixture123/']}).json()['accepted'][0]['id']
        secret = self.root / 'Credential' / 'private.png'
        secret.write_bytes(b'not a public image')
        with self.store.connect() as db:
            db.execute('INSERT INTO artifacts(id,asset_id,kind,path,created_at) VALUES (?,?,?,?,?)', (uid(),asset,'frame',str(secret),now()))
        self.assertEqual(self.client.get(f'/api/media/{asset}/frame').status_code, 403)
        bank = self.root / 'bank'
        bank.mkdir()
        image = bank / 'fixture.png'
        image.write_bytes(b'fixture content')
        with self.store.connect() as db:
            db.execute('UPDATE artifacts SET path=? WHERE asset_id=?', (str(image),asset))
        self.assertEqual(self.client.get(f'/api/media/{asset}/frame').content, b'fixture content')

    def test_comment_search_and_pagination_cover_history(self):
        with self.store.connect() as db:
            for index in range(3):
                db.execute('INSERT INTO comments(id,text,author,created_at,updated_at) VALUES (?,?,?,?,?)', (f'comment-{index}','Topic fixture' if index < 2 else 'Another',f'Author {index}',now(),now()+index))
        first = self.client.get('/api/comments', params={'q':'Topic','limit':1}).json()
        second = self.client.get('/api/comments', params={'q':'Topic','limit':1,'page':2}).json()
        self.assertEqual(first['total'], 2)
        self.assertEqual(second['total'], 2)
        self.assertNotEqual(first['items'][0]['id'], second['items'][0]['id'])
        self.assertEqual(self.client.get('/api/comments?page=0').status_code, 422)

    def test_persona_binding_records_immutable_version(self):
        with self.store.connect() as db:
            db.execute('INSERT INTO accounts(id,platform) VALUES (?,?)', ('account-fixture','youtube'))
        payload = {'name':'Fixture','style':'Ramah dan faktual.','account_id':'account-fixture'}
        self.assertEqual(self.client.put('/api/personas/bound-fixture', json=payload).status_code, 200)
        payload.pop('account_id')
        payload['style'] = 'Versi baru untuk pilihan berikutnya.'
        self.client.put('/api/personas/bound-fixture', json=payload)
        item = self.client.get('/api/personas').json()['items'][0]
        self.assertEqual(item['version'], 2)
        self.assertEqual(item['bindings'][0]['persona_version'], 1)
        payload['account_id'] = 'missing-account'
        self.assertEqual(self.client.put('/api/personas/bound-fixture', json=payload).status_code, 422)
        self.assertEqual(self.client.get('/api/personas').json()['items'][0]['version'], 2)

    def test_storage_invalid_url_and_configured_but_untested_connection(self):
        result = self.client.post('/api/storage/check', json={'bank_directory':str(self.root / 'bank'),'folder_url':'https://localhost/private'}).json()
        self.assertFalse(result['valid'])
        response = self.client.post('/api/connections/repliz/test', json={}).json()
        self.assertFalse(response['valid'])
        self.assertEqual(response['status'], 'not_configured')

    def test_personas_immutable_and_events_cursor(self):
        for style in ('Singkat dan ramah.', 'Tenang dan faktual.'):
            response = self.client.put('/api/personas/account-one', json={'name':'Akun satu','style':style})
            self.assertEqual(response.status_code, 200)
        result = self.client.get('/api/personas').json()['items']
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['version'], 2)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM personas').fetchone()[0], 2)
        events = self.client.get('/api/events?limit=2').json()
        next_events = self.client.get('/api/events', params={'after':events['cursor']}).json()
        self.assertTrue(all(e['id'] > events['cursor'] for e in next_events['items']))


if __name__ == '__main__':
    unittest.main()
