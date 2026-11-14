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
