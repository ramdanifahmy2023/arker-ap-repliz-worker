from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from . import Held
from .media import file_hashes


def folder_id(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'drive.google.com' or parsed.username or parsed.password:
        raise Held('drive_folder_url', 'Gunakan link folder Google Drive yang valid.')
    match = re.fullmatch(r'/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]{10,200})/?', parsed.path)
    if not match:
        raise Held('drive_folder_url', 'Link Google Drive harus menunjuk sebuah folder.')
    return match[1]


class Drive:
    """Verify externally synchronized files. This adapter never uploads or changes sharing."""

    def __init__(self, credentials, *, transport=None):
        if not credentials.get('access_token'):
            raise Held('drive_credentials', 'Token baca Google Drive belum dikonfigurasi.')
        self.client = httpx.AsyncClient(base_url='https://www.googleapis.com/drive/v3', headers={'Authorization': 'Bearer ' + credentials['access_token']}, timeout=30, follow_redirects=False, transport=transport)

    async def close(self):
        await self.client.aclose()

    async def get(self, path, params):
        try:
            response = await self.client.get(path, params=params)
            if response.status_code != 200:
                raise Held('drive_access', f'Google Drive mengembalikan HTTP {response.status_code}. Periksa token baca dan akses folder.')
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise Held('drive_unreachable', 'Google Drive belum dapat diperiksa.') from exc
        if not isinstance(data, dict):
            raise Held('drive_shape', 'Respons Google Drive belum lengkap.')
        return data

    async def folder(self, url):
        identifier = folder_id(url)
        result = await self.get('/files/' + identifier, {'fields': 'id,name,mimeType,trashed,capabilities(canListChildren)', 'supportsAllDrives': 'true'})
        if result.get('id') != identifier or result.get('mimeType') != 'application/vnd.google-apps.folder' or result.get('trashed'):
            raise Held('drive_folder_missing', 'Folder Google Drive tidak ditemukan atau sudah dihapus.')
        return {'id': identifier, 'name': result.get('name'), 'verified': True}

    async def verify(self, path, url):
        path = Path(path)
        identifier = folder_id(url)
        if not path.is_file() or path.is_symlink():
            raise Held('drive_local_missing', 'File lokal belum tersedia untuk pemeriksaan Drive.')
        filename = path.name.replace('\\', '\\\\').replace("'", "\\'")
        data = await self.get('/files', {
            'q': f"'{identifier}' in parents and trashed = false and name = '{filename}'",
            'fields': 'nextPageToken,incompleteSearch,files(id,name,size,md5Checksum,sha1Checksum,sha256Checksum,parents,webContentLink,permissions(type,role))',
            'pageSize': 100, 'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true',
        })
        files = data.get('files')
        if data.get('nextPageToken') or data.get('incompleteSearch') or not isinstance(files, list) or len(files) != 1:
            raise Held('drive_wait', 'Menunggu satu file yang cocok selesai disinkronkan ke Google Drive.')
        remote = files[0]
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', str(remote.get('id', ''))) or identifier not in remote.get('parents', []):
            raise Held('drive_identity', 'Identitas atau folder file Drive belum cocok.')
        try:
            size = int(remote.get('size', -1))
        except (ValueError, TypeError):
            size = -1
        if size != path.stat().st_size:
            raise Held('drive_size', 'Ukuran file Drive belum sama dengan file lokal.')
        hashes = file_hashes(path)
        for algorithm in ('md5', 'sha1', 'sha256'):
            if remote.get(algorithm + 'Checksum') != hashes[algorithm]:
                raise Held('drive_checksum', 'Checksum penuh file Drive belum cocok dengan file lokal.')
        if not any(permission.get('type') == 'anyone' and permission.get('role') == 'reader' for permission in remote.get('permissions', [])):
            raise Held('drive_not_public', 'File Drive belum memiliki izin baca tautan untuk provider. Atur berbagi di Google Drive.')
        return {'id': remote['id'], 'url': 'https://drive.google.com/uc?export=download&id=' + remote['id'], 'size': size, 'sha256': hashes['sha256'], 'checksums': hashes}
