---
project: pz-head-for-the-hills
session: 2
last_updated: 2026-08-03
continue_with: "Pick 2-3 real cabin coordinates off map.projectzomboid.com, then build the spawnregions.lua + spawnpoints.lua pair for the Remote Cabin region."
blockers: "None."

tech:
  product_name: "Head for the Hills!"
  stack: "PZ Build 42 mod: mod.info + Lua (shared/client/server) + scripts"
  target: "Project Zomboid 42.20.0"
  mod_id: HeadForTheHills
  repo: "github.com/robotsmeller/pz-head-for-the-hills (public)"
---

# Head for the Hills! - Project State

## What exists

- Repo scaffold only: `mod/mod.info` + `mod/42/mod.info` (identical content, both required — see CLAUDE.md), empty `mod/42/media/lua/{shared,client,server}` and `mod/42/media/scripts`, `.claude/` (context.md, settings.json, secrets/pii hooks, development-workflow rules), README, MIT LICENSE.
- No gameplay content yet: no spawn region, no starting kit, no vehicle spawn, no zombie-buffer logic.

## What is decided

- A start-scenario mod, not a mechanics overhaul: custom spawn region (2-3 hand-picked existing rural cabins, randomized across them) + starting kit (trait/occupation-based) + a nearby starting vehicle + a no-zombie buffer for the immediate area around the cabin, with a real drivable stretch to an existing town.
- Reuse an existing map building for the cabin rather than hand-building one in TileZed (locked in session 1 - faster, no mapping-tool learning curve, custom-built cabin stays an option for a v2).
- One mod, not split across several. `pz-` naming convention. Public repo under the `robotsmeller` GitHub org (where the rest of this account's PZ tooling lives).

## What is pending

- Pick the actual 2-3 cabin coordinates (map.projectzomboid.com for Cell/Rel values).
- Decide the profession-key strategy for spawn randomization: vanilla `spawnpoints.lua` keys point lists **by profession**, not as one flat randomized list, so either every profession key gets mapped to the same 2-3 points, or the scenario defines one dedicated occupation that owns them.
- Starting kit contents.
- Vehicle choice + spawn-near-player logic.
- Zombie-buffer approach: lean on already-sparse vanilla density at the chosen spot vs. porting Player Made Safe Zone-style active suppression.

## Recent sessions

### Session 1 (2026-08-03): Research + scaffold
Researched B42 scenario feasibility: spawn regions, zombie density heatmaps, starting kits, and vehicle-start mods are all achievable as a single mod with no custom TileZed map required. Surveyed sibling PZ projects in `c:\xampp\htdocs` for reusable tooling and hard-won B42 facts, pulled the real vanilla `SpawnRegions.lua` and a town `spawnpoints.lua` off the local PZ 42.20.0 install to confirm the profession-keyed structure firsthand. Named the project "Head for the Hills!" and scaffolded the repo.

## To Resume

Paste this into a fresh window:

> Continuing Head for the Hills (PZ B42.20 start-scenario mod) at `c:\xampp\htdocs\pz-head-for-the-hills`, session 2. Scaffold is done and pushed to `robotsmeller/pz-head-for-the-hills`. Next: pick 2-3 real cabin coordinates off map.projectzomboid.com, then build the spawnregions.lua/spawnpoints.lua pair for the "Remote Cabin" region.

## Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules, hard-won B42 facts, related sibling tooling |
| `.claude/rules/development-workflow.md` | Git, commit, workflow rules |
| `mod/` | The actual PZ mod (root `mod.info` + `42/`) — this is what gets copied/symlinked into `Zomboid/mods/` |
