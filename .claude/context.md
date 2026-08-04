---
session: 8
last_updated: 2026-08-04
continue_with: "#11 first - the bug-fix commit (blank description + lying map camera, ~2h, zero open questions). Then #12, which needs Rob's two design calls before any UI is written."
blockers: "#12 needs Rob on two questions: warning vs guard for a water coordinate, and text field vs click-to-drop-a-pin. #3 is a design decision, not code. #7 is MP-only and untestable solo. tests/verify_well.py and _pilot.py's snapshot/restore have never run live - PZ must be ticking, which means Rob at the keyboard."
---

# Head for the Hills! - Project State

## What exists

- `mod/42/media/sandbox-options.txt` - 11 options, `StartingVehicle` and `StartingEquipmentList` declared `type = string`.
- `mod/42/media/lua/client/HeadForTheHills/SandboxPickers.lua` - live vehicle dropdown + searchable equipment multi-select. The wrap-a-vanilla-screen idiom this project reuses.
- `mod/42/media/lua/shared/HeadForTheHills/SpawnScenario.lua` - everything placed at `OnNewGame`. All branches now verified live, including the well's skip-existing branch (session 7, cabin #4).
- `mod/42/media/lua/shared/HeadForTheHills/SpawnRegion.lua` - the "Remote Cabin" starting location, via `OnSpawnRegionsLoaded`. All twelve cabins are Rob's deliberate picks and are **final**.
- `tests/` - `_pilot.py` (shared plumbing: `payload()` never `result["result"]`, `teleport()` for every hop, and `snapshot_options()`/`restore_options()` so a destructive test puts the sandbox vars back), `api_checks.py`, `survey_candidates.py`, `verify_generator.py`, `verify_placement.py`, `verify_equipment.py`, `verify_spawn_region.py`, `verify_well.py`.
- Deployed to `Zomboid/mods/HeadForTheHills` as a directory junction following the checked-out branch. PZ must be quit **to desktop** to reload changed Lua.
- 4 open issues: #3, #7, #11, #12. No open PRs.

## What is decided

- Start-scenario mod, not a mechanics overhaul. Reuse existing map buildings; no TileZed until v2.
- **All twelve cabins stay.** Rob picked them specifically. The spread is the point: 3x3 shed to 20x11 farmhouse, 610 to 2383 tiles from the nearest town. Do not propose trimming.
- Live pickers instead of hardcoded lists, because enum dropdowns are parsed before mod Lua runs.
- Placement rules are Rob's spec. `BUILDING_CLEARANCE = 3`, `VEHICLE_BUILDING_CLEARANCE = 2`.
- Do not start a generator inside `OnNewGame`; re-apply on a later `OnTick`.
- Starting equipment skips anything the player already carries.
- Tests identify the mod's vehicle by key, never by proximity.
- **Custom coordinates are a `clickNext` mutation, not a sandbox option** (#12). Verified from vanilla source in session 7: starting location is chosen *before* sandbox options, `SandboxVars` is only populated on the sandbox screen's PLAY button, and `CharacterCreationProfession.initWorld:1086` reads the exact region object frozen at `MapSpawnSelect:clickNext:644`. A sandbox option and an `OnTick` teleport are both ruled out - see #12, do not revisit.
- **`MapSpawnSelect:createChildren` does not exist.** Wrap `create()` at line 923. The missing method resolves to a no-op stub, so wrapping it loads clean and does nothing visible.
- All public-facing copy runs through `/avoid-ai-writing`. No AI-attribution trailer in commits, ever.

## What is pending

- **#11 (do first).** Blank description panel + a map camera that flies to cabin #1 no matter which of the twelve you get, up to ~4,000 tiles wrong. Both live in shipped code, both verified against vanilla source, zero open questions, ~2h. Uses the same two hooks #12 needs, and repairs the feedback channel #12 depends on.
- **#12 (needs Rob).** Mechanism is settled; the two design questions are not.
- **#3 (needs Rob).** Trait/occupation default loadout alongside the picker.
- **#7.** MP: `ServerSettingsScreen` not hooked.
- **Uncommitted at handoff:** nothing - `tests/verify_well.py` and `_pilot.py`'s snapshot/restore shipped unverified. Run `python tests/verify_well.py --at 9668,8775` with PZ ticking before trusting either.
- **Open questions the review left for Claude** (all cheap, all in #12's thread): does `fillList` re-run on screen re-entry or is it cached; is `MapSpawnSelect.instance` rebuilt or reused on a second pass; does `Events.OnSpawnRegionsLoaded` stack listeners across `ResetLua`.
- Sibling repo: `rob-kingsbury/pz-test-pilot` #1 (false `harness_dead`), #2 (teleport moves nothing), **#3 (a timed-out command stays queued and fires whenever the game next ticks, filed session 7)**.

## Recent sessions

### Session 7 (2026-08-04): Cabin list finalised, two wrong designs killed by reading source
Closed #1: Rob picked all twelve cabins deliberately, so the comment calling the list provisional was corrected rather than the list trimmed. Verified the well's skip-existing branch live at cabin #4, the last untested branch that was reachable. Then two designs for user-entered coordinates died in a row, both by reading vanilla source rather than guessing: a sandbox option cannot work because starting location is chosen before sandbox options, and the replacement plan wrapped `MapSpawnSelect:createChildren`, which does not exist on that class and would have shipped a file that loads clean and does nothing. A three-reviewer pre-flight found the real mechanism - `clickNext` freezes a region reference that `initWorld` reads later - and two live defects on that screen, filed as #11. Filed pz-test-pilot#3 after a timed-out teleport sat queued in `command.txt` and would have fired on tab-back. Corrected a self-contradiction in CLAUDE.md where the tooling table still claimed `teleport` moves the player before throwing.

### Session 6 (2026-08-04): Starting Location shipped, ID card fixed, three test defects
Closed #10, #9 and #2. The teleport guard earned itself immediately: pz-test-pilot's `teleport` never moves the player at all, and `setX`/`setY` reads back correct then snaps back because nothing streams the destination chunk. `teleportTo` works. Built `SpawnRegion.lua` and verified it live end to end - Rob woke inside cabin #2 carrying exactly one ID card. `verify_placement.py` reported PASS on a spawn that placed nothing; fixed, along with a scan that read unloaded squares as empty.

### Session 5 (2026-08-04): PR #8 verified live and merged
Drove PR #8 through a fresh world and a confirmed reload. Fresh-spawn generator came back fuelled, connected and running; well, generator and vehicle all landed on dirt or grass, clear of the building and dry; all three survived a save/reload. Fixed three test defects found by running them. Merged PR #8, closed #6, filed #10.

## To Resume

Paste into a fresh window:

> Continuing Head for the Hills (PZ B42.20 start-scenario mod) at `c:\xampp\htdocs\pz-head-for-the-hills`, session 8. On `main` at the session-7 handoff commit, tree clean. 4 open issues (#3 #7 #11 #12), no open PRs. The mod works end to end: pick "Remote Cabin" and you wake in a cabin with a car, a well and a running generator.
>
> THIS WINDOW:
> 1. **#11 first.** The bug-fix commit: Remote Cabin's description panel renders blank, and the map camera flies to cabin #1 regardless of which of the twelve you actually get. Both verified against vanilla source, zero open questions, ~2h. Wrap `MapSpawnSelect:create()` at line 923 - **not `createChildren`, which does not exist on that class.**
> 2. **#12 needs Rob's two design calls** before any UI: warning vs explicit guard for a coordinate in water, and text field vs click-to-drop-a-pin. The mechanism is settled and written up in the issue; a sandbox option and an `OnTick` teleport are both ruled out, do not revisit them.
> 3. **Cheap and unclaimed:** `python tests/verify_well.py --at 9668,8775` - it shipped unverified because PZ was not ticking at handoff.
> 4. **#3 and #7** only if Rob wants them.
>
> Live testing: quit PZ **to desktop** before testing changed Lua. Drive with `tests/_pilot.py`'s helpers. **The game stops ticking when PZ loses focus**, so `harness_dead` while Rob is tabbed away is a false positive - read `Zomboid/Lua/TestPilot/result.txt` and `log.txt` first. **After any failed command, delete `command.txt` and `command_ready.txt`** from that directory, or it fires when the window regains focus (pz-test-pilot#3).

## Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules + hard-won B42 facts (teleportTo vs setX/setY, unstreamed squares reading as nil, generator startup at world init, ground/water tile tests, `isDoor` stack-dump spam, wells as entities, `StartMonth`, ghost vehicles, `getFileWriter` whitelist, harness result shape and its queued-command hazard, vanilla's spawn ID card, `haveThisKeyId` return type, `getCell():getVehicles()`) |
| `.claude/rules/development-workflow.md` | Git, commit, workflow rules |
| `mod/` | The actual PZ mod (root `mod.info` + `42/`) |
| `tests/_pilot.py` | Shared harness plumbing for every test script |
