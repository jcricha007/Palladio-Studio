"""Real local model acceptance on a disposable property; never edits user projects."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from .local_agent import AgentService, OllamaPlanner
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='gpt-oss:20b')
    parser.add_argument('--port', default=11435, type=int)
    args = parser.parse_args()
    report = Path('.palladio/checks/local-model.json')
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = check(args.model, args.port)
    except Exception as error:
        result = {'passed': False, 'model': args.model, 'error': str(error)}
    report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    print(f'Report: {report.resolve()}')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
