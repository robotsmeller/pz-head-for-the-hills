---
session: 10
last_updated: 2026-08-04
continue_with: "#13 - the zombie buffer's option now goes to 100 but the clear only removes zombies loaded in the cell, so a player setting 100 may be getting far less. Measure where the count stops growing, then cap the option or say so in the tooltip. #14 can share the same evening: find water near one of the twelve cabins off the map site, and run one start from it."
blockers: "Every remaining live check needs Rob sitting in the game window, because PZ stops ticking when it loses focus and the harness cannot reach the main menu. #3 is a design decision, not code. #7 is MP-only and untestable solo."
---

# Head for the Hills! - Project State

## What exists

- `mod/42/media/sandbox-options.txt` - 12 options. `CustomSpawnPoint`, `StartingVehicle` and `StartingEquipmentList` are `type = string`. `ZombieFreeRadius` is `0-100, default 20` as of session 9.
- `mod/42/media/lua/client/HeadForTheHills/SandboxPickers.lua` - live vehicle dropdown + searchable equipment multi-select.
- `mod/42/media/lua/client/HeadForTheHills/SpawnSelectScreen.lua` - fills the Remote Cabin description and stops the camera flying to cabin #1. Wraps `fillList` and `render` directly; `create()` needs no hook.
- `mod/42/media/lua/client/HeadForTheHills/CustomSpawnPoint.lua` - applies a typed coordinate by wrapping `SandboxOptionsScreen:setSandboxVars`.
- `mod/42/media/lua/shared/HeadForTheHills/SpawnRegion.lua` - the "Remote Cabin" starting location, plus `parsePoint` / `setCustomPoint` / `hasCustomPoint`, exported on `HFTH_SpawnRegion`.
- `mod/42/media/lua/shared/HeadForTheHills/SpawnScenario.lua` - everything placed at `OnNewGame`, around an **anchor square** passed in rather than re-read from the player. Water rescue is **three passes**: `isRealGround` (dirt/grass, outdoors, no building), then `isStandableGround`, then `isDryLand`.
- `tests/` - `_pilot.py` (use `payload()`, and its `teleport()` for every hop, which takes a 2-tuple), plus `api_checks.py`, `survey_candidates.py`, `verify_generator.py`, `verify_placement.py`, `verify_equipment.py`, `verify_spawn_region.py`, `verify_spawn_screen.py`, `verify_well.py`, `verify_custom_spawn.py`.
- Deployed to `Zomboid/mods/HeadForTheHills` as a directory junction. PZ must be quit **to desktop** to reload changed Lua, and sandbox-options.txt likewise.
- 5 open issues: #3, #7, #13, #14, #15. No open PRs.

## What is decided

- Start-scenario mod, not a mechanics overhaul. Reuse existing map buildings; no TileZed until v2.
- **All twelve cabins stay.** Rob picked them. Do not propose trimming.
- **Custom coordinates are a sandbox option, applied at `setSandboxVars`** (#12, shipped). `clickNext:644` freezes a live reference to our region table, `SandboxOptions.lua:972` fills `SandboxVars`, and `initWorld:1086` reads that same table afterwards. Overwriting the points in between redirects the spawn, so **no control goes on the map screen**.
- **Never wrap a function that was captured by value.** `Events.OnInitWorld.Add(CharacterCreationProfession.initWorld)` at `CharacterCreationProfession.lua:1562` and the PLAY button at `SandboxOptions.lua:422` both hold the function, not the field. A wrap on either loads clean and does nothing.
- **Placement takes an anchor square, not the player.** Coordinates update instantly on `teleportTo` but `getCurrentSquare()` lags about a second. `clearZombies` is the one step that still takes the player (#15).
- **A coordinate in water always moves the player to dry land, and onto real ground.** Rob: "nobody ever wants to start in the water." Dry is not enough on its own, see session 9.
- **Use https://map.projectzomboid.com/?b=1 to find a coordinate**, not a teleport hunt. Rob's correction, session 9. Confirm the found coordinate in game with one check; do not go looking for it with twelve.
- **Always fix the issue first.** Rob's standing order, session 9. Do not offer to park a defect in order to close a ticket.
- All public-facing copy runs through `/avoid-ai-writing`. No AI-attribution trailer in commits, ever.

## What is pending

- **#13 (needs Rob).** The buffer clear only sees loaded zombies, so the new max of 100 may be partly fiction. Measure the real ceiling.
- **#14 (needs Rob).** The water rescue is proven beside West Point, which is the opposite of what this mod is for. Prove it near a cabin.
- **#15.** `clearZombies` takes the player, not `centre`. Works by luck; tidy it.
- **#3 (needs Rob).** Trait/occupation default loadout alongside the picker.
- **#7.** MP: `ServerSettingsScreen` not hooked.
- Sibling repo `rob-kingsbury/pz-test-pilot`: #1 (false `harness_dead`), #2 (teleport moves nothing), #3 (queued command fires on tab-back). **#3's write-up is wrong:** `send_command` does clean up on `CommandTimeout` (`_ipc.py:179-181`); the leak is the `HarnessDead` path at `_ipc.py:167-171`, which raises with no cleanup. The heartbeat trips at 6s against a 30s timeout, so `HarnessDead` wins that race and leaks on nearly every failed command. Hit once in session 9 and it was a false positive: `status.txt` was one second old.

## Recent sessions

### Session 9 (2026-08-04): #12 verified and closed, and the fix it needed twice
Verified #12 live in three game starts and closed it. A typed coordinate lands you there, confirmed by log line and position together rather than by position alone, which a 1-in-12 random draw could have faked. Then the water rescue put Rob inside a **boathouse standing out over the Ohio**: dry, floored, and not land. A screenshot from Rob is what caught it; the measurement had said `inside=true` and had been read as a curiosity. The first fix, rejecting building footprints, was **proven insufficient by measurement before it shipped** - it would have moved him onto the open jetty, still 33 of 49 water. The fix that landed prefers vanilla's own dirt-or-grass classification, validated live before a line of it was written. Also found `verify_placement.py` failing the mod for correctly leaving cabin #4's existing well alone, and fixed the test rather than the mod. `ZombieFreeRadius` went `0-100, default 20` after Rob got attacked on spawn beside West Point; the floor stayed at 0 against his suggested 5, to keep the no-buffer start his tooltip already promises. **5-session audit ran:** 3 memory files, index matches, nothing stale.

### Session 8 (2026-08-04): #11 shipped and closed, #12 built, a wrong ruling overturned
Closed #11: description panel and camera both fixed and confirmed on screen by Rob. Verified the well's skip-existing branch live at cabin #4. Then Rob proposed a sandbox setting for custom coordinates, which the project had ruled out. Reading the source showed the ruling measured the wrong moment and he was right, so #12 shipped as a sandbox option with no map UI at all. A first-principles reminder mid-build replaced a teleport-then-wait workaround with passing an anchor square, removing the timing bug instead of pacing around it. **PZ burned full CPU for 45 minutes with a frozen heartbeat**, so `harness_dead` is not always the false positive CLAUDE.md implies.

### Session 7 (2026-08-04): Cabin list finalised, two wrong designs killed by reading source
Closed #1: all twelve cabins are deliberate, so the comment calling the list provisional was corrected rather than the list trimmed. Verified the well's skip-existing branch design. Two designs for user-entered coordinates died by reading vanilla source. A three-reviewer pre-flight found the `clickNext` mechanism and two live defects, filed as #11.

## To Resume

Paste into a fresh window:

> Continuing Head for the Hills (PZ B42.20 start-scenario mod) at `c:\xampp\htdocs\pz-head-for-the-hills`, session 10. On `main` at b5ecdae, tree clean. 5 open issues (#3 #7 #13 #14 #15), no open PRs. The mod works end to end, including custom coordinates and a water rescue that stands you on real ground.
>
> THIS WINDOW:
> 1. **#13.** `ZombieFreeRadius` now offers up to 100, but `clearZombies` only removes zombies in `getCell():getObjectListForLua()`, which holds what is loaded. Find the radius where the removed count stops growing, then cap the option there or say so in the tooltip. Needs a spawn near a town to have enough zombies to measure.
> 2. **#14.** The water rescue is only proven beside West Point. Find water near one of the twelve cabins **off https://map.projectzomboid.com/?b=1**, not by teleporting around, then run one start from it.
> 3. **#15** is a small tidy, no game needed. **#3 and #7** only if Rob wants them.
>
> Live testing: quit PZ **to desktop** before testing changed Lua or sandbox-options.txt. Drive with `tests/_pilot.py`'s helpers; its `teleport()` takes a 2-tuple. **PZ stops ticking when it loses focus**, so Rob has to be in the game window. `harness_dead` is usually false - check `status.txt`'s timestamp before believing it. **After any failed command, delete `command.txt` and `command_ready.txt`** from `Zomboid/Lua/TestPilot/`.
>
> Rob wants plain language and a short "What I need from you" at the end of every reply. Fix defects when found rather than offering to park them.

## Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules + hard-won B42 facts |
| `.claude/rules/development-workflow.md` | Git, commit, workflow rules |
| `mod/` | The actual PZ mod (root `mod.info` + `42/`) |
| `tests/_pilot.py` | Shared harness plumbing for every test script |
