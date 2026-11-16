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
from threading import Event

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
            # Ten-PR series: connected architecture, planting, reusable finishes, views and jobs.
            page.locator('#assembly-kind').select_option('dwelling')
            page.locator('#assembly-name').fill('Courtyard house');page.locator('#assembly-width').fill('12')
            page.locator('#assembly-rooms_x').fill('3');page.locator('#assembly-rooms_z').fill('2')
            page.locator('#assembly-form button[type=submit]').click();apply()
            house=library.get(project['id'])['scene']['assemblies'][-1]
            part=next(e for e in library.get(project['id'])['scene']['elements'] if e['id']==next(iter(house['members'].values())))
            page.locator('#scene-items button').filter(has_text=part['name']).first.click()
            page.locator('#foundation-panel > summary').click();page.locator('#foundation-clearance').fill('1.2')
            page.locator('#foundation-raise').click();apply()
            assert any(g['spec']['kind']=='foundation' for g in library.get(project['id'])['scene']['assemblies'])
            page.locator('#assembly-kind').select_option('gable_roof');page.locator('#roof-fit').click();apply()
            page.locator('details:has(#planting-form) > summary').click()
            page.locator('#plant-count').fill('3');page.locator('#plant-x').fill('20');page.locator('#plant-z').fill('15')
            page.locator('#planting-form button[type=submit]').click();apply()
            page.locator('#palette-panel > summary').click();page.locator('#palette-list').select_option('builtin:light-tile')
            page.locator('#palette-apply').click();apply()
            # Five-PR series: a keyed wall opening and editable non-solid water.
            page.locator('#assembly-kind').select_option('wall_run');page.locator('#assembly-name').fill('Smoke wall')
            page.locator('#assembly-form button[type=submit]').click();apply()
            wall=library.get(project['id'])['scene']['assemblies'][-1]
            part=next(e for e in library.get(project['id'])['scene']['elements'] if e['id']==next(iter(wall['members'].values())))
            page.locator('#scene-items button').filter(has_text=part['name']).first.click()
            page.locator('#wall-tools > summary').click();page.locator('#opening-key').fill('entry')
            page.locator('#opening-kind').select_option('door');page.locator('#opening-width').fill('1.4');page.locator('#opening-height').fill('2.1')
            page.locator('#opening-form button[type=submit]').click();apply()
            expect(page.locator('#opening-list option')).to_have_count(1)
            page.locator('#water-panel > summary').click();page.locator('#water-name').fill('Smoke pool')
            page.locator('#water-form button[type=submit]').click();apply();page.locator('#water-schedule').click()
            expect(page.locator('#water-result')).to_contain_text('Smoke pool')
            assert any(e.get('collision') is False for e in library.get(project['id'])['scene']['elements'])
            page.locator('#presentation-panel > summary').click();page.locator('#view-name').fill('Arrival')
            page.locator('#view-fov').fill('60');page.locator('#view-fov').press('Tab')
            page.locator('#view-save').click();apply();expect(page.locator('#view-list option')).to_have_count(1)
            page.locator('#view-open').click();assert library.get(project['id'])['scene']['views'][0]['camera']['fov_degrees']==60
            with page.expect_download() as image_download:page.locator('#view-png').click()
            image_file=Path(image_download.value.path());assert image_file.read_bytes().startswith(b'\x89PNG');assert image_file.stat().st_size>1000
            with page.expect_download() as obj_download:page.locator('#view-obj').click()
            assert '# Units: metres; Y up' in Path(obj_download.value.path()).read_text()
            page.locator('#jobs-panel > summary').click();page.locator('#job-brief').fill('Set a rainy presentation atmosphere.')
            fixture.plan={'title':'Presentation weather','steps':['set weather to rain']}
            page.locator('#job-outline').click();expect(page.locator('#job-steps')).to_have_value('set weather to rain')
            page.locator('#reference-use').uncheck();page.locator('#agent-provider').select_option('rules');page.locator('#agent-query').fill('')
            page.locator('#job-form button[type=submit]').click();expect(page.locator('#job-list option')).to_have_count(1)
            page.locator('#job-start').click();expect(page.locator('#job-propose')).to_be_enabled()
            page.locator('#job-propose').click();expect(page.locator('#proposal-text')).to_contain_text('Design job step');apply()
            expect(page.locator('#job-list option')).to_contain_text('completed')
            page.locator('#job-title').fill('Stop review');page.locator('#job-steps').fill('set weather to clear')
            page.locator('#job-form button[type=submit]').click();expect(page.locator('#job-list option')).to_have_count(2)
            page.locator('#job-start').click();page.locator('#agent-provider').select_option('ollama')
            fixture.plan={'summary':'Clear weather','commands':[{'action':'environment','environment':{'weather':'clear'}}]}
            fixture.release=Event();fixture.started.clear()
            try:
                page.locator('#job-propose').click();assert fixture.started.wait(3)
                page.locator('#job-stop').click();expect(page.locator('#job-agent-status')).to_contain_text('Job paused')
            finally:fixture.release.set()
            expect(page.locator('#job-resume')).to_be_enabled();expect(page.locator('#proposal')).to_be_hidden()
            assert library.get(project['id'])['revision']==revision
            page.locator('details:has(#diagnostics-refresh) > summary').click();page.locator('#diagnostics-refresh').click()
            expect(page.locator('#diagnostics-result')).to_contain_text('database schema 2')
            page.reload();expect(page.locator('#project-title')).to_have_text('Browser acceptance')
            expect(page.locator('#new-property')).to_be_enabled()
            assert library.get(project['id'])['scene']['references']==saved['scene']['references']
            page.locator('#baseline-view').click();page.locator('#design-view').click()
            if os.getenv('PALLADIO_SCREENSHOT'): page.screenshot(path=os.environ['PALLADIO_SCREENSHOT'],full_page=True)
            assert not errors,errors
            browser.close()
            print('PASS: Chromium terrain, assets, references, rooms, roof, planting, palettes, PNG/OBJ, saved view, model outline, job Apply/Stop, wall openings, fitted supports, water, FOV, diagnostics and reopen; no page errors')


if __name__=='__main__': main()
