from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

from arker.db import Store, uid

COOKIE_NAME = 'arker_session'
SESSION_SECONDS = 8 * 60 * 60


def password_hash(password: str) -> str:
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise ValueError('Password harus terdiri dari 12 sampai 1024 karakter.')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1, maxmem=64 * 1024 * 1024)
    return f'scrypt:32768:8:1:{salt.hex()}:{digest.hex()}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = encoded.split(':')
        if scheme != 'scrypt' or len(password) > 1024:
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def bootstrap_admin(store: Store, email: str, password: str):
    email = email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
        raise ValueError('Email admin tidak valid.')
    encoded = password_hash(password)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            raise ValueError('Admin sudah dibuat. Gunakan prosedur reset lokal.')
        identifier = uid()
        db.execute('INSERT INTO users VALUES (?,?,?,?)', (identifier, email, encoded, time.time()))
    store.event('admin.created', identifier)
    return {'id': identifier, 'email': email}


def setup_required(store):
    with store.connect() as db:
        return db.execute('SELECT 1 FROM users LIMIT 1').fetchone() is None


def login(store: Store, email: str, password: str, bucket: str):
    stamp = time.time()
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        attempt = db.execute('SELECT * FROM login_attempts WHERE bucket=?', (bucket,)).fetchone()
        if attempt and stamp - attempt['window_start'] < 900 and attempt['count'] >= 10:
            raise PermissionError('rate_limited')
        if not attempt or stamp - attempt['window_start'] >= 900:
            db.execute('INSERT OR REPLACE INTO login_attempts VALUES (?,1,?)', (bucket, stamp))
        else:
            db.execute('UPDATE login_attempts SET count=count+1 WHERE bucket=?', (bucket,))
        user = db.execute('SELECT * FROM users WHERE email=?', (email.strip().lower(),)).fetchone()
    # An absent account performs the same KDF to avoid a cheap account-enumeration timing signal.
    dummy = 'scrypt:32768:8:1:' + ('00' * 16) + ':' + ('00' * 64)
    if not verify_password(password, user['password_hash'] if user else dummy) or not user:
        raise PermissionError('invalid_login')
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with store.connect() as db:
        db.execute('DELETE FROM login_attempts WHERE bucket=?', (bucket,))
        db.execute('DELETE FROM sessions WHERE expires_at<=?', (stamp,))
        db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), user['id'], csrf, stamp + SESSION_SECONDS, stamp))
    store.event('session.started', user['id'])
    return token, {'authenticated': True, 'user': {'id': user['id'], 'email': user['email']}, 'csrf_token': csrf, 'setup_required': False}


def session(store: Store, token: str | None):
    if not token or len(token) > 200:
        return None
    with store.connect() as db:
        row = db.execute('SELECT sessions.*,users.email FROM sessions JOIN users ON users.id=sessions.user_id WHERE token_hash=? AND expires_at>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
    if not row:
        return None
    return {'authenticated': True, 'user': {'id': row['user_id'], 'email': row['email']}, 'csrf_token': row['csrf'], 'setup_required': False}


def logout(store, token):
    if token:
        with store.connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))
