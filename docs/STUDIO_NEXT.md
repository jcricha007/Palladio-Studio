# Studio development series after PR #12

Base: `main` at `adbcfd0`. Each increment targets the preceding branch. Merge in order;
retarget successors to main after their base merges. These are implementations awaiting
review, not assertions of Windows or real-model acceptance. Commits skip hosted CI.

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
