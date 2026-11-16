# Architecture and native review series

Base: merged PRs #14–#23 on `main` at `8122b57`. Five focused implementation PRs are
stacked in order. Hosted CI remains skipped; local automated checks and Windows acceptance
are reported separately. Merge status is not evidence of native rendering or model quality.

| Order | Package | Status |
| --- | --- | --- |
| 1 | Editable wall runs and multiple framed openings | Implemented in this increment |
| 2 | Foundations fitted beneath raised structures | Implemented |
| 3 | Pool and pond layouts with non-solid water | Implemented |
| 4 | Shared saved views and native recall | Next |
| 5 | Agent tools, cancellable job planning and acceptance scene | Next |

## Wall runs and openings

Create **Wall with openings** from the assembly builder. Select a part, then use **Wall
openings** to add, resize, move or remove up to 16 doors/windows. Dimensions are rough
openings, including the frame; doors have no leaf. Stable opening keys retain identities
and finish overrides while dimensions change. Wall piers/lintels are real geometry, so gaps
are represented in both viewports. Overlapping openings, undersized piers and invalid
heights are rejected atomically.

Independent box walls can be converted, preserving transform/material/finish in a linked
wall-run specification. Existing room/grid walls remain linked to their original generators;
detach explicitly before converting one. Conversion does not infer perpendicular wall axes,
merge corners or create a new room polygon. Framing is schematic, not load-bearing design.

## Fitted foundations

Preview raising a selected room/garage/dwelling/terrace above the highest terrain point and
fitting a separate pad-and-pier foundation underneath, or fit at its existing height. Each
pad uses the highest ground within its own rotated footprint. Beams meet one level host
underside; original ground and host geometry remain unchanged except the explicitly previewed
raise. Refit a selected foundation after terrain or placement changes; warnings flag stale
pad bases. Stable grid roles retain compatible finishes and identities.

Supports are independent from the host. Move/copy them together using layout sets; refit
supports afterward. Changing terrain does not silently move the building. These schematic
pads, piers and beams do not determine excavation, soils, load paths or member capacity.

## Pool and pond layouts

Create rectangular pools with walls/coping or 32-sided elliptical ponds with sloping banks.
Edit basin dimensions and water level; capacity uses the same inner geometry, reporting
surface area, depth and litres. Water surface IDs remain stable through edits. Property
snapshots preserve geometry and collision flags. Native water surfaces use no collision;
solid basin beds and walls retain it. Capturing a mixed solid/water group as one mesh is
rejected; detached non-solid water captures preserve their collision setting.

Water is static opaque colour, without refraction, waves, fluid physics or swimming. Basins
do not cut the terrain: raise them above it or edit terrain explicitly. Capacity is geometric,
not surveyed storage or hydraulic analysis. Rendered/native collision acceptance is pending.
