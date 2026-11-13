"""First planner adapter. Future local models emit the same scene commands."""

import re

from .assemblies import assembly_preview
from .scene import ELEMENTS, MATERIALS, WEATHER, ValidationError, required_text


def preview(project, prompt, selection=None):
    prompt = required_text(prompt, "Request", 8000).casefold().rstrip(".!?")
    weather = re.fullmatch(r"(?:set |change )?(?:the )?weather to ([a-z]+)", prompt)
    hour = re.fullmatch(r"set (?:the )?time to (\d{1,2})(?::([0-5]\d))?", prompt)
    addition = re.fullmatch(r"add (?:a |an )?([a-z ]+)", prompt)
    material = re.fullmatch(r"(?:use |apply )([a-z ]+)", prompt)
    assemblies = {"room": "room", "room shell": "room", "garage": "garage",
                  "garage shell": "garage", "dining set": "dining", "lounge set": "lounge", "stairs":"stairs", "path":"path", "terrace":"path", "planter":"planter"}
    if addition and addition[1] in assemblies:
        return assembly_preview(project, {"kind": assemblies[addition[1]]})
    if weather and weather[1] in WEATHER:
        summary = f"Set weather to {weather[1]}."
        command = {"action": "environment", "environment": {"weather": weather[1]}}
    elif hour and int(hour[1]) < 24:
        minutes = int(hour[2] or 0)
        summary = f"Set time to {int(hour[1]):02d}:{minutes:02d}."
        command = {"action": "environment", "environment": {"hour": int(hour[1]) + minutes / 60}}
    elif addition and addition[1] in ELEMENTS:
        kind = addition[1]
        summary = f"Add a {kind} at the site origin."
        command = {"action": "add", "element": {
            "name": kind.capitalize(), "kind": kind,
            "material": "glass" if kind == "glazing" else "concrete",
            "position": [0, 0, 0], "size": ELEMENTS[kind],
        }}
    elif material and material[1] in MATERIALS:
        target = next((item for item in project["scene"]["elements"] if item["id"] == selection), None)
        if target is None:
            raise ValidationError("Select a scene element before changing its material.")
        summary = f"Apply {material[1]} to {target['name']}."
        command = {"action": "update", "id": selection, "element": {"material": material[1]}}
    else:
        raise ValidationError("Try ‘add a wall’, ‘set weather to fog’, ‘set time to 17:30’, or ‘use oak’.")
    return {"revision": project["revision"], "summary": summary, "command": command}
