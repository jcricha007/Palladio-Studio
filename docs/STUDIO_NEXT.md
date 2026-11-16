# Studio development series after PR #12

Merged into `main` at `8122b57` on 15 November 2026 (U.S. Eastern). The merged tree
matches the final stack. The evidence and remaining workstation acceptance below are
preserved; the next series is in [ARCHITECTURE_NEXT.md](ARCHITECTURE_NEXT.md).

| Order | PR | Upgrade | Base |
| --- | --- | --- | --- |
| 1 | [#14](https://github.com/jcricha007/Palladio-Studio/pull/14) | Property transfer | main |
| 2 | [#15](https://github.com/jcricha007/Palladio-Studio/pull/15) | Layout tools | #14 |
| 3 | [#16](https://github.com/jcricha007/Palladio-Studio/pull/16) | Roof systems | #15 |
| 4 | [#17](https://github.com/jcricha007/Palladio-Studio/pull/17) | Connected rooms | #16 |
| 5 | [#18](https://github.com/jcricha007/Palladio-Studio/pull/18) | Planted landscape | #17 |
| 6 | [#19](https://github.com/jcricha007/Palladio-Studio/pull/19) | Finish palettes | #18 |
| 7 | [#20](https://github.com/jcricha007/Palladio-Studio/pull/20) | Saved views/export | #19 |
| 8 | [#21](https://github.com/jcricha007/Palladio-Studio/pull/21) | Persistent jobs | #20 |
| 9 | [#22](https://github.com/jcricha007/Palladio-Studio/pull/22) | Agent job review | #21 |
| 10 | [#23](https://github.com/jcricha007/Palladio-Studio/pull/23) | Launch, backup and acceptance | #22 |

## 1 · Portable property snapshots

Export the current saved design and original site from **Transfer property**. The versioned,
checksummed JSON embeds placed meshes and reference images. Import always creates an
independent property with a fresh history; it never overwrites an existing property.
The importer validates geometry, linked identities, generated parts, terrain layers and
references before starting its transaction. Limit: 20 MB. Prior history, unused asset
packets and local runtime configuration are not part of a snapshot.

Acceptance: export a furnished property, import it into a second library, resize a linked
assembly, compare original terrain and reopen offline. Windows/browser acceptance remains
pending; regression evidence is recorded in each PR.

## 2 · Layout sets and measurements

Add scene selections to a layout set. Linked members resolve to their whole assembly once.
Preview moving, copying, rotating about the first object's origin, aligning or distributing
origins, or snapping them to a metre grid. Measurement reports world-axis bounds of actual
mesh/box geometry and, for two objects, origin distance. All edits remain atomic and
revisioned. These are positioning aids; alignment does not create joints or solve collisions.

## 3 · Parametric roof envelopes

Gable, hip and shed roofs are closed triangle assemblies with editable rise, dimensions,
rotation and overhang. Fit a new roof to a selected room/garage shell, or place it manually.
The shell's flat cap remains as a ceiling. The fitted roof is an independent linked assembly;
include both in a layout set to move them together. These envelopes do not model framing,
roof drainage, loads or attic interiors. Both renderers use the same generated mesh.

## 4 · Connected room layouts

The Connected rooms assembly creates a one-to-four by one-to-four rectangular room grid.
Shared partitions have one doorway on every adjoining room edge; the entrance is aligned
with the front-left room. Stable room/partition roles retain compatible overrides through
resizing. Show room areas for clear dimensions excluding walls. Add a fitted roof separately.
This is a schematic layout generator, not arbitrary floor-plan drafting or code compliance.

## 5 · Planted landscape and terrain anchors

Plant individual pines, broadleaf trees or hedges, or preview a repeatable seeded planting
set of up to 64 objects. The Planted landscape panel anchors their bases to the current
terrain, including later layer changes and original-ground restoration. Moves/copies retain
explicit offsets; detach converts plants to independent pieces. Source/procedural vegetation
is unchanged. Shapes are schematic and planting overlaps are left visible for review.
Trees added through the generic assembly catalog remain unanchored until placed manually.

## 6 · Finish palettes and surface patterns

Save selected finishes as named property presets and preview applying a preset to a part
or its entire owning assembly. Overrides survive regeneration and portable export. Removing
a preset leaves applied copies intact. Wood, stone, tile and brick use matching per-face
procedural colour sampling in both renderers. These are coarse triangle-colour patterns,
not texture maps or physically based materials; mesh density controls their visible detail.

## 7 · Saved views and presentation export

Store up to 24 named orbit cameras per property, revisit them in the browser, or replace
and restore them through normal revision history. Snapshots include the views. Download
PNG of the current viewport (including unsaved previews), or export saved placed geometry
and optional terrain as OBJ in metres, Y up. OBJ omits finishes, source vegetation and water,
and is capped at 100,000 triangles. Saved cameras do not currently control the Unreal camera.

## 8 · Persistent design briefs and manual checkpoints

Create jobs with a retained brief (up to 64,000 characters) and 1–32 explicit ordered steps.
Start, pause, resume or cancel them; record each manual completion against the property
revision reviewed, with a required note. Job versions prevent two sessions advancing the
same step. Jobs survive restart and are separate from scene undo/restore. This package does
not run a model or edit geometry automatically. Up to 40 jobs per property are retained.

The database migrates from schema 1 to 2, preserving properties and revisions. Jobs live in
the same SQLite database but are deliberately excluded from portable design snapshots and
duplicated properties. Back up the database before upgrading; older builds reject schema 2.

## 9 · Agent job outlines and reviewed execution

Ask the selected installed local model to suggest an editable ordered outline, then save
it as a job. Preview one current step using the selected provider/model, object, context
filter and optional reference. The local planner sees the retained brief and nearby progress;
its scene context remains bounded. Review the proposed geometry and explicitly Apply. The
property revision and job checkpoint commit in one SQLite transaction. No next step runs
automatically. Pausing/cancelling invalidates late model results; manual scene edits require
fresh planning. Saved proposals survive restart and can be reviewed or discarded.

Automatic outlines and model job context accept briefs up to 16,000 characters (manual job
storage supports 64,000). Each step accepts 8,000 characters and 12 validated scene commands.
Longer work must be split into explicit steps/jobs; this is not unlimited autonomous execution.
Built-in commands support their existing small grammar; full instructions need a local model.
Model quality, wall time and GPU usage still require workstation acceptance.

## 10 · Windows launch, backup and acceptance

`Start-PalladioStudio.ps1` runs from any terminal directory, selects Python 3.11+, preserves
the checkout's library path, backs up before schema migration and refuses occupied ports.
Optional `-WithUnreal` discovers UE 5.7, waits for this checkout/library's health response,
then builds/opens the selected or most recently updated property. If Unreal fails, the
browser server stays available. Ctrl+C stops only the Python server started by this script.
The standalone Unreal launcher also discovers the engine and a saved property by default.

The read-only health endpoint and browser diagnostics identify the running build/library.
The diagnostics CLI provides consistent SQLite backups, including job records; it does not
migrate while inspecting. Validation captures checkout identity, console output and JSON
results, with opt-in native build and rendered browser checks. No packages are installed.
The supplied browser workflow covers the new authoring tools, saved views, exports and jobs.

At the series tip, 100 Python regressions and 14 Node suites pass locally, plus JavaScript
syntax and diff checks. Python includes combined export/import/native projection, migration,
backup and job transaction tests. Node uses DOM doubles/pure geometry. PowerShell execution,
UE 5.7 compilation/collision/visuals, rendered-browser/PNG acceptance, and real Ollama quality,
latency and GPU coexistence remain pending on the Windows workstation. Hosted CI is skipped.
