from __future__ import annotations

import os
import re
import shutil
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit


def default_config(data_dir: Path) -> dict:
    return {
        'application': {'mode': 'shadow', 'publish_enabled': False, 'timezone': 'Asia/Jakarta'},
        'appearance': {'theme': 'system', 'motion': 'system'},
        'workflow': {'daily_video_limit': 20, 'window_start': 8, 'window_end': 23, 'max_batch_links': 100, 'max_pending_assets': 1000},
        'storage': {'bank_directory': str(Path(data_dir).resolve() / 'bank'), 'sync_adapter': 'external'},
        'drive': {'folder_url': '', 'require_full_checksum': True},
        'video': {'zoom': 1.1, 'mirror': False, 'hook_seconds': 3, 'min_duration': 3, 'max_duration': 90, 'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'},
        'ai': {'enabled': False, 'base_url': 'https://api.openai.com/v1', 'model': '', 'transcription_enabled': False, 'whisper_executable': 'whisper-cli', 'whisper_model': ''},
        'reply': {'enabled': False, 'daily_limit': 20},
        'telegram': {'enabled': False, 'public_ingest': True, 'admin_id': ''},
        'reports': {'enabled': False},
        'cleanup': {'enabled': False, 'retention_hours': 24},
        'ownership': {'acknowledged': False, 'account_ids': [], 'excluded_account_ids': []},
        'credentials': {'repliz': 0, 'ai': 0, 'drive': 0, 'telegram': 0},
    }


def drive_folder_id(url: str) -> str | None:
    if not url:
        return None
    parsed = urlsplit(url)
    match = re.fullmatch(r'/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]{10,})/?', parsed.path)
    if parsed.scheme != 'https' or parsed.hostname != 'drive.google.com' or parsed.port not in (None, 443) or parsed.username or parsed.password or not match:
        raise ValueError('Gunakan link HTTPS folder drive.google.com/drive/folders/...')
    return match.group(1)


def valid_executable(value: str, basename: str) -> bool:
    if not value or len(value) > 4096 or value != value.strip() or '\x00' in value or '\n' in value or '\r' in value or value.startswith(('\\\\', '//')):
        return False
    path = PureWindowsPath(value) if '\\' in value else Path(value)
    return path.name.casefold() in (basename, basename + '.exe') and '..' not in path.parts


def bank_path(value: str, data_dir: Path) -> Path:
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError('Lokasi bank konten wajib diisi.')
    raw = Path(value).expanduser()
    if '..' in raw.parts:
        raise ValueError('Lokasi bank tidak boleh mengandung traversal.')
    if not raw.is_absolute():
        raw = data_dir / raw
    for part in [raw, *raw.parents]:
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Lokasi bank tidak boleh melalui symlink.')
    resolved = raw.resolve()
    root = data_dir.resolve()
    protected = [root / name for name in ('Credential', 'cache', 'work', 'backups', 'attempts', 'journals', '.locks')]
    if resolved == root or resolved == Path(resolved.anchor) or any(resolved == p or p in resolved.parents or resolved in p.parents for p in protected):
        raise ValueError('Pilih folder bank tersendiri, terpisah dari data internal aplikasi.')
    if resolved.exists() and not resolved.is_dir():
        raise ValueError('Lokasi bank harus berupa folder.')
    for mount_prefix in (Path('/Volumes'), Path('/media'), Path('/mnt')):
        if resolved.is_relative_to(mount_prefix) and len(resolved.relative_to(mount_prefix).parts) > 0:
            volume = mount_prefix / resolved.relative_to(mount_prefix).parts[0]
            if not volume.exists():
                raise ValueError('Volume bank belum terpasang. Sambungkan volume sebelum mengubah lokasi.')
    if resolved.anchor and not Path(resolved.anchor).exists():
        raise ValueError('Volume bank belum terpasang.')
    return resolved


def storage_check(bank_directory: str, folder_url: str, data_dir: Path) -> dict:
    findings, path, folder_id = [], None, None
    try:
        path = bank_path(bank_directory, data_dir)
    except (ValueError, OSError) as exc:
        findings.append({'field': 'storage.bank_directory', 'message': str(exc)})
    try:
        folder_id = drive_folder_id(folder_url)
    except (ValueError, TypeError):
        findings.append({'field': 'drive.folder_url', 'message': 'Link folder Google Drive tidak valid.'})
    capacity = None
    if path:
        ancestor = path
        while not ancestor.exists() and ancestor != ancestor.parent:
            ancestor = ancestor.parent
        try:
            capacity = dict(zip(('total', 'used', 'free'), shutil.disk_usage(ancestor)))
            if not os.access(ancestor, os.R_OK | os.W_OK):
                findings.append({'field': 'storage.bank_directory', 'message': 'Folder tidak dapat dibaca dan ditulis oleh layanan.'})
        except OSError:
            findings.append({'field': 'storage.bank_directory', 'message': 'Volume bank tidak dapat dibaca. Periksa koneksi disk.'})
    return {'valid': not findings, 'findings': findings, 'bank_directory': str(path) if path else None, 'exists': bool(path and path.exists()), 'folder_id': folder_id, 'capacity': capacity, 'verification': 'not_verified', 'note': 'Pemeriksaan lokal dan bentuk URL; akses Drive dan checksum diperiksa worker per file.'}


def validate_config(config: dict, data_dir: Path) -> dict:
    errors = []
    defaults = default_config(data_dir)
    if not isinstance(config, dict):
        return {'valid': False, 'errors': [{'field': 'config', 'message': 'Konfigurasi harus berbentuk objek.'}], 'impact': []}
    for section, values in defaults.items():
        if not isinstance(config.get(section), dict):
            errors.append({'field': section, 'message': 'Bagian konfigurasi wajib diisi.'})
            continue
        for key, default in values.items():
            value = config[section].get(key)
            kind = type(default)
            if kind is float:
                okay = type(value) in (int, float)
            else:
                okay = type(value) is kind
            if not okay:
                errors.append({'field': f'{section}.{key}', 'message': 'Tipe nilai tidak sesuai.'})
        for key in config[section].keys() - values.keys():
            errors.append({'field': f'{section}.{key}', 'message': 'Pengaturan tidak dikenal.'})
    for section in config.keys() - defaults.keys():
        errors.append({'field': section, 'message': 'Bagian konfigurasi tidak dikenal.'})
    if errors:
        return {'valid': False, 'errors': errors, 'impact': []}
    def require(condition, field, message):
        if not condition:
            errors.append({'field': field, 'message': message})
    require(config['application']['mode'] in ('shadow', 'live'), 'application.mode', 'Mode harus shadow atau live.')
    require(config['application']['timezone'] == 'Asia/Jakarta', 'application.timezone', 'Kuota memakai Asia/Jakarta.')
    require(config['appearance']['theme'] in ('system', 'light', 'dark'), 'appearance.theme', 'Tema tidak dikenal.')
    require(config['appearance']['motion'] in ('system', 'reduced', 'full'), 'appearance.motion', 'Pilihan animasi tidak dikenal.')
    for field, minimum, maximum in [('daily_video_limit', 1, 20), ('window_start', 0, 23), ('window_end', 1, 24), ('max_batch_links', 1, 100), ('max_pending_assets', 1, 10000)]:
        require(minimum <= config['workflow'][field] <= maximum, f'workflow.{field}', f'Nilai harus {minimum} sampai {maximum}.')
    require(config['workflow']['window_start'] < config['workflow']['window_end'], 'workflow.window_end', 'Jam akhir harus sesudah jam mulai.')
    require(1 <= config['reply']['daily_limit'] <= 100, 'reply.daily_limit', 'Batas reply harus 1 sampai 100.')
    require(config['cleanup']['retention_hours'] >= 24, 'cleanup.retention_hours', 'Retensi minimal 24 jam setelah seluruh tujuan tayang.')
    require(config['video']['mirror'] is False and config['video']['zoom'] == 1.1 and config['video']['hook_seconds'] == 3, 'video', 'Profil video: tanpa mirror, zoom 110%, hook sebelum detik 3.')
    require(3 <= config['video']['min_duration'] <= config['video']['max_duration'] <= 90, 'video.max_duration', 'Durasi harus berada antara 3 dan 90 detik.')
    require(config['drive']['require_full_checksum'] is True, 'drive.require_full_checksum', 'Verifikasi checksum wajib aktif.')
    require(config['storage']['sync_adapter'] == 'external', 'storage.sync_adapter', 'Gunakan satu penulis sinkronisasi eksternal.')
    for field in ('ffmpeg', 'ffprobe'):
        require(valid_executable(config['video'][field], field), f'video.{field}', f'Pilih executable lokal {field}, bukan skrip shell atau network share.')
    require(valid_executable(config['ai']['whisper_executable'], 'whisper-cli'), 'ai.whisper_executable', 'Pilih executable lokal whisper-cli.')
    for field in ('account_ids', 'excluded_account_ids'):
        require(all(isinstance(v, str) and 0 < len(v) <= 200 for v in config['ownership'][field]), f'ownership.{field}', 'ID akun harus teks.')
        require(len(config['ownership'][field]) <= 1000, f'ownership.{field}', 'Maksimal 1000 ID akun dalam satu scope.')
    for provider, version in config['credentials'].items():
        require(type(version) is int and version >= 0, f'credentials.{provider}', 'Versi credential tidak valid.')
    live = config['application']['mode'] == 'live' or config['application']['publish_enabled']
    if live:
        require(config['application']['mode'] == 'live' and config['application']['publish_enabled'], 'application', 'Aktivasi live memerlukan mode live dan publikasi aktif.')
        require(config['ownership']['acknowledged'] and bool(config['ownership']['account_ids']), 'ownership', 'Tetapkan scope akun eksklusif sebelum aktivasi live.')
        require(bool(config['drive']['folder_url']), 'drive.folder_url', 'Folder Drive diperlukan untuk live.')
        require(config['credentials']['repliz'] > 0 and config['credentials']['drive'] > 0, 'credentials', 'Credential Repliz dan Drive diperlukan untuk live.')
    try:
        parsed = urlsplit(config['ai']['base_url'])
        allowed_ai = parsed.scheme == 'https' and parsed.hostname in ('api.openai.com', 'openrouter.ai') and parsed.port in (None, 443) and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
    except ValueError:
        allowed_ai = False
    require(allowed_ai, 'ai.base_url', 'Endpoint AI belum didukung; gunakan provider HTTPS yang terdaftar.')
    if config['ai']['enabled']:
        require(bool(config['ai']['model'].strip()), 'ai.model', 'Model AI wajib diisi.')
        require(config['credentials']['ai'] > 0, 'credentials.ai', 'Simpan credential AI sebelum mengaktifkan penyusunan metadata.')
    if config['telegram']['enabled']:
        require(bool(re.fullmatch(r'[1-9][0-9]{3,19}', config['telegram']['admin_id'])), 'telegram.admin_id', 'Isi ID admin Telegram pribadi yang valid.')
        require(config['credentials']['telegram'] > 0, 'credentials.telegram', 'Simpan token bot sebelum mengaktifkan Telegram.')
    if config['ai']['transcription_enabled']:
        require(bool(config['ai']['whisper_model'].strip()), 'ai.whisper_model', 'Lokasi model Whisper wajib diisi.')
        require(bool(config['ai']['whisper_executable'].strip()), 'ai.whisper_executable', 'Executable Whisper wajib diisi.')
    result = storage_check(config['storage']['bank_directory'], config['drive']['folder_url'], data_dir)
    errors.extend(result['findings'])
    return {'valid': not errors, 'errors': errors, 'impact': ['Konten baru memakai versi baru setelah worker mengonfirmasi.', 'Konten lama mempertahankan konfigurasi dan lokasi bank sebelumnya.', 'Perubahan tidak membatalkan jadwal yang sudah diterima provider.']}
