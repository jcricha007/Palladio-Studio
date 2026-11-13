"""Unsaved previews for manual tools use the same commands as committed edits."""
from copy import deepcopy
from .scene import ValidationError, edit_scene
from .store import RevisionConflict
from .placement import active_terrain, footprint_range


def preview_commands(project, revision, commands):
    if type(revision) is not int or revision != project['revision']:
        raise RevisionConflict('This property changed. Reload it and preview again.')
    if not isinstance(commands, list) or not 1 <= len(commands) <= 100:
        raise ValidationError('Preview between 1 and 100 commands.')
    scene = deepcopy(project['scene'])
    changes = [edit_scene(scene, command, project['baseline']) for command in commands]
    return {'revision': revision, 'commands': deepcopy(commands), 'scene': scene,
            'summary': ' · '.join(changes), 'changes': changes,
            'warnings': placement_warnings(project, scene), 'provider': 'tools'}


def placement_warnings(project, scene):
    warnings = []
    for group in scene.get('assemblies', []):
        try:
            low, high = footprint_range(active_terrain(project['baseline'], scene), group['spec'])
            base = group['spec']['position'][1]
            if base < high - .01: warnings.append(f"{group['spec']['name']}: terrain intersects the footprint by up to {high-base:.2f} m.")
            if base > low + .05: warnings.append(f"{group['spec']['name']}: up to {base-low:.2f} m clearance beneath the footprint; supports are not generated.")
        except ValidationError:
            warnings.append(f"{group['spec']['name']}: footprint extends outside the terrain.")
    return warnings
