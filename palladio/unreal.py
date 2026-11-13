"""Project the renderer-independent scene into Unreal centimetres, Z up."""

from .scene import MATERIALS
from .groups import owner
from .landscape_tools import design_landscape


def unreal_vector(vector):
    x, y, z = vector
    return [x * 100, z * 100, y * 100]


def unreal_view(project):
    baseline = project["baseline"]
    design = design_landscape(baseline, project["scene"])
    terrain = design["terrain"]
    spacing = terrain["spacing"] * 100
    size = terrain["size"]
    edge = (size - 1) * spacing / 2
    vertices = [
        [column * spacing - edge, row * spacing - edge, terrain["heights"][row * size + column] * 100]
        for row in range(size) for column in range(size)
    ]
    triangles = []
    for row in range(size - 1):
        for column in range(size - 1):
            index = row * size + column
            triangles.extend((index, index + size, index + size + 1, index, index + size + 1, index + 1))

    elements = []
    for element in project["scene"]["elements"]:
        group = owner(project["scene"], element["id"])
        dimensions = unreal_vector(element["size"])
        center = unreal_vector(element["position"])
        center[2] += dimensions[2] / 2
        elements.append({
            "id": element["id"],
            "name": element["name"],
            **({'edit_id': group['id'], 'edit_action': 'assembly_update',
                'edit_position': group['spec']['position']} if group else {}),
            "center_cm": center,
            "dimensions_cm": dimensions,
            "yaw_degrees": -element["yaw"],
            "color": MATERIALS[element["material"]],
        })
    return {
        "name": project["name"],
        "revision": project["revision"],
        "vertices_cm": vertices,
        "triangles": triangles,
        "baseline_vertices_cm": [[column * spacing - edge, row * spacing - edge,
            baseline['terrain']['heights'][row * size + column] * 100]
            for row in range(size) for column in range(size)],
        "baseline_vegetation": [{"base_cm": unreal_vector(tree['position']), "height_cm": tree['height']*100}
            for tree in baseline['vegetation']],
        "coastal": baseline["source"]["profile"] == "coastal bluff",
        "vegetation": [
            {"base_cm": unreal_vector(tree["position"]), "height_cm": tree["height"] * 100}
            for tree in design["vegetation"]
        ],
        "elements": elements,
        "environment": project["scene"]["environment"],
        "baseline_environment": baseline["environment"],
    }
