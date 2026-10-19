"""Check the public planning foundation without accessing services or local secrets."""
from __future__ import annotations

import ast
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tomllib
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIRS = {"credential", "credentials", "runtime", "data", "bank-content", "backups"}
PRIVATE_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".mp4", ".mov", ".webm"}
SECRET_PATTERNS = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"\b\d{6,15}:[A-Za-z0-9_-]{25,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"/(?:Users|Volumes|home)/[A-Za-z0-9]"),
    re.compile(r"(?i)\b(?:password|secret_key|access_key|api_key)\s*[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_+/.:-]{12,}[\"']"),
]
LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")


def publication_issues(name: str, source: str) -> list[str]:
    path = PurePosixPath(name)
    issues = []
    if any(p.casefold() in PRIVATE_DIRS for p in path.parts) or path.suffix.lower() in PRIVATE_SUFFIXES:
        issues.append("private-file")
    if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
        issues.append("private-env")
    if any(pattern.search(source) for pattern in SECRET_PATTERNS):
        issues.append("sensitive-content")
    return issues


def link_issues(root: Path, name: str, source: str) -> list[str]:
    issues = []
    for match in LINK.finditer(source):
        target = match.group(1).strip().strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or target.startswith("#"):
            continue
        dest = (root / name).parent / unquote(parsed.path)
        if not dest.resolve().is_relative_to(root.resolve()) or not dest.exists():
            issues.append("broken-local-link")
    return issues


def candidate_files(root: Path) -> list[str]:
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    )
    return sorted(set(raw.decode("utf-8").rstrip("\0").split("\0")) - {""})


def validate(root: Path = ROOT) -> list[tuple[str, str]]:
    issues = []
    files = candidate_files(root)
    for name in files:
        path = root / name
        if path.is_symlink():
            issues.append((name, "symlink-not-allowed"))
            continue
        try:
            source = path.read_text(encoding="utf-8")
            issues.extend((name, rule) for rule in publication_issues(name, source))
            if path.suffix == ".md":
                issues.extend((name, rule) for rule in link_issues(root, name, source))
            elif path.suffix == ".json":
                json.loads(source)
            elif path.suffix == ".toml":
                tomllib.loads(source)
            elif path.suffix == ".py":
                ast.parse(source)
            elif path.suffix == ".svg":
                svg = ET.fromstring(source)
                if svg.tag != "{http://www.w3.org/2000/svg}svg":
                    issues.append((name, "invalid-svg-root"))
                for element in svg.iter():
                    if element.tag.rsplit("}", 1)[-1] in {"script", "foreignObject"}:
                        issues.append((name, "active-svg-content"))
                    for key, value in element.attrib.items():
                        if key.lower().startswith("on") or (key.endswith("href") and not value.startswith("#")):
                            issues.append((name, "active-svg-attribute"))
        except (UnicodeError, OSError, ValueError, SyntaxError, ET.ParseError):
            issues.append((name, "unreadable-or-invalid-format"))

    required = [
        "README.md", "SECURITY.md", "docs/WORKLOG.md", "docs/plans/PRODUCT_PLAN.md",
        "docs/plans/UX_PLAN.md", "docs/plans/CONFIGURATION_PLAN.md", "docs/plans/ROADMAP.md",
        "docs/architecture/CROSS_PLATFORM.md", "spec/navigation.json", "spec/dashboard-metrics.json",
        "docs/assets/architecture.svg", "docs/assets/dashboard-concept.svg", "docs/assets/configuration-flow.svg",
    ]
    for name in required:
        if name not in files:
            issues.append((name, "required-file-missing"))
    try:
        nav = json.loads((root / "spec/navigation.json").read_text(encoding="utf-8"))
        items = [item for group in nav["groups"] for item in group["items"]]
        if len(nav["groups"]) != 6 or len(items) != 22:
            issues.append(("spec/navigation.json", "navigation-count"))
        for field in ("id", "route"):
            if len({item[field] for item in items}) != len(items):
                issues.append(("spec/navigation.json", "duplicate-navigation-" + field))
        metrics = json.loads((root / "spec/dashboard-metrics.json").read_text(encoding="utf-8"))
        if metrics["missing_data"] != "null_with_reason" or metrics["progress"]["clock_generated_percent"]:
            issues.append(("spec/dashboard-metrics.json", "misleading-progress-policy"))
        config = tomllib.loads((root / "config/examples/settings.example.toml").read_text(encoding="utf-8"))
        if config["application"]["mode"] != "shadow" or config["application"]["publish_enabled"]:
            issues.append(("config/examples/settings.example.toml", "unsafe-example-mode"))
        if config["reply"]["enabled"] or config["cleanup"]["enabled"]:
            issues.append(("config/examples/settings.example.toml", "unsafe-example-automation"))
        if not 1 <= config["workflow"]["daily_video_limit"] <= 20 or config["cleanup"]["retention_hours"] < 24:
            issues.append(("config/examples/settings.example.toml", "unsafe-example-limits"))
    except (OSError, ValueError, KeyError, TypeError):
        issues.append(("spec", "invalid-foundation-contract"))
    return sorted(set(issues))


if __name__ == "__main__":
    failures = validate()
    for filename, rule in failures:
        print(f"FAIL {filename}: {rule}")
    print(f"{'FAIL' if failures else 'PASS'}: public foundation; {len(failures)} issue(s). Runtime application not tested.")
    sys.exit(bool(failures))
