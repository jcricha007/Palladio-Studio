# Designing with the local agent

Select **Local Ollama**, choose the installed model, and describe the design in metres.
Preview shows every command and the resulting geometry. Apply saves the entire batch
as one revision. Invalid commands reject the entire proposal. History can restore an
earlier revision. A response never applies itself.

## Tools available in this upgrade

| Task | Agent capability | Scope |
| --- | --- | --- |
| New building | Create a room, garage or dwelling shell, place it on terrain, optionally fit a gable/hip/shed roof and pier foundation | One `building` command; explicit ground offset; supports require at least 0.6 m clearance |
| Existing architecture | Edit dimensions, placement, materials, doors and windows; duplicate/remove assemblies; fit roofs and refit foundations | Type-specific parameters and visible assembly IDs |
| Openings | Set/remove keyed wall-run openings; convert independent box walls into wall runs | Rooms/garages retain their existing door/window layout and use scalar size controls |
| Independent parts | Detach an assembly, then edit its parts in a later preview | Geometry remains; linked parametric editing is removed |
| Layout | Move, copy, rotate, align, distribute and snap to grid | Element IDs promote to whole linked assemblies and deduplicate them; no collision solver |
| Landscape | Raise/lower/flatten ground, toggle/remove layers, restore all ground layers, plant seeded sets of 1–64 trees/hedges | Planted bases follow terrain edits; architecture does not automatically move |
| Finishes | Apply built-in/saved palettes to selected parts or whole assemblies; capture/remove saved finishes | Removing a preset retains its applied surface finishes |
| Presentation | Set weather/time; create, update or remove saved orbit cameras | Saves a camera, not an image; browser camera recall remains explicit |

New roofs and foundations are separate assemblies. Moving or resizing the host later
does not automatically update them. Pools, ponds, vegetation, furniture and buildings
remain schematic geometry. This upgrade does not add asset downloads, arbitrary code
execution, photorealistic image generation, structural analysis or construction drawings.

The assembly grammar now exposes only fields valid for each kind. In particular,
`openings` belongs only to wall runs: an empty list still intentionally removes all
openings. Garage/room window requests use `window_width`, `window_height` and
`window_sill`. Invalid fields are rejected rather than silently discarded.

## Example prompts

- Create an 8 m by 6 m garage named Workshop at X 0, Z 0, with a gable roof. Place it on the ground.
- Raise Workshop 0.8 m above the terrain and fit a 3 by 2 pier foundation.
- Widen Workshop's existing rear window to 2.4 m, preserving its other dimensions.
- Apply limestone to every part of the selected assembly.
- Plant 12 pines within 8 m of X 20, Z 15, using seed 42.
- Save an approach view looking at Workshop from the southeast.

Use the name/type context filter or select a part when the target is unclear. The
excerpt prioritizes a representative of each assembly before filling it with details,
so a large dwelling is less likely to hide nearby objects. It remains bounded to 40
parts, eight assemblies and twelve terrain layers, with a character budget for scene
records. The model receives available finish palettes, saved cameras and tool guidance.
Whole-group tools require the group's own context, not just an incidental visible child.
Whole-ground reset is offered only when every terrain layer is included.

Each proposal contains at most twelve commands. Use **Design jobs** for longer briefs:
outline the work, review and apply one step, then preview the next against the updated
property. IDs created by a proposal become available only after Apply; `building`
handles its own shell/roof/support dependencies without invented IDs.

Requests now allow 32,768 context tokens for the broader tool set. Repeated target IDs
are omitted from the textual schema description while remaining constrained in the
actual output grammar. Model memory and latency at this setting still require a live
workstation check; models unload after each response as before.

A completed reply containing malformed JSON gets one format-repair attempt against
the same scene, schema and original request. The repaired proposal still goes through
all geometry and context validators. Duplicate JSON keys and nonfinite numbers remain
invalid. Timeouts, remote replies, protocol failures and truncated responses are not
retried. Local weights are checked again before repair; pausing a job still rejects
its late reply. Wrong but valid design proposals are not silently rewritten.

When defaults are requested, the model is instructed to omit optional parameters.
The context includes planting and building-tool defaults, alongside catalog dimensions.
Room and garage opening defaults now come directly from the geometry generator. New
assembly output schemas require explicit width, depth and height, using catalog values
for unspecified dimensions. Building proposals missing any shell dimension are also
rejected server-side, so a height mentioned only in the summary cannot silently become
the catalog height. Shell height and roof rise are documented as separate fields.
These checks do not prove that a model followed every dimension in a natural-language
request; the full-scene acceptance comparison and user review remain necessary.

## Validation

Run the normal suite with `scripts/Validate-Palladio.ps1`. The added tests exercise
the actual geometry, database transactions, persistent job checkpoints, context scopes,
schema isolation, rollback, reopen, stale Apply, and revision restore. Mock transport
tests verify the Ollama request format; they do not demonstrate model reasoning quality.

With the existing local runtime running, use this from the checkout:

```powershell
python -m palladio.model_check --design --model gpt-oss:20b --port 11435
```

This runs three explicit prompts: the garage-window regression, a grounded garage with
roof/supports, and seeded planting. It compares the full requested scene result, checks
that preview saved nothing, and checks Apply against preview, using disposable properties.
It never opens the user's property database. Each case reports its own failure; a valid
JSON response that makes the wrong design or extra edits is a failure. The report is
`.palladio/checks/local-model-design.json`. These three prompts are a focused acceptance
check, not a claim that arbitrary architectural briefs will succeed.

On failure, the report retains returned commands and up to eight field differences
with expected/actual values. JSON failures include parser position and bounded model
response excerpts (at most 6,000 characters per attempt). Recovered JSON attempts are
also recorded. This capture is enabled only for these disposable checks; normal app
requests do not retain response text, and private reasoning is never captured.
