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

## Related tooling (same author, `c:\xampp\htdocs`)

| Project | Use it for |
|---|---|
| `pz-test-pilot` | Driving a running PZ instance to verify spawn location, starting kit, and zombie density without manual in-game testing. Its deployed mod folder (`Zomboid/mods/PZTestPilot`) was empty as of session 1 - resync via `launch.py --mod` before relying on it. |
| `pz-mod-checker` | Scanning this mod for B42 breaking changes once it has real content. Rule coverage currently runs through 42.20.0. |
| `pz-tilesheet` | Only needed if this project later builds a custom cabin object instead of reusing an existing map building. |
| `unbreaker` | Not directly relevant to this mod, but its `mod/` layout is the reference this scaffold copied (root + `42/` mod.info, `42/media/lua/shared`). |

## Development rules

See `.claude/rules/development-workflow.md`.
