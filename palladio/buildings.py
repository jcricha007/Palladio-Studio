"""Compose a grounded shell, roof and supports through the existing design tools."""
from .scene import ValidationError, number


def build(scene, command, baseline):
    from .groups import edit_group
    from .roofs import fit_roof
    from .foundations import edit_foundation

    data = command.get('building')
    if not isinstance(data, dict) or not data.keys() <= {'shell', 'ground_offset_m', 'roof', 'foundation'}:
        raise ValidationError('Choose supported building fields.')
    shell = data.get('shell')
    if not isinstance(shell, dict) or shell.get('kind') not in ('room', 'garage', 'dwelling'):
        raise ValidationError('Choose a room, garage or dwelling shell.')
    offset = number(data.get('ground_offset_m', 0), 'Building ground offset', -5, 50)
    # Position Y is set by ground placement. An explicit offset makes that visible.
    labels = [edit_group(scene, {'action': 'assembly', 'assembly': shell}, baseline)]
    host_id = scene['assemblies'][-1]['id']
    labels.append(edit_group(scene, {'action': 'assembly_place', 'id': host_id, 'offset_m': offset}, baseline))
    if data.get('roof') is not None:
        labels.append(fit_roof(scene, {'action': 'roof_fit', 'id': host_id, 'roof': data['roof']}, baseline))
    if data.get('foundation') is not None:
        labels.append(edit_foundation(scene, {'action': 'foundation_fit', 'id': host_id,
                                             'foundation': data['foundation']}, baseline))
    return '; '.join(labels)
