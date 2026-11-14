from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.request import Request,urlopen
from palladio.__main__ import handler_for
from palladio.store import Library
from palladio.scene import ValidationError
from palladio.transfer import snapshot,canonical
from test_local_agent import running_server
from test_references import png

class TransferTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup);self.path=Path(temp.name)
        self.library=Library(self.path/'source.sqlite3');self.p=self.library.create('Portable','meadow')
        self.p=self.library.commit(self.p['id'],1,[{'action':'assembly','assembly':{'kind':'garage'}},
            {'action':'terrain_layer','layer':{'mode':'raise','center':[0,0],'radius_m':10,'amount_m':1}},
            {'action':'reference_add','reference':{'name':'Sketch','image':png()}}])
    def test_roundtrip_new_library_preserves_group_history_and_original_ground(self):
        packet=snapshot(self.p);target=Library(self.path/'other.sqlite3')
        saved=target.import_snapshot(packet,'Imported alternative')
        self.assertNotEqual(saved['id'],self.p['id']);self.assertEqual(saved['revision'],1)
        self.assertEqual(saved['scene'],self.p['scene']);self.assertEqual(saved['baseline'],self.p['baseline'])
        group=saved['scene']['assemblies'][0]
        resized=target.commit(saved['id'],1,[{'action':'assembly_update','id':group['id'],'assembly':{'width':8}}])
        self.assertEqual(resized['scene']['assemblies'][0]['members'],group['members'])
        self.assertEqual(target.commit(saved['id'],2,restore=1)['scene'],saved['scene'])
        self.assertEqual(self.library.get(self.p['id']),self.p)
    def test_corrupt_and_semantically_invalid_packets_never_insert(self):
        original=snapshot(self.p)
        mutations=[lambda p:p['payload']['scene']['elements'][0]['size'].__setitem__(0,-1),
                   lambda p:p['payload']['scene']['assemblies'][0]['members'].__setitem__('wrong','missing'),
                   lambda p:p['payload']['scene']['terrain']['heights'].__setitem__(0,123),
                   lambda p:p['payload']['scene']['references'][0].__setitem__('data','bad')]
        corrupted=deepcopy(original);corrupted['payload']['name']='Tampered'
        with self.assertRaises(ValidationError):self.library.import_snapshot(corrupted)
        for mutate in mutations:
            packet=deepcopy(original);mutate(packet);packet['sha256']=hashlib.sha256(canonical(packet['payload'])).hexdigest()
            with self.assertRaises(ValidationError): self.library.import_snapshot(packet)
        self.assertEqual(len(self.library.list()),1)
    def test_old_ungrouped_property_and_embedded_mesh_roundtrip(self):
        old=self.library.create('Old','wooded hillside',True)
        self.assertEqual(self.library.import_snapshot(snapshot(old))['scene'],old['scene'])
        from palladio.assets import import_obj
        size,mesh=import_obj('v 0 0 0\nv 1 0 0\nv 0 1 1\nf 1 2 3','m')
        added=self.library.commit(old['id'],1,[{'action':'add','element':{'name':'Mesh','kind':'block','material':'oak','position':[1,0,0],'size':size,'mesh':mesh}}])
        self.assertEqual(self.library.import_snapshot(snapshot(added))['scene'],added['scene'])
    def test_http_download_and_import(self):
        with running_server(handler_for(self.library)) as server:
            root=f'http://127.0.0.1:{server.server_port}'
            with urlopen(root+'/api/properties/'+self.p['id']+'/export') as response: packet=json.load(response)
            request=Request(root+'/api/properties/import',data=json.dumps({'packet':packet}).encode(),headers={'Content-Type':'application/json'})
            with urlopen(request) as response: imported=json.load(response)
            self.assertEqual(imported['scene'],self.p['scene']);self.assertNotEqual(imported['id'],self.p['id'])
