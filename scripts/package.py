"""Bundle the already-built web application into a portable Python wheel."""
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'apps/web/dist'
target = ROOT / 'src/arker/web'
if not (source / 'index.html').is_file():
    raise SystemExit('Build apps/web before packaging.')
if target.is_symlink():
    raise SystemExit('Generated web directory must not be a symlink.')
shutil.copytree(source, target, dirs_exist_ok=True)
subprocess.run([sys.executable, '-m', 'build', '--wheel'], cwd=ROOT, check=True)
wheel = sorted((ROOT / 'dist').glob('*.whl'), key=lambda path: path.stat().st_mtime)[-1]
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    for required in ('arker/web/index.html', 'arker/cli.py', 'arker/worker.py', 'arker/assets/fonts/BarlowSemiCondensed-Bold.ttf', 'arker/assets/fonts/OFL.txt'):
        if required not in names:
            raise SystemExit('Wheel is missing ' + required)
    if any(name.endswith(('.sqlite3', '.db', '.log', '.key')) or 'Credential/' in name for name in names):
        raise SystemExit('Wheel contains private runtime files.')
print('PASS: wheel contains UI, API, worker and licensed font; no runtime database or credentials.')
