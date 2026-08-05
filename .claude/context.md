---
session: 11
last_updated: 2026-08-04
continue_with: "Confirm the Workshop item is actually public (open https://steamcommunity.com/sharedfiles/filedetails/?id=3777845024 in a logged-out browser), and that the corrected Custom Start Coordinate paragraph made it onto the Steam page. Then #16, the vanilla-only run, which is the only unmeasured risk left in a shipped mod."
blockers: "#16 and #17 both need Rob in the game. #3 is a design decision. #7 is answered but not the way the issue framed it, see below."
---

# Head for the Hills! - Project State

**Published to the Steam Workshop as id 3777845024, v1.0.0, on 2026-08-04.**

## What exists

- `mod/42/media/sandbox-options.txt` - 12 options. `CustomSpawnPoint`, `StartingVehicle` and `StartingEquipmentList` are `type = string`. No zombie option; see below.
- `mod/42/media/lua/client/HeadForTheHills/` - `SandboxPickers.lua` (live vehicle dropdown + searchable equipment multi-select), `SpawnSelectScreen.lua` (description panel + camera), `CustomSpawnPoint.lua` (typed coordinate, applied at `setSandboxVars`).
- `mod/42/media/lua/shared/HeadForTheHills/SpawnRegion.lua` - the "Remote Cabin" location, **seventeen** cabins, plus `parsePoint` / `setCustomPoint` / `hasCustomPoint` on `HFTH_SpawnRegion`.
- `mod/42/media/lua/shared/HeadForTheHills/SpawnScenario.lua` - everything placed at `OnNewGame`, around an **anchor square** passed in rather than re-read from the player.
- `mod/poster.png` + `mod/42/poster.png` (512px, declared in both mod.info files), `assets/` (master art, 256px preview, screenshots, Workshop description).
- `scripts/build_workshop.py` - assembles `Zomboid/Workshop/HeadForTheHills`. Refuses to build if the two mod.info files drift apart or the preview is not exactly 256x256.
- `tests/` - `_pilot.py` (use `payload()`, and its `teleport()`, which takes a 2-tuple), plus `api_checks.py`, `measure_buffer.py`, `survey_candidates.py`, `verify_*.py`.
- Deployed to `Zomboid/mods/HeadForTheHills` as a directory junction. PZ must be quit **to desktop** to reload changed Lua or sandbox-options.txt.
- 4 open issues: #3, #7, #16, #17.

## What is decided

- Start-scenario mod, not a mechanics overhaul. Reuse existing map buildings; no TileZed until v2.
- **All seventeen cabins stay.** Rob picked them. Do not propose trimming.
- **The mod places only base-game content.** `Base.Generator`, `Base.Key1`, `Base.PickUpTruck`, and a well whose entity script is name-checked as `Base.Well` before it is built, so a mod that re-points the vanilla well sprite gets refused rather than placed.
- **The zombie buffer was removed** (session 10). Its justification was 42 zombies measured inside 72 tiles of a *town*, and this mod starts people at cabins. Vanilla's own `PlayerSpawnZombieRemoval` is left at whatever the player chose. Do not rebuild it; the reasoning is in `SpawnScenario.lua`.
- **Well goes in the yard, generator goes against the house.** 6-10 tiles from the nearest building tile and 4+ from standing water for the well; 1 tile for the generator. Both reject doorways and stairs.
- **The generator is never running.** Two tickboxes, Fueled and Connected, both defaulting off. `setActivated` appears only in a comment saying it is never called.
- **MP guard is per job, not per file.** World objects belong to the authority; inventory runs everywhere, because vanilla grants starting items with no `isClient()` guard at all.
- **#7 is answered, not implemented.** `ServerSettingsScreen` builds controls inline with no per-setting factory, and its settings table is assembled at file load. Our options already appear there automatically as text boxes. A fragile wrap into a 5000-line vanilla screen nobody can test could break the whole panel. The tooltips say what to type instead.
- **Never wrap a function captured by value** (`initWorld`, the PLAY button). A wrap loads clean and does nothing.
- **Use https://map.projectzomboid.com/?b=1 to find a coordinate**, not a teleport hunt.
- **Always fix the issue first.** Do not offer to park a defect to close a ticket.
- All public-facing copy runs through `/avoid-ai-writing`. No AI-attribution trailer in commits, ever.
- **Never put the real description in `workshop.txt`.** It holds `description=See workshop page` deliberately; PZ pushes that field on every upload and would overwrite the Steam-side text. Same trap that cost Unbreaker its page copy. `build_workshop.py` seeds `workshop.txt` once and never overwrites it, because PZ stamps the item id into it.

## What is pending

- **#16 (needs Rob).** Vanilla-only run. Every measurement so far came off a 180-mod install.
- **#17 (needs Rob).** Cabins 13-17 are unverified map-site coordinates; the spawn square may be outside the building. #14 may duplicate #10.
- **#3 (needs Rob).** Trait/occupation default loadout alongside the picker.
- **#7.** See above. Closeable as "answered" if Rob agrees.
- Steam page: confirm public, and confirm the corrected Custom Start Coordinate paragraph is live. The repo copy in `assets/workshop-description.txt` is correct; the pasted one may not be.
- Sibling repo `rob-kingsbury/pz-test-pilot`: #1 (false `harness_dead`), #2 (teleport moves nothing), #3 (queued command fires on tab-back). The `HarnessDead` path at `_ipc.py:167-171` raises with no cleanup, and the 6s heartbeat beats the 30s timeout, so it leaks on nearly every failed command. **Delete `command.txt` and `command_ready.txt` after any failure.**
- `unbreaker` has one unpushed local commit: a note under "What It Cannot Fix" about mod clothing slots showing raw `UI_ClothingType_*` keys.

## Recent sessions

### Session 10 (2026-08-04): shipped v1.0.0 to the Workshop
Closed #13, #14, #15 and published. #13's measurement killed its own feature: the buffer cleared **0** zombies at `OnNewGame` because nothing has streamed in yet, and the 72-tile ceiling it was capped to was measured at a town, so Rob removed the buffer entirely. Rebuilt the well and generator placement to opposite rules and verified both live on three cabins. Split `GeneratorFueledAndRunning` into two tickboxes that never start it. Added the cabin key, which looked redundant until cabin #16 proved vanilla does not grant one for our own coordinates. Five cabins added, #12 corrected from its shed to the actual cabin. Poster, packaging, README and Workshop description written. Two live-test scripts blamed the mod for correct behaviour before the mod learned to say what it did.

### Session 9 (2026-08-04): #12 verified and closed, and the fix it needed twice
Verified #12 live in three game starts and closed it. Then the water rescue put Rob inside a **boathouse standing out over the Ohio**: dry, floored, and not land. The first fix was proven insufficient by measurement before it shipped. The fix that landed prefers vanilla's own dirt-or-grass classification. Also found `verify_placement.py` failing the mod for correctly leaving cabin #4's existing well alone, and fixed the test rather than the mod.

### Session 8 (2026-08-04): #11 shipped and closed, #12 built, a wrong ruling overturned
Closed #11: description panel and camera both fixed. Rob proposed a sandbox setting for custom coordinates, which the project had ruled out; reading the source showed the ruling measured the wrong moment and he was right. A first-principles reminder mid-build replaced a teleport-then-wait workaround with passing an anchor square.

## To Resume

Paste into a fresh window:

> Continuing Head for the Hills (PZ B42.20 start-scenario mod) at `c:\xampp\htdocs\pz-head-for-the-hills`, session 11. On `main`, tree clean. **v1.0.0 is live on the Steam Workshop, id 3777845024.** 4 open issues (#3 #7 #16 #17), no open PRs.
>
> THIS WINDOW:
> 1. **Confirm the release landed.** Open the Workshop page in a logged-out browser: it should be public, with the description, three screenshots and the 256px poster. Check the Custom Start Coordinate paragraph matches `assets/workshop-description.txt`, which says "not the whole URL, only the numbers out of it". The pasted version may still carry the wrong wording.
> 2. **#16.** One launch with only this mod enabled, one start at `6098x8055`, read `console.txt`. Everything measured so far came off a 180-mod install, and two of those mods already changed what the mod saw.
> 3. **#17.** Cabins 13-17 were never checked as interior squares. Draw each and see whether the player wakes inside the building.
> 4. **#3 and #7** only if Rob wants them. #7 is arguably closeable as answered.
>
> To publish an update: `python scripts/build_workshop.py`, then the game's main menu, WORKSHOP, Create and update items. **Never edit `workshop.txt`** and never put the real description in it. Flip visibility on the Steam page, not in the game.
>
> Live testing: quit PZ **to desktop** before testing changed Lua or sandbox-options.txt. Drive with `tests/_pilot.py`. **PZ stops ticking when it loses focus.** `harness_dead` is usually false; check `status.txt`'s timestamp. **After any failed command, delete `command.txt` and `command_ready.txt`** from `Zomboid/Lua/TestPilot/`.
>
> Rob wants plain language and a short "What I need from you" at the end of every reply. Fix defects when found rather than offering to park them.

## Reference

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project rules + hard-won B42 facts |
| `.claude/rules/development-workflow.md` | Git, commit, workflow rules |
| `mod/` | The actual PZ mod (root `mod.info` + `42/`) |
| `scripts/build_workshop.py` | Assembles the Workshop package |
| `assets/workshop-description.txt` | Steam page body text, pasted by hand |
| `tests/_pilot.py` | Shared harness plumbing for every test script |
