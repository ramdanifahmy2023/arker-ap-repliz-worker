import concurrent.futures
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arker.auth import bootstrap_admin, password_hash, verify_password
from arker.config import bank_path, default_config, drive_folder_id, validate_config
from arker.db import Store
from arker.ingest import canonical_url, intake
from arker.secrets import SecretStore


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.store = Store(self.root)

    def test_default_config_valid_and_not_publishing(self):
        config = default_config(self.root)
        self.assertTrue(validate_config(config, self.root)['valid'])
        self.assertEqual(config['application']['mode'], 'shadow')
        self.assertFalse(config['application']['publish_enabled'])
        self.assertEqual(self.store.configuration()['applied_version'], 0)

    def test_invalid_config_rejects_unsafe_limits_and_types(self):
        for section, key, value in [('workflow','daily_video_limit',21), ('workflow','daily_video_limit',True), ('cleanup','retention_hours',23), ('video','mirror',True), ('drive','require_full_checksum',False), ('ai','enabled','yes'), ('video','ffmpeg','cmd.exe'), ('video','ffprobe','ffprobe.cmd'), ('video','ffmpeg','//host/share/ffmpeg.exe'), ('ai','whisper_executable','run.sh'), ('ai','base_url','https://['), ('ai','base_url','https://api.openai.com:9000/v1')]:
            with self.subTest(field=f'{section}.{key}'):
                config = default_config(self.root)
                config[section][key] = value
                self.assertFalse(validate_config(config, self.root)['valid'])

    def test_live_requires_explicit_scope_credentials_and_drive(self):
        config = default_config(self.root)
        config['application'].update(mode='live', publish_enabled=True)
        self.assertFalse(validate_config(config, self.root)['valid'])

    def test_config_version_conflict_and_durable_apply(self):
        config = default_config(self.root)
        config['workflow']['daily_video_limit'] = 12
        version = self.store.save_configuration(config, 1)
        self.assertEqual(version, 2)
        with self.assertRaisesRegex(ValueError, 'conflict'):
            self.store.save_configuration(config, 1)
        self.assertEqual(self.store.configuration()['applied_version'], 0)
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM commands').fetchone()
            self.assertEqual(row['kind'], 'apply_configuration')
            self.assertEqual(json.loads(row['payload']), {'version': 2})

    def test_idempotency_retains_one_command_and_rejects_collision(self):
        a = self.store.command('pause_processing', {}, 'request-123')
        b = self.store.command('pause_processing', {}, 'request-123')
        self.assertEqual(a['id'], b['id'])
        with self.assertRaisesRegex(ValueError, 'idempotency_conflict'):
            self.store.command('resume_processing', {}, 'request-123')

    def test_intake_deduplicates_and_creates_three_deliveries(self):
        result = intake(self.store, ['https://instagram.com/reels/AbCdEf123/?tracking=1', 'https://www.instagram.com/reel/AbCdEf123/', 'https://evil.example/reel/AbCdEf123/'])
        self.assertEqual([len(result[k]) for k in ('accepted', 'duplicates', 'rejected')], [1,1,1])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assets').fetchone()[0], 1)
            self.assertEqual({r[0] for r in db.execute('SELECT platform FROM deliveries')}, {'tiktok','facebook','youtube'})

    def test_concurrent_intake_is_atomic(self):
        def submit(_):
            return intake(self.store, ['https://www.instagram.com/reel/Concurrent123/'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(submit, range(4)))
        self.assertEqual(sum(len(r['accepted']) for r in results), 1)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0], 3)

    def test_new_intake_uses_applied_configuration(self):
        self.store.set_meta('applied_version', 1)
        updated = default_config(self.root)
        updated['workflow']['daily_video_limit'] = 8
        self.store.save_configuration(updated, 1)
        intake(self.store, ['https://www.instagram.com/reel/Snapshot123/'])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT config_version FROM assets').fetchone()[0], 1)

    def test_secret_concurrent_rotation_keeps_all_versions(self):
        secret_store = SecretStore(self.root)
        secret_store.set('repliz', {'access_key':'fixture access value','secret_key':'fixture initial value'})
        def rotate(index):
            return SecretStore(self.root).set('repliz', {'secret_key': f'fixture revision {index}'})
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            versions = list(pool.map(rotate, range(4)))
        self.assertEqual(set(versions), {2, 3, 4, 5})
        for version in versions:
            self.assertEqual(secret_store.get('repliz', version)['access_key'], 'fixture access value')

    def test_url_and_storage_validation(self):
        for url in ('http://instagram.com/reel/Test123/', 'https://instagram.com.evil.example/reel/Test123/', 'https://user@instagram.com/reel/Test123/', 'https://instagram.com:8443/reel/Test123/'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_url(url)
        self.assertEqual(drive_folder_id('https://drive.google.com/drive/folders/FolderFixture123'), 'FolderFixture123')
        for url in ('http://drive.google.com/drive/folders/FolderFixture123', 'https://127.0.0.1/drive/folders/FolderFixture123', 'https://drive.google.com.evil.example/drive/folders/FolderFixture123'):
            with self.assertRaises(ValueError):
                drive_folder_id(url)
        for path in (str(self.root), '../escape', str(self.root / 'Credential' / 'nested')):
            with self.assertRaises(ValueError):
                bank_path(path, self.root)

    def test_password_hash_unique_salts_and_validation(self):
        value = 'test fixture passphrase only'
        first, second = password_hash(value), password_hash(value)
        self.assertNotEqual(first, second)
        self.assertNotIn(value, first)
        self.assertTrue(verify_password(value, first))
        self.assertFalse(verify_password('wrong', first))
        bootstrap_admin(self.store, 'admin@example.test', value)
        with self.assertRaises(ValueError):
            bootstrap_admin(self.store, 'other@example.test', value)

    def test_credential_directory_redirect_is_rejected(self):
        secret_store = SecretStore(self.root)
        directory = self.root / 'Credential'
        if os.name == 'nt':
            original = Path.is_junction
            with patch.object(Path, 'is_junction', lambda path: path == directory or original(path)):
                with self.assertRaisesRegex(ValueError, 'junction'):
                    SecretStore(self.root)
        else:
            relocated = self.root / 'relocated-private'
            directory.rename(relocated)
            directory.symlink_to(relocated, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                SecretStore(self.root)

    def test_secret_versions_encrypted_and_never_revealed_in_status(self):
        secrets = SecretStore(self.root)
        fixture = {'access_key': 'fixture access value', 'secret_key': 'fixture secret value'}
        self.assertEqual(secrets.set('repliz', fixture), 1)
        self.assertEqual(secrets.set('repliz', {'secret_key': 'fixture rotated value'}), 2)
        self.assertEqual(secrets.get('repliz', 1), fixture)
        self.assertEqual(secrets.get('repliz', 0), {})
        self.assertEqual(secrets.get('repliz')['access_key'], fixture['access_key'])
        self.assertEqual(secrets.status('repliz'), {'configured': True, 'version': 2})
        for path in (self.root / 'Credential').glob('*.enc'):
            self.assertNotIn(b'fixture', path.read_bytes())
        with self.assertRaises(ValueError):
            secrets.set('arbitrary', {'value':'test'})


if __name__ == '__main__':
    unittest.main()
