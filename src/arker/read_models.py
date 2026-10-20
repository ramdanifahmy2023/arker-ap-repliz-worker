from __future__ import annotations

import json
import time
from datetime import date as calendar_date, datetime, time as calendar_time, timedelta
from zoneinfo import ZoneInfo

JSON_COLUMNS = {'context', 'payload', 'result', 'capabilities'}
ATTENTION_STATES = ('failed', 'unknown', 'submit_unknown', 'blocked', 'held', 'waiting')


def record(row):
    value = dict(row)
    for key in JSON_COLUMNS & value.keys():
        try:
            value[key] = json.loads(value[key])
        except (ValueError, TypeError):
            value[key] = {}
    return value


def asset_actions(asset, deliveries=(), has_attempts=False):
    if asset['state'] in ('failed', 'held') and not has_attempts and not any(d['state'] in ('published', 'scheduled', 'accepted', 'unknown', 'submit_unknown') for d in deliveries):
        return [{'kind': 'retry_asset', 'label': 'Ulangi proses lokal', 'payload': {'asset_id': asset['id']}}]
    return []


def delivery_actions(delivery, has_attempt=False, *, has_schedule_attempt=False):
    if delivery['state'] in ('unknown', 'submit_unknown', 'scheduled', 'accepted') and (delivery.get('remote_id') or has_schedule_attempt):
        return [{'kind': 'reconcile_delivery', 'label': 'Periksa hasil', 'payload': {'delivery_id': delivery['id']}}]
    if delivery['state'] == 'held' and not has_attempt and not delivery.get('remote_id'):
        return [{'kind': 'retry_delivery_caption', 'label': 'Ulangi caption & lanjutkan', 'payload': {'delivery_id': delivery['id']}}]
    return []


def health(store):
    heartbeat = store.get_meta('worker_heartbeat')
    if heartbeat is None:
        heartbeat = store.get_meta('heartbeat_at')
    if isinstance(heartbeat, dict):
        heartbeat = heartbeat.get('at', heartbeat.get('timestamp'))
    age = max(0.0, time.time() - heartbeat) if isinstance(heartbeat, (int, float)) else None
    worker_state = store.get_meta('worker_state', 'running')
    connected = age is not None and age < 60 and worker_state != 'stopped'
    configuration = store.configuration()
    applied = store.config_at(configuration['applied_version'] or configuration['desired_version'])
    reply_enabled = bool(applied['reply']['enabled'] and not store.get_meta('reply_paused', False) and applied['application']['mode'] == 'live' and applied['application']['publish_enabled'] and applied['ownership']['acknowledged'] and applied['ownership']['account_ids'] and configuration['applied_version'] > 0 and not store.get_meta('restore_requires_reconciliation', False))
    return {'connected': connected, 'state': store.get_meta('worker_state', 'running') if connected else 'offline', 'heartbeat_at': heartbeat, 'age_seconds': age, 'components': store.get_meta('components', {}), 'applied_version': configuration['applied_version'], 'desired_version': configuration['desired_version'], 'paused': store.get_meta('processing_paused', False), 'reply_configured': applied['reply']['enabled'], 'reply_enabled': reply_enabled, 'restore_requires_reconciliation': store.get_meta('restore_requires_reconciliation', False), 'instance_id': store.get_meta('instance_id')}


def assets(store, q='', state='', page=1, limit=25, stage='', date='', scope='', batch_id=''):
    clauses, values = [], []
    if q:
        clauses.append('(source_url LIKE ? OR source_username LIKE ? OR id LIKE ?)')
        values.extend([f'%{q}%'] * 3)
    if state:
        clauses.append('state=?')
        values.append(state)
    if stage:
        clauses.append('stage=?')
        values.append(stage)
    if scope == 'active':
        clauses.append("state NOT IN ('completed','published','failed','cancelled','preview_ready')")
    if batch_id:
        clauses.append('batch_id=?')
        values.append(batch_id)
    if date:
        day = calendar_date.fromisoformat(date)
        start = datetime.combine(day, calendar_time.min, ZoneInfo('Asia/Jakarta'))
        clauses.append('created_at>=? AND created_at<?')
        values.extend([start.timestamp(), (start + timedelta(days=1)).timestamp()])
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    with store.connect() as db:
        total = db.execute('SELECT COUNT(*) FROM assets' + where, values).fetchone()[0]
        rows = db.execute('SELECT * FROM assets' + where + ' ORDER BY created_at DESC,id LIMIT ? OFFSET ?', [*values, limit, (page-1)*limit]).fetchall()
        items = []
        for row in rows:
            item = record(row)
            item['deliveries'] = [record(r) for r in db.execute('SELECT * FROM deliveries WHERE asset_id=? ORDER BY platform', (item['id'],))]
            attempted = db.execute('SELECT 1 FROM attempts WHERE delivery_id IN (SELECT id FROM deliveries WHERE asset_id=?) LIMIT 1', (item['id'],)).fetchone()
            item['available_actions'] = asset_actions(item, item['deliveries'], bool(attempted))
            items.append(item)
    return {'items': items, 'total': total, 'page': page, 'limit': limit}


def asset_detail(store, identifier):
    with store.connect() as db:
        row = db.execute('SELECT * FROM assets WHERE id=?', (identifier,)).fetchone()
        if row is None:
            return None
        asset = record(row)
        deliveries = [record(r) for r in db.execute('SELECT * FROM deliveries WHERE asset_id=? ORDER BY platform', (identifier,))]
        attempted = db.execute('SELECT 1 FROM attempts WHERE delivery_id IN (SELECT id FROM deliveries WHERE asset_id=?) LIMIT 1', (identifier,)).fetchone()
        asset['available_actions'] = asset_actions(asset, deliveries, bool(attempted))
        for item in deliveries:
            attempts = db.execute("SELECT COUNT(*) total, COUNT(CASE WHEN operation='schedule' THEN 1 END) schedules FROM attempts WHERE delivery_id=?", (item['id'],)).fetchone()
            item['available_actions'] = delivery_actions(item, bool(attempts['total']), has_schedule_attempt=bool(attempts['schedules']))
        events = [record(r) for r in db.execute('SELECT * FROM events WHERE entity_id=? OR entity_id IN (SELECT id FROM deliveries WHERE asset_id=?) ORDER BY id DESC LIMIT 250', (identifier, identifier))]
        artifacts = [record(r) for r in db.execute('SELECT * FROM artifacts WHERE asset_id=?', (identifier,))]
        for item in artifacts:
            item['url'] = f"/api/media/{identifier}/{item['kind']}"
    return {'asset': asset, 'deliveries': deliveries, 'events': events, 'artifacts': artifacts}


def overview(store):
    stamp = time.time()
    day = datetime.fromtimestamp(stamp, ZoneInfo('Asia/Jakarta')).date()
    days = [day - timedelta(days=offset) for offset in reversed(range(7))]
    throughput = {str(date): {'date': str(date), 'assets': 0, 'deliveries': 0} for date in days}
    with store.connect() as db:
        states = {row['state']: row['n'] for row in db.execute('SELECT state,COUNT(*) n FROM assets GROUP BY state')}
        delivery_states = {row['state']: row['n'] for row in db.execute('SELECT state,COUNT(*) n FROM deliveries GROUP BY state')}
        stages = [{'stage': row['stage'], 'count': row['n']} for row in db.execute("SELECT stage,COUNT(*) n FROM assets WHERE state NOT IN ('completed','published','failed','cancelled','preview_ready') GROUP BY stage")]
        for row in db.execute('SELECT created_at FROM assets WHERE created_at>?', (stamp - 8 * 86400,)):
            key = str(datetime.fromtimestamp(row['created_at'], ZoneInfo('Asia/Jakarta')).date())
            if key in throughput:
                throughput[key]['assets'] += 1
        for row in db.execute("SELECT published_at FROM deliveries WHERE state='published' AND published_at>?", (stamp - 8 * 86400,)):
            key = str(datetime.fromtimestamp(row['published_at'], ZoneInfo('Asia/Jakarta')).date())
            if key in throughput:
                throughput[key]['deliveries'] += 1
        platforms = []
        for platform in ('tiktok', 'facebook', 'youtube'):
            counts = {r['state']: r['n'] for r in db.execute('SELECT state,COUNT(*) n FROM deliveries WHERE platform=? GROUP BY state', (platform,))}
            platforms.append({'platform': platform, 'published': counts.get('published', 0), 'scheduled': counts.get('scheduled', 0), 'failed': counts.get('failed', 0), 'unknown': counts.get('unknown', 0) + counts.get('submit_unknown', 0)})
        attention = [dict(record(r), entity_type='asset') for r in db.execute("SELECT * FROM assets WHERE state IN ('failed','blocked','unknown','submit_unknown','held','waiting') ORDER BY updated_at DESC LIMIT 20")]
        for item in attention:
            destinations = db.execute('SELECT state FROM deliveries WHERE asset_id=?', (item['id'],)).fetchall()
            attempted = db.execute('SELECT 1 FROM attempts WHERE delivery_id IN (SELECT id FROM deliveries WHERE asset_id=?) LIMIT 1', (item['id'],)).fetchone()
            item['available_actions'] = asset_actions(item, destinations, bool(attempted))
        delivery_attention = [dict(record(r), entity_type='delivery') for r in db.execute("SELECT * FROM deliveries WHERE state IN ('failed','blocked','unknown','submit_unknown','held','waiting') ORDER BY updated_at DESC LIMIT 20")]
        for item in delivery_attention:
            attempts = db.execute("SELECT COUNT(*) total, COUNT(CASE WHEN operation='schedule' THEN 1 END) schedules FROM attempts WHERE delivery_id=?", (item['id'],)).fetchone()
            item['available_actions'] = delivery_actions(item, bool(attempts['total']), has_schedule_attempt=bool(attempts['schedules']))
        attention.extend(delivery_attention)
        active = [record(r) for r in db.execute("SELECT * FROM assets WHERE state NOT IN ('completed','published','failed','cancelled','preview_ready') ORDER BY updated_at DESC LIMIT 12")]
        duration_rows = db.execute("SELECT payload FROM events WHERE kind IN ('stage.completed','asset.stage') AND created_at>?", (stamp-7*86400,)).fetchall()
    durations = {}
    for row in duration_rows:
        payload = json.loads(row['payload'])
        duration = payload.get('seconds', payload.get('duration_seconds'))
        stage = 'download' if payload.get('stage') == 'queued' else payload.get('stage')
        if isinstance(duration, (int, float)) and duration >= 0 and stage:
            durations.setdefault(stage, []).append(duration)
    summary = {'assets_total': sum(states.values()), 'assets_active': sum(n for state, n in states.items() if state not in ('completed','published','failed','cancelled','preview_ready')), 'assets_completed': states.get('completed', 0) + states.get('published', 0), 'previews_ready': states.get('preview_ready', 0), 'deliveries_published': delivery_states.get('published', 0), 'deliveries_scheduled': delivery_states.get('scheduled', 0), 'attention_count': sum(states.get(s, 0) + delivery_states.get(s, 0) for s in ATTENTION_STATES)}
    return {'health': health(store), 'summary': summary, 'charts': {'throughput': list(throughput.values()), 'stages': stages, 'platforms': platforms, 'durations': [{'stage': stage, 'seconds': sum(values)/len(values), 'samples': len(values)} for stage, values in durations.items()]}, 'active_assets': active, 'attention': attention, 'generated_at': stamp}
