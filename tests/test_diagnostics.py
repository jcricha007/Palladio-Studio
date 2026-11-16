from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import subprocess
import sys
import unittest
from palladio.diagnostics import backup_library,library_info
from palladio.store import Library
from palladio.jobs import DesignJobs
from palladio.__main__ import handler_for,STATIC
from test_local_agent import running_server
import test_unreal

class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup);self.path=Path(temp.name)/'library with spaces.sqlite3'
    def test_missing_library_is_read_only_and_cli_preflight_does_not_create_it(self):
        self.assertFalse(library_info(self.path)['exists'])
        result=json.loads(subprocess.check_output([sys.executable,'-m','palladio.diagnostics','--library',str(self.path),'--backup-before-upgrade'],text=True))
        self.assertIsNone(result['backup']);self.assertFalse(self.path.exists())
    def test_backup_snapshots_properties_and_jobs_and_retains_schema_one_before_migration(self):
        library=Library(self.path);project=library.create('Backup','meadow');job=DesignJobs(library).create(project['id'],{'title':'Saved','brief':'Retained intent','steps':['add a room']})
        backup=backup_library(self.path);library.commit(project['id'],1,[{'action':'environment','environment':{'hour':8}}])
        copied=Library(backup);self.assertEqual(copied.get(project['id']),project);self.assertEqual(DesignJobs(copied).get(project['id'],job['id']),job)
        with sqlite3.connect(self.path) as db:db.executescript('DROP TABLE design_jobs;PRAGMA user_version=1;')
        result=json.loads(subprocess.check_output([sys.executable,'-m','palladio.diagnostics','--library',str(self.path),'--backup-before-upgrade'],text=True))
        self.assertEqual(library_info(result['backup'])['schema'],1);self.assertEqual(library_info(self.path)['schema'],1)
        migrated=Library(self.path);self.assertEqual(migrated.get(project['id'])['revision'],2);self.assertEqual(library_info(result['backup'])['schema'],1)
    def test_health_identifies_checkout_library_and_serves_all_registered_modules(self):
        library=Library(self.path)
        with running_server(handler_for(library)) as server:
            root=f'http://127.0.0.1:{server.server_port}';result=test_unreal.UnrealBridgeTest.read(root+'/api/health')
            self.assertEqual(result['app'],'Palladio Studio');self.assertEqual(result['api_version'],2);self.assertEqual(result['library_path'],str(self.path));self.assertIn('agent-job-review',result['features'])
            from urllib.request import urlopen
            for path in STATIC:
                with urlopen(root+path) as response:self.assertEqual(response.status,200);self.assertGreater(len(response.read()),0)
