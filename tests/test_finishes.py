import json
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import subprocess
import unittest
from palladio.store import Library
from palladio.scene import ValidationError,element
from palladio.transfer import snapshot
from palladio.geometry import surface_triangles,PATTERNS
from palladio.unreal import unreal_view
from palladio.assets import AssetStore

class FinishTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.library=Library(Path(temp.name)/'properties.sqlite3');self.p=self.library.create('Finishes','meadow')
        self.edit({'action':'assembly','assembly':{'kind':'room'}})
        self.member=self.p['scene']['elements'][0]['id']
    def edit(self,*commands):
        self.p=self.library.commit(self.p['id'],self.p['revision'],list(commands));return self.p
    def test_preset_copies_to_all_members_and_survives_regeneration_transfer(self):
        self.edit({'action':'finish_apply','finish_id':'builtin:clay-brick','ids':[self.member]})
        self.edit({'action':'finish_save','source_id':self.member,'name':'House brick'})
        preset=self.p['scene']['finishes'][0];group=self.p['scene']['assemblies'][0]
        self.edit({'action':'finish_apply','finish_id':preset['id'],'ids':[self.member],'scope':'assembly'},
                  {'action':'assembly_update','id':group['id'],'assembly':{'width':9}})
        self.assertTrue(all(e['finish']==preset['finish'] for e in self.p['scene']['elements']))
        self.assertEqual(self.library.import_snapshot(snapshot(self.p))['scene'],self.p['scene'])
        revision=self.p['revision'];self.edit({'action':'finish_remove','finish_id':preset['id']})
        self.assertFalse(self.p['scene']['finishes']);self.assertTrue(all(e['finish']==preset['finish'] for e in self.p['scene']['elements']))
        self.p=self.library.commit(self.p['id'],self.p['revision'],restore=revision)
        self.assertEqual(self.p['scene']['finishes'],[preset])
    def test_invalid_presets_roll_back_and_native_capture_is_bounded(self):
        before=self.p
        with self.assertRaises(ValidationError):self.edit({'action':'finish_save','source_id':self.member,'name':'Repeated'},{'action':'finish_save','source_id':self.member,'name':'repeated'})
        self.assertEqual(self.library.get(self.p['id']),before)
        self.edit({'action':'add','element':{'name':'Tile','kind':'block','material':'stone','size':[2,.1,2],'position':[0,0,0],'finish':{'pattern':'tile','color':'#dddddd'}}})
        item=self.p['scene']['elements'][-1];native=unreal_view(self.p)['elements'][-1]
        self.assertEqual(sum(len(s['triangles'])//3 for s in native['mesh_sections']),3072)
        asset=AssetStore(self.library.path.parent/'assets').capture(self.p,item['id'],'Tiled slab')
        self.assertLess(len(asset['mesh']['vertices']),8192);self.assertEqual(len(asset['mesh']['triangles']),9216)
    @unittest.skipUnless(shutil.which('node'),'Node is required for renderer parity')
    def test_browser_native_pattern_colors_match_on_every_face(self):
        for pattern in PATTERNS:
            item=element({'name':'Surface','kind':'block','material':'stone','position':[0,0,0],'size':[2,1.5,3],
                          'finish':{'color':'#a76e32','accent_color':'#ccbb99','pattern':pattern,'scale_m':.43,'rotation':37}})
            js="const fs=require('fs'),vm=require('vm');vm.runInThisContext(fs.readFileSync('palladio/web/mesh.js','utf8').replace('export function','function'));const e=JSON.parse(process.argv[1]);console.log(JSON.stringify(surfaceTriangles(e,'#ffffff').map(t=>'#'+t.color.map(v=>Math.round(v*255).toString(16).padStart(2,'0')).join(''))));"
            actual=json.loads(subprocess.check_output(['node','-e',js,json.dumps(item)],text=True))
            self.assertEqual(actual,[c for _,c in surface_triangles(item)],pattern)
