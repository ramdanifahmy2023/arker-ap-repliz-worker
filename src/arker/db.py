from __future__ import annotations

import contextlib
import json
import sqlite3
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), csrf TEXT NOT NULL, expires_at REAL NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts (bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, window_start REAL NOT NULL);
CREATE TABLE IF NOT EXISTS configurations (version INTEGER PRIMARY KEY AUTOINCREMENT, config TEXT NOT NULL, created_at REAL NOT NULL, actor TEXT);
CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}', idempotency_key TEXT UNIQUE NOT NULL, status TEXT NOT NULL DEFAULT 'pending', result TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS batches (id TEXT PRIMARY KEY, source TEXT NOT NULL, accepted INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS assets (id TEXT PRIMARY KEY, batch_id TEXT REFERENCES batches(id), source_url TEXT UNIQUE NOT NULL, source_username TEXT, source_verified INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'queued', stage TEXT NOT NULL DEFAULT 'queued', progress REAL, total REAL, config_version INTEGER NOT NULL, context TEXT NOT NULL DEFAULT '{}', hook TEXT, caption TEXT, error TEXT, lease_owner TEXT, lease_until REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id), platform TEXT NOT NULL CHECK(platform IN ('tiktok','facebook','youtube')), account_id TEXT, state TEXT NOT NULL DEFAULT 'pending', remote_id TEXT, post_url TEXT, scheduled_at REAL, published_at REAL, error TEXT, lease_owner TEXT, lease_until REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL, UNIQUE(asset_id,platform));
CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, platform TEXT NOT NULL, username TEXT, name TEXT, connected INTEGER NOT NULL DEFAULT 0, capabilities TEXT NOT NULL DEFAULT '{}', quota_limit INTEGER NOT NULL DEFAULT 20, quota_used INTEGER NOT NULL DEFAULT 0, quota_day TEXT, snapshot_at REAL, enabled INTEGER NOT NULL DEFAULT 0, ownership_instance TEXT);
CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id), delivery_id TEXT UNIQUE NOT NULL REFERENCES deliveries(id), day TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'reserved');
CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, delivery_id TEXT REFERENCES deliveries(id), operation TEXT NOT NULL, request_key TEXT UNIQUE NOT NULL, state TEXT NOT NULL, remote_id TEXT, payload TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id), kind TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT, size INTEGER, drive_id TEXT, drive_url TEXT, verified_at REAL, created_at REAL NOT NULL, UNIQUE(asset_id,kind));
CREATE TABLE IF NOT EXISTS comments (id TEXT PRIMARY KEY, account_id TEXT, post_id TEXT, asset_id TEXT REFERENCES assets(id), parent_id TEXT, text TEXT NOT NULL, author TEXT, state TEXT NOT NULL DEFAULT 'pending', reply TEXT, remote_reply_id TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS personas (id TEXT NOT NULL, version INTEGER NOT NULL, name TEXT NOT NULL, style TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(id,version));
CREATE TABLE IF NOT EXISTS account_personas (account_id TEXT PRIMARY KEY REFERENCES accounts(id), persona_id TEXT NOT NULL, persona_version INTEGER NOT NULL, FOREIGN KEY(persona_id,persona_version) REFERENCES personas(id,version));
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, entity_id TEXT, payload TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT, kind TEXT NOT NULL, value REAL NOT NULL, sampled_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_assets_state ON assets(state,created_at);
CREATE INDEX IF NOT EXISTS idx_assets_created ON assets(created_at DESC,id);
CREATE INDEX IF NOT EXISTS idx_deliveries_state ON deliveries(state,created_at);
CREATE INDEX IF NOT EXISTS idx_deliveries_created ON deliveries(created_at DESC,id);
CREATE INDEX IF NOT EXISTS idx_deliveries_published ON deliveries(published_at);
CREATE INDEX IF NOT EXISTS idx_reservations_account_day ON reservations(account_id,day,state);
CREATE INDEX IF NOT EXISTS idx_attempts_delivery ON attempts(delivery_id,operation);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_id,id);
CREATE INDEX IF NOT EXISTS idx_events_kind_time ON events(kind,created_at);
CREATE INDEX IF NOT EXISTS idx_comments_updated ON comments(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_sampled ON metrics(sampled_at DESC);
"""


def now() -> float:
    return time.time()


def uid() -> str:
    return uuid.uuid4().hex


class Store:
    def __init__(self, data_dir: str | Path):
        if str(data_dir).startswith(('\\\\', '//')):
            raise ValueError('Data SQLite harus berada di disk lokal, bukan network share.')
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data_dir.chmod(0o700)
        self.path = self.data_dir / 'arker.sqlite3'
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute('BEGIN IMMEDIATE')
            db.execute("INSERT OR IGNORE INTO meta VALUES ('instance_id',?)", (json.dumps(uid()),))
            if not db.execute('SELECT 1 FROM configurations LIMIT 1').fetchone():
                from arker.config import default_config
                db.execute('INSERT INTO configurations(config,created_at) VALUES (?,?)', (json.dumps(default_config(self.data_dir)), now()))
                db.execute("INSERT INTO meta VALUES ('desired_version','1')")
                db.execute("INSERT INTO meta VALUES ('applied_version','0')")
        if self.path.exists():
            self.path.chmod(0o600)

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=10000')
        try:
            with db:
                yield db
        finally:
            db.close()

    def get_meta(self, key, default=None):
        with self.connect() as db:
            row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_meta(self, key, value):
        with self.connect() as db:
            db.execute('INSERT INTO meta(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(value)))

    def event(self, kind, entity_id=None, payload=None):
        with self.connect() as db:
            cursor = db.execute('INSERT INTO events(kind,entity_id,payload,created_at) VALUES (?,?,?,?)', (kind, entity_id, json.dumps(payload or {}), now()))
            return cursor.lastrowid

    def configuration(self):
        with self.connect() as db:
            values = {r['key']: json.loads(r['value']) for r in db.execute("SELECT * FROM meta WHERE key IN ('desired_version','applied_version')")}
            row = db.execute('SELECT config FROM configurations WHERE version=?', (values['desired_version'],)).fetchone()
        return dict(config=json.loads(row[0]), **values)

    def config_at(self, version):
        with self.connect() as db:
            row = db.execute('SELECT config FROM configurations WHERE version=?', (version,)).fetchone()
        if row is None:
            raise ValueError('Versi konfigurasi tidak ditemukan.')
        return json.loads(row[0])

    def save_configuration(self, config, base_version, actor=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = json.loads(db.execute("SELECT value FROM meta WHERE key='desired_version'").fetchone()[0])
            if current != base_version:
                raise ValueError('configuration_conflict')
            version = db.execute('INSERT INTO configurations(config,created_at,actor) VALUES (?,?,?)', (json.dumps(config), now(), actor)).lastrowid
            db.execute("UPDATE meta SET value=? WHERE key='desired_version'", (json.dumps(version),))
            self._command(db, 'apply_configuration', {'version': version}, f'configuration:{version}')
        self.event('configuration.saved', str(version), {'version': version})
        return version

    @staticmethod
    def _command(db, kind, payload, idempotency_key):
        previous = db.execute('SELECT * FROM commands WHERE idempotency_key=?', (idempotency_key,)).fetchone()
        encoded = json.dumps(payload, sort_keys=True)
        if previous:
            if previous['kind'] != kind or json.loads(previous['payload']) != payload:
                raise ValueError('idempotency_conflict')
            return dict(previous)
        identifier, stamp = uid(), now()
        db.execute('INSERT INTO commands(id,kind,payload,idempotency_key,created_at,updated_at) VALUES (?,?,?,?,?,?)', (identifier, kind, encoded, idempotency_key, stamp, stamp))
        return dict(db.execute('SELECT * FROM commands WHERE id=?', (identifier,)).fetchone())

    def command(self, kind, payload, idempotency_key):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            result = self._command(db, kind, payload, idempotency_key)
        result['payload'] = json.loads(result['payload'])
        result['result'] = json.loads(result['result'])
        return result
