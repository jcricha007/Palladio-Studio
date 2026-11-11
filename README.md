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

## Current scope

The 0.1 foundation includes three procedural site profiles, a WebGL orbit viewport, basic box-based architectural elements, material swatches, simple atmosphere controls, project duplication, and revision history. Prompts use a small rule-based adapter that exercises the same validated command interface as the manual tools. Real-world terrain imports, Unreal rendering, walkthroughs, visual references, and local-model planning are roadmap milestones.

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

[Design roadmap](docs/ROADMAP.md)
