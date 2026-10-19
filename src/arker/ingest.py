from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from arker.db import Store, now, uid


def canonical_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2000:
        raise ValueError('Link tidak valid.')
    parsed = urlsplit(url.strip())
    match = re.fullmatch(r'/(?:reel|reels)/([A-Za-z0-9_-]{5,64})/?', parsed.path)
    if parsed.scheme != 'https' or parsed.hostname not in ('instagram.com', 'www.instagram.com') or parsed.username or parsed.password or parsed.port not in (None, 443) or not match:
        raise ValueError('Gunakan link HTTPS Instagram Reel.')
    return f'https://www.instagram.com/reel/{match.group(1)}/'


def intake(store: Store, urls: list[str], source='web') -> dict:
    if not isinstance(urls, list) or not urls:
        raise ValueError('Masukkan minimal satu link.')
    configuration = store.configuration()
    config_version = configuration['applied_version'] or configuration['desired_version']
    config = store.config_at(config_version)
    if len(urls) > config['workflow']['max_batch_links']:
        raise ValueError('Jumlah link melebihi batas satu batch.')
    result = {'batch_id': None, 'accepted': [], 'duplicates': [], 'rejected': []}
    stamp, batch = now(), uid()
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        backlog = db.execute("SELECT COUNT(*) FROM assets WHERE state NOT IN ('completed','published','failed','cancelled','preview_ready')").fetchone()[0]
        db.execute('INSERT INTO batches(id,source,created_at) VALUES (?,?,?)', (batch, source, stamp))
        for index, value in enumerate(urls):
            try:
                url = canonical_url(value)
            except (ValueError, TypeError):
                result['rejected'].append({'index': index, 'reason': 'Gunakan link HTTPS Instagram Reel yang valid.'})
                continue
            existing = db.execute('SELECT id FROM assets WHERE source_url=?', (url,)).fetchone()
            if existing:
                result['duplicates'].append({'index': index, 'id': existing['id'], 'source_url': url})
                continue
            if backlog >= config['workflow']['max_pending_assets']:
                result['rejected'].append({'index': index, 'reason': 'Antrean penuh. Coba kembali setelah pekerjaan selesai.'})
                continue
            identifier = uid()
            db.execute('INSERT INTO assets(id,batch_id,source_url,config_version,created_at,updated_at) VALUES (?,?,?,?,?,?)', (identifier, batch, url, config_version, stamp, stamp))
            for platform in ('tiktok', 'facebook', 'youtube'):
                db.execute('INSERT INTO deliveries(id,asset_id,platform,created_at,updated_at) VALUES (?,?,?,?,?)', (uid(), identifier, platform, stamp, stamp))
            db.execute('INSERT INTO events(kind,entity_id,payload,created_at) VALUES (?,?,?,?)', ('asset.received', identifier, json.dumps({'batch_id': batch, 'source': source}), stamp))
            result['accepted'].append({'id': identifier, 'source_url': url})
            backlog += 1
        db.execute('UPDATE batches SET accepted=? WHERE id=?', (len(result['accepted']), batch))
    result['batch_id'] = batch
    return result
