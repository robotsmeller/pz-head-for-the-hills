---
session: 9
last_updated: 2026-08-04
continue_with: "#12 is built but never run live. Start the game, put 9668,8775 in the Custom Start Coordinate box, pick Remote Cabin, and check you wake at cabin #4. Then try a coordinate in a river and check it walks you to dry land. Close #12 when both hold."
blockers: "#12's remaining checks all run through the main menu, which a harness registering on OnGameStart cannot reach - Rob has to look. #3 is a design decision, not code. #7 is MP-only and untestable solo. PZ stops ticking whenever it loses focus, so every live test needs Rob sitting in the game window."
---

# Head for the Hills! - Project State

## What exists

- `mod/42/media/sandbox-options.txt` - 12 options. `CustomSpawnPoint`, `StartingVehicle` and `StartingEquipmentList` are `type = string`.
- `mod/42/media/lua/client/HeadForTheHills/SandboxPickers.lua` - live vehicle dropdown + searchable equipment multi-select.
- `mod/42/media/lua/client/HeadForTheHills/SpawnSelectScreen.lua` - fills the Remote Cabin description and stops the camera flying to cabin #1. Wraps `fillList` and `render` directly; `create()` needs no hook.
- `mod/42/media/lua/client/HeadForTheHills/CustomSpawnPoint.lua` - **new, session 8.** Applies a typed coordinate by wrapping `SandboxOptionsScreen:setSandboxVars`.
- `mod/42/media/lua/shared/HeadForTheHills/SpawnRegion.lua` - the "Remote Cabin" starting location, plus `parsePoint` / `setCustomPoint` / `hasCustomPoint`, exported on `HFTH_SpawnRegion`.
- `mod/42/media/lua/shared/HeadForTheHills/SpawnScenario.lua` - everything placed at `OnNewGame`, now around an **anchor square** passed in rather than re-read from the player. Water rescue included.
- `tests/` - `_pilot.py` (use `payload()`, and its `teleport()` for every hop), `api_checks.py`, `survey_candidates.py`, `verify_generator.py`, `verify_placement.py`, `verify_equipment.py`, `verify_spawn_region.py`, `verify_spawn_screen.py`, `verify_well.py`, `verify_custom_spawn.py`.
- Deployed to `Zomboid/mods/HeadForTheHills` as a directory junction. PZ must be quit **to desktop** to reload changed Lua.
- 3 open issues: #3, #7, #12. No open PRs.

## What is decided

- Start-scenario mod, not a mechanics overhaul. Reuse existing map buildings; no TileZed until v2.
- **All twelve cabins stay.** Rob picked them. Do not propose trimming.
- **Custom coordinates are a sandbox option, applied at `setSandboxVars`** (#12). The session-7 note calling a sandbox option impossible measured the wrong moment: nothing builds the point list from the option. `clickNext:644` freezes a live reference to our region table, `SandboxOptions.lua:972` fills `SandboxVars`, and `initWorld:1086` reads that same table afterwards. Overwriting the points in between redirects the spawn, so **no control goes on the map screen** - Rob does not want to click the map.
- **Never wrap a function that was captured by value.** `Events.OnInitWorld.Add(CharacterCreationProfession.initWorld)` at `CharacterCreationProfession.lua:1562` and the PLAY button at `SandboxOptions.lua:422` both hold the function, not the field. A wrap on either loads clean and does nothing. Same family as `MapSpawnSelect:createChildren`, which does not exist at all.
- **Placement takes an anchor square, not the player.** "Who is spawning" and "what are we building around" are different questions. Coordinates update instantly on `teleportTo` but `getCurrentSquare()` lags about a second, so re-reading the player mid-rescue built around the water we just left.
- **A coordinate in water always moves the player to dry land.** No branch leaves them there. Rob: "nobody ever wants to start in the water."
- All public-facing copy runs through `/avoid-ai-writing`. No AI-attribution trailer in commits, ever.

## What is pending

- **#12 (needs Rob at the keyboard).** Built and committed, never run live. Typing a coordinate and waking there, and the water rescue, both need the main menu.
- **#3 (needs Rob).** Trait/occupation default loadout alongside the picker.
- **#7.** MP: `ServerSettingsScreen` not hooked.
- Sibling repo `rob-kingsbury/pz-test-pilot`: #1 (false `harness_dead`), #2 (teleport moves nothing), #3 (queued command fires on tab-back). **#3's write-up is wrong and worth correcting:** `send_command` *does* clean up on `CommandTimeout` (`_ipc.py:179-181`). The leak is the `HarnessDead` path at `_ipc.py:167-171`, which raises with no cleanup. The heartbeat trips at 6s and the timeout is 30s, so `HarnessDead` wins that race and the leak fires on nearly every failed command.

## Recent sessions

### Session 8 (2026-08-04): #11 shipped and closed, #12 built, a wrong ruling overturned
Closed #11: description panel and camera both fixed and confirmed on screen by Rob. Verified the well's skip-existing branch live at cabin #4, which finally ran `verify_well.py` and `_pilot.py`'s snapshot/restore for the first time; both passed. Then Rob proposed a sandbox setting for custom coordinates, which the project had ruled out. Reading the source showed the ruling measured the wrong moment and he was right, so #12 shipped as a sandbox option with no map UI at all - deleting the joypad patch, `isClient()` hiding, pin rendering and click handling the old plan carried. A first-principles reminder mid-build replaced a teleport-then-wait workaround with passing an anchor square, removing the timing bug instead of pacing around it. The parser needed no game, so it was run against the real shipped code offline: 15 coordinate shapes, all correct. **PZ burned full CPU for 45 minutes with a frozen heartbeat**, so `harness_dead` is not always the false positive CLAUDE.md implies.

### Session 7 (2026-08-04): Cabin list finalised, two wrong designs killed by reading source
Closed #1: all twelve cabins are deliberate, so the comment calling the list provisional was corrected rather than the list trimmed. Verified the well's skip-existing branch design. Two designs for user-entered coordinates died by reading vanilla source. A three-reviewer pre-flight found the `clickNext` mechanism and two live defects, filed as #11. Filed pz-test-pilot#3.

### Session 6 (2026-08-04): Starting Location shipped, ID card fixed, three test defects
Closed #10, #9 and #2. `teleportTo` works where `teleport` and `setX`/`setY` do not. Built `SpawnRegion.lua` and verified it live. Fixed `verify_placement.py` reporting PASS on a spawn that placed nothing, and a scan reading unloaded squares as empty.

## To Resume

Paste into a fresh window:

> Continuing Head for the Hills (PZ B42.20 start-scenario mod) at `c:\xampp\htdocs\pz-head-for-the-hills`, session 9. On `main` at e772ffd, tree clean. 3 open issues (#3 #7 #12), no open PRs. The mod works end to end: pick "Remote Cabin" and you wake in a cabin with a car, a well and a running generator.
>
> THIS WINDOW:
> 1. **#12 is built but never run live.** Start the game, put `9668,8775` in the **Custom Start Coordinate** sandbox box, pick Remote Cabin, and check you wake at cabin #4. Then try a coordinate in a river and check it walks you to dry land. Close #12 when both hold.
> 2. **Also worth a live pass:** `python tests/verify_custom_spawn.py` covers the parser and the redirect in a loaded world, and `SpawnScenario.lua`'s three placement functions changed signature this session, so re-run `verify_placement.py` on a fresh spawn.
> 3. **#3 and #7** only if Rob wants them.
>
> Live testing: quit PZ **to desktop** before testing changed Lua. Drive with `tests/_pilot.py`'s helpers. **PZ stops ticking when it loses focus**, so Rob has to be sitting in the game window - but session 8 saw PZ burn full CPU with a frozen heartbeat for 45 minutes, so check `status.txt`'s timestamp rather than assuming a false positive. **After any failed command, delete `command.txt` and `command_ready.txt`** from `Zomboid/Lua/TestPilot/`.

## Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules + hard-won B42 facts |
| `.claude/rules/development-workflow.md` | Git, commit, workflow rules |
| `mod/` | The actual PZ mod (root `mod.info` + `42/`) |
| `tests/_pilot.py` | Shared harness plumbing for every test script |
