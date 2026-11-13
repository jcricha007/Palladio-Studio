"""Optional rendered smoke: pip install playwright; python -m playwright install chromium.

Run from the repository root: python tests/browser_smoke.py
PALLADIO_CHROMIUM may select an existing Chromium executable.
Uses temporary storage and a fake loopback model, never a real site/model service.
"""
import base64
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from palladio.__main__ import handler_for
from palladio.local_agent import AgentService,OllamaPlanner
from palladio.store import Library
from test_local_agent import ModelServer,running_server
from test_references import png


def main():
    with TemporaryDirectory() as folder,sync_playwright() as playwright:
        library=Library(Path(folder)/'properties.sqlite3')
        project=library.create('Browser acceptance','meadow')
        project=library.commit(project['id'],1,[{'action':'assembly','assembly':{'kind':'garage'}}])
        group=project['scene']['assemblies'][0];member=next(iter(group['members'].values()))
        fixture=ModelServer();fixture.details['capabilities']=['completion','vision']
        fixture.plan={'summary':'Widen the whole garage using the selected reference cues.','commands':[
            {'action':'assembly_update','id':group['id'],'assembly':{'width':9}}]}
        with running_server(fixture.handler) as runtime,running_server(handler_for(library,AgentService(OllamaPlanner(runtime.server_port)))) as app:
            options={'headless':True,'args':['--enable-unsafe-swiftshader']}
            if os.getenv('PALLADIO_CHROMIUM'): options['executable_path']=os.environ['PALLADIO_CHROMIUM']
            browser=playwright.chromium.launch(**options)
            page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{app.server_port}')
            expect(page.locator('#project-title')).to_have_text('Browser acceptance')
            expect(page.locator('#view')).to_be_visible()
            page.locator('#scene-items button').first.click()
            revision=2
            def apply():
                nonlocal revision
                expect(page.locator('#apply-plan')).to_be_enabled()
                assert library.get(project['id'])['revision']==revision,'Preview must not save'
                page.locator('#apply-plan').click();revision+=1
                expect(page.locator('#proposal')).to_be_hidden()
                expect(page.locator('#new-property')).to_be_enabled()
                assert library.get(project['id'])['revision']==revision
            page.locator('#group-width').fill('8');page.locator('#group-form button[type=submit]').click();apply()
            page.locator('#finish-pattern').select_option('wood');page.locator('#finish-rotation').fill('90')
            page.locator('#finish-form button[type=submit]').click();apply()
            page.locator('#terrain-tools > summary').click();page.locator('#terrain-mode').select_option('flatten')
            page.locator('#terrain-form button[type=submit]').click();apply()
            page.locator('details:has(#asset-import-form) > summary').click()
            page.locator('#asset-file').set_input_files(str(ROOT/'examples/bench.obj'))
            page.locator('#asset-import-form button[type=submit]').click()
            expect(page.locator('#asset-list option')).to_have_count(1)
            expect(page.locator('#asset-place')).to_be_enabled()
            page.locator('#asset-x').fill('10');page.locator('#asset-place').click();apply()
            page.locator('#reference-board > summary').click()
            picture=Path(folder)/'sketch.png';picture.write_bytes(base64.b64decode(png()))
            page.locator('#reference-file').set_input_files(str(picture))
            page.locator('#reference-name').fill('Timber sketch');page.locator('#reference-cues').fill('Preserve the layout; use warm timber tones.')
            page.locator('#reference-form button[type=submit]').click()
            expect(page.locator('#proposal-text')).to_contain_text('Added reference')
            assert '[local reference image;' in page.locator('#proposal-commands').text_content()
            apply();expect(page.locator('#reference-image')).to_be_visible()
            page.wait_for_function('document.getElementById("reference-image").naturalWidth>0')
            saved=library.get(project['id']);assert saved['scene']['references'][0]['mime']=='image/jpeg'
            page.locator('#reference-use').check();page.locator('#agent-provider').select_option('ollama')
            expect(page.locator('#agent-model option[value="small:latest"]')).to_have_count(1)
            page.locator('#agent-model').select_option('small:latest')
            page.locator('#agent-query').fill('garage');page.locator('#request').fill('Widen the whole garage to nine metres using the reference cues.')
            page.locator('#preview-request').click();expect(page.locator('#proposal-text')).to_contain_text('Widen the whole garage')
            assert len([body for path,body in fixture.calls if path=='/api/chat'][0]['messages'][1]['images'])==1
            apply();assert library.get(project['id'])['scene']['assemblies'][0]['spec']['width']==9
            page.reload();expect(page.locator('#project-title')).to_have_text('Browser acceptance')
            expect(page.locator('#new-property')).to_be_enabled()
            assert library.get(project['id'])['scene']['references']==saved['scene']['references']
            page.locator('#baseline-view').click();page.locator('#design-view').click()
            if os.getenv('PALLADIO_SCREENSHOT'): page.screenshot(path=os.environ['PALLADIO_SCREENSHOT'],full_page=True)
            assert not errors,errors
            browser.close()
            print('PASS: Chromium assembly resize, wood finish, terrain layer, OBJ placement, image normalization, vision proposal, Apply and reopen; no page errors')


if __name__=='__main__': main()
