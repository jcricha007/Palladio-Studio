from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from urllib.error import HTTPError
from uuid import uuid4
from palladio.store import Library, RevisionConflict
from palladio.jobs import DesignJobs
from palladio.local_agent import AgentService, OllamaPlanner
from palladio.__main__ import handler_for
from test_local_agent import ModelServer, running_server
import test_unreal


class PlanningStopTests(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.library=Library(Path(tmp.name)/'jobs.sqlite3');self.project=self.library.create('Stop test','meadow')
        self.jobs=DesignJobs(self.library)
        self.job=self.jobs.create(self.project['id'],{'title':'Plan','brief':'A foggy scene','steps':['set weather to fog','set hour to 12']})
        self.job=self.jobs.change(self.project['id'],self.job['id'],{'action':'start','version':1})
        self.data={'version':2,'revision':1,'request_id':str(uuid4()),'step_id':self.job['steps'][0]['id']}
    def stop(self,data=None):return self.jobs.stop_planning(self.project['id'],self.job['id'],data or self.data)
    def propose(self,agent=None,**values):return self.jobs.propose(self.project['id'],self.job['id'],{**self.data,**values},agent or AgentService())
    def test_stop_before_start_blocks_delayed_request(self):
        paused=self.stop();self.assertEqual(paused['status'],'paused')
        with self.assertRaises(RevisionConflict):self.propose()
        self.assertEqual(self.library.get(self.project['id']),self.project)
    def test_stop_while_inference_runs_rejects_late_proposal(self):
        fixture=ModelServer();fixture.release=Event()
        with running_server(fixture.handler) as server,ThreadPoolExecutor(1) as pool:
            future=pool.submit(self.propose,AgentService(OllamaPlanner(server.server_port)),provider='ollama',model='small:latest')
            try:
                self.assertTrue(fixture.started.wait(3));paused=self.stop()
            finally:fixture.release.set()
            with self.assertRaises(RevisionConflict):future.result(3)
            self.assertEqual(self.jobs.get(self.project['id'],self.job['id']),paused)
            self.assertEqual(self.library.get(self.project['id']),self.project)
    def test_stop_after_response_discards_only_that_request(self):
        result=self.propose();self.assertEqual(result['job']['version'],3)
        with self.assertRaises(RevisionConflict):self.stop({**self.data,'request_id':str(uuid4())})
        paused=self.stop();self.assertEqual(paused['status'],'paused');self.assertNotIn('proposal',paused)
        resumed=self.jobs.change(self.project['id'],self.job['id'],{'action':'resume','version':paused['version']})
        with self.assertRaises(RevisionConflict):self.stop()
        self.assertEqual(self.jobs.get(self.project['id'],self.job['id']),resumed)
    def test_stop_cannot_pause_next_step_after_apply(self):
        result=self.propose();applied=self.jobs.apply(self.project['id'],self.job['id'],{'version':result['job']['version'],'revision':1})
        with self.assertRaises(RevisionConflict):self.stop()
        self.assertEqual(self.jobs.get(self.project['id'],self.job['id']),applied['job'])
        self.assertEqual(applied['job']['steps'][1]['status'],'pending')
    def test_http_stop_and_clarification_race(self):
        fixture=ModelServer();fixture.plan={'summary':'Which view?','commands':[]}
        with running_server(fixture.handler) as runtime,running_server(handler_for(self.library,AgentService(OllamaPlanner(runtime.server_port)))) as server:
            url=f'http://127.0.0.1:{server.server_port}/api/properties/{self.project["id"]}/jobs/{self.job["id"]}'
            read=test_unreal.UnrealBridgeTest.read
            result=read(url,{**self.data,'action':'propose','provider':'ollama','model':'small:latest'})
            self.assertNotIn('proposal',result['job']);self.assertEqual(result['job']['version'],3)
            paused=read(url,{**self.data,'action':'stop_planning'});self.assertEqual(paused['status'],'paused')
            with self.assertRaises(HTTPError) as old:read(url,{**self.data,'action':'stop_planning'})
            self.assertEqual(old.exception.code,409);self.assertEqual(self.library.get(self.project['id']),self.project)
