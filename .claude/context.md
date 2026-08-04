---
session: 6
last_updated: 2026-08-04
continue_with: "#10 (port the teleport guard into survey_candidates.py), then #1 (survey candidate cabins in a live world)"
blockers: "#2 is blocked on #1 producing real coordinates. #1 needs a live throwaway world."
---

# Head for the Hills! - Project State

## What exists

- `mod/42/media/sandbox-options.txt` - 11 options, including `StartingVehicle` and `StartingEquipmentList` declared `type = string`.
- `mod/42/media/lua/client/HeadForTheHills/SandboxPickers.lua` - live vehicle dropdown + searchable equipment multi-select. Verified in a live game.
- `mod/42/media/lua/shared/HeadForTheHills/SpawnScenario.lua` - applies the settings at character spawn. **Fully verified live as of session 5**: equipment, vehicle, well, generator (both branches), zombie radius, season, placement rules, and survival across a save/reload.
- `tests/_pilot.py` (shared harness plumbing - **use its `payload()`, never `result["result"]`**), `tests/api_checks.py`, `tests/survey_candidates.py` (#1 screening, see #10), `tests/verify_generator.py` (spawn/existing/persist), `tests/verify_placement.py` (ground, water, building gap, key-matched vehicle, equipment dump).
- Deployed to `Zomboid/mods/HeadForTheHills` as a directory junction. **The junction follows the checked-out branch.** `main` now carries every fix, so staying on `main` deploys verified code. PZ must be quit **to desktop** to reload changed Lua.
- 6 open issues: #1, #2, #3, #7, #9, #10. No open PRs.

## What is decided

- Start-scenario mod, not a mechanics overhaul. Reuse existing map buildings; no TileZed.
- **Live pickers instead of hardcoded lists.** Enum dropdowns are parsed before mod Lua runs, so the option is `type = string` with a wrapped `SandboxOptionsScreen:createControlForSetting`. Detail in CLAUDE.md.
- Equipment is a player-chosen multi-select, not a fixed trait kit.
- Zombie buffer uses our own tile radius and forces vanilla `ZombieLore.PlayerSpawnZombieRemoval` to 4.
- Spawn logic is MP-shaped: `shared/` + `if isClient() then return end`. Unverified on a real server.
- **Placement rules (Rob's spec, session 4):** well and generator need bare dirt or grass and a gap from the building; the vehicle needs a gap from the building and never water; the well and generator may not be adjacent. `BUILDING_CLEARANCE = 3` and `VEHICLE_BUILDING_CLEARANCE = 2` are Claude's numbers, single constants for easy retuning.
- **Do not start a generator inside `OnNewGame`.** The write is discarded. Re-apply on a later `OnTick`. Evidence in CLAUDE.md.
- **#2 hooks `OnSpawnRegionsLoaded`, it does not ship a `spawnregions.lua`.** `getSpawnRegionsAux()` only reads a map's file when `getWorld():getMap()` has no `;` in it, and that name is semicolon-joined once extra maps load (Rob runs MoreMapsB42). `api_checks.py` probes both.
- **Tests identify the mod's vehicle by key, not proximity.** Matching `vehicle:getKeyId()` against the player's keys is the only exact test; a map vehicle parked closer otherwise gets graded in its place.
- All public-facing copy runs through `/avoid-ai-writing`. No AI-attribution trailer in commits.

## What is pending

- **#10 (do first, it gates #1).** `survey_candidates.py` teleports between candidates and never reads the reply. pz-test-pilot's `teleport` is broken on B42.20: it moves the player and *then* throws. Port the warn-and-confirm guard from `verify_generator.py`'s `teleport()`.
- **#1.** Run `python tests/survey_candidates.py` in a throwaway world, then apply judgement on drive time to town. Its `result["result"]` bug is fixed but has never been exercised against a real world.
- **#2.** Blocked on #1: the region needs real cabin coordinates.
- **#9. Diagnosed, fix not written.** Vanilla `SpawnItems.lua` grants `Base.IDcard` to every new character unconditionally, so the mod granting one too makes two. The picker is fine. Fix is a skip-if-already-carried guard on the equipment loop in `SpawnScenario.lua`, general rather than ID-card specific, since `Base.Passport` and anything another mod grants collide the same way.
- **#7.** MP: `ServerSettingsScreen` not hooked.
- **#3.** Whether a trait/occupation default loadout is wanted alongside the picker.
- Sibling repo: `rob-kingsbury/pz-test-pilot#1` filed for the false `harness_dead`. The broken `teleport` deserves a second one there.

## Recent sessions

### Session 5 (2026-08-04): PR #8 verified live and merged
Drove the whole of PR #8 through a fresh world and a confirmed reload. Fresh-spawn generator came back fuelled to its cap, connected and running, which is the bug the PR was written for; well, generator and vehicle all landed on dirt or grass, clear of the building and dry; all three survived a save/reload. Fixed three test defects found by running them: `check_running` demanded exact-cap fuel and so failed on a generator burning fuel because it was running, `teleport()` ignored a broken command's reply, and `verify_placement.py` graded whichever vehicle was nearest (the neighbour's van) instead of ours. Key-matching the vehicle needed a second fix because `haveThisKeyId` returns the Key item, not a boolean. Diagnosed #9 from vanilla source rather than from a live repro: vanilla issues an ID card to everyone, which corrects a wrong claim carried in this file. Merged PR #8, closed #6, filed #10.

### Session 4 (2026-08-03): Generator root cause, placement rewrite, harness bug
Verified the existing-generator branch live. The fresh-spawn branch failed, and the cause took four eliminations by measurement: the sandbox option was a real `true`; `StartMonth=4` proved `applySeason` read `Season` in that same event; the identical creation sequence works a moment later; and re-firing `OnNewGame` passes in a loaded world. What survives is `MOGenerator.lua` replacing our object during a map-object pass. Fixed by re-applying on a later `OnTick`. Rob rejected the placement quality, so the rules were rewritten to his spec using vanilla's own ground classifier and water flag. Also caught that both test scripts read `result["result"]` when the router answers `{status, data:{result}}`. Killed 234 Java stack dumps per world start by field-testing `isDoor` instead of guarding with `pcall`.

### Session 3 (2026-08-03): SpawnScenario verified and fixed in a live world
Drove `SpawnScenario.lua` through two throwaway worlds. Verified starting equipment, vehicle spawn with condition and fuel, the car key, well construction and detection, zombie clear, and season. Fixed four measured defects: a well sprite that exists nowhere, placements jamming against the building (which produced chunk-orphaned ghost vehicles), `StartMonth` being consumed at world creation, and the existing-generator branch skipping instead of starting a dead one. Closed #4 and #5.

## To Resume

Paste into a fresh window:

> Continuing Head for the Hills (PZ B42.20 start-scenario mod) at `c:\xampp\htdocs\pz-head-for-the-hills`, session 6. On `main` at the session-5 handoff commit, tree clean. 6 open issues (#1 #2 #3 #7 #9 #10), no open PRs. PR #8 is merged, so `main` now carries the verified generator fix and placement rewrite.
>
> THIS WINDOW:
> 1. **#10 first, it gates #1.** `survey_candidates.py` teleports between candidates and never reads the reply, but pz-test-pilot's `teleport` is broken on B42.20: it moves the player and then throws `Object tried to call nil in teleport`. Port the warn-and-confirm guard from `verify_generator.py`'s `teleport()`.
> 2. **#1.** Fresh throwaway world, then `python tests/survey_candidates.py`. Cut the 12 candidates to 2-3 on drive-time judgement.
> 3. **#2** once #1 has real coordinates. It hooks `OnSpawnRegionsLoaded` rather than shipping a `spawnregions.lua` - see "What is decided".
> 4. **#9** if there is time: a skip-if-already-carried guard on the equipment loop in `SpawnScenario.lua`. Vanilla already grants everyone an ID card.
>
> Live testing: quit PZ **to desktop** before rolling a world, because the mods junction deploys whatever is checked out. Drive with `tests/_pilot.py`'s helpers, never `result["result"]`. IPC files are `.txt`. **`harness_dead` is usually a false positive** when PZ is unfocused; read `Zomboid/Lua/TestPilot/result.txt` and `log.txt` before believing it.

## Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules + hard-won B42 facts (generator startup at world init, ground/water tile tests, `isDoor` stack-dump spam, wells as entities, `StartMonth`, ghost vehicles, `getFileWriter` whitelist, harness result shape, vanilla's spawn ID card, `haveThisKeyId` return type, `getCell():getVehicles()`, the broken `teleport`) |
| `.claude/rules/development-workflow.md` | Git, commit, workflow rules |
| `.claude/afk-log.md` | Session-4 AFK decisions and what was parked (gitignored) |
| `mod/` | The actual PZ mod (root `mod.info` + `42/`) |
| `tests/_pilot.py` | Shared harness plumbing for every test script |
