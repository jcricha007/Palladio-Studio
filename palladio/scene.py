"""Property generation and validated scene edits in local metres, Y up."""

import hashlib
import math
import random
import re
from uuid import uuid4

MATERIALS = {
    "concrete": "#b0a598",
    "oak": "#b78554",
    "charred timber": "#3a3632",
    "glass": "#7fa7aa",
    "stone": "#8d8980",
    "plaster": "#e1d7c6",
}
ELEMENTS = {
    "wall": [5, 2.8, 0.25],
    "floor": [6, 0.25, 5],
    "roof": [6, 0.35, 5],
    "column": [0.35, 3, 0.35],
    "glazing": [3, 2.8, 0.10],
    "block": [1, 1, 1],
}
WEATHER = ("clear", "overcast", "fog", "rain")


class ValidationError(ValueError):
    pass


def required_text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(f"{label} must contain 1–{limit} characters.")
    return value.strip()


def number(value, label, minimum, maximum):
    if type(value) not in (int, float) or not minimum <= value <= maximum:
        raise ValidationError(f"{label} must be between {minimum} and {maximum}.")
    return value


def vector(value, label, minimum, maximum):
    if not isinstance(value, list) or len(value) != 3:
        raise ValidationError(f"{label} needs three coordinates.")
    return [number(axis, label, minimum, maximum) for axis in value]


def landscape(brief):
    """Generate and freeze an imagined site from a small terrain vocabulary."""
    brief = required_text(brief, "Landscape description", 8000)
    words = set(re.findall(r"[a-z]+", brief.casefold()))
    if words & {"coast", "coastal", "ocean", "seaside", "bluff", "cliff"}:
        profile = "coastal bluff"
    elif words & {"meadow", "grassland", "prairie", "plain", "pasture"} and not (
        words & {"forest", "wooded", "mountain", "pine", "hillside"}
    ):
        profile = "open meadow"
    else:
        profile = "wooded hills"

    seed = int.from_bytes(hashlib.sha256(brief.encode()).digest()[:4], "big")
    randomizer = random.Random(seed)
    phase = randomizer.uniform(0, 2 * math.pi)
    size, spacing = 33, 4
    edge = (size - 1) * spacing / 2

    def elevation(x, z):
        waves = math.sin(x / 21 + phase) * math.cos(z / 27 - phase)
        pad = min(1, max(0, (math.hypot(x, z) - 12) / 18))
        if profile == "coastal bluff":
            height = 3 * waves - 13 * max(0, (z - 21) / (edge - 21)) ** 0.75
        elif profile == "open meadow":
            height = 1.3 * waves + 0.025 * x
        else:
            height = 6.5 * waves + 0.09 * z
        return round(height * pad, 3)

    heights = [
        elevation(col * spacing - edge, row * spacing - edge)
        for row in range(size) for col in range(size)
    ]
    trees = []
    for _ in range({"wooded hills": 145, "coastal bluff": 50, "open meadow": 24}[profile]):
        col = randomizer.randrange(1, size - 1)
        row = randomizer.randrange(1, size - 1)
        x, z = col * spacing - edge, row * spacing - edge
        if math.hypot(x, z) < 15 or (profile == "coastal bluff" and z > 20):
            continue
        position = [x, heights[row * size + col], z]
        if any(tree["position"] == position for tree in trees):
            continue
        trees.append({
            "position": position,
            "height": round(randomizer.uniform(3, 9), 2),
        })
    return {
        "source": {"kind": "procedural", "brief": brief, "seed": seed, "profile": profile},
        "terrain": {"size": size, "spacing": spacing, "heights": heights},
        "vegetation": trees,
        "environment": {"weather": "clear", "hour": 16},
    }


def element(data):
    if not isinstance(data, dict):
        raise ValidationError("Element must be an object.")
    kind = required_text(data.get("kind"), "Element type", 40)
    material = required_text(data.get("material"), "Material", 40)
    if kind not in ELEMENTS or material not in MATERIALS:
        raise ValidationError("Choose a supported element type and material.")
    return {
        "kind": kind,
        "name": required_text(data.get("name"), "Element name", 100),
        "material": material,
        "position": vector(data.get("position"), "Position (m)", -1000, 1000),
        "size": vector(data.get("size"), "Size (m)", 0.05, 300),
        "yaw": number(data.get("yaw", 0), "Rotation (degrees)", -360, 360),
    }


def starter_elements():
    specification = [
        ("floor", "Pavilion slab", "concrete", [0, 0, 0], [12.8, 0.25, 8]),
        ("wall", "Rear timber wall", "charred timber", [0, 0.25, -3.7], [12, 3.2, 0.25]),
        ("wall", "Stone end wall", "stone", [-5.85, 0.25, 0], [0.3, 3.2, 7.4]),
        ("glazing", "Corner glazing", "glass", [5.85, 0.25, 0], [0.14, 3.2, 7.4]),
        ("glazing", "Front glazing", "glass", [-2.4, 0.25, 3.65], [6.8, 3.2, 0.14]),
        ("column", "Entry column", "charred timber", [4.4, 0.25, 3.65], [0.22, 3.2, 0.22]),
        ("roof", "Overhanging roof", "charred timber", [0, 3.45, 0], [14.6, 0.34, 9.7]),
    ]
    return [
        {"id": str(uuid4()), "kind": kind, "name": name, "material": material,
         "position": position, "size": size, "yaw": 0}
        for kind, name, material, position, size in specification
    ]


def edit_scene(scene, command, baseline=None):
    """Apply one tool command to a private scene copy owned by the transaction."""
    if not isinstance(command, dict):
        raise ValidationError("Command must be an object.")
    action = command.get("action")
    if action in {'terrain_layer','terrain_toggle','terrain_remove','terrain_restore'}:
        from .landscape_tools import edit_terrain
        return edit_terrain(scene, command, baseline)
    if action in {'assembly', 'assembly_update', 'assembly_place', 'assembly_duplicate', 'assembly_remove', 'assembly_detach'}:
        from .groups import edit_group
        return edit_group(scene, command, baseline)
    if action == "add":
        item = element(command.get("element"))
        item["id"] = str(uuid4())
        scene["elements"].append(item)
        return f"Added {item['name']}"
    if action in ("update", "remove"):
        target = next((item for item in scene["elements"] if item["id"] == command.get("id")), None)
        if target is None:
            raise ValidationError("This element is no longer in the design.")
        from .groups import member_edit
        if action == "remove":
            member_edit(scene, target)
            scene["elements"].remove(target)
            return f"Removed {target['name']}"
        changes = command.get("element")
        if not isinstance(changes, dict) or not changes.keys() <= {
            "kind", "name", "material", "position", "size", "yaw"
        }:
            raise ValidationError("Invalid element fields.")
        checked = element({**target, **changes})
        member_edit(scene, target, {key: value for key, value in changes.items() if value != target.get(key)})
        target.update(checked)
        return f"Edited {target['name']}"
    if action == "environment":
        changes = command.get("environment")
        if not isinstance(changes, dict) or not changes or not changes.keys() <= {"hour", "weather"}:
            raise ValidationError("Choose a supported weather or time edit.")
        environment = {**scene["environment"], **changes}
        if environment["weather"] not in WEATHER:
            raise ValidationError("Choose clear, overcast, fog, or rain.")
        number(environment["hour"], "Time of day", 0, 23 + 59 / 60)
        scene["environment"] = environment
        return "Changed environment"
    raise ValidationError("Unknown scene command.")
