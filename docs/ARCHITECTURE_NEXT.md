# Architecture and native review series

Base: merged PRs #14–#23 on `main` at `8122b57`. Five focused implementation PRs are
stacked in order. Hosted CI remains skipped; local automated checks and Windows acceptance
are reported separately. Merge status is not evidence of native rendering or model quality.

| Order | Package | Status |
| --- | --- | --- |
| 1 | Editable wall runs and multiple framed openings | Implemented in this increment |
| 2 | Foundations fitted beneath raised structures | Next |
| 3 | Pool and pond layouts with non-solid water | Next |
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
