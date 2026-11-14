from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch
import unittest
from urllib.error import HTTPError
from palladio.store import Library,RevisionConflict
from palladio.jobs import DesignJobs
from palladio.local_agent import AgentService,OllamaPlanner,AgentError,validated_plan
from palladio.scene import ValidationError
from palladio.__main__ import handler_for
from test_local_agent import ModelServer,running_server
import test_unreal

class JobAgentTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup);self.library=Library(Path(temp.name)/'p.sqlite3');self.p=self.library.create('Jobs','meadow')
        self.jobs=DesignJobs(self.library);self.job=self.jobs.create(self.p['id'],{'title':'House','brief':'A calm hillside home','steps':['set weather to fog','add a room']})
        self.job=self.jobs.change(self.p['id'],self.job['id'],{'version':1,'action':'start'})
    def proposal(self,agent=None,**kwargs):
        result=self.jobs.propose(self.p['id'],self.job['id'],{'version':self.job['version'],'revision':self.p['revision'],**kwargs},agent or AgentService());self.job=result['job'];return result
    def test_persistent_review_apply_uses_one_transaction_and_never_autoruns_next_step(self):
        result=self.proposal();self.assertEqual(self.library.get(self.p['id']),self.p);self.assertEqual(self.job['steps'][0]['status'],'pending')
        jobs=DesignJobs(Library(self.library.path));review=jobs.review(self.p['id'],self.job['id'],{'version':self.job['version'],'revision':1})
        self.assertEqual(review['plan']['commands'],result['plan']['commands'])
        applied=jobs.apply(self.p['id'],self.job['id'],{'version':self.job['version'],'revision':1});self.assertEqual(applied['project']['revision'],2)
        self.assertEqual(applied['job']['steps'][0]['revision'],2);self.assertEqual(applied['job']['steps'][1]['status'],'pending');self.assertNotIn('proposal',applied['job'])
        self.assertEqual(applied['project']['scene']['elements'],[])
        with self.assertRaises(RevisionConflict):jobs.apply(self.p['id'],self.job['id'],{'version':self.job['version'],'revision':1})
    def test_apply_rolls_back_scene_if_checkpoint_save_fails(self):
        self.proposal();before=self.job
        with patch.object(self.jobs,'save',side_effect=RuntimeError('disk failure')):
            with self.assertRaises(RuntimeError):self.jobs.apply(self.p['id'],self.job['id'],{'version':self.job['version'],'revision':1})
        self.assertEqual(self.library.get(self.p['id']),self.p);self.assertEqual(self.jobs.get(self.p['id'],self.job['id']),before)
    def test_manual_edits_invalidate_proposal_until_explicit_replanning(self):
        self.proposal();self.library.commit(self.p['id'],1,[{'action':'environment','environment':{'hour':10}}])
        with self.assertRaises(RevisionConflict):self.jobs.apply(self.p['id'],self.job['id'],{'version':self.job['version'],'revision':1})
        with self.assertRaises(RevisionConflict):self.jobs.review(self.p['id'],self.job['id'],{'version':self.job['version'],'revision':2})
        self.p=self.library.get(self.p['id']);self.proposal();self.assertEqual(self.job['proposal']['revision'],2)
        discarded=self.jobs.discard(self.p['id'],self.job['id'],{'version':self.job['version']});self.assertNotIn('proposal',discarded)
    def test_late_model_response_cannot_revive_paused_job(self):
        fixture=ModelServer();fixture.release=Event()
        with running_server(fixture.handler) as server,ThreadPoolExecutor(1) as pool:
            future=pool.submit(self.proposal,AgentService(OllamaPlanner(server.server_port)),provider='ollama',model='small:latest')
            self.assertTrue(fixture.started.wait(3))
            paused=self.jobs.change(self.p['id'],self.job['id'],{'action':'pause','version':self.job['version']});fixture.release.set()
            with self.assertRaises(RevisionConflict):future.result(3)
            self.assertEqual(self.jobs.get(self.p['id'],self.job['id']),paused);self.assertEqual(self.library.get(self.p['id']),self.p)
    def test_model_outline_is_unsaved_and_step_context_has_brief_and_progress(self):
        fixture=ModelServer();fixture.plan={'title':'Retreat','steps':['Add a room','Add a gable roof']}
        with running_server(fixture.handler) as server:
            agent=AgentService(OllamaPlanner(server.server_port));outline=agent.outline('A quiet retreat','small:latest')
            self.assertEqual(outline,fixture.plan);self.assertEqual(len(self.jobs.list(self.p['id'])),1)
            fixture.plan={'summary':'Please identify the room.','commands':[]};result=self.proposal(agent,provider='ollama',model='small:latest')
            self.assertNotIn('proposal',result['job']);self.assertEqual(result['job']['version'],2)
            import json
            request=json.loads([body for path,body in fixture.calls if path=='/api/chat'][-1]['messages'][1]['content'])
            self.assertEqual(request['scene_context']['design_job']['brief'],self.job['brief']);self.assertEqual(request['request'],'set weather to fog')
            fixture.plan={'title':'Bad','steps':[]}
            with self.assertRaises(ValidationError):agent.outline('Bad outline','small:latest')
            with self.assertRaises(ValidationError):agent.outline('x'*16001,'small:latest')
    def test_new_roof_and_room_parameters_validate_with_shared_agent_tools(self):
        plan=validated_plan(self.p,{'summary':'Rooms and roof','commands':[{'action':'assembly','assembly':{'kind':'dwelling','width':12,'depth':8,'rooms_x':3,'rooms_z':2}}, {'action':'assembly','assembly':{'kind':'hip_roof','overhang':.5}}]},set())
        self.assertEqual(plan['scene']['assemblies'][0]['spec']['rooms_x'],3);self.assertEqual(plan['scene']['assemblies'][1]['spec']['overhang'],.5)
    def test_http_proposal_review_and_double_apply_conflict(self):
        with running_server(handler_for(self.library)) as server:
            read=test_unreal.UnrealBridgeTest.read;url=f'http://127.0.0.1:{server.server_port}/api/properties/{self.p["id"]}/jobs/{self.job["id"]}'
            result=read(url,{'action':'propose','version':2,'revision':1,'provider':'rules'});version=result['job']['version']
            reviewed=read(url,{'action':'review','version':version,'revision':1});self.assertEqual(reviewed['plan']['job']['version'],version)
            saved=read(url,{'action':'apply','version':version,'revision':1});self.assertEqual(saved['project']['revision'],2)
            with self.assertRaises(HTTPError) as stale:read(url,{'action':'apply','version':version,'revision':1})
            self.assertEqual(stale.exception.code,409)
