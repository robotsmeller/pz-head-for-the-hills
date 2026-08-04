---
session: 7
last_updated: 2026-08-04
continue_with: "#1 (cut the cabin list to the real picks, then trim CABINS in SpawnRegion.lua), then #3 (starting kit by trait/occupation, needs Rob's design call)"
blockers: "#1 needs Rob's judgement on drive time to town - the automated screen passes all 12 and eliminates nothing. #3 is a design decision, not code. #7 is MP-only and untestable solo."
---

# Head for the Hills! - Project State

## What exists

- `mod/42/media/sandbox-options.txt` - 11 options, including `StartingVehicle` and `StartingEquipmentList` declared `type = string`.
- `mod/42/media/lua/client/HeadForTheHills/SandboxPickers.lua` - live vehicle dropdown + searchable equipment multi-select.
- `mod/42/media/lua/shared/HeadForTheHills/SpawnScenario.lua` - applies the settings at character spawn. Equipment, vehicle, well, generator (both branches), zombie radius, season, placement rules and save/reload survival all verified live.
- `mod/42/media/lua/shared/HeadForTheHills/SpawnRegion.lua` - **new, session 6.** Adds a "Remote Cabin" entry to Starting Location by hooking `OnSpawnRegionsLoaded`. Verified live: comes back once per call, 12 cabins under all 25 professions, and a character made through the screen woke indoors at cabin #2. **The `CABINS` list is provisional** and still holds a farmhouse, an army store and a 3x3 shed.
- `tests/` - `_pilot.py` (shared plumbing; use `payload()`, never `result["result"]`, and its `teleport()` for every hop), `api_checks.py`, `survey_candidates.py`, `verify_generator.py`, `verify_placement.py`, `verify_equipment.py` (#9), `verify_spawn_region.py` (#2).
- Deployed to `Zomboid/mods/HeadForTheHills` as a directory junction following the checked-out branch. PZ must be quit **to desktop** to reload changed Lua.
- 3 open issues: #1, #3, #7. No open PRs.

## What is decided

- Start-scenario mod, not a mechanics overhaul. Reuse existing map buildings; no TileZed.
- **Live pickers instead of hardcoded lists.** Enum dropdowns are parsed before mod Lua runs, so the option is `type = string` with a wrapped `SandboxOptionsScreen:createControlForSetting`.
- Zombie buffer uses our own tile radius and forces vanilla `ZombieLore.PlayerSpawnZombieRemoval` to 4. It is a one-shot clear at the spawn square and does **not** follow the player, so it protects nothing during teleport-driven testing - set Zombie Population to None for that.
- Spawn logic is MP-shaped: `shared/` + `if isClient() then return end`. Unverified on a real server.
- **Placement rules (Rob's spec):** well and generator need bare dirt or grass and a gap from the building; the vehicle needs a gap and never water; well and generator may not be adjacent. `BUILDING_CLEARANCE = 3`, `VEHICLE_BUILDING_CLEARANCE = 2`.
- **Do not start a generator inside `OnNewGame`.** The write is discarded; re-apply on a later `OnTick`.
- **#2 hooks `OnSpawnRegionsLoaded` rather than shipping `spawnregions.lua`**, because `getSpawnRegionsAux()` only reads a map's file when `getWorld():getMap()` has no `;` in it, and that name is semicolon-joined once extra maps load (Rob runs MoreMapsB42). Points are keyed by **every** profession, since vanilla's per-town files key by profession and a region defining one key sends everyone else elsewhere.
- **Starting equipment skips anything the player already carries.** Vanilla grants an ID card to everyone, plus a badge to rangers/police/firefighters and a pager to doctors, and vanilla Lua loads first. The guard is general, not ID-card specific.
- Tests identify the mod's vehicle by key, never by proximity.
- All public-facing copy runs through `/avoid-ai-writing`. No AI-attribution trailer in commits.

## What is pending

- **#1 (needs Rob).** All 12 candidates pass automated screening, so it eliminates nothing; the cut is cabin size and drive time to town. Sizes measured: #1 8x8/2rooms, #3 5x8/3, #4 8x5/3 + existing well, #7 11x5/3, #8 5x5/1, #9 6x7/1, #11 6x6/2 are cabin-scale; #2 #5 #6 #10 are houses or a farmhouse; #12 is a 3x3 shed. Claude's pick was #1, #4, #11. Rob's view: the shortlist is "just a starting canvas", there are probably a dozen more cabins, revisit once the mod works. **Once cut, trim `CABINS` in `SpawnRegion.lua` to match** - nothing else changes.
- **#3 (needs Rob).** Whether a trait/occupation default loadout is wanted alongside the picker.
- **#7.** MP: `ServerSettingsScreen` not hooked.
- **Never exercised at a cabin:** the adopt-existing branch. Cabin #4 has a map well, so spawning there should adopt it rather than dig a second. Two-minute check with `verify_generator.py existing --at 9668,8775`.
- Rob reported some of his other mods showing as inactive after a restart. Parked, unexamined, may or may not touch this mod.
- Sibling repo: `rob-kingsbury/pz-test-pilot#1` (false `harness_dead`) and **#2 (teleport moves nothing, filed session 6)**.

## Recent sessions

### Session 6 (2026-08-04): Starting Location shipped, ID card fixed, three test defects
Closed #10, #9 and #2. The teleport guard ported into `survey_candidates.py` immediately earned itself: the first live run showed pz-test-pilot's `teleport` never moves the player at all, which corrects the note claiming it moved first and threw afterwards. `setX`/`setY` was no better - it reads back correct and snaps back a second later, because nothing asks for the destination chunk. `teleportTo` works, and with it the survey ran all 12 candidates. They all passed, because the building test demanded the exact tile be inside a footprint while every shortlist coordinate lands in the yard 3-10 tiles off. Fixed, and the survey now reports building size, so the shortlist is finally readable. Built `SpawnRegion.lua` for #2 and verified it live end to end: Rob created a character through the Starting Location screen, woke inside cabin #2, and carried exactly one ID card. `verify_placement.py` then reported PASS on a spawn where it found nothing at all - two defects, an absent object only ever being a note, and a scan of a half-streamed cell reading unloaded squares as empty. Both fixed; the corrected run passed on real data.

### Session 5 (2026-08-04): PR #8 verified live and merged
Drove PR #8 through a fresh world and a confirmed reload. Fresh-spawn generator came back fuelled, connected and running; well, generator and vehicle all landed on dirt or grass, clear of the building and dry; all three survived a save/reload. Fixed three test defects found by running them. Diagnosed #9 from vanilla source. Merged PR #8, closed #6, filed #10.

### Session 4 (2026-08-03): Generator root cause, placement rewrite, harness bug
Verified the existing-generator branch live. The fresh-spawn branch failed; four eliminations by measurement left `MOGenerator.lua` replacing our object during a map-object pass, fixed by re-applying on a later `OnTick`. Rob rejected the placement quality, so the rules were rewritten to his spec using vanilla's own ground classifier and water flag. Killed 234 Java stack dumps per world start by field-testing `isDoor` instead of guarding with `pcall`.

## To Resume

Paste into a fresh window:

> Continuing Head for the Hills (PZ B42.20 start-scenario mod) at `c:\xampp\htdocs\pz-head-for-the-hills`, session 7. On `main` at the session-6 handoff commit, tree clean. 3 open issues (#1 #3 #7), no open PRs. The mod now works end to end: pick "Remote Cabin" on the new-game screen and you wake in a cabin with a car, a well and a running generator.
>
> THIS WINDOW:
> 1. **#1 needs Rob's call, not code.** All 12 candidates pass screening, so the cut is cabin size and drive time. Sizes and Claude's pick (#1, #4, #11) are in "What is pending". Once Rob picks, trim `CABINS` in `SpawnRegion.lua` to match.
> 2. **#3 needs Rob's design call** on a trait/occupation loadout alongside the picker.
> 3. **Cheap and unclaimed:** the adopt-existing branch has never run at a cabin. `python tests/verify_generator.py existing --at 9668,8775` at cabin #4, which has a map well.
> 4. **#7** MP `ServerSettingsScreen`, only if Rob wants it.
>
> Live testing: quit PZ **to desktop** before testing changed Lua. Drive with `tests/_pilot.py`'s helpers - `payload()` not `result["result"]`, and its `teleport()` for every hop, because pz-test-pilot's own teleport command moves nothing on B42.20. **The game stops ticking when PZ loses focus**, so a `harness_dead` reported while Rob is tabbed away is a false positive - read `Zomboid/Lua/TestPilot/result.txt` and `log.txt` first, and confirm PZ is actually running before blaming the harness.

## Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules + hard-won B42 facts (teleportTo vs setX/setY, unstreamed squares reading as nil, generator startup at world init, ground/water tile tests, `isDoor` stack-dump spam, wells as entities, `StartMonth`, ghost vehicles, `getFileWriter` whitelist, harness result shape, vanilla's spawn ID card, `haveThisKeyId` return type, `getCell():getVehicles()`) |
| `.claude/rules/development-workflow.md` | Git, commit, workflow rules |
| `mod/` | The actual PZ mod (root `mod.info` + `42/`) |
| `tests/_pilot.py` | Shared harness plumbing for every test script |
