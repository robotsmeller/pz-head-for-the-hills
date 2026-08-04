"""
Head for the Hills! - "Remote Cabin" starting location verification (issue #2).

SpawnRegion.lua appends a region to the list the new-game screen shows, by
hooking OnSpawnRegionsLoaded rather than shipping a spawnregions.lua file that
getSpawnRegionsAux would ignore on a multi-map install.

What this checks, in a loaded world:

    present    SpawnRegionMgr.getSpawnRegions() returns our region
    points     it carries every cabin, under every profession key
    stable     asking repeatedly does not stack up duplicate copies

That last one matters because MapSpawnSelect calls getSpawnRegions() several
times while the screen is open, and each call fires the event again.

What this canNOT check: that the entry actually appears in the Starting Location
list, or that picking it drops the player in a cabin. The harness only registers
once a save is loaded, so the main menu is out of reach. Those two need eyes.

    python tests/verify_spawn_region.py

Requires: PZ running with a save loaded, the PZTestPilot mod enabled, and the
mod's current Lua loaded - quit to desktop and back in after editing it.
"""

import sys

from _pilot import (
    load, run_lua, parse, num,
    CommandTimeout, HarnessDead, HarnessError,
)

REGION_NAME = "Remote Cabin"

# Keep in step with the CABINS table in SpawnRegion.lua.
EXPECTED_CABINS = 12


REGIONS_LUA = """
local out = {}
local function add(k, v) table.insert(out, k .. "=" .. tostring(v)) end
if not SpawnRegionMgr then return "NOMGR" end

local seen, ours = 0, nil
local names = {}
for _, region in ipairs(SpawnRegionMgr.getSpawnRegions() or {}) do
    table.insert(names, tostring(region.name))
    if region.name == "%s" then
        seen = seen + 1
        ours = region
    end
end
add("regions", #names)
add("copies", seen)
add("names", table.concat(names, " / "))
if not ours then return table.concat(out, " | ") end

local keys, points = 0, nil
for _ in pairs(ours.points or {}) do keys = keys + 1 end
add("professionKeys", keys)
points = ours.points and ours.points.unemployed
add("unemployedPoints", points and #points or 0)
if points and points[1] then
    add("firstPoint", points[1].posX .. "," .. points[1].posY)
end

--[[ Every profession the game knows must resolve to the same list, or the
     cabin someone wakes in depends on the job they picked. ]]
local missing, mismatched = {}, 0
if CharacterProfessionDefinition then
    local list = CharacterProfessionDefinition.getProfessions()
    for i = 0, list:size() - 1 do
        local id = tostring(list:get(i):getType())
        local bare = string.match(id, "([^:]+)$") or id
        local got = ours.points[bare]
        if not got then
            table.insert(missing, bare)
        elseif #got ~= #points then
            mismatched = mismatched + 1
        end
    end
    add("professions", list:size())
end
add("missingKeys", #missing == 0 and "none" or table.concat(missing, ","))
add("mismatched", mismatched)
return table.concat(out, " | ")
"""


def main():
    cfg = load()
    print(f'Starting location: the "{REGION_NAME}" region must be present, '
          "complete and stable.\n")

    fields = parse(run_lua(cfg, REGIONS_LUA % REGION_NAME))
    if fields.get("_raw"):
        print(f"FAIL\n  - {fields['_raw']}")
        return 1

    for key, value in fields.items():
        print(f"  {key:18} {value}")

    problems = []
    if not num(fields, "copies"):
        problems.append(
            f'no region named "{REGION_NAME}" came back; SpawnRegion.lua did '
            "not load, or the event never fired")
        print("\nFAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    points = num(fields, "unemployedPoints")
    if points == 1:
        # #12 lets a sandbox coordinate replace the twelve with a single point.
        # That swap happens on the menu screen, so finding it here means a
        # character was made with one set earlier in this session. Reporting it
        # beats failing on a count that is correct for what the player chose.
        print("\n  NOTE: the region holds one point, so a custom start "
              "coordinate is active.\n        The cabin-count check does not "
              "apply. See tests/verify_custom_spawn.py.")
    elif points != EXPECTED_CABINS:
        problems.append(
            f"the region carries {points:.0f} cabins, "
            f"expected {EXPECTED_CABINS}")
    if fields.get("missingKeys") != "none":
        problems.append(
            f"professions with no spawn points: {fields.get('missingKeys')}; "
            "anyone with those jobs would spawn somewhere else entirely")
    if num(fields, "mismatched"):
        problems.append(
            f"{num(fields, 'mismatched'):.0f} profession(s) resolve to a "
            "different length list, so the cabin depends on the job chosen")

    # Ask again. Each call re-fires the event, and a handler that appends
    # blindly would grow the list every time the player opens the screen.
    repeat = parse(run_lua(cfg, REGIONS_LUA % REGION_NAME))
    if num(repeat, "copies") != 1:
        problems.append(
            f"asking twice produced {num(repeat, 'copies'):.0f} copies of the "
            "region; the handler is appending on every call")

    if problems:
        print("\nFAIL")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print(f"\nPASS - {EXPECTED_CABINS} cabins, every profession keyed to the "
          "same list, one copy per call")
    print("\nStill needs eyes: that the entry shows in Starting Location on the "
          "new-game\nscreen, and that picking it wakes you inside a cabin. The "
          "harness cannot reach\nthe main menu.")
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
