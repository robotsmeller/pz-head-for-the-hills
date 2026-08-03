---
project: pz-head-for-the-hills
session: 3
last_updated: 2026-08-03
continue_with: "Test SpawnScenario.lua in a throwaway world (issue #6), then inspect the 12 candidate coordinates and cut to 2-3 (issue #1)."
blockers: "None blocking. Both #6 and #1 need a live PZ session."

tech:
  product_name: "Head for the Hills!"
  stack: "PZ Build 42 mod: mod.info + Lua (shared/client/server) + scripts"
  target: "Project Zomboid 42.20.0"
  mod_id: HeadForTheHills
  repo: "github.com/robotsmeller/pz-head-for-the-hills (public)"
---

# Head for the Hills! - Project State

## What exists

- `mod/42/media/sandbox-options.txt` - 11 sandbox options: zombie-free radius (0-20), well/generator spawn toggles, generator fueled-and-running, starting season, vehicle spawn/condition/fuel, starting-equipment toggle, plus `StartingVehicle` and `StartingEquipmentList` declared `type = string`.
- `mod/42/media/lua/client/HeadForTheHills/SandboxPickers.lua` - live vehicle dropdown + searchable equipment multi-select, on the normal new-game sandbox screen. **Verified working in a live game.**
- `mod/42/media/lua/shared/HeadForTheHills/SpawnScenario.lua` - applies those settings at character spawn. **Written and syntax-clean, but has never executed.**
- `mod/42/media/lua/shared/Translate/EN/Sandbox_EN.txt`; `tests/api_checks.py` (10 live API checks, all passing).
- Deployed to `Zomboid/mods/HeadForTheHills` as a directory junction (symlink needs admin, junction does not).
- 7 open issues (#1-#7).

## What is decided

- Start-scenario mod, not a mechanics overhaul. Reuse existing map buildings; no TileZed.
- **Live pickers instead of hardcoded lists.** Native sandbox enum dropdowns are parsed from static text before any mod Lua runs, so a runtime-built list cannot be an enum. Declaring the option `type = string` and wrapping `SandboxOptionsScreen:createControlForSetting` works because the screen persists whatever control sits in `self.controls[name]` via `getText()`/`setText()`. One screen, no separate settings UI, no custom persistence layer. Detail in CLAUDE.md.
- **Equipment is a player-chosen multi-select, not a fixed trait/occupation kit.** (#3's original premise; a trait-driven default on top is still open.)
- Zombie buffer uses our own tile radius and forces vanilla `ZombieLore.PlayerSpawnZombieRemoval` to 4, because vanilla's is a 4-value enum with no numeric radius.
- Spawn logic is MP-shaped: `shared/` + `if isClient() then return end`, matching vanilla SpawnItems.lua / MOGenerator.lua. Unverified on a real server.
- All public-facing copy runs through `/avoid-ai-writing`. No AI-attribution trailer in commits.

## What is pending

- **#6 Test `SpawnScenario.lua` in a throwaway world.** Top priority. Weakest parts: `hasWellNearby()` matches on sprite name (B42 wells are entities with no Lua class for `instanceof`), and `spawnWell()`'s construction call is a guess wrapped in `pcall`.
- **#1 Cut 12 candidate coordinates to 2-3.** All 12 plus selection criteria are in the issue. Keep 9668x8782 if it qualifies - only known existing-well test case, needed by #6.
- **#2** spawnregions.lua + spawnpoints.lua, so the player actually starts at a cabin. Nothing exists yet; the player currently spawns wherever vanilla puts them.
- **#7** MP: `ServerSettingsScreen` not hooked, so dedicated-server admins get raw text boxes instead of the pickers.
- **#3** Whether a trait/occupation default loadout is wanted alongside the picker.
- **#4/#5** Code written; open pending #6 verification.

## Recent sessions

### Session 2 (2026-08-03): Sandbox options, live pickers, spawn logic, B42.20 breakage
Built the sandbox options page and both live pickers, then the spawn logic that consumes them. Verified end to end in a live game: the modded vehicle `Base.68firebird400` and two picked items were read back out of a real save, proving the round-trip through vanilla's per-save sandbox system. 10/10 API checks pass (506 vehicles, 7839 items enumerated; `Item:getDisplayName()` safe across all of them; `VehicleScript:getDisplayName()` confirmed to throw, so `getName()` is required).

Audited the first-draft picker code and found six real defects before testing: missing `instantiate()`, a field collision with the parent class's own `closeButton`, an override on `onClose` when the titlebar X routes through `close()`, dead `getText()` fallbacks (getText returns the key, never nil), reading `getText()` where vanilla uses `getInternalText()`, and a fragile dual-file override chain.

Found and fixed an undocumented **B42.20 breaking change**: `getFileWriter` now enforces a file-extension whitelist (`.txt`/`.ini`/`.cfg` open; `.json`/`.dat`/`.tmp` return nil; `getFileReader` unaffected). It had silently killed pz-test-pilot since 42.20 shipped and produced ~4200 errors in a single session. Diagnosed with a capability probe after two wrong hypotheses (append-vs-overwrite, then subdirectories) - the probe's control check is what settled it. Fixed pz-test-pilot (`d033505`), added rule `b42-20-getfilewriter-extension-whitelist` to pz-mod-checker (`d2ddedd`; verified it fires on the real broken line, stays clean on fixed code, 31 tests pass), and corrected that ruleset's summary, which had called 42.20 "very quiet for modders" on the strength of a Lua tree diff that structurally cannot see a Java-side change. Deliberately did **not** add it to unbreaker: out of scope per its own SCOPE.md, and a write-only shim would silently diverge from `getFileReader`, which still reads `.json`.

### Session 1 (2026-08-03): Research + scaffold
Confirmed spawn regions, zombie density, starting kits and vehicle spawns are all achievable in one mod with no custom map. Named the project, scaffolded the repo, pushed to `robotsmeller/pz-head-for-the-hills`, filed #1-#5.

## To Resume

Paste into a fresh window:

> Continuing Head for the Hills (PZ B42.20 start-scenario mod) at `c:\xampp\htdocs\pz-head-for-the-hills`, session 3. `main` at 237d83e. Sandbox options + live vehicle/equipment pickers are built and **verified working in a live game**; `SpawnScenario.lua` is written but has **never executed**.
>
> THIS WINDOW:
> 1. Test `SpawnScenario.lua` in a **throwaway** world (#6) - equipment, vehicle condition/fuel, generator adjacent-not-inside, zombie radius, season. Watch the two weak spots: well detection by sprite name, and the guarded well construction call.
> 2. Inspect the 12 candidate coordinates in #1 and cut to 2-3. Keep 9668x8782 if it qualifies; it is the only known existing-well test case.
> 3. Then #2, the spawnregions/spawnpoints pair, so the player actually starts at a cabin.
>
> pz-test-pilot works again. Its IPC files are `.txt`, not `.json` - do not change them back. Drive it with `python scripts/cmd.py run_lua "..."`; this repo's checks are `tests/api_checks.py`. It only registers on `OnGameStart`, so it cannot drive main-menu screens.

## Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules + hard-won B42 facts (getFileWriter whitelist, live-picker technique, script-manager enumeration) |
| `.claude/rules/development-workflow.md` | Git, commit, workflow rules |
| `mod/` | The actual PZ mod (root `mod.info` + `42/`) |
| `tests/api_checks.py` | Live API verification driven through pz-test-pilot |
