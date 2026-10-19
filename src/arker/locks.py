from __future__ import annotations

import os
from pathlib import Path
import re
import time


class LockBusy(RuntimeError):
    pass


class DataLock:
    def __init__(self, data_dir: Path, name: str, *, blocking: bool = False, timeout: float = 30):
        if not re.fullmatch(r"[a-z0-9-]+", name):
            raise ValueError("Nama lock tidak valid.")
        folder = Path(data_dir) / ".locks"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = folder / (name + ".lock")
        self.blocking, self.timeout, self.handle = blocking, timeout, None

    def __enter__(self):
        self.handle = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self.handle.write(b"0")
            self.handle.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if not self.blocking or time.monotonic() >= deadline:
                    self.handle.close()
                    self.handle = None
                    raise LockBusy("Layanan atau operasi lain masih memakai data ini.") from None
                time.sleep(.05)

    def __exit__(self, *args):
        if self.handle is not None:
            try:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()
                self.handle = None


def is_locked(data_dir: Path, name: str) -> bool:
    try:
        with DataLock(data_dir, name):
            return False
    except LockBusy:
        return True
