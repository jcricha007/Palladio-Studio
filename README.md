# Palladio Studio

Palladio Studio is a local-first architectural sandbox for creating and revisiting deeply detailed 3D properties. Each project contains one site and its buildings, interiors, landscaping, furnishings, materials, and atmosphere. The long-term application pairs a Windows Unreal Engine viewport with manual editing and a local design agent.

## Run the studio

Use Python 3.11 or newer and a browser with WebGL. From PowerShell:

```powershell
git clone https://github.com/jcricha007/Palladio-Studio.git
Set-Location Palladio-Studio
py -m palladio
```

On macOS or Linux, run `python3 -m palladio` from the repository. If the browser does not open automatically, visit [http://127.0.0.1:8765](http://127.0.0.1:8765). Stop the app with Ctrl+C in the terminal. It runs locally with Python's standard library and requires no packages, model downloads, or API keys.

1. Create a property and describe a landscape. Try **a wooded hillside with a clearing in the pines**, **a coastal bluff above the ocean**, or **an open meadow**. Leave the starter pavilion enabled to begin with editable architecture.
2. Drag in the viewport to orbit, Shift+drag to pan, and scroll to zoom. Select an element in the scene list or the viewport to change its size, position, rotation, or material.
3. Change the weather or time in the inspector, or enter a supported prompt such as **set weather to fog**, **set time to 17:30**, **add a wall**, or **use oak** with an element selected. Review the proposed change and click **Apply**.
4. Switch to **Original site** to see the generated terrain and initial atmosphere. Restore an earlier design from **History** or duplicate the property to try a separate design.
5. Close and relaunch the app to reopen the property. Committed edits are saved as revisions in `.palladio/properties.sqlite3` relative to the launch directory. Use `--library PATH` to choose a different database and `--port PORT` if 8765 is occupied.

## Run the Unreal viewport preview on Windows

Use Unreal Engine 5.7 and a Visual Studio C++ toolchain with the Windows SDK. Start the Python workspace from this checkout, open a saved property or create one with the starter pavilion, and leave the server running.

In a second PowerShell window at the repository root, launch the viewport with your most recently updated property:

```powershell
$Property = Invoke-RestMethod 'http://127.0.0.1:8765/api/properties' | Select-Object -First 1
if (-not $Property) { throw 'Create a saved property in the browser first.' }
& .\scripts\Launch-PalladioUnreal.ps1 -UnrealRoot 'C:\Program Files\Epic Games\UE_5.7' -PropertyId $Property.id
```

The launcher compiles the Unreal editor target and starts it in a game window. Pass the same `-Port` as the Python server if you changed the default.

| Control | Action |
| --- | --- |
| 1 | Free flight. WASD moves, the mouse looks around, and Q/E descends or climbs. |
| 2 | Orbit the selected element or the site origin. Move the mouse to orbit and zoom with scroll or W/S. |
| 3 | Walk at eye level. Palladio looks for a clear surface below the camera and falls back to the site entrance. WASD moves and the mouse looks around. |
| Tab | Select the next pavilion element |
| Arrow keys | Move the selected element 0.5 m along the property axes and save a revision |
| B | Toggle the original site and the current design |
| R | Reload the latest saved revision |

For a round-trip check, select an element, move it once, and verify the new position and revision in the browser after reopening the property. Close and relaunch Unreal with the same ID to check persistence there. If another client edits the property first, the server rejects the stale move. Press **R** to load the new revision before trying again.

For the Windows navigation check:

1. In **Fly**, move with WASD, look around with the mouse, and test Q/E.
2. Press **2**, then **Tab**. Orbit the newly selected element and zoom in and out. Press **B** and verify the orbit moves to the original site center.
3. Switch back to the design and fly over open ground by the pavilion entrance. Press **3**. Walk through the open entrance and into a wall to check that the wall stops movement. Walk outside onto sloping terrain, then press **1** to fly again.
4. Move an element while orbiting it. The orbit should follow it after the save and the browser should show the new revision.

The preview uses basic material colors and simple sunlight and fog. Richer weather and a packaged Windows build are follow-up work.

## Current scope

The studio includes procedural landscapes, imported and downloaded elevation, a WebGL orbit viewport, editable architectural pieces and four assemblies, material swatches, atmosphere controls, property duplication, and revision history. The Unreal developer preview opens the same saved properties and commits element moves to the same history. Built-in commands and an optional local Ollama adapter propose edits through the shared command interface. Detailed materials and assets, persistent parametric assemblies, visual references, terrain editing, and autonomous design jobs remain on the roadmap.

## Develop

```powershell
py -m unittest discover -s tests -v
node tests/test_assembly_ui.cjs
node tests/test_agent_ui.cjs
node tests/test_site_ui.cjs
```

| Path | Responsibility |
| --- | --- |
| `palladio/scene.py` | Procedural site generation, element definitions, and validated scene commands |
| `palladio/store.py` | Local property library, immutable baselines, and transactional revisions |
| `palladio/agent.py` | Built-in deterministic prompt adapter |
| `palladio/local_agent.py` | Local Ollama transport, planner contract, bounded context and strict proposal validation |
| `palladio/terrain.py` | Elevation-grid and source-metadata validation |
| `palladio/sites.py` | U.S. address lookup, USGS elevation sampling, and immutable download cache |
| `palladio/__main__.py` | Loopback application server and JSON interface |
| `palladio/web/` | Property workspace, inspector, and WebGL renderer |
| `palladio/unreal.py` | Scene projection from local metres and Y up into Unreal centimetres and Z up |
| `unreal/` | Native viewport, navigation, and revision-aware element moves |

[Design roadmap](docs/ROADMAP.md)

## Build a room, garage, or furnished space

The **Assemblies** inspector adds configurable room and garage shells, a dining set,
and a lounge set. Start with a blank property to avoid overlapping the starter pavilion.

1. Choose an assembly and set its width, depth, height, position, rotation and material.
2. Click **Preview assembly**. The added geometry is temporary until **Apply**; **Discard**
   returns to the saved property. Changing a field or property also clears the proposal.
3. Apply once to save all generated pieces in one revision. Each piece then appears in
   the scene list and can be edited or removed individually using the existing inspector.
4. Press **R** in the Unreal preview to load the saved pieces. The same IDs, positions,
   dimensions and materials are projected into Unreal. Use history to restore the entire
   addition, or duplicate the property before experimenting.

Try `add a room`, `add a garage`, `add a dining set`, or `add a lounge set` in the prompt
field for default-size previews. These are deterministic commands, not a connected AI model.

Shell width/depth describe the outside walls, and height is the clear wall height above a
0.15 m slab. Position Y is the slab bottom. Roofs overhang 0.2 m on each side. The front
(+Z before rotation) has an open doorway, the rear has a glazed window opening. The garage
entry is 2.8 × 2.5 m. Furniture width/depth describes its footprint; height is its tallest part.
Placement does **not** snap to terrain or avoid existing objects. Use the flat site origin
or set the elevation deliberately. Generated pieces are independent after creation; changing
one does not regenerate the assembly. These schematic box models do not establish structural,
accessibility, planning, energy, or building-code compliance.

Developer verification:

```powershell
py -m unittest discover -s tests -v
node tests/test_assembly_ui.cjs
```

The Node check uses a small DOM/viewport test double to check preview state and edit flows.
It is not a substitute for browser rendering or Windows Unreal acceptance.

## Create a property from a real U.S. location

1. Choose **New property → Real U.S. location** and name the property. Enter latitude and
   longitude, or use **Look up address** and explicitly select a matching U.S. street address.
   Check the coordinates before proceeding. Address matches are approximate.
2. Set the site width from 20 to 256 metres and click **Preview terrain**. Try latitude
   `35.6`, longitude `-82.6`, width `128` for a Blue Ridge reference site. Orbit the preview
   and inspect its elevation range and source details.
3. Click **Create property** to save that exact grid as the original site. Changing the
   coordinates or width clears the preview and requires another download or cache lookup.
4. Add architecture using the existing tools. Use **Site source** in the inspector to see
   the recorded coordinates, sample spacing, source tiles, and acquisition time. Open the
   same property in Unreal using the Windows launcher above.
5. Restart Palladio without a network connection and reopen the saved property. Its terrain
   and source details live in the property database and need no further downloads.

Address lookup sends the address to the [U.S. Census geocoder](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html).
Terrain preview sends coordinates to the [USGS 3DEP elevation service](https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer).
Neither service requires an API key. Downloaded terrain uses a 17 × 17 grid in a local
metre-based frame. A 128 m site has 8 m sample spacing. Source pixel resolution and the
studio's sample spacing are separate quantities. The source tile names and service-reported
pixel sizes are retained. The vertical datum must be verified against the listed source
tiles before using heights for measured design work.

Downloads are cached beside the database, by default in `.palladio/properties-sites`.
Repeating a preview for the same coordinates and width reuses the cache. **Download fresh
elevation** acquires a new snapshot while preserving any previously reviewed snapshot.
Previewing creates no property. **Cancel request** ignores a late reply, though the server
may finish caching the download. Missing or invalid coverage produces an error without
saving a partial property. This increment provides bare ground relief. Buildings, parcel
boundaries, aerial textures, vegetation inference, and direct GeoTIFF import remain future work.

For Windows acceptance, create the Blue Ridge reference above, edit its atmosphere, compare
**Original site**, duplicate it, and reopen it after restarting offline. Check the same
property in Unreal. Also preview a location and cancel before creating it, confirming that
the property list is unchanged. Run the Python and Node checks from **Develop** before
testing the live provider or viewport.

## Import an elevation grid

Choose **New property → Import elevation grid** and upload a prepared JSON file. Try
[`examples/elevation-grid.json`](examples/elevation-grid.json) first. It contains synthetic
elevations for testing the workflow. After saving, the property is available in both
viewports through the usual launch commands.

Use an odd square grid of 3–129 samples per side with uniform spacing in metres and a
20–256 m span. Write elevations in metres, row by row from north to south, with columns
running west to east. Record the centre latitude and longitude in decimal degrees and
identify the source dataset and vertical datum. The centre sample becomes local zero
height, with +X east and +Z south in the studio. Source metadata and original relief are
saved with the property. The import expects a grid already projected onto a local
metre-based plane.

Imported properties start with bare terrain. Place buildings manually using the local
height of the ground. Use **Real U.S. location** for direct elevation downloads. Direct
GeoTIFF import and inferred vegetation and surroundings are later steps.

## Local agent and in-app model switching

The **Agent** panel keeps **Built-in commands** available without any AI runtime. Choose
**Local Ollama** to use a separately installed, running Ollama server on this computer.
Palladio does not install Ollama, download models, send prompts to a hosted API, or store keys.
Install a chat model yourself using [Ollama's documentation](https://docs.ollama.com/quickstart).
For a strict offline runtime, disable Ollama cloud features (`OLLAMA_NO_CLOUD=1`) and restart
Ollama; see [Ollama's FAQ](https://docs.ollama.com/faq). Palladio additionally rejects cloud
names/remote aliases and requires local weight metadata before sending scene context.

1. Start Palladio normally and open a property. Choose **Local Ollama**, click **Refresh
   models**, and explicitly choose an installed model. Switch models in the same selector
   whenever you want; the last local model choice is remembered by this browser.
2. Select a scene element and try `Make the selected wall 4 metres wide and use oak`, or
   try `Add a 6 by 8 metre garage at x 15, z 0; leave existing objects alone`.
3. Click **Preview request**. Read the proposal, inspect its validated commands and temporary
   scene, then **Apply** or **Discard**. A response with no commands is informational and
   cannot be applied. Unsupported or invalid plans fail without saving anything.
4. Confirm Apply advances History once. Restore the previous revision to undo the whole
   batch. In the separate Unreal viewport, press **R** to load the committed result.
5. Change provider, model, prompt, selection or property to discard a pending proposal.
   **Cancel** discards the browser request and prevents a late result from being applied;
   it does not guarantee the model runtime stops generating immediately.

The connection is fixed to `127.0.0.1:11434`; use `py -m palladio --ollama-port 11435`
for another local port. There is intentionally no arbitrary remote endpoint field.
An unavailable runtime leaves manual editing and Built-in commands usable. Only one model
request runs at a time; retry after the prior request finishes if the app reports busy.
The transport uses a 120-second socket inactivity timeout, not an absolute job deadline.

### What this increment actually does

A replaceable planner receives the prompt, current revision, selection, environment,
material/assembly catalogs, and a bounded scene excerpt (up to 40 elements, selected first,
then nearby). It returns schema-constrained JSON, not executable code. Every command is
checked against the allowlist and existing scene validators on a private copy. Only explicit
Apply uses the existing revision-checked transaction. A concurrent edit invalidates the
proposal rather than overwriting it. Existing-object edits can target only IDs included in
the supplied excerpt. Full-scene reasoning is not promised; context is character-bounded,
not token-counted, so a runtime may still truncate an unusually large/non-ASCII request.

Supported commands: add/update/remove simple elements, add the four existing assemblies,
and change atmosphere. A proposal can contain at most 12 commands. Newly added objects
cannot be referred to by ID later in the same proposal. Model-generated geometry uses the
same schematic assets as manual editing, not photorealistic generation. No images, shell
execution, arbitrary Python, filesystem tools, automatic saves, model installation, autonomous
jobs, or native Unreal agent panel are included. Browser model selection does not change the
renderer. A model can still misunderstand intent, so inspect the preview before applying.

No default model is imposed. Gemma/Ministral candidates can be compared after installing
compatible Ollama models; quality, latency and VRAM alongside Unreal need measurement on the
Windows workstation. The adapter requests model unloading after each reply (`keep_alive: 0`)
to avoid keeping switched models resident, at the cost of cold-start latency. That does not
guarantee a model fits in available VRAM during generation.

Developer checks (no hosted CI required):

```powershell
py -m unittest discover -s tests -v
node tests/test_assembly_ui.cjs
node tests/test_agent_ui.cjs
```

Agent tests use a fake loopback Ollama server to verify model switching, wire payloads,
remote-model rejection, malformed output, stale revisions, atomic edits, timeout errors and
no-save previews. DOM tests cover controls and late-response cancellation. These tests do
not benchmark real model quality, Windows/Unreal performance, or browser rendering.
