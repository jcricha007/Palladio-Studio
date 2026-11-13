"""Persistent assembly ownership and deterministic regeneration."""
from copy import deepcopy
from uuid import uuid4
from .assemblies import generate_assembly
from .scene import ValidationError
from .placement import place_spec


def owner(scene, member_id):
    return next((g for g in scene.get('assemblies', []) if member_id in g['members'].values()), None)


def find_group(scene, group_id):
    group = next((g for g in scene.get('assemblies', []) if g['id'] == group_id), None)
    if group is None:
        raise ValidationError('This assembly is no longer in the design.')
    return group


def regenerate(scene, group, data):
    spec, pieces = generate_assembly(data)
    old_members = group.get('members', {})
    overrides = group.get('overrides', {})
    members, generated = {}, []
    for piece in pieces:
        role = piece['role']
        members[role] = old_members.get(role, str(uuid4()))
        generated.append({**piece, **overrides.get(role, {}), 'id': members[role]})
    missing = set(overrides) - set(members)
    if missing:
        raise ValidationError('This change removes overridden parts. Detach the assembly before changing its topology.')
    scene['elements'] = [e for e in scene['elements'] if e['id'] not in old_members.values()] + generated
    group.update(spec=spec, members=members, overrides=overrides)


def edit_group(scene, command, baseline):
    action = command['action']
    if action == 'assembly':
        group = {'id': str(uuid4()), 'members': {}, 'overrides': {}}
        regenerate(scene, group, command.get('assembly'))
        scene.setdefault('assemblies', []).append(group)
        return f"Added {group['spec']['name']} ({len(group['members'])} linked parts)"
    group = find_group(scene, command.get('id'))
    if action == 'assembly_update':
        changes = command.get('assembly')
        if not isinstance(changes, dict) or not changes or 'kind' in changes:
            raise ValidationError('Change assembly parameters without changing its type.')
        regenerate(scene, group, {**group['spec'], **changes})
    elif action == 'assembly_place':
        if baseline is None:
            raise ValidationError('Ground placement requires the saved property terrain.')
        regenerate(scene, group, place_spec(baseline, scene, group['spec'], command.get('offset_m', 0)))
    elif action == 'assembly_duplicate':
        spec = {**group['spec'], 'position': command.get('position')}
        duplicate = {'id': str(uuid4()), 'members': {}, 'overrides': deepcopy(group.get('overrides', {}))}
        regenerate(scene, duplicate, spec)
        scene.setdefault('assemblies', []).append(duplicate)
    elif action in ('assembly_remove', 'assembly_detach'):
        if action == 'assembly_remove':
            scene['elements'] = [e for e in scene['elements'] if e['id'] not in group['members'].values()]
        else:
            for e in scene['elements']:
                if e['id'] in group['members'].values(): e.pop('role', None)
        scene['assemblies'].remove(group)
    else:
        raise ValidationError('Unknown assembly command.')
    return f"{action.replace('assembly_', '').capitalize()} {group['spec']['name']}"


def member_edit(scene, target, changes=None):
    group = owner(scene, target['id'])
    if not group: return
    if changes is None or not changes.keys() <= {'name', 'material', 'finish'}:
        raise ValidationError('This part belongs to an assembly. Edit the group, or detach it before editing individual geometry.')
    if not changes: return
    role = next(role for role,key in group['members'].items() if key == target['id'])
    group.setdefault('overrides', {}).setdefault(role, {}).update(deepcopy(changes))
