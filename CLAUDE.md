@.claude/context.md

# Head for the Hills! - Project Rules

## What this is

A Project Zomboid Build 42 start-scenario mod. The player wakes up at a hand-picked remote cabin, stocked with basic supplies and a vehicle, with a zombie-free buffer immediately around the cabin and a real drivable stretch to the nearest town for anyone who wants to push their luck.

## Project info

| Property | Value |
|---|---|
| Repo | github.com/robotsmeller/pz-head-for-the-hills (public) |
| Target | Project Zomboid Build 42.20.0 |
| Mod id | HeadForTheHills |
| Mod root | `mod/` - this is what gets symlinked/copied into `Zomboid/mods/` |

## Hard-won B42 facts (verified empirically by sibling projects, not guessed)

- **B42 silently rejects a mod missing `42/mod.info`.** Root `mod.info` alone is not enough - the mod won't appear in the in-game mods list and nothing gets logged to `console.txt`. Keep root and `42/mod.info` in sync on every change. Verified against a live 180-mod install by `pz-mod-checker` (session 9) and applied to `unbreaker`'s own shipped structure.
- Vanilla `spawnpoints.lua` keys point lists **by profession** (`chef`, `unemployed`, `farmer`, etc.), not as one flat randomized list per region. Getting 2-3 cabins to randomize regardless of chosen occupation means either mapping every profession key to the same point list, or defining one dedicated occupation for this scenario.
- Real vanilla reference lives on disk, not just in blog posts: `C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid\media\lua\shared\SpawnRegions.lua` and per-town `spawnpoints.lua` under `media\maps\<Town>\`. Read the real files before guessing at API shape or field names.
- `SpawnRegionMgr.getSpawnRegionsAux()` looks for `media/maps/<mapname>/spawnregions.lua` first, falling back to an auto-generated region per loaded map. A custom "Remote Cabin" region needs to hook in via the mod's own Lua rather than editing vanilla files directly.
- **B42.20 restricts `getFileWriter` to a whitelist of file extensions.** Measured on 42.20.0 (session 2): `.txt`, `.ini`, `.cfg` open fine; `.json`, `.dat`, `.tmp` return **nil**. The append flag and root-vs-subdirectory make no difference, only the extension does. `getFileReader` is unaffected, so `.json` stays readable and a mod that only reads config never notices. Because the failure is a nil return rather than a throw, it surfaces later and elsewhere as `attempted index: close of non-table: null`. Double extensions are judged on the last one, so `foo.json.ready` is rejected for `.ready`. This broke `pz-test-pilot` completely; rule `b42-20-getfilewriter-extension-whitelist` in `pz-mod-checker` now catches it. Caveat: only those six extensions were tested, so treat `.txt`/`.ini`/`.cfg` as known-good rather than as the complete whitelist.
- Native Sandbox Vars **enum** dropdowns are parsed from a static `sandbox-options.txt` before any mod Lua runs, so their choices cannot be generated at runtime. To offer a list built from what is actually installed, declare the option as `type = string` and replace its control by wrapping `SandboxOptionsScreen:createControlForSetting`. The screen persists whatever sits in `self.controls[name]` via `control:getText()`/`setText()`, so a custom widget that implements those two methods rides the normal per-save sandbox system with no extra persistence layer and no second settings screen. This is how the live vehicle and equipment pickers work (`mod/42/media/lua/client/HeadForTheHills/SandboxPickers.lua`).
- `getScriptManager():getAllVehicleScripts()` and `:getAllItems()` enumerate everything currently loaded, vanilla plus enabled mods (measured: 506 vehicles, 7839 items on a modded install). `Item:getDisplayName()` is safe across all of them (0 failures in 7839), but `VehicleScript:getDisplayName()` **throws** - it does not exist on that class in B42, so use `getName()`/`getFullName()`.

## Related tooling (same author, `c:\xampp\htdocs`)

| Project | Use it for |
|---|---|
| `pz-test-pilot` | Driving a running PZ instance to verify spawn location, starting kit, and zombie density without manual in-game testing. Already deployed as a symlink at `Zomboid/mods/PZTestPilot` - no sync step, and there is no `launch.py`. Send commands with `python scripts/cmd.py <action>`; `run_lua` executes arbitrary Lua in the running game. The harness only registers on `OnGameStart`, so it can verify anything in a loaded save but cannot drive main-menu screens. Its IPC files are `.txt` (not `.json`) because of the B42.20 restriction above - do not "fix" them back. This project's own checks live in `tests/api_checks.py`. |
| `pz-mod-checker` | Scanning this mod for B42 breaking changes once it has real content. Rule coverage currently runs through 42.20.0. |
| `pz-tilesheet` | Only needed if this project later builds a custom cabin object instead of reusing an existing map building. |
| `unbreaker` | Not directly relevant to this mod, but its `mod/` layout is the reference this scaffold copied (root + `42/` mod.info, `42/media/lua/shared`). |

## Development rules

See `.claude/rules/development-workflow.md`.
