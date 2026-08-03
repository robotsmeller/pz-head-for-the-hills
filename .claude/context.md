---
project: pz-head-for-the-hills
session: 4
last_updated: 2026-08-03
continue_with: "#6 - exercise both generator paths in a live spawn, then run tests/survey_candidates.py to cut #1 down to 2-3."
blockers: "none"
---

# Head for the Hills! - Project State

## What exists

- `mod/42/media/sandbox-options.txt` - 11 options, including `StartingVehicle` and `StartingEquipmentList` declared `type = string`.
- `mod/42/media/lua/client/HeadForTheHills/SandboxPickers.lua` - live vehicle dropdown + searchable equipment multi-select. **Verified in a live game.**
- `mod/42/media/lua/shared/HeadForTheHills/SpawnScenario.lua` - applies the settings at character spawn. **Verified end to end in a live throwaway world (session 3)** except the two generator paths, see pending.
- `tests/api_checks.py` (10 live API checks) and `tests/survey_candidates.py` (screens the 12 candidate coordinates for #1).
- Deployed to `Zomboid/mods/HeadForTheHills` as a directory junction. Edits are live on disk, but **PZ must be quit to desktop** to reload changed Lua.
- 5 open issues: #1, #2, #3, #6, #7.

## What is decided

- Start-scenario mod, not a mechanics overhaul. Reuse existing map buildings; no TileZed.
- **Live pickers instead of hardcoded lists.** Enum dropdowns are parsed before mod Lua runs, so the option is `type = string` with a wrapped `SandboxOptionsScreen:createControlForSetting`. Detail in CLAUDE.md.
- Equipment is a player-chosen multi-select, not a fixed trait kit.
- Zombie buffer uses our own tile radius and forces vanilla `ZombieLore.PlayerSpawnZombieRemoval` to 4.
- Spawn logic is MP-shaped: `shared/` + `if isClient() then return end`. Unverified on a real server.
- **The player always spawns inside the cabin**, so every placement must clear the building footprint. Vehicle searches 6-16 tiles needing 5x5 clear (3x3 fallback, else skip the car); well and generator search 2-10 tiles, rejecting any square beside a door. Spawning a car at radius 1 produced chunk-orphaned ghost vehicles.
- Mod-added vehicle parts attach after `addVehicle` returns and keep their own condition. Judged not worth a deferred second pass.
- All public-facing copy runs through `/avoid-ai-writing`. No AI-attribution trailer in commits.

## What is pending

- **#6 (top priority).** Everything else in its checklist is verified. Still unproven: `spawnGenerator`'s **fuelled-and-running** behaviour has never executed inside `OnNewGame`, on either branch (starting the cabin's existing generator, or fuelling a freshly spawned one). Needs one throwaway world. Also unproven at spawn: the skip-because-a-well-exists path, though the detection predicate itself is verified against a real well.
- **#1.** Run `python tests/survey_candidates.py` in a throwaway world to screen the 12 coordinates on building, well, generator and placement, then apply human judgement on drive time to town. Criteria in the issue comments are current as of session 3.
- **#2.** spawnregions.lua + spawnpoints.lua. Nothing exists yet; the player spawns wherever vanilla puts them.
- **#7.** MP: `ServerSettingsScreen` not hooked, so dedicated-server admins get raw text boxes.
- **#3.** Whether a trait/occupation default loadout is wanted alongside the picker.
- Sibling repo: `rob-kingsbury/pz-test-pilot#1` filed for the false `harness_dead`.

## Recent sessions

### Session 3 (2026-08-03): SpawnScenario verified and fixed in a live world
Drove `SpawnScenario.lua` through two throwaway worlds via pz-test-pilot. Verified working: starting equipment (three items including a modded one), vehicle spawn with condition and fuel, the car key landing in the keyring, well construction, well detection, zombie clear (nearest zombie 42 tiles against a radius of 20), and season. Fixed four real defects, each measured rather than inferred: the well used a sprite that exists nowhere and its detection matched a substring that could never fire; every placement searched from radius 1 and jammed against the building, which spawned the car through the porch and produced **chunk-orphaned ghost vehicles** (confirmed ours by A/B with the mod disabled, confirmed fixed by driving afterwards); `SandboxVars.StartMonth` is consumed at world creation so the season write was a no-op; and the existing-generator branch skipped instead of starting the cabin's dead one. Also corrected a wrong conclusion of my own: generator modData fuel *does* carry across the constructor, and `setFuel(100)` clamps *down* to a cap of 10 that reads as 100%. Added `tests/survey_candidates.py` for #1, catching a silent-truncation bug in it before shipping. Closed #4 and #5.

### Session 2 (2026-08-03): Sandbox options, live pickers, B42.20 breakage
Built the sandbox page and both live pickers, verified the round-trip through a real save, and wrote the spawn logic. Found and fixed an undocumented B42.20 breaking change: `getFileWriter` now enforces a file-extension whitelist, which had silently killed pz-test-pilot. Fixed there and added a rule to pz-mod-checker.

### Session 1 (2026-08-03): Research + scaffold
Confirmed spawn regions, zombie density, starting kits and vehicle spawns are achievable in one mod with no custom map. Scaffolded the repo, pushed, filed #1-#5.

## To Resume

Paste into a fresh window:

> Continuing Head for the Hills (PZ B42.20 start-scenario mod) at `c:\xampp\htdocs\pz-head-for-the-hills`, session 4. `main` tip is the "Session 3 handoff" commit, tree clean, 5 open issues (#1 #2 #3 #6 #7). Session 3's work landed in e0dc8a1, 88f72f4, 93ff97d, fe0784d.
>
> `SpawnScenario.lua` is now **verified in a live world** for equipment, vehicle, well, zombie radius and season. One gap remains.
>
> THIS WINDOW:
> 1. **#6:** exercise the generator in a live spawn. Both branches are unproven: starting the cabin's existing generator, and fuelling a freshly spawned one. Expect fuel 100% and a "Turn off" option in the context menu. Needs a fresh throwaway world, and PZ must be quit **to desktop** first or the edited Lua will not load.
> 2. **#1:** run `python tests/survey_candidates.py` in that world to screen the 12 coordinates, then cut to 2-3 on drive-time judgement.
> 3. Then **#2**, the spawnregions/spawnpoints pair, so the player actually starts at a cabin.
>
> pz-test-pilot: drive with `python scripts/cmd.py run_lua "..."`. Its IPC files are `.txt`, not `.json`. **`harness_dead` is usually a false positive** when PZ is unfocused; read `Zomboid/Lua/TestPilot/result.txt` before believing it.

## Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules + hard-won B42 facts (wells as entities, StartMonth, generator fuel cap, ghost vehicles, getFileWriter whitelist) |
| `.claude/rules/development-workflow.md` | Git, commit, workflow rules |
| `mod/` | The actual PZ mod (root `mod.info` + `42/`) |
| `tests/api_checks.py` | Live API verification driven through pz-test-pilot |
| `tests/survey_candidates.py` | Candidate cabin screening for #1 |
