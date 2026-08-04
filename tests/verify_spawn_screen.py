"""
Head for the Hills! - the Remote Cabin row on Starting Location (issue #11).

Two defects shipped in session 6, both caused by the same thing: the screen is
built around getMapInfo(), which is keyed on media/maps/<name>/, and this mod
ships no map directory. The row therefore takes every no-info else branch.

    desc      MapSpawnSelect:fillList set item.desc = "" and the panel rendered
              empty. SpawnSelectScreen.lua fills it from a translation key.
    camera    render fell through to region.points.unemployed[1], always
              CABINS[1], and flew there whichever cabin the player would get.
              SpawnSelectScreen.lua stops the move rather than guessing.

What this checks, in a loaded world:

    wrapped   SpawnSelectScreen.lua ran to the end, so both wraps are installed
    exported  HFTH_SpawnRegion carries the name and cabins the screen hook reads
    copy      the description key resolves to real text, not back to the key
    camera    what vanilla would have flown to, and that it is one fixed cabin

What this canNOT check: how the panel and the map actually look. The harness
only registers once a save is loaded, so the main menu is out of reach. Boot to
the new-game screen and use your eyes for that part.

    python tests/verify_spawn_screen.py

Requires: PZ running with a save loaded, the PZTestPilot mod enabled, and the
mod's current Lua loaded - quit to desktop and back in after editing it.
"""

import sys

from _pilot import (
    load, run_lua, parse, num, boolean,
    CommandTimeout, HarnessDead, HarnessError,
)

DESC_KEY = "UI_HeadForTheHills_RemoteCabin_desc"
REGION_NAME = "Remote Cabin"
EXPECTED_CABINS = 12

# A blank panel was the bug, so a key that resolves to something very short is
# a failure too, not just one that resolves to itself.
MIN_DESC_LENGTH = 120


SCREEN_LUA = """
local out = {}
local function add(k, v) table.insert(out, k .. "=" .. tostring(v)) end

--[[ The class the hook wraps. Present on any client, loaded or not. ]]
add("classExists", MapSpawnSelect ~= nil)
if MapSpawnSelect then
    add("wrapped", MapSpawnSelect.HFTH_wrapped == true)
    add("fillListType", type(MapSpawnSelect.fillList))
    add("renderType", type(MapSpawnSelect.render))
end
add("installFlag", HFTH_SpawnSelectScreenInstalled == true)

--[[ What SpawnRegion.lua exports for the hook to read. ]]
if not HFTH_SpawnRegion then
    add("exported", false)
else
    add("exported", true)
    add("exportedName", tostring(HFTH_SpawnRegion.NAME))
    add("exportedCabins", #(HFTH_SpawnRegion.CABINS or {}))
end

--[[ getText answers the key itself when a key is missing, so comparing the two
     is how we tell "translation loaded" from "file never got read". ]]
local text = getText("%s")
add("descResolves", text ~= "%s")
add("descLength", #text)
add("descHasLineBreak", string.find(text, "<LINE>") ~= nil)

--[[ The point vanilla's render would have flown to. Recorded so the test says
     what the camera used to do, not just that our flag is set. ]]
if SpawnRegionMgr then
    for _, region in ipairs(SpawnRegionMgr.getSpawnRegions() or {}) do
        if region.name == "%s" then
            local points = region.points and region.points.unemployed
            if points and points[1] then
                add("vanillaCameraTarget", points[1].posX .. "," .. points[1].posY)
                add("cabinCount", #points)
            end
        end
    end
end
return table.concat(out, " | ")
"""


def main():
    cfg = load()
    print("Starting location: the Remote Cabin row must carry real copy, and "
          "the screen\nhook must be installed.\n")

    lua = SCREEN_LUA % (DESC_KEY, DESC_KEY, REGION_NAME)
    fields = parse(run_lua(cfg, lua))
    if fields.get("_raw"):
        print(f"FAIL\n  - {fields['_raw']}")
        return 1

    for key, value in fields.items():
        print(f"  {key:20} {value}")

    problems = []

    if boolean(fields, "classExists") is not True:
        problems.append(
            "MapSpawnSelect does not exist, so nothing could be wrapped; this "
            "is not a client, or the class was never required")
    elif boolean(fields, "wrapped") is not True:
        problems.append(
            "MapSpawnSelect.HFTH_wrapped is not set, so SpawnSelectScreen.lua "
            "did not run to the end; the row keeps vanilla's blank desc and "
            "the camera still flies to cabin 1")

    if boolean(fields, "exported") is not True:
        problems.append(
            "HFTH_SpawnRegion is missing, so the hook cannot name the region "
            "and every row fails its match; SpawnRegion.lua did not load")
    else:
        if fields.get("exportedName") != REGION_NAME:
            problems.append(
                f"exported region name is {fields.get('exportedName')!r}, "
                f"expected {REGION_NAME!r}")
        if num(fields, "exportedCabins") != EXPECTED_CABINS:
            problems.append(
                f"exported cabin list has {num(fields, 'exportedCabins'):.0f} "
                f"entries, expected {EXPECTED_CABINS}")

    if boolean(fields, "descResolves") is not True:
        problems.append(
            f"getText({DESC_KEY!r}) answered the key back, so UI_EN.txt was "
            "not loaded; the panel would show the raw key")
    elif num(fields, "descLength") < MIN_DESC_LENGTH:
        problems.append(
            f"the description is {num(fields, 'descLength'):.0f} characters, "
            f"under the {MIN_DESC_LENGTH} expected; it may be truncated")
    elif boolean(fields, "descHasLineBreak") is not True:
        problems.append(
            "the description has no <LINE> tag, so ISRichTextPanel renders it "
            "as one run-on block")

    if problems:
        print("\nFAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    target = fields.get("vanillaCameraTarget")
    print(f"\nPASS - hook installed, {EXPECTED_CABINS} cabins exported, "
          f"description resolves to\n       {num(fields, 'descLength'):.0f} "
          "characters of real copy")
    if target:
        print(f"\n       Vanilla's render would have flown to {target} every "
              "time, whichever\n       of the twelve the player was actually "
              "going to get. The wrap leaves the\n       camera where it is "
              "instead.")
    print("\nStill needs eyes: open the new-game screen, pick Remote Cabin, and "
          "check that\nthe description panel has text and the map does not jump "
          "to one fixed cabin.\nThe harness cannot reach the main menu.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except HarnessDead as exc:
        print(f"\n[DEAD] {exc}")
        print("       If PZ is alive and just unfocused, this is the "
              "tick-heartbeat false positive.")
        sys.exit(2)
    except CommandTimeout as exc:
        print(f"\n[TIMEOUT] {exc}")
        sys.exit(2)
    except HarnessError as exc:
        print(f"\n[HARNESS] {exc}")
        sys.exit(2)
