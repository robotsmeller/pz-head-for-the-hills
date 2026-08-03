---
project: pz-head-for-the-hills
session: 5
last_updated: 2026-08-03
continue_with: "Verify PR #8 in a fresh throwaway world (verify_generator.py spawn, verify_placement.py), then merge it, then run survey_candidates.py for #1."
blockers: "PR #8 is unverified in a live game. #2 is blocked on #1."
---

# Head for the Hills! - Project State

## What exists

- `mod/42/media/sandbox-options.txt` - 11 options, including `StartingVehicle` and `StartingEquipmentList` declared `type = string`.
- `mod/42/media/lua/client/HeadForTheHills/SandboxPickers.lua` - live vehicle dropdown + searchable equipment multi-select. **Verified in a live game.**
- `mod/42/media/lua/shared/HeadForTheHills/SpawnScenario.lua` - applies the settings at character spawn. Equipment, vehicle, well, zombie radius, season and the existing-generator branch are all verified live. The session-4 rewrite on top of that is **unverified**, see pending.
- `tests/_pilot.py` (shared harness plumbing - **use its `payload()`, never `result["result"]`**), `tests/api_checks.py` (12 checks), `tests/survey_candidates.py` (#1 screening), `tests/verify_generator.py` (spawn/existing/persist), `tests/verify_placement.py` (ground, water, building gap, equipment-list dump).
- Deployed to `Zomboid/mods/HeadForTheHills` as a directory junction. **The junction follows the checked-out branch**, so `main` deploys pre-fix code and `session4-generator-and-placement` deploys the fix. PZ must be quit **to desktop** to reload changed Lua.
- 6 open issues: #1, #2, #3, #6, #7, #9. One open PR: #8.

## What is decided

- Start-scenario mod, not a mechanics overhaul. Reuse existing map buildings; no TileZed.
- **Live pickers instead of hardcoded lists.** Enum dropdowns are parsed before mod Lua runs, so the option is `type = string` with a wrapped `SandboxOptionsScreen:createControlForSetting`. Detail in CLAUDE.md.
- Equipment is a player-chosen multi-select, not a fixed trait kit.
- Zombie buffer uses our own tile radius and forces vanilla `ZombieLore.PlayerSpawnZombieRemoval` to 4.
- Spawn logic is MP-shaped: `shared/` + `if isClient() then return end`. Unverified on a real server.
- **Placement rules (Rob's spec, session 4):** well and generator need bare dirt or grass and a gap from the building; the vehicle needs a gap from the building and never water; the well and generator may not be adjacent. `BUILDING_CLEARANCE = 3` and `VEHICLE_BUILDING_CLEARANCE = 2` are Claude's numbers, not Rob's, and are single constants for easy retuning.
- **Do not start a generator inside `OnNewGame`.** The write is discarded. Re-apply on a later `OnTick`. Full evidence in CLAUDE.md.
- **#2 hooks `OnSpawnRegionsLoaded`, it does not ship a `spawnregions.lua`.** `getSpawnRegionsAux()` only reads a map's file when `getWorld():getMap()` has no `;` in it, and that name is semicolon-joined once extra maps load (Rob runs MoreMapsB42). The event returns the same table it passes, so a handler appends a fully formed `{ name, points }` region. `api_checks.py` probes both before anything is built on it.
- All public-facing copy runs through `/avoid-ai-writing`. No AI-attribution trailer in commits.

## What is pending

- **PR #8 (top priority).** Generator startup fix + placement rewrite + test tooling, on branch `session4-generator-and-placement`. Syntax-checked with `luac -p`; **the world-creation path has not been re-tested since the fix**. Verify, then merge. The fix prints `generator was not running after world init` when it catches the bug, which also confirms the diagnosis.
- **#6.** Existing-generator branch passed live. Fresh-spawn branch is what PR #8 fixes and what verification closes.
- **#1.** Run `python tests/survey_candidates.py` in a throwaway world, then apply judgement on drive time to town. The result-shape bug that would have scored all 12 OUT is fixed.
- **#2.** Blocked on #1: the region needs real cabin coordinates.
- **#9.** Two ID cards at spawn. Vanilla issues none at spawn and the picker cannot emit a duplicate, so it is likely two distinct ID-card items selected. `verify_placement.py` prints the saved list as its first output.
- **#7.** MP: `ServerSettingsScreen` not hooked.
- **#3.** Whether a trait/occupation default loadout is wanted alongside the picker.
- Sibling repo: `rob-kingsbury/pz-test-pilot#1` filed for the false `harness_dead`.

## Recent sessions

### Session 4 (2026-08-03): Generator root cause, placement rewrite, harness bug
Verified the existing-generator branch live: re-fired `OnNewGame` against a dead generator, which fuelled it to the cap, connected, activated, and added no second one. The fresh-spawn branch failed, and the cause took four eliminations by measurement rather than reasoning: the sandbox option is a real `true` in both `SandboxVars` and `getSandboxOptions()`; `StartMonth=4` proved `applySeason` read `Season` in that same event; the identical creation sequence works a moment later (`0/10` to `10/10 conn=true act=true`); and `triggerEvent("OnNewGame", ...)` passes in a loaded world. What survives is `MOGenerator.lua` replacing our object during a map-object pass, since it builds exactly the observed state and registers on that sprite. Fixed by re-applying on a later `OnTick`, which holds regardless of that diagnosis. Rob rejected the placement quality, so the rules were rewritten to his spec using vanilla's own ground classifier and water flag. Also caught, before any live time was spent on it, that both test scripts read `result["result"]` when the router answers `{status, data:{result}}` - `survey_candidates.py` would have scored all 12 candidates OUT and looked like a map problem. Killed 234 Java stack dumps per world start by field-testing `isDoor` instead of guarding with `pcall`.

### Session 3 (2026-08-03): SpawnScenario verified and fixed in a live world
Drove `SpawnScenario.lua` through two throwaway worlds. Verified: starting equipment, vehicle spawn with condition and fuel, the car key in the keyring, well construction and detection, zombie clear, and season. Fixed four measured defects: a well sprite that exists nowhere, placements searching from radius 1 and jamming against the building (which produced chunk-orphaned ghost vehicles), `StartMonth` being consumed at world creation, and the existing-generator branch skipping instead of starting a dead one. Closed #4 and #5.

### Session 2 (2026-08-03): Sandbox options, live pickers, B42.20 breakage
Built the sandbox page and both live pickers, verified the round-trip through a real save, and wrote the spawn logic. Found and fixed an undocumented B42.20 breaking change: `getFileWriter` now enforces a file-extension whitelist, which had silently killed pz-test-pilot. Fixed there and added a rule to pz-mod-checker.

## To Resume

Paste into a fresh window:

> Continuing Head for the Hills (PZ B42.20 start-scenario mod) at `c:\xampp\htdocs\pz-head-for-the-hills`, session 5. Checked out on branch `session4-generator-and-placement`, tip is the "Session 4 handoff" commit, tree clean. 6 open issues (#1 #2 #3 #6 #7 #9), one open PR (#8). `main` is at 03fde5d and does **not** have the session-4 fixes.
>
> PR #8 fixes the generator failing to start at world creation and rewrites placement to Rob's spec. It is syntax-checked but **never run in a live world**.
>
> THIS WINDOW:
> 1. Fresh throwaway world - quit PZ **to desktop** first, and stay on this branch, because the mods junction deploys whatever is checked out. Then `python tests/verify_generator.py spawn` and `python tests/verify_placement.py`. The latter prints the starting equipment list, which answers #9.
> 2. Merge PR #8 once that passes.
> 3. `python tests/survey_candidates.py` for #1, then cut to 2-3 on drive-time judgement.
> 4. Then #2, which hooks `OnSpawnRegionsLoaded` rather than shipping a `spawnregions.lua` - see "What is decided".
>
> pz-test-pilot: drive with `tests/_pilot.py`'s helpers, never `result["result"]`. IPC files are `.txt`. **`harness_dead` is usually a false positive** when PZ is unfocused; read `Zomboid/Lua/TestPilot/result.txt` before believing it.

## Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules + hard-won B42 facts (generator startup at world init, ground/water tile tests, `isDoor` stack-dump spam, wells as entities, `StartMonth`, ghost vehicles, `getFileWriter` whitelist, harness result shape) |
| `.claude/rules/development-workflow.md` | Git, commit, workflow rules |
| `.claude/afk-log.md` | Session-4 AFK decisions and what was parked (gitignored) |
| `mod/` | The actual PZ mod (root `mod.info` + `42/`) |
| `tests/_pilot.py` | Shared harness plumbing for every test script |
