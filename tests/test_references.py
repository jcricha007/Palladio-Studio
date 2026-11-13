import base64
import copy
import json
import struct
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from urllib.request import Request,urlopen

from palladio.__main__ import handler_for
from palladio.assets import import_obj
from palladio.commands import preview_commands
from palladio.local_agent import AgentError,AgentService,OllamaPlanner,scene_context,validated_plan
from palladio.references import image,selected_references
from palladio.scene import ValidationError
from palladio.store import Library,RevisionConflict
from test_local_agent import ModelServer,running_server


def png(width=1):
    def chunk(kind,data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    raw=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0'+b'\x80\x40\x20'*width))+chunk(b'IEND',b'')
    return base64.b64encode(raw).decode()


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.library=Library(Path(temp.name)/'properties.sqlite3')
        self.p=self.library.create('Reference house','meadow')
    def edit(self,*commands):
        self.p=self.library.commit(self.p['id'],self.p['revision'],list(commands));return self.p
    def add_reference(self):
        self.edit({'action':'reference_add','reference':{'name':'Warm timber','cues':'Use the colour, preserve dimensions.','image':png()}})
        return self.p['scene']['references'][0]
    def test_reference_preview_restore_duplicate_and_offline_reopen(self):
        command={'action':'reference_add','reference':{'name':'Sketch','cues':'Horizontal grain','image':png()}}
        plan=preview_commands(self.p,1,[command]);self.assertEqual(len(plan['scene']['references']),1)
        self.assertNotIn('references',self.library.get(self.p['id'])['scene'])
        self.edit(command);ref=self.p['scene']['references'][0];saved=copy.deepcopy(self.p)
        self.edit({'action':'reference_update','id':ref['id'],'reference':{'cues':'Vertical grain'}})
        self.edit({'action':'reference_remove','id':ref['id']});self.assertEqual(self.p['scene']['references'],[])
        self.p=self.library.commit(self.p['id'],self.p['revision'],restore=saved['revision'])
        self.assertEqual(self.p['scene'],saved['scene'])
        self.assertEqual(Library(self.library.path).get(self.p['id']),self.p)
        self.assertEqual(self.library.duplicate(self.p['id'],'Copy')['scene'],self.p['scene'])
    def test_image_headers_bounds_and_reference_failures_are_atomic(self):
        self.assertEqual(image(png())['width'],1)
        # A complete 2 by 3 pixel JPEG fixture also exercises the browser's saved format.
        jpeg='/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAADAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDjqKKK8c98/9k='
        self.assertEqual((image(jpeg)['mime'],image(jpeg)['width'],image(jpeg)['height']),('image/jpeg',2,3))
        invalid=['https://example.com/image.png','data:image/png;base64,'+png(),png(2049),'A'*670001]
        damaged=bytearray(base64.b64decode(png()));damaged[20]^=1;invalid.append(base64.b64encode(damaged).decode())
        for data in invalid:
            with self.subTest(data=data[:30]),self.assertRaises(ValidationError):
                self.edit({'action':'environment','environment':{'hour':7}}, {'action':'reference_add','reference':{'name':'Bad','image':data}})
            self.assertEqual(self.library.get(self.p['id']),self.p)
        for _ in range(6): self.add_reference()
        with self.assertRaises(ValidationError): self.add_reference()
        for ids in [['missing'],[[]],[self.p['scene']['references'][0]['id']]*2]:
            with self.assertRaises(ValidationError): selected_references(self.p,ids)
    def test_vision_payload_uses_selected_image_and_preview_never_saves(self):
        ref=self.add_reference();self.add_reference()
        fixture=ModelServer();fixture.details['capabilities']=['completion','vision']
        with running_server(fixture.handler) as runtime:
            service=AgentService(OllamaPlanner(runtime.server_port))
            plan=service.preview(self.p,'Use this colour',provider='ollama',model='small:latest',revision=self.p['revision'],references=[ref['id']])
            self.assertEqual(plan['reference_names'],['Warm timber'])
            payload=[p for path,p in fixture.calls if path=='/api/chat'][0]
            self.assertEqual(payload['messages'][1]['images'],[ref['data']])
            context=json.loads(payload['messages'][1]['content'])['scene_context']
            self.assertEqual(context['references'][0]['cues'],ref['cues'])
            self.assertNotIn(ref['data'],payload['messages'][1]['content'])
            self.assertEqual(self.library.get(self.p['id']),self.p)
    def test_text_only_or_remote_models_receive_no_reference_payload(self):
        ref=self.add_reference();fixture=ModelServer()
        with running_server(fixture.handler) as runtime:
            service=AgentService(OllamaPlanner(runtime.server_port))
            for details in [{'model_info':{'x':1}}, {'model_info':{'x':1},'capabilities':['completion']},
                            {'model_info':{'x':1},'capabilities':['completion','vision'],'remote_host':'example.com'}]:
                fixture.details=details
                with self.subTest(details=details),self.assertRaises(ValidationError):
                    service.preview(self.p,'Use image',provider='ollama',model='small:latest',revision=self.p['revision'],references=[ref['id']])
            self.assertFalse(any(path=='/api/chat' for path,_ in fixture.calls))
            with self.assertRaises(ValidationError): service.preview(self.p,'add a room',references=[ref['id']])
            with self.assertRaises(RevisionConflict):
                service.preview(self.p,'test',provider='ollama',model='small:latest',revision=1,references=[ref['id']])
    def test_context_filter_summarizes_mesh_and_preserves_group_ownership(self):
        self.edit({'action':'assembly','assembly':{'kind':'garage','name':'Garage'}})
        member=self.p['scene']['elements'][0]
        size,model=import_obj('v 0 0 0\nv 1 0 0\nv 0 1 1\nf 1 2 3','m');model['triangles']*=1000
        self.edit({'action':'add','element':{'kind':'block','material':'oak','name':'Garden chair','size':size,'position':[20,0,0],'mesh':model}})
        imported=self.p['scene']['elements'][-1]
        context=scene_context(self.p,member['id'],'garden')
        self.assertEqual(len(context['elements']),2);self.assertEqual(context['elements'][0]['id'],member['id'])
        self.assertEqual(context['assemblies'][0]['part_count'],len(self.p['scene']['elements'])-1)
        compact=next(e for e in context['elements'] if e['id']==imported['id'])
        self.assertNotIn('mesh',compact);self.assertEqual(compact['mesh_summary']['triangles'],1000)
        self.assertTrue(context['context_is_partial']);self.assertLess(len(json.dumps(context)),12000)
        with self.assertRaises(ValidationError): scene_context(self.p,None,'not-found')
    def test_agent_group_finish_and_terrain_batch_uses_shared_validators(self):
        self.edit({'action':'assembly','assembly':{'kind':'garage'}})
        group=self.p['scene']['assemblies'][0];member=next(iter(group['members'].values()))
        fixture=ModelServer();fixture.plan={'summary':'Resize the whole garage, finish its slab and flatten the approach.','commands':[
            {'action':'assembly_update','id':group['id'],'assembly':{'width':8}},
            {'action':'update','id':member,'element':{'finish':{'color':'#884422','pattern':'wood','rotation':90}}},
            {'action':'terrain_layer','layer':{'mode':'flatten','name':'Approach','center':[0,10],'radius_m':12,'height_m':0}}]}
        before=copy.deepcopy(self.p)
        with running_server(fixture.handler) as runtime:
            plan=AgentService(OllamaPlanner(runtime.server_port)).preview(self.p,'Resize and finish',member,provider='ollama',model='small:latest',revision=self.p['revision'])
        self.assertEqual(self.p,before);self.assertIn('warnings',plan)
        self.edit(*plan['commands'])
        self.assertEqual(self.p['scene']['assemblies'][0]['spec']['width'],8)
        self.assertEqual(self.p['scene']['elements'][0]['finish']['rotation'],90)
        self.assertEqual(len(self.p['scene']['terrain_layers']),1)
        self.assertEqual(self.library.commit(self.p['id'],self.p['revision'],restore=before['revision'])['scene'],before['scene'])
    def test_model_cannot_edit_omitted_groups_layers_or_reference_board(self):
        self.edit({'action':'assembly','assembly':{'kind':'room'}})
        group=self.p['scene']['assemblies'][0]
        bad=[{'action':'assembly_remove','id':group['id']}, {'action':'terrain_remove','id':'outside'},
             {'action':'reference_add','reference':{'name':'Photo','image':png()}},
             {'action':'assembly_update','id':group['id'],'assembly':{'kind':'garage'}},
             {'action':'add','element':{'mesh':{}}}]
        for command in bad:
            with self.subTest(command=command),self.assertRaises(ValidationError):
                validated_plan(self.p,{'summary':'Bad','commands':[command]},set())
        self.assertEqual(self.library.get(self.p['id']),self.p)
    def test_reference_fields_round_trip_through_http_preview(self):
        ref=self.add_reference();fixture=ModelServer();fixture.details['capabilities']=['completion','vision']
        with running_server(fixture.handler) as runtime,running_server(handler_for(self.library,AgentService(OllamaPlanner(runtime.server_port)))) as app:
            body={'prompt':'Use timber tones','provider':'ollama','model':'small:latest','revision':self.p['revision'],'references':[ref['id']],'query':''}
            request=Request(f'http://127.0.0.1:{app.server_port}/api/properties/{self.p["id"]}/preview',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            with urlopen(request,timeout=5) as response: plan=json.load(response)
            self.assertEqual(plan['reference_names'],['Warm timber'])
            self.assertEqual(self.library.get(self.p['id']),self.p)
