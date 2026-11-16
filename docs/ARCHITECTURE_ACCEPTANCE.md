# Five-PR architecture walkthrough

Use the exact final commit in an isolated worktree. `Check-PalladioArchitecture.ps1`
runs Python/Node regressions, JavaScript syntax and the Unreal editor build, then creates
a **new** `acceptance.sqlite3` beside the report. It refuses existing fixture paths and
dirty/mismatched checkouts. `-Open` launches the browser and Unreal with that fixture on
port 8877. Keep the terminal open; Ctrl+C stops its server. Existing personal libraries
are not opened or copied. Fixtures remain on disk so the same property can be reopened.

`-SkipUnreal` explicitly selects browser-only checks; the report records that native
compilation was not run. `-BrowserSmoke` adds the optional rendered Playwright workflow;
Playwright and Chromium must already be installed. The checker downloads no dependencies
or models, and does not enable hosted CI. Model protocol tests use a fake loopback model.

Record PASS/FAIL with the commit from `report.json`. A compiled target is not proof that
framing, collision or real-model behavior passed. Screenshots and actual observations are
needed for the rows below; no prefilled acceptance result is supplied.

| Check | Action and expected result |
| --- | --- |
| Both viewers | Browser and Unreal open **Architecture review · five PRs** at revision 8. The house has four rooms, a separate gable roof and pad-and-pier supports. Pool, pond and framed wall are visible. |
| Multiple openings | Select a part of **Opening review wall**. In Wall openings choose `view`, change its width to 2.4 m, preview and Apply. `entry` stays unchanged. Try overlapping the openings; the whole preview is rejected and the revision stays unchanged. |
| Native doorway | Press R then V/Shift+V to **Wall doorway**. Press 3 and walk through the door gap. The adjacent wall and window glazing stop movement. Press 1 to fly again. |
| Supports | Select the house, inspect the separate foundation's level top and grounded pads. Lower ground locally by 0.2 m, select a foundation part and preview Refit. Pads move to saved ground; the foundation top and house stay fixed. Use History to restore afterward. Supports do not automatically follow host movement. |
| Water level | Select **Pool collision review**, change water level from 2.2 to 2.0 m, preview and Apply. Capacity decreases. Reload Unreal; the water plane lowers, while basin walls and floor stay fixed. Pond capacity uses its sloping geometry. |
| Water collision | Recall **Pool collision**, then press 3. The capsule lands on the basin floor below the water, not on the water surface. Basin walls stop walking. Press 1 to exit. Water is opaque static geometry; swimming, buoyancy and refraction are not implemented. |
| Shared cameras | Recall all five views with V/Shift+V. Compare the same browser view at the same window aspect ratio. Resize Unreal: vertical framing stays fixed, horizontal coverage changes. Orbit slightly and press K; reload the browser and open the new **Unreal view N**. The target, pose and FOV agree. |
| Save conflicts | Leave Unreal on an old revision, apply a browser edit, then press K. The save conflicts; R reloads and K can save a new view. No earlier browser edit is lost. |
| Built-in job | Refresh jobs, select **Architecture review job**, Start, and preview its first step with Built-in commands. Only Apply saves fog and completes that step. The next step remains pending. |
| Real local model | Select an installed local Ollama model. Preview the second step with context filter `review` so both the wall and pool appear. Inspect the proposed IDs, keyed opening dimensions and pool level before Apply. Repeat once while pressing Stop planning: the job becomes paused, no proposal remains, and no property revision is saved. Resume explicitly. |
| Stop race | Stop while inference is running, wait for its old request to finish, and refresh jobs. No late result should reappear. Stop may leave Ollama computing until its request finishes; the UI does not claim to terminate that process. If pause cannot be confirmed, the error asks you to refresh jobs. |
| Persistence | Close both windows/server, relaunch Start-PalladioStudio.ps1 with `-LibraryPath` from `acceptance.json`, and verify the edited views, water/openings and paused job. Snapshot export/import preserves the scene, but intentionally excludes job history. |

The checker stores `report.json`, `console.txt`, `acceptance.json`, this walkthrough and
the new database together. A failed automated check prevents fixture launch. If Unreal
launch itself fails after compilation, the existing launcher reports the failure and keeps
the browser server open for diagnosis. Record that as a failed native launch.

These are schematic authoring tools, not construction/structural analysis, a water solver,
or a photorealism milestone. The next fidelity work remains detailed assets/PBR, arbitrary
plans, richer terrain/weather, performance measurement and packaged Windows delivery.
