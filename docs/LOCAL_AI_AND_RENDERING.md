# Local AI and the refreshed Studio

The Studio now groups tools into Edit, Build, Site, Finish and Present. Design assistant
settings expand above a multiline prompt. Focus view hides both side panels without
changing the property or discarding a proposal. Tab navigation supports arrow keys,
Home and End. The tool tab and browser render quality are remembered locally.

## Windows local model setup

The reference workstation was probed on November 15, 2026: Intel i7-14700K, 64 GB RAM,
RTX 4090 with 24 GB VRAM (about 21.9 GiB free during the probe), and about 575 GiB free
on C:. The selected text planner is OpenAI's `gpt-oss:20b`, about 14 GB in Ollama's
MXFP4 distribution. This is a hardware fit assessment, not a measured inference result.

From a normal PowerShell terminal at this checkout:

```powershell
& .\scripts\Start-PalladioAI.ps1
```

This explicitly requested setup downloads the official portable Ollama v0.40.16 release,
checks its published SHA-256, and installs the model. It runs a separate, loopback-only
server on port **11435**, with cloud features disabled, one concurrent request, and one
loaded model. Binaries and weights live under `%LOCALAPPDATA%\Palladio`, outside the
checkout. It does not replace an existing Ollama installation, alter PATH, configure
startup, or stop another runtime. Rerun the same command to reuse the installed weights.
An interrupted model pull can resume. An occupied unmanaged port requires another
`-OllamaPort` value. The managed runtime remains running after Studio closes.

The setup verifies one real schema-constrained weather proposal against a disposable
property before launching Studio. The result is in `.palladio/checks/local-model.json`.
The check confirms the requested scene result and that preview did not save anything;
it is not a benchmark of architectural reasoning or image interpretation. If it fails,
the script reports the failure instead of claiming the model is ready.

Use `-SetupOnly` to install/check without opening Studio. Use `-LibraryPath` to open an
existing property database from another checkout. Keep that original database path when
changing checkouts. Do not run two Studio servers against it during acceptance.

Open **Design assistant > Local Ollama > Refresh models > gpt-oss:20b**. The browser
still requires an explicit model selection. Preview, Apply, Discard and revision checks
are unchanged. This text-only model cannot read reference images; leave **Use selected
image** unchecked unless selecting a separately installed vision-capable model.

Requests use 32,768 context tokens for the expanded design-tool grammar and scene context,
and unload the model after the reply (`keep_alive: 0`). ID values stay in the constrained
output grammar but are listed only once in the prompt context to reduce repetition.
Models reporting a low reasoning level use it with a 4,096-token output budget, so
reasoning does not consume the entire JSON budget. Older gpt-oss metadata is recognized
by architecture. Model weights still occupy VRAM during inference, so pause heavy native
render work if GPU memory becomes tight. No simultaneous model/Unreal benchmark has run.

## Render quality

| Browser mode | Maximum device-pixel ratio | Shadow map | Filtering |
| --- | --- | --- | --- |
| Draft | 1 | Off | Direct light and material response |
| Studio | 1.5 | 1024 px | 3 × 3 shadow filtering |
| Presentation | 2 | 2048 px | 5 × 5 shadow filtering |

The actual map size is capped by the GPU's texture/renderbuffer limit. If framebuffer
allocation fails, material lighting remains available. Shadows are camera-centred and
finite in extent. Lighting uses world-space normals, moving sun direction, warmer low
sun, sky fill, roughness highlights, tone mapping and depth haze. Geometry, saved finish
colours, cameras, measurements and PNG/OBJ export remain authoritative. Quality is a
viewport preference, not a scene revision. The renderer draws on interaction instead
of continuously using the GPU while idle.

The native Unreal project enables DX12, hardware ray tracing when supported, Lumen GI
and reflections, virtual shadow maps, volumetric fog, and bounded exposure for lux-scale
sunlight. Rebuild from this checkout. First launch may need substantial shader compilation:

```powershell
& .\scripts\Start-PalladioAI.ps1 -WithUnreal -UnrealRoot 'C:\Program Files\Epic Games\UE_5.7'
```

This is a lighting foundation. Browser glass and water are still opaque shaded surfaces;
trees and furniture remain schematic. Neither viewport now provides production-quality
architectural assets, texture/normal-map libraries, physically accurate glass, water
simulation, or progressive path-traced output. Those are the next realism milestones.

## Validation and outstanding acceptance

Run `scripts/Validate-Palladio.ps1` for the Python and Node suites. With Playwright and
Chromium installed, add `-BrowserSmoke`; add `-BuildUnreal` for a native build. The browser
smoke exercises all quality modes, GL errors, panel focus, the new tool tabs, and the
existing preview/apply, model, camera and export flows. Inspect a noon, sunset, fog and
night view, switch quality, export PNG, and reopen the saved property in Unreal.

During implementation, 104 Python tests and all 20 Node suites passed. The unchanged
baseline had 27 errors and two failures across 26 tests caused by blocked loopback
connections; those 26 tests were excluded from the offline run, not counted as passes.
The same environment blocked model downloads and browser automation; the native build
launcher reported a lock and was stopped before compilation. Real installation, rendered browser acceptance,
native compilation and side-by-side GPU performance must be verified on the workstation;
do not treat mock transport tests as evidence that the model is installed.

Sources: [Ollama Windows](https://docs.ollama.com/windows),
[model details](https://ollama.com/library/gpt-oss:20b),
[thinking controls](https://docs.ollama.com/capabilities/thinking),
[pinned release](https://github.com/ollama/ollama/releases/tag/v0.40.16),
[Unreal Lumen](https://dev.epicgames.com/documentation/en-us/unreal-engine/lumen-global-illumination-and-reflections-in-unreal-engine).
