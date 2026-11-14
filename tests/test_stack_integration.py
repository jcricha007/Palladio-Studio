from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.error import HTTPError
from palladio.store import Library
from palladio.transfer import snapshot
from palladio.unreal import unreal_view
from palladio.presentation import scene_obj
from palladio.jobs import DesignJobs
from palladio.__main__ import handler_for
from test_local_agent import running_server
import test_unreal

class StackIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup);self.library=Library(Path(temp.name)/'p.sqlite3');self.p=self.library.create('Integrated house','meadow')
    def edit(self,*commands):self.p=self.library.commit(self.p['id'],self.p['revision'],list(commands));return self.p
    def test_rooms_roof_plants_layout_finish_and_views_survive_transfer(self):
        self.edit({'action':'assembly','assembly':{'kind':'dwelling','width':12,'depth':8,'rooms_x':3,'rooms_z':2}})
        house=self.p['scene']['assemblies'][0];member=next(iter(house['members'].values()))
        self.edit({'action':'roof_fit','id':house['id'],'roof':{'kind':'gable_roof','height':2,'overhang':.5}},
                  {'action':'planting','planting':{'kind':'pine','center':[20,15],'count':3,'seed':8,'radius_m':3}})
        roof=self.p['scene']['assemblies'][1];roof_part=next(iter(roof['members'].values()))
        self.edit({'action':'layout','layout':{'ids':[member,roof_part],'operation':'move','offset':[3,0,2]}},
                  {'action':'finish_apply','finish_id':'builtin:light-tile','scope':'part','ids':[member]},
                  {'action':'finish_save','source_id':member,'name':'Tile'},
                  {'action':'view_save','name':'Arrival','camera':{'target':[3,2,2],'pitch':.6,'azimuth':.7,'distance':40}})
        imported=self.library.import_snapshot(snapshot(self.p));self.assertEqual(imported['scene'],self.p['scene'])
        self.assertEqual(len(unreal_view(imported)['elements']),len(imported['scene']['elements']));self.assertGreater(scene_obj(imported,False)['triangles'],100)
        self.assertEqual(imported['scene']['assemblies'][0]['members'],house['members']);self.assertEqual(DesignJobs(self.library).list(imported['id']),[])
    def test_invalid_tool_action_types_return_400_and_preserve_revision(self):
        with running_server(handler_for(self.library)) as server:
            read=test_unreal.UnrealBridgeTest.read;url=f'http://127.0.0.1:{server.server_port}/api/properties/{self.p["id"]}'
            for command in [{'action':[]},{'action':{}},{'action':'planting','planting':{'kind':[]}}]:
                with self.subTest(command=command),self.assertRaises(HTTPError) as bad:read(url+'/edit',{'revision':1,'commands':[{'action':'environment','environment':{'hour':7}},command]})
                self.assertEqual(bad.exception.code,400)
            job=read(url+'/jobs',{'title':'Invalid action','brief':'Test','steps':['add a room']})
            with self.assertRaises(HTTPError) as bad:read(url+'/jobs/'+job['id'],{'version':1,'action':[]})
            self.assertEqual(bad.exception.code,400);self.assertEqual(self.library.get(self.p['id']),self.p)
    def test_snapshot_excludes_jobs_and_duplicate_does_not_resume_original_job(self):
        jobs=DesignJobs(self.library);job=jobs.create(self.p['id'],{'title':'Original','brief':'Preserved','steps':['add a room']})
        jobs.change(self.p['id'],job['id'],{'action':'start','version':1})
        for alternative in [self.library.duplicate(self.p['id'],'Alternative'),self.library.import_snapshot(snapshot(self.p))]:self.assertEqual(jobs.list(alternative['id']),[])
        self.assertEqual(jobs.get(self.p['id'],job['id'])['status'],'active')
