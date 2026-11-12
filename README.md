# Palladio Studio

Palladio Studio is a local-first architectural sandbox for creating and revisiting deeply detailed 3D properties. Each project contains one site and its buildings, interiors, landscaping, furnishings, materials, and atmosphere. The long-term application pairs a Windows Unreal Engine viewport with manual editing and a local design agent.

## Run the first build

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
| WASD and mouse | Fly around the property |
| Tab | Select the next pavilion element |
| Arrow keys | Move the selected element 0.5 m along the property axes and save a revision |
| B | Toggle the original site and the current design |
| R | Reload the latest saved revision |

For a round-trip check, select an element, move it once, and verify the new position and revision in the browser after reopening the property. Close and relaunch Unreal with the same ID to check persistence there. If another client edits the property first, the server rejects the stale move. Press **R** to load the new revision before trying again.

The preview uses free-flight navigation, basic material colors, and simple sunlight and fog. Walk and orbit controls, richer weather, and a packaged Windows build are follow-up work.

## Current scope

The 0.1 foundation includes three procedural site profiles, a WebGL orbit viewport, basic box-based architectural elements, material swatches, simple atmosphere controls, project duplication, and revision history. Prompts use a small rule-based adapter that exercises the same validated command interface as the manual tools. The Unreal developer preview opens the same saved properties and commits element moves to the same revision history. Real-world terrain imports, visual references, and local-model planning are later milestones.

## Develop

```powershell
py -m unittest discover -s tests -v
```

| Path | Responsibility |
| --- | --- |
| `palladio/scene.py` | Procedural site generation, element definitions, and validated scene commands |
| `palladio/store.py` | Local property library, immutable baselines, and transactional revisions |
| `palladio/agent.py` | Prompt-to-command preview adapter |
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
