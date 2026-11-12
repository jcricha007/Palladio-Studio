# Palladio Studio design roadmap

## Product definition

Open one persistent property at a time. Start from a described setting or a real-world address or coordinates, then design the property from its terrain and architecture down to furnishings, vehicles, lighting, weather, and material grain. Keep many independent properties and branch a design when exploring alternatives.

**Realistic interpretation** is the default for a real location. Preserve recognizable terrain, shoreline, roads, and other supported features. Fill gaps with plausible vegetation, surface materials, or surroundings. Record the source and resolution of observed inputs and identify inferred or generated content. Save the starting environment as an immutable baseline so the user can compare it with the design and, as terrain editing matures, restore features selectively.

## Creation engine

| Method | Examples | Editable state |
| --- | --- | --- |
| Parametric components | Walls, floors, roofs, windows, stairs, cabinetry | Dimensions, profiles, material slots, openings, and attachments |
| Procedural geometry and placement | Custom massing, landforms, retaining walls, paths, planting | Curves, footprints, terrain layers, constraints, and generation seeds |
| Imported or authored assets | Furniture, vehicles, fixtures, trees, decorative objects | Stable asset reference, transform, variants, and material overrides |
| Material and atmosphere controls | Oak grain, stone veining, concrete finish, mist, rain, dusk | Scale, orientation, color, roughness, maps, and environmental parameters |

Store a versioned property model independently of the renderer. Use stable IDs for scene elements and local metres with Y up in the prototype. The Unreal adapter will convert axes and scale at its boundary. Store a real site's georeference alongside the local scene so geographic imports can align without large renderer coordinates. Keep external assets and references addressable by stable identifiers and preserve provenance alongside them.

Manual controls and agent proposals use the same command interface. Validate commands against the active scene revision, commit each edit batch atomically, and keep restore points. The local model will propose structured commands, with deterministic tools handling geometry, placement, materials, and saving.

## Milestones

| Milestone | Build | Acceptance |
| --- | --- | --- |
| **0.1 · Property foundation** | Local property library, procedural terrain, basic 3D editor, editable pavilion, weather and time, revision history, and rule-based prompt preview. | Create two independent properties, edit one, compare its baseline, restore a prior revision, and reopen the saved design after a restart. |
| **0.2 · Unreal viewport and Windows workflow** | Unreal desktop shell, orbit and walk navigation, scene adapter, lighting and terrain rendering, and a Windows developer launch workflow. | Load a 0.1 property in Unreal with matching position, scale, materials, and time. Edit a property and reopen the result without losing its history. |
| **0.3 · Real and imagined sites** | Location lookup, georeferenced elevation import, source metadata, an offline cache for permitted datasets, editable terrain layers, and richer procedural landscape tools. | Reconstruct a reference Blue Ridge site with recognizable terrain and documented source coverage. Compare the baseline with the designed site and generate a separate imagined property without a network connection. |
| **0.4 · Architecture and property detail** | Parametric openings, roofs, stairs, rooms, drives and planting. Add furnishing and vehicle import, material parameters, and richer weather and lighting. | Build and walk through a furnished home with a garage and landscaped approach. Change flooring grain direction and outdoor conditions, then reopen the result with both edits intact. |
| **0.5 · Local model and visual references** | Local model adapter, scene queries, selection-aware editing, and attached photos and sketches with user-selected design cues. | Apply a photo's material or window proportions to a selected element and preview the change. Ask for a precise edit, confirm the intended target, and restore the previous version. |
| **0.6 · Autonomous design jobs** | Persistent briefs, task decomposition, prerequisite tracking, incremental validation, progress, pause and resume, and version checkpoints. | Submit one brief covering a house, interiors, and landscaping. Pause at a checkpoint, make a manual edit, and resume against the latest revision without losing the manual change. |

## Agent behavior

- Quick requests resolve the intended object and apply a validated, reversible edit. Show a preview or ask a focused question when the target or result is ambiguous.
- Large requests retain the full brief and references, extract requirements, then give each planning step the relevant constraints and scene context. This lets long requests exceed a single model context window.
- Run long jobs in reviewable batches with visible progress. Save the current revision and unresolved requirements at each checkpoint. On resume, reconcile manual changes before executing dependent work.
- Place large replacements in a new design version. Request confirmation before permanently deleting project data. Surface unsupported requests and missing assets explicitly.
- Benchmark local inference while the Unreal viewport is running on the target Windows workstation with its RTX 4090. Measure edit latency, frame time, VRAM use, and how often plans need correction before choosing a default model and quality preset.

## Current 0.2 development

The Unreal developer preview loads existing terrain, vegetation, and pavilion geometry from the local property server. It projects positions, dimensions, and yaw into Unreal coordinates and uses the same stable element IDs and revision checks as the browser. Free flight, original-site comparison, and horizontal element moves are included in the preview.

Complete Windows acceptance with a saved 0.1 property, then add orbit and collision-aware walkthrough navigation before closing 0.2.

## Architecture assembly increment

Room and garage shells with genuine door gaps and window wall segmentation, plus simple
dining and lounge furnishings, now use the same revision-safe command path as individual
parts. Browser previews are unsaved; Apply commits all parts atomically. Both renderers
consume the generated editable elements. This is an early 0.4 building block, not completion
of that milestone or the intervening real-site work. Assemblies do not remain parametric
groups after insertion, and arbitrary openings, stair generation, detailed assets, terrain
imports and local-model planning remain future work. The separate navigation PR continues
0.2 without changes to its Unreal code in this increment.
