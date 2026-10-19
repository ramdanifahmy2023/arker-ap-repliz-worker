"""Provider and media adapters. No adapter starts a worker or reads production data."""


class AdapterError(RuntimeError):
    def __init__(self, code: str, message: str, *, ambiguous: bool = False):
        super().__init__(message)
        self.code = code
        self.ambiguous = ambiguous


class Held(AdapterError):
    """A missing prerequisite; advancing would misrepresent or duplicate a result."""


async def test_connection(provider: str, secrets: dict, config: dict) -> dict:
    if provider == 'repliz':
        from .repliz import Repliz
        client = Repliz(secrets)
        try:
            accounts = await client.accounts()
            return {'connected': True, 'read_only': True, 'account_count': len(accounts), 'message': 'Kredensial diterima; daftar akun lengkap dapat dibaca.'}
        finally:
            await client.close()
    if provider == 'drive':
        from .drive import Drive
        client = Drive(secrets)
        try:
            folder = await client.folder(config.get('drive', {}).get('folder_url', ''))
            return {'connected': True, 'read_only': True, 'folder': folder, 'message': 'Folder bisa dibaca. Checksum tetap diperiksa per file.'}
        finally:
            await client.close()
    if provider in {'ai', 'telegram'}:
        import httpx
        from urllib.parse import urlparse
        if provider == 'telegram':
            token = secrets.get('bot_token')
            if not token:
                raise Held('telegram_credentials', 'Token bot belum diisi.')
            endpoint, headers = 'https://api.telegram.org/bot' + token + '/getMe', {}
        else:
            base = config.get('ai', {}).get('base_url', '').rstrip('/')
            parsed = urlparse(base)
            if parsed.scheme != 'https' or parsed.hostname not in {'api.openai.com', 'openrouter.ai'}:
                raise Held('ai_url', 'Endpoint AI belum didukung.')
            endpoint, headers = base + '/models', {'Authorization': 'Bearer ' + secrets.get('api_key', '')}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                response = await client.get(endpoint, headers=headers)
                if response.status_code != 200:
                    raise Held('connection_http', f'Layanan mengembalikan HTTP {response.status_code}.')
                data = response.json()
                if provider == 'telegram' and data.get('ok') is not True:
                    raise Held('telegram_test', 'Bot belum dapat diverifikasi.')
        except (httpx.HTTPError, ValueError) as exc:
            raise Held('connection_unavailable', 'Layanan belum dapat dihubungi.') from exc
        return {'connected': True, 'read_only': True, 'message': 'Koneksi baca berhasil.'}
    raise Held('provider_unknown', 'Layanan belum didukung.')
