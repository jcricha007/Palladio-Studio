from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from urllib.error import HTTPError
from palladio.store import Library,RevisionConflict,MissingProject
from palladio.scene import ValidationError
from palladio.jobs import DesignJobs
from palladio.__main__ import handler_for
from test_local_agent import running_server
import test_unreal

class JobTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup);self.path=Path(temp.name)/'p.sqlite3'
        self.library=Library(self.path);self.p=self.library.create('House','meadow');self.jobs=DesignJobs(self.library)
        self.job=self.jobs.create(self.p['id'],{'title':'Cabin','brief':'A quiet place','steps':['Build a room','Finish its walls']})
    def change(self,action,**data):
        self.job=self.jobs.change(self.p['id'],self.job['id'],{'action':action,'version':self.job['version'],**data});return self.job
    def test_lifecycle_reopen_checkpoints_and_no_scene_edits(self):
        self.change('start');self.change('pause')
        with self.assertRaises(ValidationError):self.change('checkpoint',revision=1,note='Not yet')
        self.assertEqual(DesignJobs(Library(self.path)).get(self.p['id'],self.job['id']),self.job)
        self.change('resume');self.change('checkpoint',revision=1,note='Existing room reviewed')
        self.assertEqual(self.job['steps'][0]['revision'],1);self.assertEqual(self.job['status'],'active')
        self.change('checkpoint',revision=1,note='Finish reviewed');self.assertEqual(self.job['status'],'completed')
        with self.assertRaises(ValidationError):self.change('resume')
        self.assertEqual(self.library.get(self.p['id']),self.p)
    def test_two_sessions_cannot_advance_same_job_and_stale_scene_is_rejected(self):
        def start(_):
            try:return self.jobs.change(self.p['id'],self.job['id'],{'action':'start','version':1})['status']
            except RevisionConflict:return 'conflict'
        with ThreadPoolExecutor(2) as pool:self.assertCountEqual(pool.map(start,range(2)),['active','conflict'])
        self.job=self.jobs.get(self.p['id'],self.job['id'])
        self.library.commit(self.p['id'],1,[{'action':'environment','environment':{'hour':12}}])
        with self.assertRaises(RevisionConflict):self.change('checkpoint',revision=1,note='Old view')
        self.assertEqual(self.jobs.get(self.p['id'],self.job['id']),self.job)
    def test_outline_limits_revision_and_property_isolation(self):
        with self.assertRaises(ValidationError):self.jobs.create(self.p['id'],{'title':'Bad','brief':'text','steps':['']})
        with self.assertRaises(ValidationError):self.jobs.create(self.p['id'],{'title':'Bad','brief':'text','steps':['x']*33})
        self.change('revise',title='Revised',brief='Updated intent',steps=['Build a pavilion']);self.assertEqual(len(self.job['steps']),1)
        other=self.library.create('Other','meadow')
        with self.assertRaises(MissingProject):self.jobs.get(other['id'],self.job['id'])
        self.change('start')
        with self.assertRaises(ValidationError):self.change('revise',title='x',brief='x',steps=['x'])
        self.change('cancel');self.assertEqual(self.job['status'],'cancelled')
    def test_schema_one_migrates_without_changing_property_or_history(self):
        with sqlite3.connect(self.path) as db:db.executescript('DROP TABLE design_jobs;PRAGMA user_version=1;')
        reopened=Library(self.path);self.assertEqual(reopened.get(self.p['id']),self.p);self.assertEqual(DesignJobs(reopened).list(self.p['id']),[])
        with sqlite3.connect(self.path) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],2)
    def test_http_job_lifecycle_and_stale_conflict(self):
        with running_server(handler_for(self.library)) as server:
            url=f'http://127.0.0.1:{server.server_port}/api/properties/{self.p["id"]}/jobs';read=test_unreal.UnrealBridgeTest.read
            self.assertEqual(len(read(url)),1)
            job=read(url,{'title':'HTTP','brief':'Persistent','steps':['Place a wall']});self.assertEqual(job['version'],1)
            active=read(url+'/'+job['id'],{'version':1,'action':'start'});self.assertEqual(active['status'],'active')
            with self.assertRaises(HTTPError) as stale:read(url+'/'+job['id'],{'version':1,'action':'start'})
            self.assertEqual(stale.exception.code,409)
