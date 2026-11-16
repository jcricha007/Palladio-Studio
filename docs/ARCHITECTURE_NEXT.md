# Architecture and native review series

Base: merged PRs #14–#23 on `main` at `8122b57`. Five focused implementation PRs are
stacked in order. Hosted CI remains skipped; local automated checks and Windows acceptance
are reported separately. Merge status is not evidence of native rendering or model quality.

| Order | Package | Status |
| --- | --- | --- |
| 1 | [#25](https://github.com/jcricha007/Palladio-Studio/pull/25) · Editable wall runs and multiple framed openings | Open |
| 2 | [#26](https://github.com/jcricha007/Palladio-Studio/pull/26) · Foundations fitted beneath raised structures | Open |
| 3 | [#27](https://github.com/jcricha007/Palladio-Studio/pull/27) · Pool and pond layouts with non-solid water | Open |
| 4 | [#28](https://github.com/jcricha007/Palladio-Studio/pull/28) · Shared saved views and native recall | Open |
| 5 | `palladio/architecture-agent-acceptance` · Agent tools, cancellable job planning and acceptance scene | Implemented at this stack tip |

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

## Shared saved views

Saved orbit cameras now carry an optional vertical field of view (15–100 degrees; old views
retain 45 degrees). Browser framing/picking and native payloads use the same pose, converting
metres/Y-up to centimetres/Z-up. Unreal V/Shift+V cycles saved views, and K saves the current
orbit as a new revisioned view. Fly/walk capture is rejected; switch to orbit and look downward
toward its target. Browser reload exposes native saves. Stale saves never overwrite newer edits.
Recall retains the orbit target across scene reloads; Tab or original-site mode resets it.
Changing the camera after recall does not overwrite a saved view. The native camera explicitly
maintains vertical FOV across window sizes using the camera's reference aspect ratio.

Pose, transfer, persistence and HTTP conflict tests run locally. Unreal compilation, actual
framing after window resize and V/K interaction need Windows acceptance. Camera API reference:
[Epic UCameraComponent](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/Camera/UCameraComponent?application_version=5.5).

## Agent tools and repeatable acceptance

The local planner can create keyed wall openings and pool/pond basins, edit/remove existing
openings, set water levels and fit/refit independent foundations. Target IDs must be in its
bounded context; manual validators still reject the whole proposal on any invalid command.
The model cannot invent support offsets, detach walls implicitly or excavate terrain.

Job **Stop planning** stays available while outline/step requests are busy. A step stop is
bound to its request ID, starting version and pending step. It pauses and clears the proposal
whether it arrives before inference or just after that response saves, and rejects a stop
that would affect a later step/session. Browser request cancellation also ignores late
responses from transports that do not honor abort. Outline stops preserve existing drafts.
The model process may continue computing; no GPU/process termination is claimed. Failure
to confirm a pause is explicit and requires refreshing jobs. Apply remains a separate action.

`python -m palladio.acceptance --library NEW_PATH` creates a dedicated review property and
refuses existing files. `scripts/Check-PalladioArchitecture.ps1` verifies the exact clean
commit, runs local checks and the native build, seeds that property and optionally opens both
viewers. See [ARCHITECTURE_ACCEPTANCE.md](ARCHITECTURE_ACCEPTANCE.md) for the walkthrough.
Topology edits keep the edited group selected when a wall span is replaced. Camera controls
stay aligned with reset/recalled views. These integration fixes are part of the final package.

Final local evidence: **125 Python tests and 19 Node suites passed**, including real loopback
HTTP with fake models, request-stop races, atomic tools, transfers, native payloads and fixture
creation. JavaScript syntax, optional browser-script Python syntax and diff checks passed.
The optional rendered smoke workflow now covers the new controls; it has not run here.
PowerShell execution, native compilation/rendering/collision and real-model quality remain
Windows acceptance work. Hosted CI is deliberately skipped.

Windows test compatibility: migration fixtures explicitly close SQLite connections before
temporary-directory cleanup. The UI harness normalizes LF/CRLF in memory and requires a
known startup boundary before evaluating the workspace code. Its new regression runs both
assembly/agent suites against LF and CRLF source; the full 19-suite Node run also passes
against both checkout formats. This verifies line-ending handling, not a native Windows run.
