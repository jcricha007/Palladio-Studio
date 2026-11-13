"""Deterministic, editable block assemblies, not construction-ready designs."""

import math
from .scene import ValidationError, element, number, required_text, vector

ASSEMBLIES = {
    "room": {"label": "Room shell", "width": 6, "depth": 5, "height": 3, "material": "plaster"},
    "garage": {"label": "Garage shell", "width": 6, "depth": 7, "height": 3.2, "material": "concrete"},
    "dining": {"label": "Dining set", "width": 3, "depth": 2.6, "height": 0.8, "material": "oak"},
    "stairs": {"label":"Straight stairs","width":1.2,"depth":4,"height":2.8,"material":"oak"},
    "path": {"label":"Path / terrace","width":3,"depth":8,"height":.15,"material":"stone"},
    "planter": {"label":"Raised planter","width":2,"depth":2,"height":.6,"material":"concrete"},
    "lounge": {"label": "Lounge set", "width": 3.4, "depth": 2.8, "height": 0.9, "material": "oak"},
}

for _kind, _item in ASSEMBLIES.items():
    _shell = _kind in ("room", "garage")
    _item["limits"] = {
        "width": [4 if _kind == "garage" else 3 if _shell else 2, 30 if _shell else 8],
        "depth": [4 if _kind == "garage" else 3 if _shell else 2, 30 if _shell else 8],
        "height": [3 if _kind == "garage" else 2.5 if _shell else .6, 8 if _shell else 1.5],
    }

for _kind, _limits in {
    'stairs': {'width':[.6,4], 'depth':[1,12], 'height':[.3,4]},
    'path': {'width':[.5,30], 'depth':[1,50], 'height':[.05,1]},
    'planter': {'width':[1,8], 'depth':[1,8], 'height':[.3,2]},
}.items(): ASSEMBLIES[_kind]['limits'] = _limits


def generate_assembly(data):
    if not isinstance(data, dict) or not data.keys() <= {
        "kind", "name", "width", "depth", "height", "position", "yaw", "material",
        "door_width", "door_height", "window_width", "window_height", "window_sill", "steps"
    }:
        raise ValidationError("Choose supported assembly fields.")
    kind = data.get("kind")
    if not isinstance(kind, str) or kind not in ASSEMBLIES:
        raise ValidationError("Choose a supported assembly from the catalog.")
    defaults = ASSEMBLIES[kind]
    shell = kind in ("room", "garage")
    minimum = 4 if kind == "garage" else 3 if shell else 2
    spec = {
        "kind": kind,
        "name": required_text(data.get("name", defaults["label"]), "Assembly name", 60),
        "width": number(data.get("width", defaults["width"]), "Width (m)", *defaults["limits"]["width"]),
        "depth": number(data.get("depth", defaults["depth"]), "Depth (m)", *defaults["limits"]["depth"]),
        "height": number(data.get("height", defaults["height"]), "Height (m)", *defaults["limits"]["height"]),
        "position": vector(data.get("position", [0, 0, 0]), "Assembly position", -900, 900),
        "yaw": number(data.get("yaw", 0), "Assembly rotation", -360, 360),
        "material": data.get("material", defaults["material"]),
    }
    if shell:
        spec.update({
            'door_width': number(data.get('door_width', 2.8 if kind == 'garage' else 1.2), 'Door width', .6, spec['width'] - .6),
            'door_height': number(data.get('door_height', 2.5 if kind == 'garage' else 2.2), 'Door height', 1, spec['height'] - .1),
            'window_width': number(data.get('window_width', min(2, spec['width'] - 1)), 'Window width', .4, spec['width'] - .6),
            'window_height': number(data.get('window_height', 1.2), 'Window height', .3, spec['height'] - .2),
            'window_sill': number(data.get('window_sill', .9), 'Window sill', .1, spec['height'] - .4),
        })
        if spec['window_height'] + spec['window_sill'] > spec['height'] - .1:
            raise ValidationError('Window opening must leave at least 0.1 m above it.')
    elif any(key.startswith(('door_', 'window_')) for key in data):
        raise ValidationError('Openings apply to room and garage shells.')
    if kind == 'stairs':
        steps = data.get('steps', max(2, math.ceil(spec['height'] / .18)))
        if type(steps) is not int or not 2 <= steps <= 32:
            raise ValidationError('Stairs need 2 to 32 steps.')
        if spec['height'] / steps < .05 or spec['height'] / steps > .3 or spec['depth'] / steps < .05:
            raise ValidationError('Stair rise must be 0.05–0.3 m and tread depth at least 0.05 m.')
        spec['steps'] = steps
    elif 'steps' in data:
        raise ValidationError('Step count only applies to stairs.')
    # Validate material even before producing any geometry.
    element({"kind": "block", "name": "check", "size": [1, 1, 1],
             "position": [0, 0, 0], "material": spec["material"]})
    pieces = []
    roles = {}
    angle = math.radians(spec["yaw"])

    def add(label, position, size, material=None, piece_kind="block"):
        roles[label] = roles.get(label, 0) + 1
        x, y, z = position
        px, py, pz = spec["position"]
        pieces.append(element({
            "kind": piece_kind, "name": f"{spec['name']} · {label}",
            "position": [px + x * math.cos(angle) + z * math.sin(angle), py + y,
                         pz - x * math.sin(angle) + z * math.cos(angle)],
            "size": size, "yaw": spec["yaw"], "material": material or spec["material"],
        }))
        pieces[-1]["role"] = f"{label}:{roles[label]}"

    w, d, h = spec["width"], spec["depth"], spec["height"]
    if shell:
        t, floor = .2, .15
        add("floor", [0, 0, 0], [w, floor, d], "concrete", "floor")
        add("roof", [0, floor + h, 0], [w + .4, .2, d + .4], None, "roof")
        for x, label in [(-w / 2 + t / 2, "left wall"), (w / 2 - t / 2, "right wall")]:
            add(label, [x, floor, 0], [t, h, d], None, "wall")
        inner = w - 2 * t
        door_w, door_h = spec["door_width"], spec["door_height"]
        z = d / 2 - t / 2
        side = (inner - door_w) / 2
        for sign, label in [(-1, "entry left"), (1, "entry right")]:
            add(label, [sign * (door_w / 2 + side / 2), floor, z], [side, h, t], None, "wall")
        add("entry lintel", [0, floor + door_h, z], [door_w, h - door_h, t], None, "wall")
        # Window is an actual gap in the rear wall, filled only by glazing.
        window_w, sill, window_h = spec["window_width"], spec["window_sill"], spec["window_height"]
        side = (inner - window_w) / 2
        z = -d / 2 + t / 2
        for sign, label in [(-1, "window left"), (1, "window right")]:
            add(label, [sign * (window_w / 2 + side / 2), floor, z], [side, h, t], None, "wall")
        add("window sill wall", [0, floor, z], [window_w, sill, t], None, "wall")
        add("window header", [0, floor + sill + window_h, z], [window_w, h - sill - window_h, t], None, "wall")
        add("window glazing", [0, floor + sill, z], [window_w, window_h, .06], "glass", "glazing")
    elif kind == 'stairs':
        steps=spec['steps']
        for i in range(steps):
            add(f"step {i+1}", [0,0,-d/2+(i+.5)*d/steps], [w,h*(i+1)/steps,d/steps])
    elif kind == 'path':
        add('surface', [0,0,0], [w,h,d], None, 'floor')
    elif kind == 'planter':
        t=.15
        add('base',[0,0,0],[w,.1,d])
        for sign in (-1,1):
            add('side',[sign*(w-t)/2,.1,0],[t,h-.1,d])
            add('end',[0,.1,sign*(d-t)/2],[w-2*t,h-.1,t])
        add('soil',[0,.1,0],[w-2*t,max(.05,h-.2),d-2*t], 'charred timber')
    elif kind == "dining":
        top_w, top_d, thick = w * .58, d * .45, .08
        add("table top", [0, h - thick, 0], [top_w, thick, top_d])
        for x in (-top_w / 2 + .12, top_w / 2 - .12):
            for z in (-top_d / 2 + .12, top_d / 2 - .12):
                add("table leg", [x, 0, z], [.1, h - thick, .1])
        seat = min(.5, w * .2)
        for side in (-1, 1):
            for x in (-w * .24, w * .24):
                z = side * (d / 2 - seat / 2)
                add("chair seat", [x, h * .48, z], [seat, .08, seat])
                add("chair base", [x, 0, z], [seat * .6, h * .48, seat * .6])
                add("chair back", [x, h * .48 + .08, z + side * (seat / 2 - .04)], [seat, h * .52 - .08, .08])
    else:
        sofa_d = d * .38
        add("sofa base", [0, 0, -d / 2 + sofa_d / 2], [w, h * .45, sofa_d])
        add("sofa back", [0, h * .45, -d / 2 + .12], [w, h * .55, .24])
        for x in (-w / 2 + .12, w / 2 - .12):
            add("sofa arm", [x, h * .45, -d / 2 + sofa_d / 2], [.24, h * .3, sofa_d])
        add("coffee table top", [0, h * .4, d * .23], [w * .55, .08, d * .3])
        add("coffee table base", [0, 0, d * .23], [w * .35, h * .4, d * .2])
    return spec, pieces


def assembly_preview(project, data):
    spec, pieces = generate_assembly(data)
    return {
        "revision": project["revision"],
        "summary": f"Add {spec['name']} ({len(pieces)} editable parts). Nothing is saved until Apply.",
        "command": {"action": "assembly", "assembly": spec},
        "elements": [{**piece, "id": f"preview-{index}"} for index, piece in enumerate(pieces)],
    }
