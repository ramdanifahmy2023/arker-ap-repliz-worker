from __future__ import annotations

import os
from pathlib import Path
import sys


def default_data_dir(platform: str | None = None) -> Path:
    platform = platform or sys.platform
    if os.environ.get("ARKER_DATA_DIR"):
        return Path(os.environ["ARKER_DATA_DIR"]).expanduser().resolve()
    if platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Arker"
    if platform == "darwin":
        return Path.home() / "Library/Application Support/Arker"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "arker"


def frontend_directory() -> Path | None:
    packaged = Path(__file__).parent / "web"
    if (packaged / "index.html").is_file():
        return packaged
    checkout = Path(__file__).resolve().parents[2] / "apps/web/dist"
    return checkout if (checkout / "index.html").is_file() else None
