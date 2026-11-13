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

Store a versioned property model independently of the renderer. Use stable IDs for scene elements and local metres with Y up in the prototype. The Unreal adapter converts axes and scale at its boundary. Store a real site's georeference alongside the local scene so geographic imports can align without large renderer coordinates. Keep external assets and references addressable by stable identifiers and preserve provenance alongside them.

Manual controls and agent proposals use the same command interface. Validate commands against the active scene revision, commit each edit batch atomically, and keep restore points. The local model proposes structured commands, with deterministic tools handling geometry, placement, materials, and saving.

## Roadmap review after the real-site package

| Stage | Available in this branch | Remaining acceptance or development |
| --- | --- | --- |
| **0.1 · Property foundation** | Saved independent properties, three procedural landscape profiles, editable elements, baseline comparison, duplication and revision restore. | Preserve these behaviours as the scene model grows. |
| **0.2 · Unreal and Windows** | UE 5.7 developer launch, shared scene projection, fly/orbit/walk navigation and revision-aware element moves. The initial Windows scene load has been confirmed. | Complete the navigation and imported-terrain walkthrough checks. Improve materials, atmosphere and packaging. |
| **0.3 · Real and imagined sites** | Prepared elevation JSON import, U.S. address lookup, coordinate-based USGS terrain preview, source attribution and an offline download cache. | Editable terrain layers, paths and planting, shoreline handling, richer procedural sites and wider import formats. |
| **0.4 · Architecture and detail** | Room and garage shells with openings, dining and lounge presets, and individually editable pieces. | Persistent parametric groups, configurable openings, stairs and roofs, placement tools, imported furnishings/vehicles and detailed materials. |
| **0.5 · Local agent and references** | Built-in commands and switchable local Ollama models, bounded selection-aware context, validated proposal previews and explicit Apply. | Real model quality/VRAM measurements, broader scene queries, attached photos and sketches, and a native Unreal agent panel. |
| **0.6 · Long design jobs** | Revision-safe batches provide the persistence foundation. | Persistent briefs, decomposition, dependencies, progress, pause/resume and reconciliation with manual edits. |

These stages overlap. The room presets and single-turn agent are early parts of later
stages. They do not make detailed architectural modelling or autonomous design complete.

## This upgrade package

Connect the existing terrain, assembly and agent work into one branch based on current
`main`. The local-agent PR was merged into the older assembly branch after that branch's
original PR reached `main`. This package brings that work into the current application
while preserving the merged navigation and elevation import.

The real-site workflow accepts coordinates or an explicitly selected Census address match,
previews a 17 × 17 USGS elevation grid, and saves the reviewed terrain as an immutable
baseline. Each saved source carries its coordinates, sample spacing, source-tile identities,
service-reported pixel sizes and acquisition time. The user can reuse cached downloads,
refresh them without changing prior previews, and reopen saved sites offline.

This is ground-elevation acquisition. It does not identify property boundaries, existing
buildings or vegetation. Address matches are approximate, and the source tile's vertical
datum remains a verification item. Design geometry continues to use local metres with
+X east, +Z south and the centre elevation as zero.

Acceptance for this package is to create the Blue Ridge reference at 35.6, -82.6 with a
128 m width, inspect its source details, edit and duplicate it, compare its original site,
and reopen it offline. Open that property in Unreal and verify the terrain, orientation and
saved atmosphere. Download cancellation, invalid coverage and stale edits must leave the
property library unchanged. Separately verify local model selection and preview/Apply with
Ollama running on the Windows workstation.

## Recommended next packages

1. **Architectural editing and site placement.** Keep room and garage assemblies as
   persistent editable groups. Add regeneratable dimensions and openings, group selection,
   duplication and transforms, terrain height queries, and explicit ground placement.
   Acceptance is to resize a furnished shell and place it on imported terrain while keeping
   group identity, undo history and both viewports consistent.
2. **Landscape and visual detail.** Add revisioned terrain modifications, paths, planting,
   an asset library for furniture and vehicles, and material maps with scale/orientation.
   Acceptance is a furnished home, garage and landscaped approach that reopens with the same
   materials and supports a continuous walkthrough.
3. **Reference-guided local agent.** Expand scene queries and local-model measurements, then
   attach reference photos and sketches with user-selected design cues. Acceptance is a
   selection-specific material or proportion change that can be previewed and restored.
4. **Long design jobs.** Retain the full brief, plan dependencies, and checkpoint each batch.
   Acceptance is a house/interior/landscape job that can pause for a manual edit and resume
   against the new revision without losing it.

## Agent behavior

- Quick requests resolve the intended object and apply a validated, reversible edit. Show a preview or ask a focused question when the target or result is ambiguous.
- Large requests retain the full brief and references, extract requirements, then give each planning step the relevant constraints and scene context. This lets long requests exceed a single model context window.
- Run long jobs in reviewable batches with visible progress. Save the current revision and unresolved requirements at each checkpoint. On resume, reconcile manual changes before executing dependent work.
- Place large replacements in a new design version. Request confirmation before permanently deleting project data. Surface unsupported requests and missing assets explicitly.
- Benchmark local inference while the Unreal viewport is running on the target Windows workstation with its RTX 4090. Measure edit latency, frame time, VRAM use, and how often plans need correction before choosing a default model and quality preset.

## Verification status for this package

Python tests cover terrain validation, immutable downloads, offline cache reuse, HTTP
preview/save, source persistence, revisions, duplication, Unreal projection, and the local
agent contract. Node tests use DOM/viewport doubles for assembly, agent and site-picker state,
including cancellation and late responses. A live 289-sample Blue Ridge download, cache reuse,
and the Census documentation's example address lookup were checked successfully.

Browser rendering, Windows Unreal navigation on the downloaded site, and real Ollama model
quality remain manual acceptance work. The automated checks do not substitute for those
checks. Keep hosted CI disabled and run the repository's local Python and Node commands.
