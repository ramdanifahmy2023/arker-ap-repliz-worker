"""The same offline application checks run locally and in the OS CI matrix."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run(args, cwd=ROOT):
    print('Check:', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--media', action='store_true', help='Run actual FFmpeg synthetic preview; no provider requests.')
    args = parser.parse_args()
    artifact = ROOT / '.artifacts'
    artifact.mkdir(exist_ok=True)
    run([sys.executable, 'scripts/validate.py'])
    run([sys.executable, 'scripts/render_visuals.py', '--check'])
    run([sys.executable, '-m', 'pytest', '-q', '--junitxml=.artifacts/backend-tests.xml'])
    npm = shutil.which('npm')
    if not npm:
        raise SystemExit('Node.js 22.12+ and npm are required.')
    for script in ('format:check', 'test', 'build'):
        run([npm, 'run', script], ROOT / 'apps/web')
    if args.media:
        run([sys.executable, '-m', 'arker', 'preview', '--output', artifact / ('media-' + uuid.uuid4().hex)])
    print('PASS: public source, backend, frontend' + (', actual synthetic media' if args.media else '') + '. Provider publishing was not tested.')


if __name__ == '__main__':
    main()
