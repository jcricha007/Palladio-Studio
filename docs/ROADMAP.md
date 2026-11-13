# Palladio Studio build roadmap

Updated 13 November 2026 after [PR #7](https://github.com/jcricha007/Palladio-Studio/pull/7)
merged into `main` at `05e3515`. This roadmap distinguishes implemented capabilities,
observed validation, and planned work. Milestone numbers describe product areas that can
advance together. A merged increment does not close every acceptance item in its area.

## Four-PR stack above PR #8

This branch contains implementation beyond `main`. Merge in dependency order; these entries
are not claims that the work has already merged or passed native acceptance.

| Order | Branch / PR | Delivered in the stack |
| --- | --- | --- |
| 1 | `palladio/assembly-placement` · [#9](https://github.com/jcricha007/Palladio-Studio/pull/9) | Persistent groups, stable part IDs, parameter edits, explicit detach and footprint-aware ground placement. |
| 2 | `palladio/building-landscape` · [#10](https://github.com/jcricha007/Palladio-Studio/pull/10) | Linked stairs, paths/terraces, planters and reversible terrain layers with original-site comparison. |
| 3 | `palladio/assets-finishes` · [#11](https://github.com/jcricha007/Palladio-Studio/pull/11) | Local OBJ/captured asset library, transferable packets, embedded instances, colour and wood finishes. |
| 4 | `palladio/reference-agent` | Revisioned image/cue boards, local vision proposals, context filtering and validated group/finish/terrain agent commands. |

At the stack tip, 62 Python tests and seven Node suites pass locally. The Python tests cover
real loopback HTTP and a fake Ollama runtime; Node uses DOM doubles/pure geometry checks.
A rendered Chromium smoke test is supplied, but startup was blocked by the development
environment's socket permissions. UE 5.7 compilation, visual/collision checks, Windows
PowerShell execution and real-model quality/VRAM remain outstanding. Hosted CI is skipped.

## Product goal

Work on one persistent, highly detailed property at a time, with a library of independent
properties and design alternatives. Start from a described landscape or a real-world
location, then develop the architecture, interiors, grounds, furnishings, vehicles,
materials, lighting, and weather. Manual tools and a local design agent operate on the
same saved property.

For real locations, prioritize a realistic interpretation that preserves the site's
character. Record which terrain and features come from sources and which are inferred or
generated. Keep the starting environment as an immutable baseline for comparison and
restoration. Fine detail and long design briefs remain the goal as the current prototype's
geometry, input limits, and performance mature.

## Implemented on main at PR #7

| Area | Implemented capability | State and remaining work |
| --- | --- | --- |
| **0.1 · Property foundation** | Local SQLite property library, three procedural landscape profiles, editable pavilion and simple elements, browser orbit view, atmosphere controls, original-site comparison, duplication and revision restore. | Foundation implemented in [PR #1](https://github.com/jcricha007/Palladio-Studio/pull/1). Preserve old properties and history as the model expands. |
| **0.2 · Unreal and Windows** | UE 5.7 developer launcher, shared terrain/element projection, fly/orbit/walk navigation, element selection and saved movement. | [PR #2](https://github.com/jcricha007/Palladio-Studio/pull/2) and [PR #3](https://github.com/jcricha007/Palladio-Studio/pull/3) merged. Initial Windows scene load confirmed. Full navigation, collision and imported-terrain acceptance remain open. |
| **0.3 · Real and imagined sites** | Prepared elevation JSON import, U.S. address lookup, coordinates, downloaded terrain preview, source details, immutable download snapshots and offline cache reuse. Saved properties contain their terrain. | Acquisition implemented through [PR #6](https://github.com/jcricha007/Palladio-Studio/pull/6) and [PR #7](https://github.com/jcricha007/Palladio-Studio/pull/7). Terrain modification, richer surroundings and additional import formats remain planned. |
| **0.4 · Architecture and detail** | Configurable room and garage shells with openings, dining and lounge presets, preview/Apply and individual editing of generated pieces. | [PR #4](https://github.com/jcricha007/Palladio-Studio/pull/4) merged. Assemblies currently become independent pieces. Persistent groups, ground placement, richer building tools, detailed assets and materials remain planned. |
| **0.5 · Local agent and references** | Built-in commands, local Ollama model discovery/switching, selection-aware context, validated edit previews, cancellation and revision-checked Apply. | [PR #5](https://github.com/jcricha007/Palladio-Studio/pull/5) is integrated into `main` through PR #7. Real model evaluation, broader scene queries, photo/sketch references and native Unreal agent controls remain open. |
| **0.6 · Long design jobs** | Atomic edit batches and saved revisions provide the underlying persistence mechanisms. | Jobs are planned. Persistent briefs, decomposition, progress, pause/resume and reconciliation with manual edits are not implemented. |

The current connected workflow is to create a site, preview an assembly or agent proposal,
apply it to a saved revision, and open the same property in Unreal. Restore and duplication
support experimentation without replacing the original site.

## Evidence and remaining acceptance

| Check | Recorded result |
| --- | --- |
| Python regression suite for the implementation merged in PR #7 | **37 tests passed.** Covers property persistence, revisions, assemblies, elevation, cache refresh/offline reuse, HTTP preview/save, Unreal scene projection and the local-agent contract. |
| JavaScript state suites for PR #7 | **All three suites passed.** Assembly, agent and site-picker controls use DOM/viewport doubles, including cancellation and late responses. JavaScript syntax and diff checks also passed. |
| Public data services | Live 289-sample USGS download at 35.6, -82.6 with a 128 m site width succeeded, followed by a cache hit. The Census documentation's example address lookup succeeded. |
| Windows Unreal | John confirmed the earlier build compiled and its scene loaded. Later navigation and downloaded-terrain walkthroughs have no recorded acceptance yet. |
| Browser rendering | Pending visual acceptance. The development environment could not launch local Chromium or connect its separate cloud browser to the local server. |
| Real Ollama runtime | Pending installed-model switching, edit quality, latency and VRAM checks alongside Unreal on the Windows workstation. Automated transport tests use a fake runtime. |

The table above preserves the PR #7 evidence. New checks for the four-PR stack are recorded
below and do not imply that its Windows or rendered-browser acceptance has passed.

To close the current user acceptance items:

1. Create the Blue Ridge reference at latitude **35.6**, longitude **-82.6**, width **128 m**.
   Inspect its preview and source details, edit its atmosphere, compare the original site,
   duplicate it, then restart offline and reopen the saved property.
2. Open the same property in Unreal. Check scale, orientation and atmosphere. Verify
   flight, selection-centred orbit, walking on slopes and through a shell doorway, wall
   collision, and a saved element move visible in the browser.
3. With Ollama running locally, choose an installed model, preview a selected-object edit,
   apply it once and restore the prior revision. Check cancellation and switching models.
   Record response quality, latency, frame time and VRAM use before choosing a default model.

Run local checks using the commands in [the README](../README.md#develop). Keep hosted CI
disabled until its use is requested.

## Boundaries recorded at PR #7

- Downloaded sites use a **17 × 17** ground-elevation grid over **20–256 m**. A 128 m site
  has 8 m sample spacing. Prepared JSON imports support odd grids of 3–129 samples per side
  within the same extent limit. The studio's spacing and the source's pixel size are distinct.
- U.S. address matches are approximate. Source tiles and acquisition metadata are retained,
  while the vertical datum needs checking against the source tiles. Parcel boundaries,
  existing buildings, aerial textures and inferred vegetation are not acquired automatically.
- Current architecture and furnishings are schematic geometry. Pieces can be edited, but
  resizing one wall does not resize its former room. Placement neither snaps to the ground
  nor resolves overlaps. Materials are basic swatches and the Unreal atmosphere is preliminary.
- The agent handles bounded, single-turn proposals with up to 12 commands and context for
  up to 40 elements. Photo input, unrestricted whole-property reasoning and long autonomous
  jobs are future capabilities. Preview cancellation ignores late replies but may leave an
  already-started download or model request finishing in the background.

## Package 1 acceptance: persistent assemblies and terrain placement

**Outcome:** create a room or garage on a real site, then resize, move, rotate or duplicate
the whole assembly while preserving its identity, history and matching geometry in both
viewports.

| Work item | Required behaviour |
| --- | --- |
| Persistent assembly model | Store assembly identity, generator parameters and child relationships. Keep generated part identities stable where their roles survive a resize. Open existing properties and revisions with their independent elements intact. |
| Group selection and editing | Select an assembly, inspect its parameters, and preview whole-group transforms, duplication or removal. Define how individual part edits become overrides or detached pieces so regeneration cannot silently erase them. |
| Parametric shell edits | Regenerate room/garage width, depth and height after insertion. Add validated controls for the existing doorway and window openings. Treat stairs, arbitrary roof systems and detailed joinery as subsequent building tools. |
| Ground placement | Query height from the same terrain surface shown by the renderers. Provide explicit placement and vertical offset, with feedback for a footprint intersecting terrain or extending outside coverage. Preserve the site's original terrain. |
| Shared command path | Use the same validated, revision-aware commands for manual controls and agent proposals. Project the result into Unreal and handle its element-move path consistently with group ownership. |
| Compatibility and acceptance | Test old property loading, preview/discard, group identity, member-edit policy, stale revisions, duplication, restore, offline reopen and browser/Unreal agreement. |

Acceptance is a garage placed on the downloaded Blue Ridge site, resized and rotated as
one object, duplicated as an alternative, restored to an earlier revision and reopened
offline. The original terrain remains unchanged and unsupported placement is visible
before Apply. These requirements guided stack increment 1. Code and local regression evidence are now
recorded below; the Windows walkthrough remains open.

## Packages after that

| Order | Package | User-visible result and completion check |
| --- | --- | --- |
| 2 | **Building and landscape tools** | Extend openings, roofs, stairs and room layouts. Add revisioned terrain modifications, paths, drives, planting and water/shoreline treatment. Build a coherent home and approach, then restore the original ground independently of the architecture. Keep source-backed and generated surroundings identifiable. |
| 3 | **Materials, assets and atmosphere** | Add persistent asset references and import for furnishings, fixtures, trees and vehicles. Add texture maps, roughness, material scale/orientation and richer Unreal lighting/weather. Reopen a furnished property with the same assets and finishes, including deliberate wood-grain direction. |
| 4 | **Reference-guided local agent** | Expand scene queries and target resolution, evaluate local models, and attach photos or sketches with chosen design cues. Preview a reference-driven material or proportion change on the intended element and restore it. Surface missing context and unsupported requests. |
| 5 | **Long design jobs** | Retain the complete brief and references, decompose work, track prerequisites and validate each batch. Show progress, checkpoint, pause/resume and reconcile intervening manual edits. Complete a house/interior/landscape brief without losing changes made while paused. |

Each package may be delivered through several focused PRs. Detailed tools should become
available to manual editing before the agent is expected to operate them. Add agent commands
as those tools gain validation and preview support.

## Architecture and delivery rules

- Keep the property model independent of its renderers. Use stable IDs and local metres with
  Y up. For imported sites, +X is east, +Z is south and the centre elevation is local zero.
  Convert to Unreal centimetres and Z up only at the adapter boundary.
- Preserve source metadata and immutable baselines. Store future terrain changes as design
  state so original-site comparison and selective restoration remain possible.
- Validate edits on the active revision, commit each batch atomically and retain restore
  points. Plan compatible schema changes and recovery before adding new persistent structures.
- Keep the local planner replaceable. Manual controls and agent tools share the same command
  contract. Quick edits remain reviewable; long briefs retain requirements outside a single
  model context window and resume against the latest scene revision.
- Develop Windows delivery alongside features: a repeatable fresh-terminal launch, stable
  property storage, useful errors, backups/export, and eventually a packaged application.
  Maintain local regression checks and browser/Unreal acceptance as separate evidence.

The broader walkthrough target is a furnished home, garage and landscaped approach on a
recognizable site, with detailed materials and atmosphere, reliable persistence, and both
manual and agent-driven editing. Closing that target requires the remaining work above.

## Stack increment 1: assembly editing and placement

Implemented above PR #8 on `palladio/assembly-placement`: persistent assembly specifications,
stable part identities, finish/name overrides, explicit detachment, whole-group editing,
copy/removal, parametric openings and triangular-terrain footprint placement. Existing
ungrouped properties are preserved. Native arrow movement addresses group ownership.

Local evidence: 43 Python tests and four Node state suites pass. Windows Unreal compilation
and browser/Unreal visual acceptance remain open. The local agent still uses its existing
allowlist; explicit group tools are exposed to it in the reference-agent increment.

## Stack increment 2: building and landscape tools

Implemented on `palladio/building-landscape` above the assembly increment: linked stairs,
paths/terraces and planters; ordered raise/lower/flatten terrain layers; layer enable/remove;
and original-ground restoration independent of architecture. Both renderers receive the
current and original ground, and procedural trees follow the active surface. Complex roofs,
planting tools and water remain open within this roadmap area.

Local evidence: 48 Python tests and four Node suites pass. Manual browser rendering and
native UE 5.7 compilation, collision refresh and baseline switching remain required.

## Stack increment 3: reusable geometry and finishes

Implemented on `palladio/assets-finishes`: bounded triangulated OBJ import with explicit
units; whole-selection capture; immutable, exportable local asset packets; embedded scene
instances; per-face colours and solid/wood finishes with scale and direction. Browser and
native projections use corresponding geometry. Group finish overrides survive regeneration.

Local evidence: 54 Python tests and six Node suites pass. Native compilation and interactive
asset/finish acceptance remain required. Texture/PBR maps, high-detail asset streaming,
GLTF/FBX import and richer lighting/weather are still future work in the larger milestone.

## Stack increment 4: reference-guided local agent

Implemented on `palladio/reference-agent`: up to six persistent photo/sketch references and
chosen cues, revisioned add/update/remove, bounded local image copies, opt-in vision input,
capability/remote-model checks, name/type context filtering, mesh summaries and explicit
group/layer target scope. The model can propose group parameter changes, placement, copies,
removal, surface finishes and terrain-layer edits through the same validators as manual tools.
The native mesh actor receives its transform after root attachment so placement is explicit.

Limits remain deliberate: one browser-selected image per request (two supported by the API),
up to 12 commands, 40 element excerpts, eight group summaries and twelve terrain layers;
character limits may reduce these further. No arbitrary file tools, photo-derived exact
measurements, automatic saves, native agent panel or autonomous long-job execution.

## Where development goes next

1. Complete the Windows walkthrough of this stack: old-property reopening, group editing,
   terrain restore, imported mesh silhouettes/placement/collision, finishes and reference
   history. Run the optional rendered test and evaluate a real local vision model alongside
   Unreal before choosing a default. Record findings rather than treating merge as acceptance.
2. Deepen building and landscape authoring: connected layouts, roof systems, more useful
   openings, planted vegetation, water and support/overlap feedback. Preserve group identity.
3. Improve material/asset fidelity: PBR/texture maps, asset provenance and streaming budgets,
   richer furnishings/vegetation, and lighting/weather. The current OBJ and coarse wood
   implementation is a foundation, not completion of this larger milestone.
4. Build long design jobs on the revisioned command path: durable briefs/references,
   decomposition, checkpoints, pause/resume and reconciliation after manual edits. Keep
   Windows delivery and backup/export evolving with these capabilities.
