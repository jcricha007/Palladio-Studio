"""Real local model acceptance on a disposable property; never edits user projects."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from .local_agent import AgentService, OllamaPlanner, validated_plan
from .store import Library


def check(model, port):
    planner = OllamaPlanner(port=port)
    service = AgentService(planner)
    started = time.perf_counter()
    with TemporaryDirectory(prefix='palladio-model-') as folder:
        library = Library(Path(folder) / 'check.sqlite3')
        project = library.create('Local model acceptance', 'open meadow', True)
        result = service.preview(
            project, 'Set the weather to fog. Make no other changes.',
            provider='ollama', model=model, revision=project['revision'])
        if result['scene']['environment']['weather'] != 'fog':
            raise RuntimeError('The model returned a valid plan but did not set fog.')
        expected = json.loads(json.dumps(project['scene']))
        expected['environment']['weather'] = 'fog'
        if result['scene'] != expected:
            raise RuntimeError('The model proposed extra changes beyond the requested weather.')
        if library.get(project['id']) != project:
            raise RuntimeError('The preview unexpectedly changed the saved property.')
        return {'passed': True, 'model': model, 'endpoint': f'127.0.0.1:{port}',
                'elapsed_seconds': round(time.perf_counter() - started, 2),
                'commands': result['commands'], 'saved_property_unchanged': True,
                'scope': 'One real weather proposal; not broad model-quality acceptance.'}


def design_signature(scene):
    """Compare full scene results, excluding IDs generated during each preview."""
    result = deepcopy(scene)
    for item in result['elements']: item.pop('id')
    for group in result.get('assemblies', []):
        group.pop('id'); group['members'] = sorted(group['members'])
    return result


def check_design(model, port):
    service = AgentService(OllamaPlanner(port=port))
    reports = []
    with TemporaryDirectory(prefix='palladio-design-model-') as folder:
        library = Library(Path(folder) / 'check.sqlite3')
        for case in ('garage-window', 'complete-building', 'planting'):
            project = library.create(case, 'open meadow')
            selection = None
            if case == 'garage-window':
                project = library.commit(project['id'], project['revision'], [
                    {'action': 'assembly', 'assembly': {'kind': 'garage', 'name': 'Workshop'}}])
                group = project['scene']['assemblies'][0]
                selection = next(iter(group['members'].values()))
                prompt = 'Widen the existing rear window of Workshop to 2.4 m. Preserve every other property and do not add openings.'
                expected = [{'action': 'assembly_update', 'id': group['id'], 'assembly': {'window_width': 2.4}}]
            elif case == 'complete-building':
                prompt = ('Use the building tool to create a garage named Workshop, width 8 m, depth 6 m, height 3 m, '
                          'at X 0, Z 0, yaw 0, with ground offset 0.8 m. Fit a gable roof named Workshop roof, '
                          'height 1.8 m and overhang 0.5 m, plus a foundation with 3 columns in X and 2 in Z. '
                          'Use default materials and all other defaults. Make no other edits.')
                expected = [{'action': 'building', 'building': {
                    'shell': {'kind': 'garage', 'name': 'Workshop', 'width': 8, 'depth': 6, 'height': 3,
                              'position': [0, 0, 0], 'yaw': 0}, 'ground_offset_m': .8,
                    'roof': {'kind': 'gable_roof', 'name': 'Workshop roof', 'height': 1.8, 'overhang': .5},
                    'foundation': {'columns_x': 3, 'columns_z': 2}}}]
            else:
                prompt = ('Use planting to scatter 4 pine trees named Courtyard pine, height 5 m, within a 3 m radius '
                          'around X 12, Z 12 using seed 17. Use default width, depth and ground offset. Make no other edits.')
                expected = [{'action': 'planting', 'planting': {'kind': 'pine', 'name': 'Courtyard pine',
                             'height': 5, 'center': [12, 12], 'radius_m': 3, 'count': 4, 'seed': 17}}]
            started = time.perf_counter()
            report = {'case': case, 'passed': False}
            try:
                target = validated_plan(project, {'summary': 'Acceptance target', 'commands': expected},
                                        {e['id'] for e in project['scene']['elements']},
                                        {g['id'] for g in project['scene'].get('assemblies', [])})
                result = service.preview(project, prompt, selection, provider='ollama', model=model, revision=project['revision'])
                if library.get(project['id']) != project:
                    raise RuntimeError('Preview unexpectedly changed the disposable property.')
                if design_signature(result['scene']) != design_signature(target['scene']):
                    raise RuntimeError('The valid proposal did not match the requested design, or changed extra properties.')
                saved = library.commit(project['id'], result['revision'], result['commands'])
                if design_signature(saved['scene']) != design_signature(result['scene']):
                    raise RuntimeError('Applied geometry differs from the preview.')
                report.update(passed=True, commands=result['commands'], preview_unchanged=True, apply_matches=True)
            except Exception as error:
                report['error'] = str(error)
            report['elapsed_seconds'] = round(time.perf_counter() - started, 2)
            reports.append(report)
    return {'passed': all(r['passed'] for r in reports), 'model': model, 'endpoint': f'127.0.0.1:{port}',
            'cases': reports, 'scope': 'Three explicit design prompts on disposable properties; not general model-quality acceptance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='gpt-oss:20b')
    parser.add_argument('--port', default=11435, type=int)
    parser.add_argument('--design', action='store_true', help='Check window editing, a complete building and planting on disposable properties.')
    args = parser.parse_args()
    report = Path('.palladio/checks/local-model-design.json' if args.design else '.palladio/checks/local-model.json')
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = check_design(args.model, args.port) if args.design else check(args.model, args.port)
    except Exception as error:
        result = {'passed': False, 'model': args.model, 'error': str(error)}
    report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    print(f'Report: {report.resolve()}')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
