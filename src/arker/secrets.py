from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from arker.locks import DataLock

PROVIDERS = {'repliz': ('access_key', 'secret_key'), 'ai': ('api_key',), 'drive': ('access_token',), 'telegram': ('bot_token',)}


class SecretStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.directory = Path(data_dir) / 'Credential'
        self._check_path(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.key_file = self.directory / '.key'
        self._check_path(self.key_file)
        with DataLock(self.data_dir, 'secret-key', blocking=True):
            if not self.key_file.exists():
                descriptor, temporary = tempfile.mkstemp(dir=self.directory, prefix='.key-pending-')
                try:
                    with os.fdopen(descriptor, 'wb') as file:
                        file.write(Fernet.generate_key())
                        file.flush()
                        os.fsync(file.fileno())
                    os.replace(temporary, self.key_file)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
        self.key_file.chmod(0o600)
        self._fernet = Fernet(self.key_file.read_bytes())

    @staticmethod
    def _check_path(path):
        if any(part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()) for part in (path, *path.parents)):
            raise ValueError('Penyimpanan credential harus berupa file lokal tanpa symlink atau junction.')

    def _versions(self, provider):
        if provider not in PROVIDERS:
            raise ValueError('Provider tidak didukung.')
        self._check_path(self.directory)
        versions = []
        for path in self.directory.glob(f'{provider}.*.enc'):
            self._check_path(path)
            if match := re.fullmatch(rf'{provider}\.(\d+)\.enc', path.name):
                versions.append(int(match.group(1)))
        return sorted(versions)

    def set(self, provider: str, fields: dict) -> int:
        if provider not in PROVIDERS:
            raise ValueError('Provider tidak didukung.')
        with DataLock(self.data_dir, 'secret-' + provider, blocking=True):
            return self._set(provider, fields)

    def _set(self, provider: str, fields: dict) -> int:
        versions = self._versions(provider)
        if set(fields) - set(PROVIDERS[provider]):
            raise ValueError('Kolom credential tidak dikenal.')
        existing = self.get(provider) if versions else {}
        for key, value in fields.items():
            if not isinstance(value, str) or len(value) > 8192:
                raise ValueError('Nilai credential tidak valid.')
            if value.strip():
                existing[key] = value.strip()
        if any(not existing.get(key) for key in PROVIDERS[provider]):
            raise ValueError('Isi semua kolom credential yang diwajibkan.')
        version = (versions[-1] if versions else 0) + 1
        encoded = self._fernet.encrypt(json.dumps(existing).encode())
        descriptor, temporary = tempfile.mkstemp(dir=self.directory, prefix='.pending-')
        try:
            with os.fdopen(descriptor, 'wb') as file:
                file.write(encoded)
                file.flush()
                os.fsync(file.fileno())
            target = self.directory / f'{provider}.{version}.enc'
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return version

    def get(self, provider: str, version: int | None = None) -> dict:
        versions = self._versions(provider)
        if not versions:
            if version:
                raise ValueError('Versi credential tidak tersedia.')
            return {}
        selected = versions[-1] if version is None else version
        if selected == 0:
            return {}
        if selected not in versions:
            raise ValueError('Versi credential tidak tersedia.')
        path = self.directory / f'{provider}.{selected}.enc'
        self._check_path(path)
        path.chmod(0o600)
        try:
            return json.loads(self._fernet.decrypt(path.read_bytes()))
        except (InvalidToken, ValueError):
            raise ValueError('Credential tersimpan tidak dapat dibaca.') from None

    def status(self, provider=None):
        if provider is None:
            return {name: self.status(name) for name in PROVIDERS}
        versions = self._versions(provider)
        return {'configured': bool(versions), 'version': versions[-1] if versions else 0}
