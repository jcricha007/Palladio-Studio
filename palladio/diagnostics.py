"""Read-only library diagnostics and SQLite-consistent backups before upgrades."""
import argparse
from contextlib import closing
from datetime import datetime,timezone
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
from uuid import uuid4

SCHEMA_VERSION=2
FEATURES=['property-transfer','layout-tools','roof-systems','connected-rooms','planted-landscape',
          'finish-palettes','presentation-views','design-jobs','agent-job-review']
ROOT=Path(__file__).resolve().parents[1]


def build_revision():
    try:
        result=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,timeout=2)
        return result.stdout.strip() if result.returncode==0 else 'unknown'
    except (OSError,subprocess.TimeoutExpired):return 'unknown'


def library_info(path):
    path=Path(path).resolve();result={'path':str(path),'exists':path.exists(),'schema':0,'properties':0,'jobs':0}
    if not path.exists():return result
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as connection:
        result['schema']=connection.execute('PRAGMA user_version').fetchone()[0]
        result['integrity']=connection.execute('PRAGMA quick_check').fetchone()[0]
        tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'properties' in tables:result['properties']=connection.execute('SELECT COUNT(*) FROM properties').fetchone()[0]
        if 'design_jobs' in tables:result['jobs']=connection.execute('SELECT COUNT(*) FROM design_jobs').fetchone()[0]
    return result


def _snapshot_sqlite(path, target):
    # backup() snapshots SQLite coherently even when the source uses a journal/WAL.
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source, \
            closing(sqlite3.connect(target)) as destination:
        source.backup(destination)


def backup_library(path):
    path=Path(path).resolve()
    if not path.is_file():raise FileNotFoundError('No saved library exists to back up.')
    directory=path.parent/'backups';directory.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=directory/(path.stem+'-'+stamp+'-'+uuid4().hex[:8]+'.sqlite3')
    # Only complete, checked copies appear as SQLite backups. Staging on the
    # same filesystem keeps the final rename atomic; close SQLite first on Windows.
    with TemporaryDirectory(prefix='.palladio-backup-', dir=directory) as folder:
        staged = Path(folder) / 'library.sqlite3'
        staged.touch(mode=0o600, exist_ok=False)
        _snapshot_sqlite(path, staged)
        with closing(sqlite3.connect(staged.as_uri() + '?mode=ro', uri=True)) as copy:
            if copy.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise sqlite3.DatabaseError('Backup SQLite integrity check failed.')
        staged.replace(target)
    return target


def health(library):
    return {'app':'Palladio Studio','api_version':2,'database_schema':SCHEMA_VERSION,'build':build_revision(),
            'python':platform.python_version(),'source_root':str(ROOT),'library_path':str(library.path),'features':FEATURES}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,default=ROOT/'.palladio/properties.sqlite3')
    parser.add_argument('--backup',action='store_true');parser.add_argument('--backup-before-upgrade',action='store_true')
    args=parser.parse_args();info=library_info(args.library)
    if info['schema']>SCHEMA_VERSION:parser.error('This library was written by a newer Palladio build. Update the checkout.')
    if info.get('integrity','ok')!='ok':parser.error('SQLite integrity check failed. Keep the database and restore from a known backup.')
    backup=None
    if args.backup or (args.backup_before_upgrade and info['exists'] and info['schema']<SCHEMA_VERSION):backup=str(backup_library(args.library))
    print(json.dumps({'app':'Palladio Studio','build':build_revision(),'python':platform.python_version(),'library':info,'backup':backup},indent=2))


if __name__=='__main__':main()
