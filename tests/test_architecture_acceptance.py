from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from palladio.acceptance import create_fixture
from palladio.store import Library
from palladio.scene import ValidationError
from palladio.jobs import DesignJobs
from palladio.local_agent import AgentService, OllamaPlanner, validated_plan
from palladio.transfer import snapshot
from palladio.unreal import unreal_view
from palladio.foundations import pad_ground
from palladio.placement import active_terrain
from test_local_agent import ModelServer, running_server


class ArchitectureAcceptanceTests(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup);self.path=Path(tmp.name)/'acceptance.sqlite3'
        self.manifest=create_fixture(self.path);self.library=Library(self.path);self.project=self.library.get(self.manifest['property_id'])
        self.groups={g['spec']['kind']:g for g in self.project['scene']['assemblies']}
    def test_fixture_preserves_transfer_native_views_and_solid_flags(self):
        p=self.project;self.assertEqual(len(p['scene']['views']),5);self.assertGreater(len(p['scene']['elements']),90)
        native=unreal_view(p);self.assertEqual(len(native['views']),5)
        self.assertEqual(sum(e.get('collision') is False for e in native['elements']),2)
        support=self.groups['foundation']['spec'];host=self.groups['dwelling']['spec']
        self.assertAlmostEqual(support['position'][1]+support['height'],host['position'][1])
        for offset,ground in zip(support['support_offsets'],pad_ground(support,active_terrain(p['baseline'],p['scene']))):
            self.assertAlmostEqual(support['position'][1]+offset,ground)
        transferred=self.library.import_snapshot(snapshot(p));self.assertEqual(transferred['scene'],p['scene'])
        self.assertEqual(unreal_view(transferred)['views'],native['views'])
        jobs=DesignJobs(self.library);self.assertEqual(jobs.list(p['id'])[0]['status'],'ready');self.assertEqual(jobs.list(transferred['id']),[])
    def test_existing_library_is_never_changed(self):
        before=self.path.read_bytes()
        with self.assertRaises(ValidationError):create_fixture(self.path)
        self.assertEqual(self.path.read_bytes(),before)
        bad=self.path.parent/'sentinel';bad.write_bytes(b'do not change')
        with self.assertRaises(ValidationError):create_fixture(bad)
        self.assertEqual(bad.read_bytes(),b'do not change')
    def test_agent_opening_water_and_refit_are_atomic_context_scoped_previews(self):
        p=self.project;before=deepcopy(p);wall=self.groups['wall_run'];pool=self.groups['pool'];foundation=self.groups['foundation']
        opening={**wall['spec']['openings'][1],'width':2.4}
        commands=[{'action':'opening_set','id':wall['id'],'opening':opening},
                  {'action':'assembly_update','id':pool['id'],'assembly':{'water_level':2}},
                  {'action':'foundation_refit','id':foundation['id'],'foundation':{}}]
        ids={g['id'] for g in self.groups.values()}
        plan=validated_plan(p,{'summary':'Widen the keyed window, lower the pool and refit supports.','commands':commands},set(),ids)
        self.assertEqual(self.library.get(p['id']),before)
        updated={g['id']:g for g in plan['scene']['assemblies']}
        self.assertEqual(updated[wall['id']]['members'],wall['members']);self.assertEqual(updated[pool['id']]['spec']['water_level'],2)
        for allowed in [set(),ids-{wall['id']}]:
            with self.assertRaises(ValidationError):validated_plan(p,{'summary':'Out of scope','commands':commands},set(),allowed)
        invalid=deepcopy(commands);invalid[0]['opening']['center']=100
        with self.assertRaises(ValidationError):validated_plan(p,{'summary':'Invalid opening','commands':invalid},set(),ids)
        self.assertEqual(self.library.get(p['id']),before)
    def test_agent_can_fit_and_create_new_architecture_without_claiming_excavation(self):
        host=self.groups['dwelling'];commands=[{'action':'foundation_fit','id':host['id'],'foundation':{'columns_x':2,'columns_z':2}},
            {'action':'assembly','assembly':{'kind':'wall_run','position':[25,0,0],'openings':[{'key':'entry','kind':'door'}]}},
            {'action':'assembly','assembly':{'kind':'pond','position':[25,0,10],'water_level':1}}]
        plan=validated_plan(self.project,{'summary':'New supports, wall and pond.','commands':commands},set(),{host['id']})
        self.assertEqual(len(plan['scene']['assemblies']),len(self.project['scene']['assemblies'])+3)
        self.assertEqual(plan['scene']['terrain'],self.project['scene']['terrain'])
        with self.assertRaises(ValidationError):validated_plan(self.project,{'summary':'Bad support','commands':[
            {'action':'foundation_fit','id':host['id'],'foundation':{'support_offsets':[99]}}]},set(),{host['id']})
    def test_ollama_protocol_receives_keyed_opening_and_new_tools(self):
        wall=self.groups['wall_run'];opening={**wall['spec']['openings'][1],'width':2.4};fixture=ModelServer()
        fixture.plan={'summary':'Widen only the selected wall window.','commands':[{'action':'opening_set','id':wall['id'],'opening':opening}]}
        with running_server(fixture.handler) as server:
            result=AgentService(OllamaPlanner(server.server_port)).preview(self.project,'Widen the view window to 2.4 m',
                next(iter(wall['members'].values())),provider='ollama',model='small:latest',revision=self.project['revision'],query='Opening review wall')
        self.assertEqual(result['commands'],fixture.plan['commands'])
        body=next(body for path,body in fixture.calls if path=='/api/chat')
        actions=[item['properties']['action']['const'] for item in body['format']['properties']['commands']['items']['oneOf']]
        self.assertIn('opening_set',actions);self.assertIn('foundation_refit',actions)
        self.assertEqual(self.library.get(self.project['id']),self.project)
